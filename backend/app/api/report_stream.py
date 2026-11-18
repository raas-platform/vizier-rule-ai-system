"""
POST /rules/report/stream - 검증 리포트 스트리밍 생성

본문: {"format": "md" | "html", "rule": {...룰...}, "validation": {...검증 응답...}}
응답: text/event-stream. 각 이벤트는 `data: <JSON>` 한 줄이며 type 으로 구분한다.
  {"type": "start", "model": ..., "format": ...}
  {"type": "delta", "text": ...}          ← 문서 조각 (순서대로 이어 붙이면 완성 문서)
  {"type": "done", "stop_reason": ..., "usage": {...}, "cost_usd": ..., "ttft_ms": ..., "total_ms": ...}
  {"type": "error", "message": ..., "partial": true}

서버는 상태를 저장하지 않는다. 클라이언트가 연결을 끊으면(중지) Claude 스트림도 닫는다.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, AsyncIterator, Deque, Dict, Literal, Optional

import anthropic
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import settings
from ..services import report_writer as rw
from ..utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ReportStreamRequest(BaseModel):
    format: Literal["md", "html"] = Field(..., description="md 또는 html")
    rule: Any = Field(..., description="검증에 보낸 룰 (객체 또는 검증 요청과 같은 배열)")
    validation: Dict[str, Any] = Field(..., description="/rules/validate-json 응답 그대로")


def _sse(payload: Dict[str, Any]) -> bytes:
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


def _get_client() -> anthropic.AsyncAnthropic:
    # 테스트에서 이 함수를 바꿔 끼워 실제 API 호출 없이 검증한다.
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _usage_dict(usage: Any) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        v = getattr(usage, k, None) if usage is not None else None
        if isinstance(v, int):
            out[k] = v
    return out


def _total_cost(final: Any, default_model: str) -> Optional[float]:
    """usage.iterations(폴백 시도별 사용량)가 있으면 시도별 모델 단가로 합산."""
    usage = getattr(final, "usage", None)
    iterations = getattr(usage, "iterations", None) if usage is not None else None
    if iterations:
        total = 0.0
        for it in iterations:
            model = getattr(it, "model", None) or getattr(final, "model", None) or default_model
            c = rw.estimate_cost(model, _usage_dict(it))
            if c is None:
                return None
            total += c
        return round(total, 5)
    return rw.estimate_cost(getattr(final, "model", None) or default_model, _usage_dict(usage))


def _error_message(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "Anthropic API 키가 올바르지 않습니다. 서버의 ANTHROPIC_API_KEY를 확인하세요."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "이 API 키로는 리포트 모델을 쓸 권한이 없습니다."
    if isinstance(e, anthropic.NotFoundError):
        return f"리포트 모델({settings.report_model})을 찾을 수 없습니다."
    if isinstance(e, anthropic.RateLimitError):
        return "Anthropic 사용량 한도에 걸렸습니다. 잠시 후 다시 시도하세요."
    if isinstance(e, anthropic.BadRequestError):
        return f"리포트 요청이 거절되었습니다: {getattr(e, 'message', e)}"
    if isinstance(e, anthropic.APIStatusError):
        return f"Anthropic 서버 오류({e.status_code})입니다. 잠시 후 다시 시도하세요."
    if isinstance(e, anthropic.APIConnectionError):
        return "Anthropic 서버에 연결하지 못했습니다. 서버의 네트워크를 확인하세요."
    return f"리포트 생성 중 오류가 발생했습니다: {e}"


class _ReportLimiter:
    """브라우저 호출용 한도: IP당 분당 호출 수 + 하루(KST) 전체 생성 건수. 메모리 기반(서버 1대 기준)."""

    def __init__(self) -> None:
        self._per_ip: Dict[str, Deque[float]] = defaultdict(deque)
        self._day = ""
        self._day_count = 0

    def reset(self) -> None:
        self._per_ip.clear()
        self._day, self._day_count = "", 0

    def check(self, ip: str, per_minute: int, daily: int) -> Optional[str]:
        now = time.time()
        q = self._per_ip[ip]
        while q and now - q[0] > 60:
            q.popleft()
        today = datetime.now(rw.KST).strftime("%Y-%m-%d")
        if today != self._day:
            self._day, self._day_count = today, 0
        if per_minute > 0 and len(q) >= per_minute:
            return f"리포트 요청이 너무 잦습니다. 1분에 {per_minute}번까지 만들 수 있으니 잠시 후 다시 시도하세요."
        if daily > 0 and self._day_count >= daily:
            return f"오늘 리포트 생성 한도({daily}건)를 모두 사용했습니다. 내일 다시 시도해 주세요."
        q.append(now)
        self._day_count += 1
        return None


limiter = _ReportLimiter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def authorize(request: Request, api_key: Optional[str]) -> str:
    """리포트 호출 허용 여부(요구사항 G). 허용 방식("server" | "browser")을 돌려주고, 아니면 HTTPException.

    1) 서버 간 호출: X-API-Key == REPORT_API_KEY 이면 허용(한도 없음).
    2) 브라우저 호출(키 없음): REPORT_ALLOWED_ORIGINS에 있는 Origin이면 허용 + IP당 분당/하루 한도.
       REPORT_ALLOWED_ORIGINS와 REPORT_API_KEY가 둘 다 없으면 로컬 개발용으로 전부 허용(한도는 적용).
       REPORT_API_KEY만 있고 허용 Origin 목록이 없으면 키 없는 호출은 받지 않는다.
    """
    server_key = settings.report_api_key
    if api_key:
        if server_key and api_key == server_key:
            return "server"
        raise HTTPException(status_code=401, detail="API 키(X-API-Key)가 맞지 않습니다.")

    origins = settings.get_report_allowed_origins()
    origin = request.headers.get("origin")
    if origins:
        if origin not in origins:
            raise HTTPException(status_code=403, detail="이 화면(Origin)에서는 리포트를 만들 수 없습니다. 관리자에게 허용 주소 등록을 요청하세요.")
    elif server_key:
        raise HTTPException(status_code=401, detail="리포트를 만들려면 API 키(X-API-Key)가 필요합니다.")

    msg = limiter.check(_client_ip(request), settings.report_rate_per_minute, settings.report_daily_limit)
    if msg:
        raise HTTPException(status_code=429, detail=msg)
    return "browser"


@router.post("/report/stream")
async def stream_report(
    body: ReportStreamRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="서버에 ANTHROPIC_API_KEY가 설정되지 않아 리포트를 만들 수 없습니다.")
    authorize(request, x_api_key)

    facts = rw.build_facts(body.rule, body.validation)
    fmt = body.format
    model = settings.report_model

    async def gen() -> AsyncIterator[bytes]:
        t0 = time.monotonic()
        ttft_ms: Optional[int] = None
        sent_any = False
        yield _sse({"type": "start", "model": model, "format": fmt})
        if fmt == "html":
            yield _sse({"type": "delta", "text": rw.html_head(facts)})
        client = _get_client()
        fence = rw.FenceStripper()
        try:
            async with client.beta.messages.stream(
                model=model,
                max_tokens=settings.report_max_tokens,
                system=rw.build_system_prompt(fmt),
                messages=[{"role": "user", "content": rw.build_user_message(facts)}],
                output_config={"effort": settings.report_effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                async for raw in stream.text_stream:
                    text = fence.feed(raw)
                    if not text:
                        continue
                    if ttft_ms is None:
                        ttft_ms = int((time.monotonic() - t0) * 1000)
                    sent_any = True
                    yield _sse({"type": "delta", "text": text})
                    if await request.is_disconnected():
                        logger.info("리포트 생성 중지: 클라이언트 연결 끊김")
                        return
                final = await stream.get_final_message()
            rest = fence.flush()
            if rest:
                sent_any = True
                yield _sse({"type": "delta", "text": rest})
        except (asyncio.CancelledError, GeneratorExit):
            logger.info(f"리포트 생성 중지: 클라이언트 연결 끊김 ({int((time.monotonic() - t0) * 1000)}ms)")
            raise
        except Exception as e:  # noqa: BLE001 - 원인 문구를 화면에 보여주고 받은 부분은 유지
            logger.error(f"리포트 생성 실패: {e}", exc_info=True)
            yield _sse({"type": "error", "message": _error_message(e), "partial": sent_any})
            return

        if fmt == "html":
            yield _sse({"type": "delta", "text": rw.HTML_TAIL})

        stop_reason = getattr(final, "stop_reason", None)
        served_model = getattr(final, "model", None) or model
        payload: Dict[str, Any] = {
            "type": "done",
            "model": served_model,
            "stop_reason": stop_reason,
            "usage": _usage_dict(getattr(final, "usage", None)),
            "cost_usd": _total_cost(final, model),
            "effort": settings.report_effort,
            "ttft_ms": ttft_ms,
            "total_ms": int((time.monotonic() - t0) * 1000),
            "issue_count": facts["건수"]["전체"],
        }
        if stop_reason == "refusal":
            payload["warning"] = "모델이 리포트 작성을 거절했습니다. 받은 부분은 완전하지 않을 수 있습니다."
        elif stop_reason == "max_tokens":
            payload["warning"] = "출력 길이 한도에 걸려 리포트가 중간에 끊겼습니다."
        logger.info(
            f"리포트 생성 완료 format={fmt} model={served_model} ttft={ttft_ms}ms "
            f"total={payload['total_ms']}ms usage={payload['usage']} cost=${payload['cost_usd']}"
        )
        yield _sse(payload)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
