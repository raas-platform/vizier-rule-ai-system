"""
검증 리포트 작성 (POST /rules/report/stream 에서 사용)

화면이 이미 받은 검증 응답(+룰)을 정리해 Claude에 넘기고, Claude는 문서만 작성한다.
재분석·새 판정은 하지 않는다: 프롬프트에 넣는 이슈 목록이 리포트에 실릴 이슈의 전부다.

- MD: Claude가 문서 전체(마크다운)를 쓴다.
- HTML: 서버가 <head>(고정 CSS)와 닫는 태그를 붙이고, Claude는 <article> 안쪽 본문만 쓴다.
  모양이 매번 같고, 출력 토큰과 첫 화면 표시 시간이 줄어든다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

KST = timezone(timedelta(hours=9))

# 화면(tools/vizier-mock)과 같은 한글 이름
ISSUE_LABELS: Dict[str, str] = {
    "ambiguous_branch": "애매한 분기",
    "complexity_warning": "복잡도 경고",
    "contradictory_conditions": "상충 조건",
    "duplicate_condition": "중복 조건",
    "invalid_operator": "잘못된 연산자",
    "missing_condition": "누락 조건",
    "missing_conditions": "조건 없음",
    "missing_operator": "연산자 누락",
    "missing_value": "값 누락",
    "missing_name": "이름 누락",
    "missing_description": "설명 누락",
    "missing_action": "액션 누락",
    "missing_action_type": "액션 타입 누락",
    "missing_parameters": "파라미터 누락",
    "self_contradiction": "자기 모순",
    "type_mismatch": "타입 불일치",
    "uncommon_operator": "드문 연산자",
}

# 1M 토큰당 USD (Anthropic 공개 단가, 2026-11 기준). 모르는 모델이면 비용은 None.
MODEL_PRICES: Dict[str, Tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
}


def _first_rule(rule: Any) -> Dict[str, Any]:
    """화면은 검증 요청과 같은 배열 형태로 보낼 수 있으므로 첫 룰만 사용."""
    if isinstance(rule, list):
        return rule[0] if rule and isinstance(rule[0], dict) else {}
    return rule if isinstance(rule, dict) else {}


def _walk_conditions(node: Any, out: Dict[str, Dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return
    if isinstance(node.get("condition"), list):
        for child in node["condition"]:
            _walk_conditions(child, out)
        return
    uuid = node.get("condUuid")
    if uuid:
        out[uuid] = node


def _cond_text(c: Dict[str, Any]) -> str:
    return f'{c.get("dispName") or "-"} ({c.get("keyName") or "-"}) {c.get("operator") or ""} {c.get("value", "")}'.strip()


def _tree_lines(node: Any, depth: int = 0) -> List[str]:
    pad = "  " * depth
    if not isinstance(node, dict):
        return []
    if isinstance(node.get("condition"), list):
        lines = [f'{pad}[{node.get("logicType", "AND")} 그룹]']
        for child in node["condition"]:
            lines.extend(_tree_lines(child, depth + 1))
        return lines
    return [f'{pad}- {node.get("condUuid", "?")}: {_cond_text(node)} [{node.get("fieldDataType", "")}]']


def _fmt_time(ts: Optional[str]) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(KST)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(ts)


_RISK_LABELS = {"critical": "매우 높음", "high": "높음", "medium": "보통", "low": "낮음", "none": "없음"}


def _risk_text(risk: Any) -> Optional[str]:
    if not isinstance(risk, dict) or not risk.get("risk_level"):
        return None
    label = _RISK_LABELS.get(str(risk["risk_level"]).lower(), str(risk["risk_level"]))
    return f'{label} ({risk["risk_message"]})' if risk.get("risk_message") else label


def _related_conditions(issue: Dict[str, Any], cond: Optional[Dict[str, Any]],
                        by_key: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """이슈가 가리키는 조건들을 표시명 문장으로. 같은 항목(keyName)의 조건을 트리 순서로 모두 담는다.
    조건을 특정할 수 없는 이슈(룰 전체 복잡도 등)는 ["룰 전체"]."""
    key = issue.get("keyName") or (cond or {}).get("keyName")
    same = by_key.get(key or "") if key else None
    if same:
        return [_cond_text(c) for c in same]
    if cond:
        return [_cond_text(cond)]
    return ["룰 전체"]


def build_facts(rule_in: Any, validation: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Claude에 넘길 '사실' 묶음. 건수·판정·번호는 서버가 정해서 Claude가 바꾸지 못하게 한다."""
    rule = _first_rule(rule_in)
    conds: Dict[str, Dict[str, Any]] = {}
    _walk_conditions(rule.get("conditionTree"), conds)

    raw_issues = [i for i in (validation.get("issues") or []) if isinstance(i, dict)]
    errors = [i for i in raw_issues if i.get("severity") == "error"]
    others = [i for i in raw_issues if i.get("severity") != "error"]

    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for c in conds.values():
        by_key.setdefault(c.get("keyName") or "", []).append(c)

    issues: List[Dict[str, Any]] = []
    for prefix, group in (("E", errors), ("W", others)):
        for n, i in enumerate(group, 1):
            c = conds.get(i.get("condUuid") or "")
            item = {
                "번호": f"{prefix}{n}",
                "severity": i.get("severity"),
                "issue_type": i.get("issue_type"),
                "유형": ISSUE_LABELS.get(i.get("issue_type") or "", i.get("issue_type")),
                "condUuid": i.get("condUuid"),
                "keyName": i.get("keyName"),
                "관련 조건": _related_conditions(i, c, by_key),
                "필드 타입": c.get("fieldDataType") if c else None,
            }
            # location("1, 2" 같은 번호)은 독자에게 의미가 없어 넘기지 않는다. 위치는 위의 "관련 조건"으로만 말한다.
            for k in ("explanation", "suggestion", "ai_explanation", "ai_suggestion",
                      "impact_level", "affected_scenarios"):
                if i.get(k):
                    item[k] = i[k]
            issues.append(item)

    is_valid = bool(validation.get("is_valid"))
    if not is_valid:
        verdict = "수정 필요"
    elif raw_issues:
        verdict = "검토 권장"
    else:
        verdict = "문제 없음"

    meta = validation.get("report_metadata") or {}
    now = now or datetime.now(KST)
    facts = {
        "룰": {
            "이름": rule.get("ruleName") or meta.get("ruleName") or "",
            "ID": rule.get("ruleUuid") or meta.get("ruleUuid") or "",
            "설명": rule.get("ruleMsg") or "",
            "조건 트리": "\n".join(_tree_lines(rule.get("conditionTree"))),
        },
        "검증 일시": _fmt_time(meta.get("analysis_timestamp")) or now.strftime("%Y-%m-%d %H:%M"),
        "리포트 작성 일시": now.strftime("%Y-%m-%d %H:%M"),
        "판정": verdict,
        "is_valid": is_valid,
        "위험도": _risk_text(validation.get("risk_assessment")),
        "건수": {"전체": len(raw_issues), "오류": len(errors), "경고": len(others)},
        "유형별 건수": validation.get("issue_counts") or {},
        "검증 요약 문장": validation.get("summary"),
        "품질 점수": validation.get("quality_metrics"),
        "AI 코멘트": validation.get("ai_comment"),
        "이슈": issues,
    }
    # 응답에 있는 그 밖의 분석 정보(있으면): 문장 작성 근거로만 쓰고 새 이슈로 만들지 않음
    extra = {k: validation[k] for k in ("structure", "performance_metrics", "risk_assessment",
                                         "improvement_recommendations", "ai_insights")
             if validation.get(k)}
    if extra:
        facts["참고 정보"] = extra
    ai_state = {k: validation[k] for k in ("ai_status", "ai_error") if validation.get(k)}
    if ai_state and not validation.get("ai_comment"):
        facts["AI 분석 상태"] = ai_state
    return facts


