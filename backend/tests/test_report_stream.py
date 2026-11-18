"""POST /rules/report/stream 테스트 (Anthropic 호출은 가짜 스트림으로 대체)"""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.api import report_stream
from backend.app.config import settings
from backend.app.main import app
from backend.app.services import report_writer as rw

RULE = {
    "ruleUuid": "r-1",
    "ruleName": "나이 룰",
    "ruleMsg": "테스트",
    "conditionTree": {
        "logicType": "AND",
        "condition": [
            {"condUuid": "cond-001", "keyName": "USER_AGE", "dispName": "사용자 나이",
             "operator": ">=", "value": "30", "fieldDataType": "Number"},
            {"condUuid": "cond-002", "keyName": "USER_AGE", "dispName": "사용자 나이",
             "operator": "<", "value": "25", "fieldDataType": "Number"},
        ],
    },
}
VALIDATION = {
    "is_valid": False,
    "summary": "2건",
    "issue_counts": {"self_contradiction": 1, "missing_condition": 1},
    "issues": [
        {"condUuid": "cond-001", "keyName": "USER_AGE", "issue_type": "missing_condition",
         "severity": "warning", "explanation": "0이면 빠짐"},
        {"condUuid": "cond-001", "keyName": "USER_AGE", "issue_type": "self_contradiction",
         "severity": "error", "explanation": "모순"},
    ],
    "quality_metrics": {"maintainability_score": 50, "readability_score": 50, "completeness_score": 50,
                        "consistency_score": 50, "overall_score": 50},
    "ai_comment": "단순화하세요",
    "report_metadata": {"analysis_timestamp": "2026-11-17T22:56:00", "ruleName": "나이 룰"},
    "risk_assessment": {"risk_level": "high", "risk_message": "즉시 수정이 필요합니다"},
}


class FakeStream:
    def __init__(self, chunks, final=None, fail_after=None):
        self.chunks, self.fail_after = chunks, fail_after
        self.final = final or SimpleNamespace(
            model="claude-opus-5-5", stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500, iterations=None))
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        self.closed = True

    @property
    def text_stream(self):
        async def gen():
            for n, c in enumerate(self.chunks):
                if self.fail_after is not None and n == self.fail_after:
                    raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))
                yield c
        return gen()

    async def get_final_message(self):
        return self.final


class FakeClient:
    def __init__(self, stream):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self._s = stream

    def _stream(self, **kw):
        self.calls.append(kw)
        return self._s


def events(resp):
    out = []
    for block in resp.text.split("\n\n"):
        if block.startswith("data: "):
            out.append(json.loads(block[6:]))
    return out


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "report_api_key", None)
    monkeypatch.setattr(settings, "report_allowed_origins", None)
    monkeypatch.setattr(settings, "report_rate_per_minute", 100)
    monkeypatch.setattr(settings, "report_daily_limit", 100)
    report_stream.limiter.reset()
    with TestClient(app) as c:
        yield c


def use_fake(monkeypatch, stream):
    fake = FakeClient(stream)
    monkeypatch.setattr(report_stream, "_get_client", lambda: fake)
    return fake


def post(c, fmt="md", headers=None):
    return c.post("/rules/report/stream", json={"format": fmt, "rule": [RULE], "validation": VALIDATION},
                  headers=headers or {})


def test_md_stream_and_request_shape(client, monkeypatch):
    fake = use_fake(monkeypatch, FakeStream(["```markdown\n", "# 룰 검증 리포트: 나이 룰\n", "본문 `E1`\n", "```"]))
    r = post(client)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    assert ev[0]["type"] == "start" and ev[-1]["type"] == "done"
    text = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert text.startswith("# 룰 검증 리포트") and "```" not in text and "`E1`" in text
    done = ev[-1]
    assert done["usage"] == {"input_tokens": 1000, "output_tokens": 500}
    assert done["cost_usd"] == pytest.approx((1000 * 4 + 500 * 20) / 1e6)
    assert done["issue_count"] == 2 and done["ttft_ms"] is not None
    kw = fake.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default" and report_stream.FALLBACK_BETA in kw["betas"]
    assert "temperature" not in kw and "thinking" not in kw
    msg = kw["messages"][0]["content"]
    # 서버가 번호·건수를 정해서 넘긴다: 오류가 먼저 E1, 경고는 W1
    facts = json.loads(msg[msg.index("<facts>") + 7:msg.index("</facts>")])
    assert [i["번호"] for i in facts["이슈"]] == ["E1", "W1"]
    assert facts["건수"] == {"전체": 2, "오류": 1, "경고": 1}
    assert facts["판정"] == "수정 필요" and facts["위험도"].startswith("높음")
    # location 번호는 넘기지 않고, 같은 항목의 조건을 표시명으로 풀어서 넘긴다
    assert "location" not in facts["이슈"][0]
    assert facts["이슈"][0]["관련 조건"] == ["사용자 나이 (USER_AGE) >= 30", "사용자 나이 (USER_AGE) < 25"]
    system = kw["system"]
    assert "타당성을 판단하거나 반박하거나" in system and "번호로 가리키지 마세요" in system
    # 7차 검수 반영: 따옴표 조언 금지, 추측·새 필드 금지, 조건부 조언은 대안에만, AI 의견 없으면 절 생략
    assert "따옴표 유무를 말하지 마세요" in system and "추측해 쓰지 마세요" in system
    assert "새 필드" in system and "고치는 방법의 대안" in system and "통째로 빼세요" in system
    assert "관련 조건 | 내용" in system
    assert "모르겠다면 확인하세요" in system and "선택지를 나열하는" in system


