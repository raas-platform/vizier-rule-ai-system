"""검증 AI 설명: 기본 모델, 실패해도 검증 진행, ai_status / ai_error 테스트."""

import asyncio
import json

import pytest

from app.config import Settings
from app.models.rule import Rule
from app.services.llm_service import classify_llm_error
from app.services.rule_analyzer_v2 import RuleAnalyzerV2

SECRET = "sk-ant-SECRET-KEY-VALUE"

RULE = {
    "ruleUuid": "r1",
    "ruleName": "t",
    "ruleMsg": "t",
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


class FakeLLM:
    def __init__(self, reason=None, response=None, error=None):
        self._reason, self._response, self._error = reason, response, error

    def unavailable_reason(self, model_id):
        return self._reason

    def is_model_available(self, model_id):
        return self._reason is None

    async def generate_text(self, prompt, model_id, fast=False):
        if self._error:
            raise self._error
        return self._response


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"error with key {SECRET}")
        self.status_code = status_code


class RealisticLLM:
    """프롬프트 종류에 맞는 JSON을 돌려주는 가짜 LLM. fence=True면 ```json 코드 블록으로 감싼다."""

    def __init__(self, fence=False, delay=0.0, drop_items=0, garbage_for=None, no_purpose=False):
        self.no_purpose = no_purpose
        self.fence, self.delay, self.drop_items = fence, delay, drop_items
        self.garbage_for = garbage_for
        self.calls = []

    def unavailable_reason(self, model_id):
        return None

    async def generate_text(self, prompt, model_id, fast=False):
        self.calls.append(fast)
        await asyncio.sleep(self.delay)
        self.prompts = getattr(self, "prompts", []) + [prompt]
        if '"what"' in prompt:
            body, kind = {
                "what": "나이가 <b>30</b> 이상인 경우를 대상으로 합니다.",
                "purpose": "성인 고객 대상 혜택으로 보입니다." if not self.no_purpose else None,
            }, "desc"
        elif "enhanced_issues" in prompt:
            n = prompt.count("이슈 ") and len(
                [l for l in prompt.splitlines() if l.startswith("이슈 ") and l.endswith(":")]
            )
            n = max(n - self.drop_items, 0)
            body = {
                "enhanced_issues": [
                    {
                        "enhanced_explanation": f"설명 {i}",
                        "enhanced_suggestion": f"제안 {i}",
                        "impact_level": "high",
                        "affected_scenarios": ["a"],
                    }
                    for i in range(n)
                ]
            }
            kind = "batch"
        elif "complexity_analysis" in prompt:
            body, kind = {"complexity_analysis": "x", "design_patterns": []}, "insights"
        else:
            body, kind = [{"priority": "high", "title": "t", "description": "d"}], "recs"
        if self.garbage_for == kind:
            return "죄송합니다. 분석 결과를 정리하면 다음과 같습니다."
        text = json.dumps(body, ensure_ascii=False)
        return f"```json\n{text}\n```" if self.fence else text


def run(llm):
    analyzer = RuleAnalyzerV2()
    analyzer.ai_enhancer.llm_service = llm
    return asyncio.run(analyzer.analyze_rule(Rule(**RULE)))


def assert_rule_result_intact(result):
    assert result.is_valid is False
    assert any(i.issue_type == "type_mismatch" and i.condUuid == "c1" for i in result.issues)


def test_default_model_is_sonnet(monkeypatch):
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    assert Settings(_env_file=None).default_model == "claude-sonnet-5-5"


def test_no_key_is_skipped_with_reason():
    result = run(FakeLLM(reason="API 키 없음"))
    assert result.ai_status == "skipped"
    assert result.ai_error == "API 키 없음"
    assert_rule_result_intact(result)