# ---------------------------------------------------------------- 프롬프트

_COMMON_RULES = """당신은 룰 검증 결과를 기획·운영 담당자에게 전달하는 리포트를 씁니다.
입력은 <facts> 안의 JSON 하나입니다. 이 JSON이 리포트 내용의 전부입니다.

반드시 지킬 것
1. 룰을 다시 분석하거나 새 판정을 내리지 마세요. <facts>의 "이슈" 목록에 있는 것만 씁니다. 목록에 없는 문제를 추가하지 말고, 있는 이슈를 빼지도 합치지도 마세요.
   이슈의 타당성을 판단하거나 반박하거나 조건을 달아 해석하지 마세요. "AND/OR 연결에 따라 문제가 아닐 수 있다", "먼저 확인해 보세요"처럼 목록에 없는 가정을 덧붙이지 말고, 이슈는 목록에 적힌 그대로 사실로 전달합니다. 조건 트리는 이슈의 위치를 설명하는 데만 쓰세요.
   "~라면" 같은 조건부 표현은 이슈의 성립 여부·판정을 바꾸지 않는 "고치는 방법의 대안"에서만 쓸 수 있습니다(예: "등급을 나누려는 목적이라면 구간을 나누세요").
   독자가 원인이나 의도를 모른다고 가정하는 확인 안내("~모르겠다면 확인하세요", "~하려던 것이라면 확인하세요")는 쓰지 마세요. 고치기 선택지를 나열하는 "~라면"만 허용합니다.
   <facts>에 없는 위험·영향·원인을 추측해 쓰지 마세요(예: "값이 true로 해석되면 혜택이 잘못 적용될 위험"). 새 필드, 새 항목, 새 데이터 구조를 만들자는 제안도 하지 마세요(예: "premium_status 항목을 추가"). 고치는 방법은 이슈의 suggestion·explanation에 있는 방향과 기존 조건의 값·연산자 수정 범위 안에서만 쓰세요.
2. 모든 이슈는 본문에 정확히 한 번(오류는 "먼저 고쳐야 할 것", 경고는 "검토하면 좋은 것"), 부록 표에 정확히 한 번 나옵니다. 각 이슈의 "번호"(E1, W3 같은 값)를 그대로 표시하세요.
3. 건수·판정·점수·일시·이름·ID·조건 값은 <facts>에 있는 값을 그대로 옮기세요. 계산하거나 바꾸지 마세요.
4. 독자는 개발자가 아닙니다. "무엇이 문제인지"와 "어떻게 고치면 되는지"를 쉬운 한국어 존댓말로 짧게 쓰세요. 조건은 표시명(dispName) 위주로 말하고 키 이름은 괄호로 덧붙이세요. condUuid, issue_type, severity 같은 기술 용어는 부록에만 씁니다.
   위치는 이슈의 "관련 조건"(표시명과 값)으로만 말하세요. "조건 3", "위치 2"처럼 번호로 가리키지 마세요.
5. 조건 값을 고치라고 안내할 때 따옴표 유무를 말하지 마세요. 비교 값은 시스템이 항상 문자열로 전달하므로 "'25'가 아니라 25로 입력"처럼 쓰면 틀린 조언입니다. "숫자 값(예: 25)으로 바꾸세요"처럼만 쓰세요.
   설명은 이슈의 explanation, suggestion, ai_explanation, ai_suggestion, 조건 트리에 근거해 쉽게 풀어 쓰세요. 근거가 없는 수치나 영향(매출, 고객 수 등)을 지어내지 마세요.
6. "AI 종합 의견"은 <facts>의 "AI 코멘트"를 쉬운 말로 다듬어 옮깁니다. AI 코멘트가 비어 있으면 이 절을 통째로 빼세요. 단 <facts>에 "AI 분석 상태"가 있으면 절 제목은 두고 그 사유를 한 줄로만 쓰세요.
7. 이슈가 0건이면 오류/경고 절에 각각 "해당 없음"이라고 쓰고, 부록 표는 헤더만 둡니다.
8. 문서만 출력하세요. 앞뒤 인사말, 설명, 코드 블록 울타리(```)를 붙이지 마세요.

문서 구성 (이 순서)
- 제목과 기본 정보(룰 이름, 룰 ID, 룰 설명, 검증 일시, 판정과 오류/경고 건수)
- 한눈에 보기: 2~4문장으로 이 룰의 상태와 가장 중요한 문제, 그리고 오류/경고 건수 표와 품질 점수·위험도(있을 때)
- 먼저 고쳐야 할 것 (오류 N건): 오류마다 짧은 제목, 관련 조건, 문제, 고치는 방법
- 검토하면 좋은 것 (경고 N건): 표 한 개 — 번호 | 항목 | 관련 조건 | 내용 | 제안
- AI 종합 의견 (AI 코멘트가 있을 때만)
- 부록: 기술 정보 — 표 한 개: 번호 | 심각도 | 유형 | condUuid | keyName, 그 아래 품질 세부 점수 한 줄
"""

