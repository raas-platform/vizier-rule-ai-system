"""Vizier AI 패널에 바로 그릴 markdown 조립 (스펙: judge/ai-panel-requirements.md 7~9).

- ai_summary_md: 검증 직후 패널 위쪽에 보이는 요약
- condition_details_md: 트리의 모든 조건 condUuid → 그 조건을 눌렀을 때 요약 아래 보이는 설명

새 AI 호출은 없다. 이미 만든 검증 응답 값만으로 조립한다.
룰 이름·표시명·AI 문장 등 바깥에서 들어온 글자는 모두 md_text()로 감싸서
raw HTML/script와 markdown 링크·이미지가 만들어지지 않게 한다.
"""

import re
from typing import Any, Dict, Iterable, List, Optional

from .report_writer import ISSUE_LABELS

NO_ISSUE_MD = "✅ 이상 없음"

_HTML_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
# 링크·이미지(`[..](..)`, `![..](..)`)와 코드 표시가 생기지 않도록 대괄호·백틱·백슬래시는 백슬래시로 무력화
_MD_ESC = {"\\": "\\\\", "[": "\\[", "]": "\\]", "`": "\\`"}


def md_text(value: Any) -> str:
    """바깥에서 온 값을 markdown 본문에 넣을 수 있게 이스케이프.

    `<`, `>`, `&`는 HTML 엔티티로 바꿔서 raw HTML이 절대 만들어지지 않게 하고,
    줄 머리의 `#`, `>`, `-` 같은 블록 문법은 줄 단위로 무력화한다.
    """
    s = "" if value is None else str(value)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "".join(_HTML_ESC.get(c, _MD_ESC.get(c, c)) for c in s)
    lines = []
    for line in s.split("\n"):
        line = line.lstrip()  # 들여쓰기 4칸 → 코드 블록이 되지 않게
        # 제목(#), 목록(-, +, *, 1.), 인용(&gt;는 이미 엔티티), 코드 울타리(~~~) 시작을 막음
        line = re.sub(r"^(\s*)([#+\-*=]|~{3,})", r"\1\\\2", line)
        line = re.sub(r"^(\s*\d+)([.)])", r"\1\\\2", line)
        lines.append(line)
    return "\n".join(lines).strip()


def _md_inline(value: Any) -> str:
    """한 줄로 써야 하는 자리(제목·목록 항목)용. 줄바꿈은 공백으로."""
    return re.sub(r"\s*\n\s*", " ", md_text(value))


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return dict(getattr(obj, "__dict__", {}))


