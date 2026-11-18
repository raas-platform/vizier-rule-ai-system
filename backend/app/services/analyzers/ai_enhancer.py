"""
AI 개선기 (AIEnhancer)

AI를 활용한 이슈 개선, 통찰 생성, 추천 등을 담당합니다.
- 이슈 배치 처리 및 AI 개선
- AI 기반 통찰 생성
- 개선 제안 생성
- 위험도 평가
"""

import asyncio
import html
import json
from typing import Any, Dict, List, Optional

from ...models.rule import Rule, RuleCondition
from ...models.validation_result import (
    ConditionIssue,
    RuleDescription,
    StructureInfo,
)
from ...config import settings
from ...services.llm_service import LLMService, classify_llm_error
from ...utils.logger import get_logger

# AI 보강에 사용하는 모델 (DEFAULT_MODEL 환경변수로 변경 가능)
AI_MODEL = settings.default_model

_JSON_ONLY_SUFFIX = (
    "\n\n응답은 JSON만 출력하세요. 코드 블록(```)이나 앞뒤 설명 문장을 붙이지 마세요."
)


def extract_json(text: Optional[str]) -> Any:
    """AI 응답에서 JSON 값(객체/배열)을 꺼낸다.

    ```json 코드 블록으로 감싸거나 앞뒤에 설명이 붙어 있어도 첫 번째 JSON 값을 찾아 파싱한다.
    찾지 못하면 ValueError.
    """
    if not text or not text.strip():
        raise ValueError("빈 응답")
    decoder = json.JSONDecoder()
    candidate = text.strip()
    # 코드 블록 울타리 제거 (```json ... ```)
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rstrip()[:-3]
    for source in (candidate, text):
        for idx, ch in enumerate(source):
            if ch in "{[":
                try:
                    value, _ = decoder.raw_decode(source[idx:])
                    return value
                except json.JSONDecodeError:
                    continue
    raise ValueError("JSON을 찾을 수 없음")