_MD_FORMAT = """출력 형식: GitHub 위키/저장소에 그대로 붙일 Markdown(GFM).
- 맨 첫 줄은 "# 룰 검증 리포트: <룰 이름>"
- 기본 정보는 "- **룰 ID**: ..." 같은 목록
- 판정 줄 앞에는 수정 필요=❌, 검토 권장=⚠️, 문제 없음=✅ 를 붙이세요
- 절 제목은 ##, 오류 하나하나는 "### E1. <짧은 제목>" 형태
- 부록 앞에 --- 구분선
"""

_HTML_FORMAT = """출력 형식: HTML 조각. 서버가 이미 <!DOCTYPE html>, <head>, 스타일, <body><article class="rep"> 를 붙였고 닫는 태그도 붙입니다.
당신은 <article> 안쪽 본문만 씁니다. <html>, <head>, <body>, <style>, <script>, 외부 링크/이미지는 쓰지 마세요. 인라인 style 속성도 아래에 적힌 것 외에는 쓰지 마세요.
아래 클래스만 사용해 이 골격을 그대로 따르세요(값만 채움). 텍스트의 <, >, & 는 &lt; &gt; &amp; 로 쓰세요.

<header>
  <span class="kicker">룰 검증 리포트</span>
  <h1>룰 이름</h1>
  <div class="meta"><span>룰 ID <b>...</b></span><span>검증 <b>YYYY-MM-DD HH:mm</b></span><span>설명 <b>...</b></span></div>
</header>
<section class="verdict bad|warn|ok">   ← 수정 필요=bad, 검토 권장=warn, 문제 없음=ok
  <div class="score" style="--s:점수"><div><strong>점수</strong><span>/ 100</span></div></div>
  <div>
    <span class="pill bad|warn|ok">판정 · 위험도 (위험도가 없으면 판정만)</span>
    <h2 class="sr">한눈에 보기</h2>
    <p>한눈에 보기 문장</p>
    <div class="counts"><span>오류 N</span><span>경고 N</span><span>유지보수성 N</span><span>가독성 N</span><span>완전성 N</span><span>일관성 N</span></div>
  </div>
</section>
<section>
  <h2><span class="pill bad">오류 N</span> 먼저 고쳐야 할 것</h2>
  <div class="issues">
    <div class="issue"><h3><span class="no">E1</span> 짧은 제목</h3><span class="where">표시명 · 키 · 조건</span><span>문제 설명</span><span class="fix">고치는 방법: ...</span></div>
  </div>
</section>
<section>
  <h2><span class="pill warn">경고 N</span> 검토하면 좋은 것</h2>
  <div class="tbl"><table><thead><tr><th>번호</th><th>항목</th><th>관련 조건</th><th>내용</th><th>제안</th></tr></thead><tbody>
    <tr><td class="k">W1</td><td class="k"><span class="tag">항목</span></td><td>...</td><td>...</td><td>...</td></tr>
  </tbody></table></div>
</section>
<section class="ai"><h2>AI 종합 의견</h2><p>...</p></section>
<details open><summary>부록: 기술 정보 (개발자용)</summary>
  <div class="tbl"><table class="mono"><thead><tr><th>번호</th><th>심각도</th><th>유형</th><th>condUuid</th><th>keyName</th></tr></thead><tbody>...</tbody></table></div>
  <p class="foot">품질 세부 점수: ...</p>
</details>
<p class="foot">이 리포트는 검증 결과를 바탕으로 AI가 작성했습니다. 작성 일시 YYYY-MM-DD HH:mm</p>

품질 점수가 없으면 score 블록과 점수 span들은 빼세요.
"""