def _walk(node: Any, out: List[Dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return
    if isinstance(node.get("condition"), list):
        for child in node["condition"]:
            _walk(child, out)
        return
    if node.get("condUuid"):
        out.append(node)


def tree_conditions(rule_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """룰 JSON(conditionTree)에서 condUuid가 있는 조건을 트리 순서대로."""
    out: List[Dict[str, Any]] = []
    _walk((rule_data or {}).get("conditionTree"), out)
    return out


def _is_error(issue: Dict[str, Any]) -> bool:
    return issue.get("severity") == "error"


def _sev_label(issue: Dict[str, Any]) -> str:
    return "🔴 오류" if _is_error(issue) else "🟡 경고"


def _title(issue: Dict[str, Any]) -> str:
    t = issue.get("issue_type") or ""
    return ISSUE_LABELS.get(t, t or "이슈")


def _issue_block(issue: Dict[str, Any]) -> List[str]:
    """이슈 하나: 심각도·제목, 설명, (AI 설명), 고치는 방법."""
    lines = [f"**{_sev_label(issue)} · {_md_inline(_title(issue))}**", ""]
    explanation = (issue.get("explanation") or "").strip()
    ai_explanation = (issue.get("ai_explanation") or "").strip()
    if explanation:
        lines += [md_text(explanation), ""]
    if ai_explanation and ai_explanation != explanation:
        lines += [f"*AI 설명* · {md_text(ai_explanation)}", ""]
    fix = (issue.get("ai_suggestion") or issue.get("suggestion") or "").strip()
    if fix:
        lines += [f"*고치는 방법* · {md_text(fix)}", ""]
    return lines


def _cond_heading(cond: Dict[str, Any]) -> str:
    name = cond.get("dispName") or cond.get("keyName") or cond.get("condUuid")
    expr = " ".join(
        str(x) for x in (cond.get("keyName"), cond.get("operator"), cond.get("value")) if x not in (None, "")
    )
    head = f"### {_md_inline(name)}"
    return f"{head} · {_md_inline(expr)}" if expr else head


def build_condition_details_md(
    conditions: Iterable[Dict[str, Any]], issues: List[Dict[str, Any]]
) -> Dict[str, str]:
    by_uuid: Dict[str, List[Dict[str, Any]]] = {}
    for i in issues:
        if i.get("condUuid"):
            by_uuid.setdefault(i["condUuid"], []).append(i)

    out: Dict[str, str] = {}
    for cond in conditions:
        uuid = cond["condUuid"]
        if uuid in out:  # 같은 condUuid가 트리에 두 번 있으면 처음 것만
            continue
        mine = sorted(by_uuid.get(uuid, []), key=lambda i: 0 if _is_error(i) else 1)
        lines = [_cond_heading(cond), ""]
        if not mine:
            lines.append(NO_ISSUE_MD)
        else:
            errs = sum(1 for i in mine if _is_error(i))
            lines += [f"오류 {errs}건 · 경고 {len(mine) - errs}건", ""]
            for i in mine:
                lines += _issue_block(i)
        out[uuid] = "\n".join(lines).strip() + "\n"
    return out


RULE_DESCRIPTION_NOTE = "AI가 조건을 읽고 정리한 설명입니다."


def _rule_description_lines(desc: Any) -> List[str]:
    """맨 위 "이 룰은" 칸 (judge/rule-description-requirements.md 6~8).

    rule_description이 없거나 what이 비면 칸을 통째로 뺀다.
    """
    d = _as_dict(desc) if desc else {}
    what = (d.get("what") or "").strip() if isinstance(d.get("what"), str) else ""
    if not what:
        return []
    lines = [f"> **이 룰은** {_md_inline(what)}"]
    purpose = d.get("purpose")
    if isinstance(purpose, str) and purpose.strip():
        lines += [">", f"> **목적(추정)** · {_md_inline(purpose)}"]
    lines += [">", f"> {RULE_DESCRIPTION_NOTE}", ""]
    return lines


def build_ai_summary_md(
    validation: Dict[str, Any], issues: List[Dict[str, Any]], tree_uuids: Iterable[str]
) -> str:
    known = set(tree_uuids)
    errs = sum(1 for i in issues if _is_error(i))
    warns = len(issues) - errs
    verdict = "✅ 유효" if validation.get("is_valid") else "⛔ 수정 필요"

    lines = _rule_description_lines(validation.get("rule_description"))
    lines += [f"## {verdict}", "", f"**오류 {errs}건 · 경고 {warns}건**", ""]
    if validation.get("summary"):
        lines += [md_text(validation["summary"]), ""]

    ai_comment = (validation.get("ai_comment") or "").strip()
    if ai_comment:
        # ai_comment는 실제 AI가 아니라 규칙으로 만든 문장이라 "AI"를 붙이지 않음 (스펙 9)
        lines += ["### 종합 의견", "", md_text(ai_comment), ""]

    ai_status = validation.get("ai_status")
    ai_error = (validation.get("ai_error") or "").strip()
    if ai_status and ai_status != "ok" and ai_error:
        lines += [f"*AI 설명 상태* · {_md_inline(ai_error)}", ""]

    # condUuid가 없거나 트리에 없는 이슈 = 룰 전체에 대한 이슈
    rule_wide = [i for i in issues if not i.get("condUuid") or i.get("condUuid") not in known]
    if rule_wide:
        lines += ["### 룰 전체에 대한 이슈", ""]
        for i in sorted(rule_wide, key=lambda x: 0 if _is_error(x) else 1):
            text = (i.get("explanation") or i.get("ai_explanation") or "").strip()
            fix = (i.get("ai_suggestion") or i.get("suggestion") or "").strip()
            item = f"- **{_sev_label(i)} · {_md_inline(_title(i))}**"
            if text:
                item += f" — {_md_inline(text)}"
            if fix:
                item += f" (고치는 방법: {_md_inline(fix)})"
            lines.append(item)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_panel_markdown(rule_data: Optional[Dict[str, Any]], validation: Any) -> Dict[str, Any]:
    """validate-json 응답에 붙일 두 필드를 만든다."""
    v = _as_dict(validation)
    issues = [_as_dict(i) for i in (v.get("issues") or [])]
    conds = tree_conditions(rule_data or {})
    details = build_condition_details_md(conds, issues)
    return {
        "ai_summary_md": build_ai_summary_md(v, issues, details.keys()),
        "condition_details_md": details,
    }
