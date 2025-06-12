"""
AI 개선기 (AIEnhancer)

AI를 활용한 이슈 개선, 통찰 생성, 추천 등을 담당합니다.
- 이슈 배치 처리 및 AI 개선
- AI 기반 통찰 생성
- 개선 제안 생성
- 위험도 평가
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from ...models.rule import Rule, RuleCondition
from ...models.validation_result import ConditionIssue, StructureInfo
from ...services.llm_service import LLMService
from ...config import settings, SUPPORTED_MODELS
from ...utils.logger import get_logger


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

        # 기본 및 대체 모델 정보 저장
        self.default_model = settings.default_model
        self.fallback_model = settings.fallback_model

    def _select_model(self) -> Optional[str]:
        """사용 가능한 LLM 모델을 선택

        우선순위:
        1. 환경설정의 default_model
        2. 환경설정의 fallback_model
        3. SUPPORTED_MODELS 목록 중 사용 가능한 첫 번째 모델

        Returns:
            Optional[str]: 선택된 모델 ID (없으면 None)
        """

        # 1) 기본 모델 시도
        if self.llm_service.is_model_available(self.default_model):
            return self.default_model

        # 2) 대체 모델 시도
        if self.fallback_model and self.llm_service.is_model_available(self.fallback_model):
            return self.fallback_model

        # 3) 나머지 지원 모델 순회
        for model_id in SUPPORTED_MODELS.keys():
            if self.llm_service.is_model_available(model_id):
                return model_id

        # 4) 사용 가능한 모델 없음
        return None

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

            # AI 호출 (동적 모델 선택)
            model_id = self._select_model()

            if model_id:
                ai_response = await self.llm_service.generate_text(ai_prompt, model_id)

                # 응답 파싱 및 각 이슈에 적용
                await self._apply_batch_enhancement(issue_batch, ai_response)
            else:
                self.logger.warning("사용 가능한 LLM 모델이 없어 AI 개선을 건너뜁니다.")

        except Exception as e:
            self.logger.error(f"배치 처리 중 오류: {str(e)}", exc_info=True)

    async def _apply_batch_enhancement(
        self, issue_batch: List[ConditionIssue], ai_response: str
    ) -> None:
        """
        AI 응답을 파싱하여 이슈 배치에 적용

        Args:
            issue_batch (List[ConditionIssue]): 개선할 이슈 배치
            ai_response (str): AI 응답 텍스트
        """
        try:
            ai_data = json.loads(ai_response)
            enhanced_issues = ai_data.get("enhanced_issues", [])

            for i, enhanced in enumerate(enhanced_issues):
                if i < len(issue_batch):
                    issue = issue_batch[i]
                    issue.ai_explanation = enhanced.get("enhanced_explanation")
                    issue.ai_suggestion = enhanced.get("enhanced_suggestion")
                    issue.impact_level = enhanced.get("impact_level", "medium")
                    issue.affected_scenarios = enhanced.get("affected_scenarios", [])

        except json.JSONDecodeError:
            # JSON 파싱 실패 시 첫 번째 이슈에만 적용
            if issue_batch:
                truncated_response = (
                    ai_response[:200] + "..." if len(ai_response) > 200 else ai_response
                )
                issue_batch[0].ai_explanation = truncated_response
                self.logger.warning("AI 응답 JSON 파싱 실패, 첫 번째 이슈에만 적용")
        except Exception as e:
            self.logger.error(f"AI 응답 적용 중 오류: {str(e)}", exc_info=True)

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

            model_id = self._select_model()
            if model_id:
                response = await self.llm_service.generate_text(prompt, model_id)

                try:
                    insights = json.loads(response)
                    self.logger.info("AI 통찰 생성 완료")
                    return insights
                except json.JSONDecodeError:
                    self.logger.warning("AI 통찰 JSON 파싱 실패")
                    return {"analysis": response}

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

            model_id = self._select_model()
            if model_id:
                response = await self.llm_service.generate_text(prompt, model_id)

                try:
                    recommendations = json.loads(response)
                    self.logger.info("AI 개선 제안 생성 완료")
                    return recommendations
                except json.JSONDecodeError:
                    self.logger.warning("AI 개선 제안 JSON 파싱 실패")
                    return [{"title": "일반적인 개선", "description": response}]

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

    async def generate_ai_comment(
        self,
        rule: Rule,
        issues: List[ConditionIssue],
        structure: StructureInfo,
        conditions: Optional[List[RuleCondition]] = None,
    ) -> Optional[str]:
        """AI 기반 종합 코멘트 생성

        우선 LLM을 호출해 한 문장 요약 코멘트를 얻고, 모델을 사용할 수 없거나
        호출 실패 시 기존 규칙 기반(휴리스틱) 코멘트를 반환합니다.
        """

        # 규칙 기반 코멘트(백업용) 먼저 계산
        fallback_comment = self._generate_rule_based_comment(
            rule, issues, structure, conditions
        )

        model_id = self._select_model()
        if not model_id:
            return fallback_comment

        try:
            rule_name = getattr(rule, "ruleName", getattr(rule, "name", "Unknown"))
            error_count = len([i for i in issues if i.severity == "error"])
            warning_count = len([i for i in issues if i.severity == "warning"])

            summary_payload = {
                "rule_name": rule_name,
                "depth": structure.depth,
                "condition_nodes": structure.condition_node_count,
                "errors": error_count,
                "warnings": warning_count,
            }

            prompt = (
                "다음 룰 요약 정보를 참고하여 한 문장(120자 이내)으로 종합 코멘트를 한국어로 작성하세요. "
                "가장 시급한 개선 방향을 제시하고, 지나치게 장황하지 않게 해주세요.\n"
                f"룰 요약 JSON:\n{json.dumps(summary_payload, ensure_ascii=False, indent=2)}"
            )

            ai_comment = await self.llm_service.generate_text(prompt, model_id)
            if ai_comment:
                return ai_comment.strip()

        except Exception as e:
            self.logger.error(f"ai_comment LLM 생성 실패: {str(e)}", exc_info=True)

        return fallback_comment

    # ------------------------------------------------------------------
    # 내부 휴리스틱 코멘트 생성 (기존 로직 유지)
    # ------------------------------------------------------------------

    def _generate_rule_based_comment(
        self,
        rule: Rule,
        issues: List[ConditionIssue],
        structure: StructureInfo,
        conditions: Optional[List[RuleCondition]] = None,
    ) -> Optional[str]:
        """LLM 호출 실패 시 사용할 규칙 기반 코멘트"""

        if not issues and structure.depth <= 2 and structure.condition_node_count <= 5:
            return None

        comments: list[str] = []

        # 구조 복잡성 평가
        if structure.depth >= 4 or structure.condition_node_count >= 8:
            comments.append(
                "조건이 중첩된 구조는 유지보수에 취약할 수 있으므로 간결하게 리팩토링을 고려하세요."
            )

        # 필드/논리 분석
        if conditions:
            field_condition_counts: dict[str, int] = {}
            logical_operators = {"and": 0, "or": 0}

            def analyze_fields(cond_list):
                for cond in cond_list or []:
                    if cond is None:
                        continue
                    field = getattr(cond, "keyName", getattr(cond, "field", None))
                    if field and field != "placeholder":
                        field_condition_counts[field] = field_condition_counts.get(field, 0) + 1

                    if cond.operator and cond.operator.lower() in ("and", "or"):
                        logical_operators[cond.operator.lower()] += 1

                    if hasattr(cond, "conditions") and cond.conditions:
                        analyze_fields(cond.conditions)

            analyze_fields(conditions)

            if logical_operators["or"] > 2 and logical_operators["or"] > logical_operators["and"] * 2:
                comments.append(
                    "OR 연산자 사용이 많습니다. 일부 조건은 의미적으로 중복되거나 합쳐질 수 있는지 검토해보세요."
                )

            for field, cnt in field_condition_counts.items():
                if cnt >= 3:
                    comments.append(
                        f"{field} 필드에 대한 조건이 {cnt}개로 많습니다. 조건을 범위로 단순화할 수 있는지 검토하세요."
                    )
                    break

        if not comments:
            return None

        return " ".join(comments[:2])

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
