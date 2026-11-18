"""검증 요약 문장의 건수 표현 (오류와 경고를 나눠 씀)."""

from typing import Any, Iterable


def _severity(issue: Any) -> str:
    return issue.get("severity") if isinstance(issue, dict) else getattr(issue, "severity", "")


def issue_count_phrase(issues: Iterable[Any]) -> str:
    """'문제 N건(오류 a건·경고 b건)', 한쪽만 있으면 '오류 a건' 또는 '경고 b건'.

    severity가 error가 아닌 것은 경고로 센다(화면·AI 패널과 같은 기준).
    """
    items = list(issues)
    errors = sum(1 for i in items if _severity(i) == "error")
    warnings = len(items) - errors
    if errors and warnings:
        return f"문제 {len(items)}건(오류 {errors}건·경고 {warnings}건)"
    if errors:
        return f"오류 {errors}건"
    return f"경고 {warnings}건"


def validation_summary(rule_name: str, is_valid: bool, issues: Iterable[Any]) -> str:
    items = list(issues)
    if not items:
        return f"룰 '{rule_name}'은(는) 유효합니다."
    if is_valid:
        return f"룰 '{rule_name}'은(는) 유효합니다. {issue_count_phrase(items)}이 있습니다."
    return f"룰 '{rule_name}'에 {issue_count_phrase(items)}이 발견되었습니다."