class AIEnhancer:
    """
    AI 기반 개선 및 통찰을 담당하는 클래스

    이 클래스는 다음 기능들을 제공합니다:
    - 이슈에 대한 AI 기반 설명 개선
    - 룰 분석 통찰 생성
    - 개선 제안 생성
    - 위험도 평가
    """

    def __init__(self):
        """AIEnhancer 초기화"""
        self.logger = get_logger(__name__)
        self.llm_service = LLMService()
        # 이번 분석에서의 AI 호출 결과 (ai_status / ai_error 계산용)
        self._ai_ok_count = 0
        self._ai_skip_reason: Optional[str] = None
        self._ai_failures: List[str] = []

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """AI를 호출한다. 실패해도 예외를 던지지 않고 None을 반환하며 사유를 기록한다.

        키 값이나 예외 메시지는 기록하지 않는다 (사유는 예외 종류/상태 코드만).
        """
        reason = self.llm_service.unavailable_reason(AI_MODEL)
        if reason:
            if self._ai_skip_reason is None:
                self.logger.warning(f"AI 설명 건너뜀: {reason} (모델: {AI_MODEL})")
            self._ai_skip_reason = reason
            return None
        try:
            response = await asyncio.wait_for(
                self.llm_service.generate_text(
                    prompt + _JSON_ONLY_SUFFIX, AI_MODEL, fast=True
                ),
                timeout=settings.ai_timeout,
            )
            self._ai_ok_count += 1
            return response
        except Exception as e:
            reason = classify_llm_error(e)
            if reason not in self._ai_failures:
                self._ai_failures.append(reason)
            self.logger.warning(f"AI 호출 실패, 규칙 판정 결과만 반환: {reason} (모델: {AI_MODEL})")
            return None

    def _note_failure(self, reason: str, detail: str = "") -> None:
        """AI 처리 실패 사유 기록 (응답 원문은 기록하지 않음)"""
        if reason not in self._ai_failures:
            self._ai_failures.append(reason)
        self.logger.warning(f"AI 응답 처리 실패: {reason} {detail}".strip())

    def get_ai_status(self) -> tuple:
        """(ai_status, ai_error) 반환. ok | skipped | failed"""
        if self._ai_failures:
            return "failed", ", ".join(self._ai_failures)
        if self._ai_skip_reason and self._ai_ok_count == 0:
            return "skipped", self._ai_skip_reason
        return "ok", None

    async def enhance_issues_batch(
        self, issues: List[ConditionIssue], rule: Rule, batch_size: int = 5
    ) -> None:
        """
        이슈들을 배치로 AI 개선 처리

        Args:
            issues (List[ConditionIssue]): 개선할 이슈 리스트
            rule (Rule): 룰 객체
            batch_size (int): 배치 크기 (기본값: 5)
        """
        if not issues:
            return

        try:
            # 이슈들을 배치로 그룹화
            batches = [
                issues[i : i + batch_size] for i in range(0, len(issues), batch_size)
            ]

            # 각 배치를 병렬로 처리
            tasks = []
            for batch in batches:
                task = self._process_issue_batch(batch, rule)
                tasks.append(task)

            # 모든 배치를 병렬 실행
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self.logger.info(
                f"AI 배치 이슈 개선 완료: {len(issues)}개 이슈, {len(batches)}개 배치"
            )

        except Exception as e:
            self.logger.error(f"AI 배치 이슈 개선 중 오류: {str(e)}", exc_info=True)

    async def _process_issue_batch(
        self, issue_batch: List[ConditionIssue], rule: Rule
    ) -> None:
        """
        이슈 배치를 처리하여 AI 개선 적용

        Args:
            issue_batch (List[ConditionIssue]): 처리할 이슈 배치
            rule (Rule): 룰 객체
        """
        try:
            rule_name = getattr(rule, "ruleName", getattr(rule, "name", "Unknown"))

            # 배치 프롬프트 생성
            batch_context = {
                "rule_name": rule_name,
                "issues": [
                    {
                        "field": issue.keyName,
                        "issue_type": issue.issue_type,
                        "explanation": issue.explanation,
                        "suggestion": issue.suggestion,
                    }
                    for issue in issue_batch
                ],
            }

            ai_prompt = self._create_batch_enhancement_prompt(batch_context)

            # AI 호출
            ai_response = await self._call_llm(ai_prompt)
            if ai_response is not None:
                # 응답 파싱 및 각 이슈에 적용
                await self._apply_batch_enhancement(issue_batch, ai_response)

        except Exception as e:
            self.logger.error(f"배치 처리 중 오류: {str(e)}", exc_info=True)

    async def _apply_batch_enhancement(
        self, issue_batch: List[ConditionIssue], ai_response: str
    ) -> None:
        """AI 응답을 파싱하여 이슈 배치에 적용 (실패 시 사유만 기록하고 이슈는 건드리지 않음)"""
        try:
            ai_data = extract_json(ai_response)
        except ValueError as e:
            self._note_failure("AI 응답 형식 오류(JSON 파싱 실패)", f"({e})")
            return

        enhanced_issues = (
            ai_data.get("enhanced_issues") if isinstance(ai_data, dict) else ai_data
        )
        if not isinstance(enhanced_issues, list):
            self._note_failure("AI 응답 형식 오류(enhanced_issues 없음)")
            return

        filled = 0
        for issue, enhanced in zip(issue_batch, enhanced_issues):
            if not isinstance(enhanced, dict) or not enhanced.get("enhanced_explanation"):
                continue
            issue.ai_explanation = str(enhanced.get("enhanced_explanation"))
            issue.ai_suggestion = enhanced.get("enhanced_suggestion")
            issue.impact_level = enhanced.get("impact_level", "medium")
            issue.affected_scenarios = enhanced.get("affected_scenarios", [])
            filled += 1
        if filled < len(issue_batch):
            self._note_failure(
                "AI 설명 일부 누락",
                f"({len(issue_batch) - filled}/{len(issue_batch)}건)",
            )

    def _create_batch_enhancement_prompt(self, batch_context: dict) -> str:
        """
        배치 AI 개선용 프롬프트 생성

        Args:
            batch_context (dict): 배치 컨텍스트 정보

        Returns:
            str: 생성된 프롬프트
        """
        issues_text = ""
        for i, issue in enumerate(batch_context["issues"]):
            issues_text += f"""
이슈 {i+1}:
- 필드: {issue['field']}
- 타입: {issue['issue_type']}
- 설명: {issue['explanation']}
- 제안: {issue['suggestion']}
"""

        return f"""
다음 룰의 여러 이슈들을 분석하고 더 상세하고 실용적인 설명과 제안을 제공해주세요:

룰명: {batch_context['rule_name']}
{issues_text}

다음 JSON 형식으로 응답해주세요:
{{
    "enhanced_issues": [
        {{
            "enhanced_explanation": "더 상세하고 이해하기 쉬운 설명",
            "enhanced_suggestion": "구체적이고 실행 가능한 개선 제안",
            "impact_level": "low|medium|high",
            "affected_scenarios": ["시나리오1", "시나리오2"]
        }}
    ]
}}
"""

    # ------------------------------------------------------------------
    # 룰 설명 ("이 룰은 무엇인가")
    # ------------------------------------------------------------------
    @staticmethod
    def _node_attr(node: Any, name: str) -> Any:
        if isinstance(node, dict):
            return node.get(name)
        return getattr(node, name, None)

    def _describe_tree_lines(self, node: Any, depth: int = 0) -> List[str]:
        """조건 트리를 들여쓰기 텍스트로 변환 (표시명, 키, 연산자, 값, AND/OR만)"""
        pad = "  " * depth
        logic = self._node_attr(node, "logicType")
        children = self._node_attr(node, "condition")
        if children is None:
            children = self._node_attr(node, "conditions")
        if logic or children is not None:
            lines = [f"{pad}[{str(logic or 'AND').upper()}]"]
            for child in children or []:
                lines.extend(self._describe_tree_lines(child, depth + 1))
            return lines
        disp = self._node_attr(node, "dispName") or self._node_attr(node, "keyName")
        return [
            f"{pad}- {disp} ({self._node_attr(node, 'keyName')}) "
            f"{self._node_attr(node, 'operator')} {self._node_attr(node, 'value')}"
        ]

    def _create_rule_description_prompt(self, rule: Rule) -> str:
        name = getattr(rule, "ruleName", None) or getattr(rule, "name", "")
        msg = getattr(rule, "ruleMsg", "") or ""
        tree_lines = self._describe_tree_lines(getattr(rule, "conditionTree", None))
        tree_text = "\n".join(tree_lines)
        return f"""
다음 룰이 무엇인지 설명해주세요. 입력은 룰 이름, 룰 메시지, 조건 트리가 전부입니다.

룰 이름: {name}
룰 메시지: {msg}
조건 트리 ([AND]는 모두 만족, [OR]는 하나라도 만족):
{tree_text}

규칙:
- what: 조건이 말하는 그대로 풀어 쓴 1~2문장. AND/OR 구조를 정확히 반영하세요. 표시명과 값은 입력에 있는 그대로 쓰세요.
- purpose: 룰 이름·메시지·조건 표시명으로 추정한 목적 1문장. "~으로 보입니다" 꼴로 쓰세요. 근거가 약하면 null로 두고 지어내지 마세요.
- 이 룰이 유효한지 판단하지 마세요. 모순이나 오류를 지적하거나 고치는 방법을 조언하지 마세요. HTML 태그를 쓰지 마세요.

JSON 형식으로 응답:
{{
    "what": "조건을 풀어 쓴 문장",
    "purpose": "목적 추정 문장 또는 null"
}}
"""

    async def generate_rule_description(self, rule: Rule) -> Optional[RuleDescription]:
        """AI로 룰 설명 생성. 실패하면 None (검증은 계속 진행, 사유는 ai_error에 기록)"""
        try:
            response = await self._call_llm(self._create_rule_description_prompt(rule))
            if response is None:
                return None
            try:
                data = extract_json(response)
                if not isinstance(data, dict):
                    raise ValueError("객체가 아님")
                what = data.get("what")
                if not isinstance(what, str) or not what.strip():
                    raise ValueError("what 없음")
                purpose = data.get("purpose")
                if not isinstance(purpose, str) or purpose.strip().lower() in ("", "null", "none"):
                    purpose = None
                # raw HTML이 섞여 와도 화면에서 태그로 해석되지 않도록 이스케이프
                return RuleDescription(
                    what=html.escape(what.strip(), quote=False),
                    purpose=html.escape(purpose.strip(), quote=False) if purpose else None,
                )
            except ValueError as e:
                self._note_failure("AI 응답 형식 오류(룰 설명)", f"({e})")
        except Exception as e:
            self.logger.error(f"룰 설명 생성 중 오류: {type(e).__name__}", exc_info=True)
        return None

    async def generate_ai_insights(
        self,
        rule: Rule,
        issues: List[ConditionIssue],
        structure: StructureInfo,
        conditions: List[RuleCondition],
    ) -> Optional[Dict[str, Any]]:
        """
        AI 기반 심층 분석 통찰 생성

        Args:
            rule (Rule): 분석할 룰
            issues (List[ConditionIssue]): 검출된 이슈들
            structure (StructureInfo): 구조 정보
            conditions (List[RuleCondition]): 조건들

        Returns:
            Optional[Dict[str, Any]]: AI 통찰 정보
        """
        try:
            rule_summary = {
                "name": getattr(rule, "ruleName", getattr(rule, "name", "Unknown")),
                "condition_count": len(conditions),
                "depth": structure.depth,
                "unique_fields": len(structure.unique_fields),
                "issues_count": len(issues),
                "error_count": len([i for i in issues if i.severity == "error"]),
            }

            prompt = self._create_insights_prompt(rule_summary)

            response = await self._call_llm(prompt)
            if response is not None:
                try:
                    insights = extract_json(response)
                    if not isinstance(insights, dict):
                        raise ValueError("객체가 아님")
                    self.logger.info("AI 통찰 생성 완료")
                    return insights
                except ValueError as e:
                    self._note_failure("AI 응답 형식 오류(종합 통찰)", f"({e})")

        except Exception as e:
            self.logger.error(f"AI 통찰 생성 중 오류: {str(e)}", exc_info=True)

        return None

    def _create_insights_prompt(self, rule_summary: dict) -> str:
        """
        통찰 생성용 프롬프트 생성

        Args:
            rule_summary (dict): 룰 요약 정보

        Returns:
            str: 생성된 프롬프트
        """
        return f"""
다음 룰에 대한 심층 분석과 통찰을 제공해주세요:

룰 정보:
- 이름: {rule_summary['name']}
- 조건 수: {rule_summary['condition_count']}
- 중첩 깊이: {rule_summary['depth']}
- 사용된 필드 수: {rule_summary['unique_fields']}
- 발견된 이슈 수: {rule_summary['issues_count']} (오류: {rule_summary['error_count']})

JSON 형식으로 응답:
{{
    "complexity_analysis": "복잡성 분석",
    "design_patterns": ["발견된 디자인 패턴들"],
    "potential_improvements": ["개선 가능성들"],
    "business_impact": "비즈니스 영향도 분석"
}}
"""

    async def generate_improvement_recommendations(
        self,
        rule: Rule,
        issues: List[ConditionIssue],
        conditions: List[RuleCondition],
    ) -> Optional[List[Dict[str, str]]]:
        """
        AI 기반 개선 제안 생성

        Args:
            rule (Rule): 분석할 룰
            issues (List[ConditionIssue]): 검출된 이슈들
            conditions (List[RuleCondition]): 조건들

        Returns:
            Optional[List[Dict[str, str]]]: 개선 제안 리스트
        """
        try:
            issue_summary = {}
            for issue in issues:
                if issue.issue_type not in issue_summary:
                    issue_summary[issue.issue_type] = 0
                issue_summary[issue.issue_type] += 1

            prompt = self._create_recommendations_prompt(issue_summary)

            response = await self._call_llm(prompt)
            if response is not None:
                try:
                    recommendations = extract_json(response)
                    if isinstance(recommendations, dict):
                        recommendations = recommendations.get("recommendations")
                    if not isinstance(recommendations, list):
                        raise ValueError("배열이 아님")
                    recommendations = [
                        {k: str(v) for k, v in r.items()}
                        for r in recommendations
                        if isinstance(r, dict)
                    ]
                    self.logger.info("AI 개선 제안 생성 완료")
                    return recommendations
                except ValueError as e:
                    self._note_failure("AI 응답 형식 오류(개선 제안)", f"({e})")

        except Exception as e:
            self.logger.error(f"개선 제안 생성 중 오류: {str(e)}", exc_info=True)

        return None

    def _create_recommendations_prompt(self, issue_summary: dict) -> str:
        """
        개선 제안용 프롬프트 생성

        Args:
            issue_summary (dict): 이슈 요약

        Returns:
            str: 생성된 프롬프트
        """
        return f"""
다음 이슈들을 바탕으로 우선순위가 높은 개선 제안을 3개 제공해주세요:

이슈 요약: {issue_summary}

JSON 배열로 응답:
[
    {{
        "priority": "high|medium|low",
        "title": "개선 제안 제목",
        "description": "구체적인 개선 방법",
        "effort": "소요 시간 예상"
    }}
]
"""

    async def generate_risk_assessment(
        self, issues: List[ConditionIssue], structure: StructureInfo
    ) -> Optional[Dict[str, Any]]:
        """
        AI 기반 위험도 평가 생성

        Args:
            issues (List[ConditionIssue]): 검출된 이슈들
            structure (StructureInfo): 구조 정보

        Returns:
            Optional[Dict[str, Any]]: 위험도 평가 정보
        """
        try:
            error_count = len([i for i in issues if i.severity == "error"])
            warning_count = len([i for i in issues if i.severity == "warning"])

            # 규칙 기반 위험도 계산
            risk_score = min(
                100,
                (error_count * 20) + (warning_count * 5) + (structure.depth * 2),
            )

            if risk_score >= 70:
                risk_level = "high"
                risk_message = "즉시 수정이 필요합니다"
            elif risk_score >= 40:
                risk_level = "medium"
                risk_message = "검토 후 수정을 권장합니다"
            else:
                risk_level = "low"
                risk_message = "현재 상태가 양호합니다"

            risk_assessment = {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "risk_message": risk_message,
                "critical_issues": [
                    i.issue_type for i in issues if i.severity == "error"
                ],
                "recommendations": [
                    "중요도가 높은 오류부터 수정하세요",
                    "정기적인 룰 검토를 수행하세요",
                ],
            }

            self.logger.info(
                f"위험도 평가 완료: {risk_level} 수준 (점수: {risk_score})"
            )
            return risk_assessment

        except Exception as e:
            self.logger.error(f"위험도 평가 중 오류: {str(e)}", exc_info=True)

        return None

    def generate_ai_comment(
        self,
        rule: Rule,
        issues: List[ConditionIssue],
        structure: StructureInfo,
        conditions: List[RuleCondition] = None,
    ) -> Optional[str]:
        """
        AI 기반 코멘트 생성 (빠른 분석용)

        Args:
            rule (Rule): 분석할 룰
            issues (List[ConditionIssue]): 검출된 이슈들
            structure (StructureInfo): 구조 정보
            conditions (List[RuleCondition], optional): 조건들

        Returns:
            Optional[str]: 생성된 코멘트
        """
        # 간단한 경우는 코멘트 생략
        if not issues and structure.depth <= 2 and structure.condition_node_count <= 5:
            return None

        comments = []

        # 구조적 복잡성 분석
        if structure.depth >= 4 or structure.condition_node_count >= 8:
            comments.append(
                "조건이 중첩된 구조는 유지보수에 취약할 수 있으므로 간결하게 리팩토링을 고려하세요."
            )

        # 필드별 조건 수 분석
        if conditions:
            field_condition_counts = {}
            logical_operators = {"and": 0, "or": 0}

            def analyze_fields(conditions_list):
                if not conditions_list:
                    return

                for condition in conditions_list:
                    if condition is None:
                        continue

                    # 필드 조건 카운트 (간단한 방식)
                    field = getattr(
                        condition, "keyName", getattr(condition, "field", None)
                    )
                    if field and field != "placeholder":
                        if field not in field_condition_counts:
                            field_condition_counts[field] = 0
                        field_condition_counts[field] += 1

                    # 논리 연산자 카운트
                    if condition.operator and condition.operator.lower() in [
                        "and",
                        "or",
                    ]:
                        logical_operators[condition.operator.lower()] += 1

                    # 중첩 조건 재귀 분석
                    if hasattr(condition, "conditions") and condition.conditions:
                        analyze_fields(condition.conditions)

            analyze_fields(conditions)

            # OR 연산자가 많은 경우
            if (
                logical_operators["or"] > 2
                and logical_operators["or"] > logical_operators["and"] * 2
            ):
                comments.append(
                    "OR 연산자 사용이 많습니다. 일부 조건은 의미적으로 중복되거나 합쳐질 수 있는지 검토해보세요."
                )

            # 특정 필드에 조건이 집중된 경우
            for field, count in field_condition_counts.items():
                if count >= 3:
                    comments.append(
                        f"{field} 필드에 대한 조건이 {count}개로 많습니다. 조건을 범위로 단순화할 수 있는지 검토하세요."
                    )
                    break

        # 최종 코멘트 조합 (1-2개 선택)
        if not comments:
            return None

        selected_comments = comments[: min(2, len(comments))]
        return " ".join(selected_comments)

    async def enhance_issues_individual(
        self,
        issues: List[ConditionIssue],
        conditions: List[RuleCondition],
        rule: Rule,
    ) -> None:
        """
        개별 이슈 AI 개선 (레거시 지원용)

        Args:
            issues (List[ConditionIssue]): 개선할 이슈들
            conditions (List[RuleCondition]): 조건들
            rule (Rule): 룰 객체
        """
        # 배치 처리로 리다이렉트
        await self.enhance_issues_batch(issues, rule)
        self.logger.info("개별 이슈 개선이 배치 처리로 리다이렉트됨")
