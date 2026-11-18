"""Vizier 오류 표시 호환 + 검증 시간 상한 테스트.

스펙: 프로젝트 파일 judge/vizier-error-compat-requirements.md 1~3번 (2026-11-18)
- 401 금지(403으로), 모든 오류 JSON에 errorMsg, 검증 API 시간 상한
"""

import asyncio
import re
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings
from app.middleware.rate_limiter import rate_limiter
from app.models.rule import Rule
from app.services.analyzers.ai_enhancer import AIEnhancer
from app.services.rule_analyzer_v2 import RuleAnalyzerV2

APP_DIR = Path(__file__).resolve().parent.parent / "app"

RULE = [
    {
        "ruleUuid": "e1",
        "ruleName": "e1",
        "ruleMsg": "e1",
        "conditionTree": {
            "logicType": "AND",
            "condition": [
                {
                    "condUuid": "c1",
                    "keyName": "AGE",
                    "dispName": "AGE",
                    "operator": ">=",
                    "value": "abc",
                    "fieldDataType": "Number",
                }
            ],
        },
    }
]


def _is_korean_sentence(text):
    return isinstance(text, str) and text.strip() and re.search(r"[가-힣]", text)


@pytest.fixture
def app():
    app = main_module.create_app()

    async def raise_401():
        raise HTTPException(
            status_code=401, detail="Invalid API key", headers={"WWW-Authenticate": "Bearer"}
        )

    async def raise_403():
        raise HTTPException(status_code=403, detail="API key mismatch")

    async def boom():
        raise RuntimeError("internal secret detail sk-SECRET-123")

    app.add_api_route("/_t/401", raise_401)
    app.add_api_route("/_t/403", raise_403)
    app.add_api_route("/_t/boom", boom)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. 401 금지
# ---------------------------------------------------------------------------
def test_no_code_path_returns_401():
    """앱 코드 어디에도 401 응답을 만드는 곳이 없다 (외부 API 응답 코드를 읽는 곳은 제외)."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"status_code\s*=\s*401|HTTP_401|status\.HTTP_401", line):
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    assert not offenders, offenders


def test_http_401_is_converted_to_403(client):
    res = client.get("/_t/401")
    assert res.status_code == 403
    body = res.json()
    assert body["detail"] == "Invalid API key"
    assert _is_korean_sentence(body["errorMsg"])
    assert "www-authenticate" not in {k.lower() for k in res.headers}


# ---------------------------------------------------------------------------
# 2. 모든 오류 응답에 errorMsg
# ---------------------------------------------------------------------------
def test_403_has_error_msg(client):
    res = client.get("/_t/403")
    assert res.status_code == 403
    assert res.json()["detail"] == "API key mismatch"
    assert _is_korean_sentence(res.json()["errorMsg"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"bad": 1}},  # 배열이 아님 (FastAPI 본문 검증)
        {"content": b"{not json", "headers": {"Content-Type": "application/json"}},
        {"json": []},  # 빈 배열 (엔드포인트 검사)
        {"json": [{"ruleName": "x"}]},  # 필수 필드 누락
    ],
)
def test_422_has_error_msg_and_keeps_detail(client, kwargs):
    res = client.post("/rules/validate-json", **kwargs)
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body
    assert body["errorMsg"] == "룰 데이터 형식이 올바르지 않습니다. 입력값을 확인해 주세요."


def test_404_and_405_have_error_msg(client):
    res = client.get("/no-such-path")
    assert res.status_code == 404 and _is_korean_sentence(res.json()["errorMsg"])
    res = client.get("/rules/validate-json")
    assert res.status_code == 405 and _is_korean_sentence(res.json()["errorMsg"])


def test_429_has_error_msg(client, monkeypatch):
    monkeypatch.setattr(rate_limiter, "rate_limit_per_minute", 1)
    monkeypatch.setattr(rate_limiter, "requests", {})
    client.post("/rules/validate-json", json=RULE)
    res = client.post("/rules/validate-json", json=RULE)
    assert res.status_code == 429
    assert res.json()["errorMsg"] == "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."
    assert "message" in res.json()  # 기존 필드 유지


def test_500_in_validation_has_error_msg_without_internal_detail(client, monkeypatch):
    async def fail(self, rule):
        raise RuntimeError("internal secret detail sk-SECRET-123")

    monkeypatch.setattr(RuleAnalyzerV2, "analyze_rule", fail)
    res = client.post("/rules/validate-json", json=RULE)
    assert res.status_code == 500
    body = res.json()
    assert body["errorMsg"] == "검증 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    assert "sk-SECRET-123" not in res.text


def test_unhandled_exception_has_error_msg(client):
    res = client.get("/_t/boom")
    assert res.status_code == 500
    assert _is_korean_sentence(res.json()["errorMsg"])
    assert "sk-SECRET-123" not in res.text


# ---------------------------------------------------------------------------
# 3. 검증 시간 상한
# ---------------------------------------------------------------------------
def test_default_time_limit_is_50_seconds():
    assert settings.validation_timeout_seconds == 50
    assert RuleAnalyzerV2().time_limit_seconds == 50


def test_rule_phase_over_limit_returns_504(client, monkeypatch):
    monkeypatch.setattr(settings, "validation_timeout_seconds", 0)
    res = client.post("/rules/validate-json", json=RULE)
    assert res.status_code == 504
    body = res.json()
    assert body["errorMsg"] == "검증 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    assert body["detail"]["type"] == "validation_timeout"


def _slow_ai(monkeypatch, seconds=5):
    async def slow(self, *args, **kwargs):
        await asyncio.sleep(seconds)
        for issue in args[0] if args and isinstance(args[0], list) else []:
            issue.ai_explanation = "늦은 AI 설명"

    monkeypatch.setattr(AIEnhancer, "enhance_issues_batch", slow)
    monkeypatch.setattr(AIEnhancer, "generate_ai_insights", slow)
    monkeypatch.setattr(AIEnhancer, "generate_improvement_recommendations", slow)


def test_ai_over_limit_gives_up_ai_only(monkeypatch):
    monkeypatch.setattr(settings, "validation_timeout_seconds", 0.5)
    _slow_ai(monkeypatch)
    analyzer = RuleAnalyzerV2()
    started = time.time()
    result = asyncio.run(analyzer.analyze_rule(Rule(**RULE[0])))
    elapsed = time.time() - started
    assert elapsed < 2, elapsed
    assert analyzer.ai_timed_out is True
    # 규칙 판정 결과는 그대로
    assert result.is_valid is False
    assert any(i.issue_type == "type_mismatch" and i.condUuid == "c1" for i in result.issues)
    assert all(getattr(i, "ai_explanation", None) != "늦은 AI 설명" for i in result.issues)
    assert result.ai_insights is None and result.improvement_recommendations is None


def test_ai_over_limit_api_returns_200(client, monkeypatch):
    monkeypatch.setattr(settings, "validation_timeout_seconds", 0.5)
    _slow_ai(monkeypatch)
    started = time.time()
    res = client.post("/rules/validate-json", json=RULE)
    assert res.status_code == 200
    assert time.time() - started < 2
    assert res.json()["is_valid"] is False


def test_fast_ai_not_marked_timed_out():
    analyzer = RuleAnalyzerV2()
    asyncio.run(analyzer.analyze_rule(Rule(**RULE[0])))
    assert analyzer.ai_timed_out is False