@pytest.mark.parametrize(
    "error,expected",
    [
        (asyncio.TimeoutError(), "시간 초과"),
        (StatusError(429), "API 오류(요청 한도 초과, 코드 429)"),
        (StatusError(500), "API 오류(코드 500)"),
        (StatusError(404), "모델 사용 불가"),
        (StatusError(401), "API 키 오류"),
    ],
)
def test_failure_is_reported_but_validation_continues(error, expected):
    result = run(FakeLLM(error=error))
    assert result.ai_status == "failed"
    assert expected in result.ai_error
    assert SECRET not in result.ai_error
    assert_rule_result_intact(result)


def test_error_reason_never_contains_exception_message():
    assert SECRET not in classify_llm_error(StatusError(500))
    assert SECRET not in classify_llm_error(RuntimeError(SECRET))


def test_success_is_ok():
    result = run(RealisticLLM())
    assert result.ai_status == "ok"
    assert result.ai_error is None
    assert_rule_result_intact(result)


def test_real_service_without_default_model_key_is_skipped(monkeypatch):
    """기본 모델(Anthropic)의 키가 없으면 다른 모델로 폴백하지 않고 skipped + 사유를 남긴다."""
    from app.services import llm_service as llm_module

    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", None)
    monkeypatch.setattr(llm_module.settings, "openai_api_key", "placeholder")
    service = llm_module.LLMService()
    assert "anthropic" not in service.providers
    assert service.unavailable_reason("claude-sonnet-5-5") == "API 키 없음"

    result = run(service)
    assert result.ai_status == "skipped"
    assert result.ai_error == "API 키 없음"
    assert_rule_result_intact(result)


# ------------------------------------------------------------------
# 실제 Claude 응답 형태 (thinking 블록 + 코드 블록 JSON)
# ------------------------------------------------------------------
class _Block:
    def __init__(self, type_, text=None):
        self.type = type_
        if text is not None:
            self.text = text


class _Resp:
    def __init__(self, blocks):
        self.content = blocks


def test_extract_text_blocks_skips_thinking_blocks():
    from app.services.llm_service import extract_text_blocks

    resp = _Resp([_Block("thinking"), _Block("text", '{"a": 1}'), _Block("text", " ")])
    assert extract_text_blocks(resp) == '{"a": 1} '
    assert extract_text_blocks(_Resp([_Block("thinking")])) == ""


@pytest.mark.parametrize(
    "text",
    [
        '{"a": [1, 2]}',
        '```json\n{"a": [1, 2]}\n```',
        '```\n{"a": [1, 2]}\n```',
        '다음과 같습니다.\n```json\n{"a": [1, 2]}\n```\n끝',
        '결과: {"a": [1, 2]} 입니다',
    ],
)
def test_extract_json_handles_code_fences_and_prose(text):
    from app.services.analyzers.ai_enhancer import extract_json

    assert extract_json(text) == {"a": [1, 2]}


@pytest.mark.parametrize("text", ["", "   ", "JSON 없음", "{깨진"])
def test_extract_json_raises_on_garbage(text):
    from app.services.analyzers.ai_enhancer import extract_json

    with pytest.raises(ValueError):
        extract_json(text)


def test_anthropic_provider_reads_text_after_thinking_block(monkeypatch):
    from app.config import SUPPORTED_MODELS
    from app.services.llm_service import AnthropicProvider

    provider = AnthropicProvider("dummy-key")
    seen = {}

    async def fake_create(**kwargs):
        seen.update(kwargs)
        return _Resp([_Block("thinking"), _Block("text", "본문")])

    monkeypatch.setattr(provider.client.messages, "create", fake_create)
    config = SUPPORTED_MODELS["claude-sonnet-5-5"]
    assert asyncio.run(provider.generate_text("p", config, fast=True)) == "본문"
    assert seen["thinking"] == {"type": "disabled"}
    assert seen["output_config"] == {"effort": "low"}
    assert asyncio.run(provider.generate_text("p", config)) == "본문"


