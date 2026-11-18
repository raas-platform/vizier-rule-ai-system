"""validate-json 응답의 AI 패널용 필드 (ai_summary_md, condition_details_md) 테스트

스펙: judge/ai-panel-requirements.md 7~10
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.panel_markdown import (
    NO_ISSUE_MD,
    build_panel_markdown,
    md_text,
    tree_conditions,
)

ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)

RULE = {
    "ruleUuid": "r-1",
    "ruleName": "나이 룰",
    "ruleMsg": "테스트",
    "conditionTree": {
        "logicType": "AND",
        "condition": [
            {"condUuid": "cond-001", "keyName": "USER_AGE", "dispName": "사용자 나이",
             "operator": ">=", "value": "30", "fieldDataType": "Number"},
            {"logicType": "OR", "condition": [
                {"condUuid": "cond-002", "keyName": "USER_AGE", "dispName": "사용자 나이",
                 "operator": "<", "value": "25", "fieldDataType": "Number"},
                {"condUuid": "cond-003", "keyName": "REGION", "dispName": "지역",
                 "operator": "==", "value": "SEOUL", "fieldDataType": "String"},
            ]},
        ],
    },
}
VALIDATION = {
    "is_valid": False,
    "summary": "룰 '나이 룰'에 2건",
    "issues": [
        {"condUuid": "cond-001", "issue_type": "missing_condition", "severity": "warning",
         "explanation": "0이면 빠짐", "suggestion": "0도 넣으세요"},
        {"condUuid": "cond-001", "issue_type": "self_contradiction", "severity": "error",
         "explanation": "모순", "ai_explanation": "30 이상이면서 25 미만은 없습니다",
         "ai_suggestion": "둘 중 하나를 지우세요", "suggestion": "규칙 기본 제안"},
        {"condUuid": None, "issue_type": "complexity_warning", "severity": "warning",
         "explanation": "조건이 많습니다"},
        {"condUuid": "cond-999", "issue_type": "missing_name", "severity": "error",
         "explanation": "트리에 없는 조건"},
    ],
    "ai_comment": "전체적으로 나이 조건을 정리하세요.",
}


def test_tree_conditions_in_order_and_nested():
    assert [c["condUuid"] for c in tree_conditions(RULE)] == ["cond-001", "cond-002", "cond-003"]


def test_condition_details_cover_every_condition():
    md = build_panel_markdown(RULE, VALIDATION)["condition_details_md"]
    assert set(md) == {"cond-001", "cond-002", "cond-003"}
    # 이슈 없는 조건은 "이상 없음" 한 줄
    assert NO_ISSUE_MD in md["cond-002"] and NO_ISSUE_MD in md["cond-003"]
    assert NO_ISSUE_MD not in md["cond-001"]


def test_condition_detail_has_severity_title_explanation_fix():
    d = build_panel_markdown(RULE, VALIDATION)["condition_details_md"]["cond-001"]
    assert "오류 1건 · 경고 1건" in d
    assert "오류 · 자기 모순" in d and "경고 · 누락 조건" in d
    # 오류가 경고보다 먼저
    assert d.index("자기 모순") < d.index("누락 조건")
    assert "모순" in d and "30 이상이면서 25 미만은 없습니다" in d
    # 고치는 방법: AI 제안이 있으면 그것, 없으면 규칙 제안
    assert "둘 중 하나를 지우세요" in d and "규칙 기본 제안" not in d
    assert "0도 넣으세요" in d


def test_summary_verdict_counts_comment_and_rule_wide_issues():
    s = build_panel_markdown(RULE, VALIDATION)["ai_summary_md"]
    assert "수정 필요" in s
    assert "오류 2건 · 경고 2건" in s
    assert "룰 '나이 룰'에 2건" in s
    assert "### 종합 의견" in s and "AI 종합 의견" not in s and "나이 조건을 정리하세요" in s
    # condUuid 없음 + 트리에 없는 condUuid → 룰 전체 이슈 목록
    assert "룰 전체에 대한 이슈" in s
    assert "조건이 많습니다" in s and "트리에 없는 조건" in s
    # 조건에 붙은 이슈는 요약 목록에 넣지 않음
    assert "0이면 빠짐" not in s


def test_summary_valid_rule_without_ai():
    s = build_panel_markdown(RULE, {"is_valid": True, "summary": "유효합니다", "issues": []})["ai_summary_md"]
    assert "유효" in s and "오류 0건 · 경고 0건" in s
    assert "종합 의견" not in s and "룰 전체에 대한 이슈" not in s


def test_summary_ai_status_reason_only_when_not_ok():
    v = dict(VALIDATION, ai_status="failed", ai_error="AI 호출 시간이 초과되었습니다")
    assert "AI 호출 시간이 초과되었습니다" in build_panel_markdown(RULE, v)["ai_summary_md"]
    v = dict(VALIDATION, ai_status="ok", ai_error="무시돼야 함")
    assert "무시돼야 함" not in build_panel_markdown(RULE, v)["ai_summary_md"]


XSS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "[클릭](javascript:alert(1))",
    "![x](https://evil.example/t.png)",
    "<a href='javascript:alert(1)'>a</a>",
]


@pytest.mark.parametrize("payload", XSS)
def test_no_raw_html_or_links_anywhere(payload):
    rule = json.loads(json.dumps(RULE))
    rule["conditionTree"]["condition"][0]["dispName"] = payload
    rule["conditionTree"]["condition"][0]["value"] = payload
    v = dict(VALIDATION, summary=payload, ai_comment=payload, ai_status="failed", ai_error=payload)
    v["issues"] = [dict(i, explanation=payload, ai_explanation=payload + "!", ai_suggestion=payload)
                   for i in VALIDATION["issues"]]
    out = build_panel_markdown(rule, v)
    texts = [out["ai_summary_md"], *out["condition_details_md"].values()]
    for t in texts:
        assert "<" not in t and ">" not in t.replace("&gt;", "")
        assert "](" not in t.replace("\\](", "")  # 대괄호가 모두 무력화됨


def test_md_text_escapes_block_syntax():
    assert md_text("# 제목") == "\\# 제목"
    assert md_text("- 목록") == "\\- 목록"
    assert md_text("1. 하나") == "1\\. 하나"
    assert md_text("    코드") == "코드"
    assert md_text("a > b & c") == "a &gt; b &amp; c"
    assert md_text("`x`") == "\\`x\\`"


def test_validate_json_response_has_panel_fields():
    sample = json.loads((ROOT / "test_self_contradiction.json").read_text(encoding="utf-8"))
    r = client.post("/rules/validate-json", json=sample)
    assert r.status_code == 200, r.text
    body = r.json()
    # 기존 필드 유지 (호환)
    for k in ("is_valid", "summary", "issues", "structure", "issue_counts"):
        assert k in body
    assert isinstance(body["ai_summary_md"], str) and body["ai_summary_md"]
    uuids = [c["condUuid"] for c in tree_conditions(sample[0])]
    assert sorted(body["condition_details_md"]) == sorted(set(uuids))
    assert "<" not in body["ai_summary_md"]


def test_summary_sentence_splits_errors_and_warnings():
    from backend.app.utils.summary_text import validation_summary
    e, w = {"severity": "error"}, {"severity": "warning"}
    assert validation_summary("R", False, [e, w, w]) == "룰 'R'에 문제 3건(오류 1건·경고 2건)이 발견되었습니다."
    assert validation_summary("R", False, [e]) == "룰 'R'에 오류 1건이 발견되었습니다."
    assert validation_summary("R", True, [w, w]) == "룰 'R'은(는) 유효합니다. 경고 2건이 있습니다."
    assert validation_summary("R", True, []) == "룰 'R'은(는) 유효합니다."


def test_validate_json_summary_matches_counts():
    sample = json.loads((ROOT / "test_all_errors_combined.json").read_text(encoding="utf-8"))
    body = client.post("/rules/validate-json", json=sample).json()
    errs = sum(1 for i in body["issues"] if i["severity"] == "error")
    warns = len(body["issues"]) - errs
    assert f"오류 {errs}건·경고 {warns}건" in body["summary"]
    assert "건의 오류" not in body["summary"]
    assert f"오류 {errs}건 · 경고 {warns}건" in body["ai_summary_md"]


def test_rule_description_on_top_of_summary():
    v = dict(VALIDATION, rule_description={"what": "30세 이상인 사용자를 대상으로 합니다.",
                                           "purpose": "연령 기반 할인 대상을 고르는 룰로 보입니다."})
    s = build_panel_markdown(RULE, v)["ai_summary_md"]
    assert s.startswith("> **이 룰은** 30세 이상인 사용자를 대상으로 합니다.")
    assert "**목적(추정)** · 연령 기반 할인 대상을 고르는 룰로 보입니다." in s
    assert "AI가 조건을 읽고 정리한 설명입니다." in s
    # 판정보다 위
    assert s.index("이 룰은") < s.index("수정 필요")


def test_rule_description_purpose_null_and_missing():
    s = build_panel_markdown(RULE, dict(VALIDATION, rule_description={"what": "설명", "purpose": None}))["ai_summary_md"]
    assert "이 룰은" in s and "목적(추정)" not in s
    for desc in (None, {}, {"what": "", "purpose": "x"}):
        s = build_panel_markdown(RULE, dict(VALIDATION, rule_description=desc))["ai_summary_md"]
        assert "이 룰은" not in s and "AI가 조건을 읽고" not in s
    assert "이 룰은" not in build_panel_markdown(RULE, VALIDATION)["ai_summary_md"]


def test_rule_description_escaped():
    v = dict(VALIDATION, rule_description={"what": "<script>x</script>\n# 제목", "purpose": "[a](javascript:1)"})
    s = build_panel_markdown(RULE, v)["ai_summary_md"]
    assert "<" not in s and "](" not in s.replace("\\](", "")