def test_html_wraps_fixed_head_and_tail(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["<header><h1>나이 룰</h1></header>"]))
    ev = events(post(client, "html"))
    deltas = [e["text"] for e in ev if e["type"] == "delta"]
    assert deltas[0].startswith("<!DOCTYPE html>") and "<title>룰 검증 리포트 - 나이 룰</title>" in deltas[0]
    assert deltas[-1].strip().endswith("</html>")
    assert "<h1>나이 룰</h1>" in "".join(deltas)


def test_error_mid_stream_keeps_partial(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 제목입니다 충분히 긴 첫 줄\n", "둘째"], fail_after=1))
    ev = events(post(client))
    assert ev[-1]["type"] == "error" and ev[-1]["partial"] is True
    assert "연결하지 못했습니다" in ev[-1]["message"]
    assert any(e["type"] == "delta" for e in ev)


def test_no_anthropic_key(client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    r = post(client)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_bad_format_rejected(client):
    r = client.post("/rules/report/stream", json={"format": "pdf", "rule": RULE, "validation": VALIDATION})
    assert r.status_code == 422


def test_auth_server_key(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "report_api_key", "secret")
    assert post(client).status_code == 403                                   # 키 없음 + 허용 Origin 목록 없음
    assert post(client, headers={"X-API-Key": "wrong"}).status_code == 403
    assert post(client, headers={"X-API-Key": "secret"}).status_code == 200


def test_auth_browser_origin_and_limits(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "report_api_key", "secret")
    monkeypatch.setattr(settings, "report_allowed_origins", "https://vizier.example.com, null")
    assert post(client, headers={"Origin": "https://evil.example.com"}).status_code == 403
    assert post(client, headers={"Origin": "https://vizier.example.com"}).status_code == 200
    assert post(client, headers={"Origin": "null"}).status_code == 200      # file:// 로 연 테스트 화면
    monkeypatch.setattr(settings, "report_rate_per_minute", 2)
    r = post(client, headers={"Origin": "https://vizier.example.com"})
    assert r.status_code == 429 and "1분에 2번" in r.json()["detail"]
    # 서버 키 호출은 한도와 무관
    assert post(client, headers={"X-API-Key": "secret"}).status_code == 200


def test_daily_limit_message(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "report_daily_limit", 1)
    assert post(client).status_code == 200
    r = post(client)
    assert r.status_code == 429
    assert r.json()["detail"] == "오늘 리포트 생성 한도(1건)를 모두 사용했습니다. 내일 다시 시도해 주세요."


def test_related_conditions_whole_rule():
    v = {"is_valid": False, "issues": [{"issue_type": "complexity_warning", "severity": "warning",
                                         "location": "3"}]}
    f = rw.build_facts(RULE, v)
    assert f["이슈"][0]["관련 조건"] == ["룰 전체"] and "location" not in f["이슈"][0]


def test_facts_no_issues():
    f = rw.build_facts(RULE, {"is_valid": True, "issues": []})
    assert f["판정"] == "문제 없음" and f["건수"]["전체"] == 0 and f["이슈"] == []


def test_fence_stripper_keeps_inline_code():
    s = rw.FenceStripper()
    out = "".join(s.feed(c) for c in ["# T\n", "a `b` c ", "`d`"]) + s.flush()
    assert out == "# T\na `b` c `d`"


def test_ai_state_passed_only_without_comment():
    v = {"is_valid": True, "issues": [], "ai_status": "failed", "ai_error": "timeout"}
    assert rw.build_facts(RULE, v)["AI 분석 상태"] == {"ai_status": "failed", "ai_error": "timeout"}
    assert "AI 분석 상태" not in rw.build_facts(RULE, {**v, "ai_comment": "의견"})


def test_origin_falls_back_to_cors_list(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "cors_allowed_origins", "https://vizier.example.com")
    assert settings.get_report_allowed_origins() == ["https://vizier.example.com"]
    assert post(client, headers={"Origin": "https://vizier.example.com"}).status_code == 200
    assert post(client, headers={"Origin": "https://evil.example.com"}).status_code == 403
    assert post(client, headers={"Origin": "http://localhost:3000"}).status_code == 403   # 운영에선 localhost 불가
    assert post(client).status_code == 403                                                # 운영: Origin 없고 키도 없음


def test_localhost_origin_allowed_outside_production(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "environment", "development")
    assert post(client, headers={"Origin": "http://localhost:8080"}).status_code == 200


def test_rate_limit_uses_cloudfront_client_ip(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "trust_cloudfront", True)
    monkeypatch.setattr(settings, "cloudfront_origin_secret", "s3cret")
    monkeypatch.setattr(settings, "report_rate_per_minute", 1)
    h = lambda ip: {"X-Origin-Verify": "s3cret", "X-Forwarded-For": f"9.9.9.9,{ip}"}
    assert post(client, headers=h("1.1.1.1")).status_code == 200
    assert post(client, headers=h("1.1.1.1")).status_code == 429
    assert post(client, headers=h("2.2.2.2")).status_code == 200      # 엣지가 달라도 접속자가 다르면 별도 집계


def test_errors_carry_errormsg_and_never_401(client, monkeypatch):
    monkeypatch.setattr(settings, "report_api_key", "secret")
    r = post(client, headers={"X-API-Key": "wrong"})
    assert r.status_code == 403 and r.json()["errorMsg"] == r.json()["detail"]
    monkeypatch.setattr(settings, "report_api_key", None)
    monkeypatch.setattr(settings, "report_allowed_origins", "https://vizier.example.com")
    r = post(client, headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403 and r.json()["errorMsg"]
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    r = post(client)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["errorMsg"]


def test_rate_limit_has_errormsg(client, monkeypatch):
    use_fake(monkeypatch, FakeStream(["# 리포트 첫 줄이 충분히 깁니다\n"]))
    monkeypatch.setattr(settings, "report_daily_limit", 1)
    post(client)
    r = post(client)
    assert r.status_code == 429 and r.json()["errorMsg"] == r.json()["detail"]


def test_sse_error_has_errormsg_without_internal_text(client, monkeypatch):
    class Boom(FakeStream):
        @property
        def text_stream(self):
            async def gen():
                yield "# 제목입니다 충분히 긴 첫 줄\n"
                raise RuntimeError("secret-internal-detail sk-123")
            return gen()
    use_fake(monkeypatch, Boom([]))
    err = events(post(client))[-1]
    assert err["type"] == "error" and err["errorMsg"] == err["message"]
    assert "sk-123" not in err["errorMsg"] and "secret-internal" not in err["errorMsg"]


def test_total_timeout_ends_with_error_event(client, monkeypatch):
    import asyncio

    class Slow(FakeStream):
        @property
        def text_stream(self):
            async def gen():
                yield "# 제목입니다 충분히 긴 첫 줄\n"
                await asyncio.sleep(5)
                yield "늦은 조각"
            return gen()
    use_fake(monkeypatch, Slow([]))
    monkeypatch.setattr(settings, "report_total_timeout_seconds", 1)
    ev = events(post(client))
    assert ev[0]["type"] == "start"                      # 첫 이벤트는 바로 나간다
    assert ev[-1]["type"] == "error" and ev[-1]["partial"] is True and "1초" in ev[-1]["errorMsg"]
    assert "늦은 조각" not in "".join(e.get("text", "") for e in ev)


def test_rule_description_in_facts_and_prompt():
    f = rw.build_facts(RULE, {"is_valid": True, "issues": [],
                              "rule_description": {"what": " 30세 이상 대상입니다. ", "purpose": None}})
    assert f["룰 설명"] == {"what": "30세 이상 대상입니다."}          # purpose 없으면 생략
    f2 = rw.build_facts(RULE, {"is_valid": True, "issues": [],
                               "rule_description": {"what": "A", "purpose": "B으로 보입니다."}})
    assert f2["룰 설명"] == {"what": "A", "purpose": "B으로 보입니다."}
    assert rw.build_facts(RULE, {"is_valid": True, "issues": []})["룰 설명"] is None
    assert rw.build_facts(RULE, {"is_valid": True, "issues": [], "rule_description": {"what": ""}})["룰 설명"] is None
    system = rw.build_system_prompt("md")
    assert "목적(추정)" in system and "새로 추정하거나" in system and "종합 의견" in system
    assert "AI 종합 의견" not in system
