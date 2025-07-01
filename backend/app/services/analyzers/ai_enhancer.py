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

        # 기본 및 대체 모델 정보 저장 (분석 전용 우선순위)
        self.default_model = getattr(settings, "analysis_default_model", settings.default_model)
        self.fallback_model = getattr(settings, "analysis_fallback_model", settings.fallback_model)

        # --- 통계 수집용 ---
        self.last_model_used: Optional[str] = None
        self.total_latency_ms: int = 0

    # 관리용 통계 리셋
    def reset_stats(self):
        self.last_model_used = None
        self.total_latency_ms = 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "model_used": self.last_model_used,
            "total_latency_ms": self.total_latency_ms,
        }

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
                t0 = asyncio.get_event_loop().time()
                ai_response = await self.llm_service.generate_text(ai_prompt, model_id)
                latency_ms = int((asyncio.get_event_loop().time() - t0) * 1000)

                # 통계 업데이트 (가장 마지막 호출 기준)
                self.last_model_used = model_id
                self.total_latency_ms += latency_ms

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
            # 🟢 AI 응답 로깅 (디버깅용)
            self.logger.info(f"🤖 AI 원본 응답 (처음 500자): {ai_response[:500]}...")
            
            ai_data = json.loads(ai_response)
            enhanced_issues = ai_data.get("enhanced_issues", [])

            for i, enhanced in enumerate(enhanced_issues):
                if i < len(issue_batch):
                    issue = issue_batch[i]
                    issue.ai_explanation = enhanced.get("enhanced_explanation") or "-"
                    issue.ai_suggestion = enhanced.get("enhanced_suggestion", "-")
                    issue.impact_level = enhanced.get("impact_level", "medium")
                    issue.affected_scenarios = enhanced.get("affected_scenarios", [])

        except json.JSONDecodeError as e:
            # 🟢 JSON 파싱 실패 시 응답 정리 후 재시도
            self.logger.warning(f"AI 응답 JSON 파싱 실패: {str(e)}")
            self.logger.info(f"🔍 실패한 AI 응답 전체: {ai_response}")
            
            # 마크다운 코드블록 제거 시도
            cleaned_response = ai_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            try:
                # 🟢 정리된 응답으로 재시도
                self.logger.info(f"🔧 정리된 응답으로 재시도: {cleaned_response[:200]}...")
                ai_data = json.loads(cleaned_response)
                enhanced_issues = ai_data.get("enhanced_issues", [])

                for i, enhanced in enumerate(enhanced_issues):
                    if i < len(issue_batch):
                        issue = issue_batch[i]
                        issue.ai_explanation = enhanced.get("enhanced_explanation") or "-"
                        issue.ai_suggestion = enhanced.get("enhanced_suggestion", "-")
                        issue.impact_level = enhanced.get("impact_level", "medium")
                        issue.affected_scenarios = enhanced.get("affected_scenarios", [])
                
                self.logger.info("✅ 정리된 응답으로 JSON 파싱 성공")
                return
                
            except json.JSONDecodeError as e2:
                # 🟢 재시도도 실패하면 프롬프트 문제로 판단하고 기본값 적용
                self.logger.error(f"❌ 정리된 응답도 JSON 파싱 실패: {str(e2)}")
                self.logger.error("🚨 프롬프트 개선이 필요합니다!")
                
                # 모든 이슈에 기본 AI 설명 적용
                for i, issue in enumerate(issue_batch):
                    issue.ai_explanation = f"AI 분석: {issue.explanation}"
                    issue.ai_suggestion = f"개선 제안: {issue.suggestion}"
                    issue.impact_level = "medium"
                    issue.affected_scenarios = ["일반적인 사용 시나리오"]
                
        except Exception as e:
            # 🟢 기타 오류 시에도 모든 이슈에 기본값 적용
            self.logger.error(f"AI 응답 적용 중 오류: {str(e)}, 기본값으로 설정", exc_info=True)
            
            for i, issue in enumerate(issue_batch):
                issue.ai_explanation = f"시스템 분석: {issue.explanation}"
                issue.ai_suggestion = f"권장 사항: {issue.suggestion}"
                issue.impact_level = "medium"
                issue.affected_scenarios = ["표준 처리 시나리오"]

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
다음 룰의 여러 이슈들을 분석하여 JSON만 반환하세요.

📌 **중요**: 모든 응답은 반드시 한국어로 작성하세요.

룰명: {batch_context['rule_name']}
{issues_text}

반드시 아래 Strict JSON 포맷을 **그대로** 지키세요. 마크다운, 주석, 여분 텍스트 금지.

{{
  "enhanced_issues": [
    {{
      "enhanced_explanation": "한국어로 상세한 문제 설명...",
      "enhanced_suggestion":  "한국어로 구체적인 개선 방안...",
      "impact_level":        "low|medium|high",
      "affected_scenarios": ["한국어로 영향받는 시나리오들..."]
    }}
  ]
}}

⚠️ enhanced_explanation과 enhanced_suggestion은 반드시 한국어로 작성하세요.
응답이 유효 JSON이 아니면 평가에 사용되지 않습니다. Strict JSON ONLY.
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
아래 요약을 참고하여 심층 통찰을 Strict JSON ONLY 로 반환하세요. 주석·마크다운 금지.

📌 **중요**: 모든 응답은 반드시 한국어로 작성하세요.

룰 요약:
- 이름: {rule_summary['name']}
- 조건 수: {rule_summary['condition_count']}
- 중첩 깊이: {rule_summary['depth']}
- 사용된 필드 수: {rule_summary['unique_fields']}
- 발견된 이슈 수: {rule_summary['issues_count']} (오류: {rule_summary['error_count']})