HTML_HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#f3f4f6;--paper:#fff;--fg:#1b2130;--mute:#5f6878;--line:#dfe3ea;--accent:#2f5bd3;
--err:#c4342b;--err-bg:#fdeceb;--warn:#a86a00;--warn-bg:#fff4dc;--ok:#1f7a4d;--ok-bg:#e6f4ec;--note-bg:#eaf0ff;
--sans:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;--mono:ui-monospace,Consolas,"D2Coding",monospace}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12151c;--paper:#1a1f29;--fg:#e6e9ef;--mute:#9aa3b2;--line:#2c3341;--accent:#7d9cff;
--err:#ff7b70;--err-bg:#3a1f1d;--warn:#f0b444;--warn-bg:#36290f;--ok:#5fd19a;--ok-bg:#16301f;--note-bg:#1f2a44;color-scheme:dark}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 var(--sans);padding:24px 16px 48px}}
.rep{{max-width:860px;margin:0 auto;background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:28px;display:flex;flex-direction:column;gap:24px}}
.rep header{{display:flex;flex-direction:column;gap:8px}}
.kicker{{font:12px var(--mono);color:var(--mute)}}
.rep h1{{margin:0;font-size:26px;line-height:1.3}}
.meta{{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--mute)}}
.meta b{{color:var(--fg);font-weight:500}}
.verdict{{display:grid;grid-template-columns:auto 1fr;gap:20px;align-items:center;padding:18px;border-radius:10px;--c:var(--err);--cb:var(--err-bg);background:var(--cb)}}
.verdict.warn{{--c:var(--warn);--cb:var(--warn-bg)}} .verdict.ok{{--c:var(--ok);--cb:var(--ok-bg)}}
.verdict p{{margin:6px 0 0}}
.score{{width:96px;height:96px;border-radius:50%;display:grid;place-items:center;text-align:center;background:conic-gradient(var(--c) calc(var(--s,0)*1%),var(--line) 0)}}
.score>div{{width:76px;height:76px;border-radius:50%;background:var(--cb);display:grid;place-content:center}}
.score strong{{font-size:26px;line-height:1}} .score span{{font-size:11px;color:var(--mute)}}
.pill{{display:inline-block;font:700 12px var(--sans);padding:2px 10px;border-radius:999px;color:#fff;background:var(--err)}}
.pill.warn{{background:var(--warn)}} .pill.ok{{background:var(--ok)}}
.counts{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;font-size:13px}}
.counts span{{background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:2px 8px}}
.rep section{{display:flex;flex-direction:column;gap:12px}}
.rep h2{{margin:0;font-size:18px;display:flex;align-items:center;gap:8px}}
.sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
.issues{{display:flex;flex-direction:column;gap:10px}}
.issue{{border:1px solid var(--line);border-left:4px solid var(--err);border-radius:8px;padding:12px 14px;display:flex;flex-direction:column;gap:4px}}
.issue h3{{margin:0;font-size:15px}}
.no{{font:12px var(--mono);color:var(--mute);margin-right:4px}}
.where{{font:12px var(--mono);color:var(--mute)}}
.fix{{color:var(--ok);font-weight:500}}
.tbl{{overflow-x:auto}}
.tbl table{{border-collapse:collapse;width:100%;font-size:14px;min-width:560px}}
.tbl th{{font-size:12px;color:var(--mute);text-align:left;font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px}}
.tbl td{{border-bottom:1px solid var(--line);padding:8px;vertical-align:top}}
.tbl td.k{{white-space:nowrap}}
.tag{{font-size:12px;padding:1px 8px;border-radius:999px;background:var(--warn-bg);color:var(--warn);white-space:nowrap}}
.ai{{background:var(--note-bg);border-radius:8px;padding:14px 16px}} .ai h2{{font-size:15px}} .ai p{{margin:0}}
details{{border-top:1px solid var(--line);padding-top:14px}} summary{{cursor:pointer;font-weight:500}}
.mono{{font-family:var(--mono);font-size:12.5px}}
.foot{{font-size:12px;color:var(--mute);margin:8px 0 0}}
@media (max-width:520px){{.verdict{{grid-template-columns:1fr}}.rep{{padding:18px}}}}
@media print{{body{{background:#fff;padding:0}}.rep{{border:0}}}}
</style>
</head>
<body>
<article class="rep">
"""

HTML_TAIL = "\n</article>\n</body>\n</html>\n"


def build_system_prompt(fmt: str) -> str:
    return _COMMON_RULES + "\n" + (_HTML_FORMAT if fmt == "html" else _MD_FORMAT)


def build_user_message(facts: Dict[str, Any]) -> str:
    return (
        "<facts>\n" + json.dumps(facts, ensure_ascii=False, indent=1) + "\n</facts>\n\n"
        f'이슈 {facts["건수"]["전체"]}건(오류 {facts["건수"]["오류"]}, 경고 {facts["건수"]["경고"]})을 '
        "하나도 빠뜨리거나 더하지 말고 리포트를 작성하세요."
    )


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def html_head(facts: Dict[str, Any]) -> str:
    return HTML_HEAD.format(title=html_escape(f'룰 검증 리포트 - {facts["룰"]["이름"] or "이름 없음"}'))


def estimate_cost(model: str, usage: Dict[str, int]) -> Optional[float]:
    price = MODEL_PRICES.get(model)
    if not price:
        return None
    inp, out = price
    cost = (
        usage.get("input_tokens", 0) * inp
        + usage.get("cache_creation_input_tokens", 0) * inp * 1.25
        + usage.get("cache_read_input_tokens", 0) * inp * 0.1
        + usage.get("output_tokens", 0) * out
    ) / 1_000_000
    return round(cost, 5)


class FenceStripper:
    """모델이 지시와 달리 문서를 ``` 울타리로 감싸도 화면·파일에 울타리가 남지 않게 걸러낸다.

    앞쪽: 첫 줄바꿈(또는 16자)까지 모아 ``` 로 시작하면 그 줄을 버린다.
    뒤쪽: '`' 가 들어간 마지막 몇 글자는 붙잡아 두었다가 끝에서 울타리면 버린다.
    """

    HOLD = 8

    def __init__(self) -> None:
        self._head_done = False
        self._buf = ""

    def feed(self, text: str) -> str:
        self._buf += text
        if not self._head_done:
            stripped = self._buf.lstrip()
            if "\n" not in self._buf and len(stripped) < 16:
                return ""
            self._head_done = True
            if stripped.startswith("```"):
                nl = stripped.find("\n")
                self._buf = stripped[nl + 1:] if nl >= 0 else ""
            else:
                self._buf = stripped
        tail = self._buf[-self.HOLD:]
        if "`" in tail:
            cut = len(self._buf) - self.HOLD + tail.index("`")
            out, self._buf = self._buf[:cut], self._buf[cut:]
            return out
        out, self._buf = self._buf, ""
        return out

    def flush(self) -> str:
        rest = self._buf if self._head_done else self._buf.lstrip()
        self._buf = ""
        if not self._head_done and rest.startswith("```"):
            nl = rest.find("\n")
            rest = rest[nl + 1:] if nl >= 0 else ""
        stripped = rest.rstrip()
        if stripped.endswith("```"):
            return stripped[:-3].rstrip() + "\n"
        return rest
