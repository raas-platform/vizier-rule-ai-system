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

    async def generate_text(self, prompt, model_id):
        if self._error:
            raise self._error
        return self._response


class StatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"error with key {SECRET}")
        self.status_code = status_code


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
    payload = json.dumps({"enhanced_issues": [], "analysis": "ok"})
    result = run(FakeLLM(response=payload))
    assert result.ai_status == "ok"
    assert result.ai_error is None
    assert_rule_result_intact(result)