예시 포맷 (모든 내용은 한국어로):
{{
  "complexity_analysis": "한국어로 복잡도 분석...",
  "design_patterns": ["한국어로 패턴 설명1", "한국어로 패턴 설명2"],
  "potential_improvements": ["한국어로 개선점1", "한국어로 개선점2"],
  "business_impact": "한국어로 비즈니스 영향 분석..."
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
                    data = json.loads(response)
                    # 응답이 단일 객체면 리스트로 래핑
                    if isinstance(data, dict):
                        data = [data]
                    self.logger.info("AI 개선 제안 생성 완료")
                    return data
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
다음 이슈 요약을 참고해 Strict JSON ONLY 배열 형식으로 상위 3개 개선 제안을 반환하세요.

📌 **중요**: 모든 응답은 반드시 한국어로 작성하세요.

이슈 요약: {issue_summary}

예시 (모든 내용은 한국어로):
[
  {{
    "priority": "high|medium|low",
    "title": "한국어로 개선 제안 제목...",
    "description": "한국어로 상세한 개선 방법 설명...",
    "effort": "한국어로 소요 노력 예상..."
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
        """AI 기반 독창적 코멘트 생성

        로직으로는 판단할 수 없는 AI만의 독창적 분석과 통찰을 제공합니다.
        AI 호출 실패 시에는 아예 코멘트를 제공하지 않습니다.
        """
        self.logger.info("🤖 AI 독창적 코멘트 생성 시작")

        model_id = self._select_model()
        if not model_id:
            self.logger.warning("사용 가능한 모델이 없어 AI 코멘트 생략")
            return None

        try:
            rule_name = getattr(rule, "ruleName", getattr(rule, "name", "Unknown"))
            error_count = len([i for i in issues if i.severity == "error"])
            warning_count = len([i for i in issues if i.severity == "warning"])

            # 이슈 유형별 분석
            issue_types = [i.issue_type for i in issues] if issues else []
            issue_details = []
            
            if issues:
                for issue in issues[:3]:  # 상위 3개 이슈만
                    detail = f"{issue.issue_type}"
                    if hasattr(issue, 'location') and issue.location:
                        detail += f" (위치: {issue.location})"
                    issue_details.append(detail)

            # 조건 구조 분석 (AI가 패턴을 발견할 수 있도록)
            condition_patterns = []
            if conditions:
                # 필드 사용 패턴
                fields_used = set()
                operators_used = set()
                for cond in conditions:
                    if hasattr(cond, 'keyName') and cond.keyName:
                        fields_used.add(cond.keyName)
                    if hasattr(cond, 'operator') and cond.operator:
                        operators_used.add(cond.operator)
                
                condition_patterns.append(f"사용 필드: {list(fields_used)[:5]}")
                condition_patterns.append(f"연산자: {list(operators_used)}")

            # --- 길이 제한 설정 ------------------------------
            max_len = getattr(settings, "ai_comment_max_length", 0)
            length_directive = (
                f"{max_len}자 이내 " if max_len and max_len > 0 else ""
            )

            # --- 프롬프트 생성 ------------------------------
            prompt = f"""당신은 비즈니스 룰 전문가입니다. 다음 룰을 분석하고 AI만이 할 수 있는 독창적인 통찰을 한 문장으로 제공하세요.

룰명: {rule_name}
구조: 깊이 {structure.depth}, 조건 노드 {structure.condition_node_count}개
문제점: 오류 {error_count}건, 경고 {warning_count}건
이슈 유형: {', '.join(issue_types[:3]) if issue_types else '없음'}
조건 패턴: {'; '.join(condition_patterns) if condition_patterns else '분석 불가'}

**중요**: 단순한 오류 개수나 구조적 복잡성은 언급하지 마세요. 대신 다음 중 하나의 관점에서 AI만의 독창적 분석을 제공하세요:
- 비즈니스 로직의 일관성이나 모순점
- 사용자 경험 관점에서의 룰 적용 예측
- 데이터 품질이나 성능에 미칠 영향
- 유지보수나 확장성 관점의 숨겨진 위험
- 도메인 지식 기반의 개선 아이디어

한국어 {length_directive}한 문장으로만 답변하세요."""

            self.logger.info(f"🚀 AI 독창적 코멘트 LLM 호출 시작 (모델: {model_id})")
            ai_comment = await self.llm_service.generate_text(prompt, model_id)
            
            if ai_comment:
                clean_comment = ai_comment.strip()
                # ⚠️ 강제 절단 제거: AI가 길게 응답해도 그대로 반환
                # 필요 시 공백·개행 정리만 수행합니다.
                # if max_len and max_len > 0:
                #     # 설정값이 명시된 경우에만 길이를 제한합니다.
                #     clean_comment = clean_comment[:max_len]

                if clean_comment:
                    self.logger.info(f"✅ AI 독창적 코멘트 생성 성공: {clean_comment}")
                    return clean_comment
                else:
                    self.logger.warning("AI 코멘트가 정리 후 비어있음")
            else:
                self.logger.warning("AI 코멘트가 비어있음")

        except Exception as e:
            self.logger.error(f"AI 독창적 코멘트 생성 실패: {str(e)}", exc_info=True)

        self.logger.info("AI 코멘트 생성 실패로 코멘트 없음")
        return None

    # ------------------------------------------------------------------
    # 내부 휴리스틱 메트릭 생성
    # ------------------------------------------------------------------

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
