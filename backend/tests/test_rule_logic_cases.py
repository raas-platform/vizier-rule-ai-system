"""룰 검사 로직 회귀 테스트 (58 케이스).

기대값은 "올바른 룰 검사기라면 이래야 한다"는 기준으로 먼저 정한 것이며
(tests/logic_cases.py), /rules/validate-json 과 같은 경로(Rule -> RuleAnalyzerV2)로 검증한다.
"""

import asyncio

import pytest

from app.models.rule import Rule
from app.services.rule_analyzer_v2 import RuleAnalyzerV2

from . import logic_cases as cases


def _uuids(tree):
    out = set()
    for c in tree.get("condition", []):
        if "logicType" in c:
            out |= _uuids(c)
        else:
            out.add(c["condUuid"])
    return out


@pytest.mark.parametrize("cs", cases.CASES, ids=[c["id"] for c in cases.CASES])
def test_logic_case(cs):
    rule = Rule(**cases.to_req(cs)[0])
    result = asyncio.run(RuleAnalyzerV2().analyze_rule(rule))
    issues = result.issues

    assert result.is_valid == cs["valid"], (
        f"{cs['id']} {cs['title']}: 유효판정 기대 {cs['valid']} / 실제 {result.is_valid}, "
        f"이슈={[(i.issue_type, i.severity, i.condUuid) for i in issues]}"
    )
    for issue_type, uuid in cs["must"]:
        assert any(
            i.issue_type == issue_type and (uuid is None or i.condUuid == uuid)
            for i in issues
        ), f"못 잡음: {issue_type} @{uuid}"
    for issue_type in cs["must_not"]:
        assert not any(i.issue_type == issue_type for i in issues), f"오탐: {issue_type}"

    tree_uuids = _uuids(cs["tree"])
    orphans = [i.issue_type for i in issues if i.condUuid and i.condUuid not in tree_uuids]
    assert not orphans, f"트리에 없는 condUuid: {orphans}"


def test_complexity_is_never_an_error():
    cs = next(c for c in cases.CASES if c["id"] == "M02")
    rule = Rule(**cases.to_req(cs)[0])
    result = asyncio.run(RuleAnalyzerV2().analyze_rule(rule))
    cx = [i for i in result.issues if i.issue_type == "complexity_warning"]
    assert cx and all(i.severity == "warning" for i in cx)
    assert result.is_valid