def test_anthropic_provider_retries_without_fast_options_on_400(monkeypatch):
    import anthropic
    import httpx

    from app.config import SUPPORTED_MODELS
    from app.services.llm_service import AnthropicProvider

    provider = AnthropicProvider("dummy-key")
    calls = []

    async def fake_create(**kwargs):
        calls.append(sorted(kwargs))
        if "thinking" in kwargs:
            req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            raise anthropic.BadRequestError(
                "bad", response=httpx.Response(400, request=req), body=None
            )
        return _Resp([_Block("text", "ok")])

    monkeypatch.setattr(provider.client.messages, "create", fake_create)
    config = SUPPORTED_MODELS["claude-sonnet-5-5"]
    assert asyncio.run(provider.generate_text("p", config, fast=True)) == "ok"
    assert len(calls) == 2 and "thinking" not in calls[1]


def test_fenced_json_responses_are_applied_to_all_issues():
    llm = RealisticLLM(fence=True)
    result = run(llm)
    assert result.ai_status == "ok", result.ai_error
    assert all(i.ai_explanation for i in result.issues)
    assert result.ai_insights and result.improvement_recommendations
    assert all(llm.calls)  # 모든 호출이 빠른 모드(fast=True)


def test_parse_failure_is_reported_and_raw_text_is_not_put_into_issues():
    result = run(RealisticLLM(garbage_for="batch"))
    assert result.ai_status == "failed"
    assert "JSON 파싱 실패" in result.ai_error
    assert all(i.ai_explanation is None for i in result.issues)  # 원문 200자 대입 제거
    assert_rule_result_intact(result)


def test_insights_and_recommendations_parse_failure_is_reported():
    result = run(RealisticLLM(garbage_for="insights"))
    assert result.ai_status == "failed" and "종합 통찰" in result.ai_error
    assert result.ai_insights is None
    result = run(RealisticLLM(garbage_for="recs"))
    assert result.ai_status == "failed" and "개선 제안" in result.ai_error
    assert result.improvement_recommendations is None


def test_partial_issue_explanations_are_reported():
    result = run(RealisticLLM(drop_items=1))
    assert result.ai_status == "failed"
    assert "일부 누락" in result.ai_error


def test_batch_insights_recommendations_run_concurrently():
    import time

    llm = RealisticLLM(delay=0.4)
    t0 = time.monotonic()
    result = run(llm)
    elapsed = time.monotonic() - t0
    assert len(llm.calls) >= 3
    # 순차 실행이면 호출 수 x 0.4초 이상 걸린다
    assert elapsed < 0.4 * 2, f"순차 실행으로 보임: {elapsed:.2f}s"
    assert result.ai_status == "ok"


# ------------------------------------------------------------------
# AI 룰 설명 (rule_description)
# ------------------------------------------------------------------
def test_rule_description_is_returned_and_html_escaped():
    llm = RealisticLLM(fence=True)
    result = run(llm)
    assert result.ai_status == "ok", result.ai_error
    assert result.rule_description is not None
    assert "<b>" not in result.rule_description.what  # raw HTML 이스케이프
    assert "&lt;b&gt;30&lt;/b&gt;" in result.rule_description.what
    assert result.rule_description.purpose.endswith("보입니다.")


def test_rule_description_prompt_has_only_rule_name_message_and_tree():
    llm = RealisticLLM()
    run(llm)
    prompt = next(p for p in llm.prompts if '"what"' in p)
    assert "룰 이름: t" in prompt and "AGE" in prompt and ">=" in prompt
    # 검증 이슈는 입력에 넣지 않는다
    assert "type_mismatch" not in prompt and "자기모순" not in prompt


def test_rule_description_purpose_null_when_weak():
    result = run(RealisticLLM(no_purpose=True))
    assert result.rule_description.purpose is None


def test_rule_description_failure_is_null_with_reason_and_validation_continues():
    result = run(RealisticLLM(garbage_for="desc"))
    assert result.rule_description is None
    assert result.ai_status == "failed" and "룰 설명" in result.ai_error
    assert_rule_result_intact(result)


def test_rule_description_is_skipped_without_key():
    result = run(FakeLLM(reason="API 키 없음"))
    assert result.rule_description is None
    assert result.ai_status == "skipped"
