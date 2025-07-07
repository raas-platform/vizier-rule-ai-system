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
            rule_name = getattr(rule, "ruleName", getattr(rule, "name", "Unknown"))
            
            # 이슈들을 배치로 그룹화
            batches = [
                issues[i : i + batch_size] for i in range(0, len(issues), batch_size)
            ]

            self.logger.info(f"🔄 AI 배치 처리 시작 - 룰: {rule_name}")
            self.logger.info(f"  - 총 이슈 수: {len(issues)}개")
            self.logger.info(f"  - 배치 크기: {batch_size}")
            self.logger.info(f"  - 총 배치 수: {len(batches)}개")
            self.logger.info(f"  - 예상 동시 API 호출: {len(batches)}개")

            # 각 배치를 병렬로 처리
            tasks = []
            for i, batch in enumerate(batches):
                self.logger.info(f"  - 배치 {i+1}: {len(batch)}개 이슈")
                task = self._process_issue_batch_with_logging(batch, rule, i+1)
                tasks.append(task)

            # 모든 배치를 병렬 실행
            if tasks:
                self.logger.info(f"🚀 {len(tasks)}개 배치 병렬 실행 시작")
                start_time = asyncio.get_event_loop().time()
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                end_time = asyncio.get_event_loop().time()
                total_time_ms = int((end_time - start_time) * 1000)
                
                # 결과 분석
                success_count = 0
                error_count = 0
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        error_count += 1
                        self.logger.error(f"❌ 배치 {i+1} 실패: {result}")
                    else:
                        success_count += 1
                        self.logger.info(f"✅ 배치 {i+1} 성공")
                
                self.logger.info(f"🏁 AI 배치 처리 완료:")
                self.logger.info(f"  - 총 소요시간: {total_time_ms}ms")
                self.logger.info(f"  - 성공한 배치: {success_count}/{len(batches)}")
                self.logger.info(f"  - 실패한 배치: {error_count}/{len(batches)}")

            self.logger.info(
                f"AI 배치 이슈 개선 완료: {len(issues)}개 이슈, {len(batches)}개 배치"
            )

        except Exception as e:
            self.logger.error(f"AI 배치 이슈 개선 중 오류: {str(e)}", exc_info=True)

    async def _process_issue_batch_with_logging(
        self, issue_batch: List[ConditionIssue], rule: Rule, batch_number: int
    ) -> None:
        """
        로깅이 강화된 이슈 배치 처리

        Args:
            issue_batch (List[ConditionIssue]): 처리할 이슈 배치
            rule (Rule): 룰 객체
            batch_number (int): 배치 번호
        """
        batch_start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info(f"🔄 배치 {batch_number} 처리 시작 - {len(issue_batch)}개 이슈")
            
            await self._process_issue_batch(issue_batch, rule)
            
            batch_end_time = asyncio.get_event_loop().time()
            batch_time_ms = int((batch_end_time - batch_start_time) * 1000)
            
            self.logger.info(f"✅ 배치 {batch_number} 처리 완료 - 소요시간: {batch_time_ms}ms")
            
        except Exception as e:
            batch_end_time = asyncio.get_event_loop().time()
            batch_time_ms = int((batch_end_time - batch_start_time) * 1000)
            
            self.logger.error(f"❌ 배치 {batch_number} 처리 실패 - 소요시간: {batch_time_ms}ms")
            self.logger.error(f"  - 오류: {str(e)}", exc_info=True)
            raise

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

            # AI 모델 선택
            model_id = self._select_model()
            
            if not model_id:
                self.logger.warning("사용 가능한 LLM 모델이 없어 AI 개선을 건너뜁니다.")
                # 모델이 없는 경우 기본값 설정
                self._set_default_enhancement_values(issue_batch)
                return
            
            self.logger.info(f"🤖 배치 AI 호출 준비:")
            self.logger.info(f"  - 룰명: {rule_name}")
            self.logger.info(f"  - 이슈 수: {len(issue_batch)}")
            self.logger.info(f"  - 선택된 모델: {model_id}")

            # 프롬프트 생성 및 로깅
            prompt = self._create_batch_enhancement_prompt(batch_context)
            self.logger.info(f"  - 프롬프트 길이: {len(prompt)}자")
            self.logger.info(f"  - 프롬프트 미리보기 (첫 200자): {prompt[:200]}...")

            # AI 응답 생성
            ai_call_start_time = asyncio.get_event_loop().time()
            
            ai_response = await self.llm_service.generate_text(prompt, model_id)
            
            ai_call_end_time = asyncio.get_event_loop().time()
            ai_call_time_ms = int((ai_call_end_time - ai_call_start_time) * 1000)

            # AI 응답 상세 로깅
            self.logger.info(f"🔍 AI 응답 분석:")
            self.logger.info(f"  - AI 호출 소요시간: {ai_call_time_ms}ms")
            self.logger.info(f"  - 응답 타입: {type(ai_response)}")
            self.logger.info(f"  - 응답 길이: {len(ai_response) if ai_response else 0}자")
            self.logger.info(f"  - 응답이 빈 문자열: {ai_response == ''}")
            self.logger.info(f"  - 응답이 None: {ai_response is None}")
            
            if ai_response:
                self.logger.info(f"  - 응답 미리보기 (첫 300자): {ai_response[:300]}...")
                # JSON 형태인지 확인
                if ai_response.strip().startswith('{') and ai_response.strip().endswith('}'):
                    self.logger.info(f"  - JSON 형태로 보임: ✅")
                else:
                    self.logger.warning(f"  - JSON 형태가 아님: ❌")
                    self.logger.warning(f"  - 응답 시작: {repr(ai_response[:50])}")
                    self.logger.warning(f"  - 응답 끝: {repr(ai_response[-50:])}")
            else:
                self.logger.error(f"  - ❌ 빈 AI 응답 감지!")
                self.logger.error(f"  - 응답 repr: {repr(ai_response)}")

            # 🟢 통계 수집 (가장 마지막 호출 기준)
            self.last_model_used = model_id
            self.total_latency_ms += ai_call_time_ms
            
            self.logger.info(f"📊 AI Enhancer 통계 업데이트:")
            self.logger.info(f"  - 사용된 모델: {self.last_model_used}")
            self.logger.info(f"  - 누적 소요시간: {self.total_latency_ms}ms")

            # 배치에 AI 개선 적용
            await self._apply_batch_enhancement(issue_batch, ai_response)

        except Exception as e:
            self.logger.error(f"💥 이슈 배치 처리 중 오류: {str(e)}", exc_info=True)
            raise

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
            
            # 빈 응답 체크
            if not ai_response or ai_response.strip() == "":
                self.logger.warning("AI 응답이 비어있음. 기본값으로 설정합니다.")
                self._set_default_enhancement_values(issue_batch)
                return
            
            ai_data = json.loads(ai_response)
            enhanced_issues = ai_data.get("enhanced_issues", [])

            # enhanced_issues가 비어있는 경우 처리
            if not enhanced_issues:
                self.logger.warning("AI 응답에 enhanced_issues가 없음. 기본값으로 설정합니다.")
                self._set_default_enhancement_values(issue_batch)
                return

            for i, enhanced in enumerate(enhanced_issues):
                if i < len(issue_batch):
                    issue = issue_batch[i]
                    issue.ai_explanation = enhanced.get("enhanced_explanation") or "AI 분석 중 오류가 발생했습니다."
                    issue.ai_suggestion = enhanced.get("enhanced_suggestion") or "수동 검토를 권장합니다."
                    issue.impact_level = enhanced.get("impact_level", "medium")
                    issue.affected_scenarios = enhanced.get("affected_scenarios", ["일반적인 시나리오"])

            # 처리되지 않은 이슈들에 대해 기본값 설정
            for i in range(len(enhanced_issues), len(issue_batch)):
                issue = issue_batch[i]
                issue.ai_explanation = "AI 분석 중 오류가 발생했습니다."
                issue.ai_suggestion = "수동 검토를 권장합니다."
                issue.impact_level = "medium"
                issue.affected_scenarios = ["일반적인 시나리오"]

        except json.JSONDecodeError as e:
            # 🟢 JSON 파싱 실패 시 응답 정리 후 재시도
            self.logger.warning(f"AI 응답 JSON 파싱 실패: {str(e)}")
            self.logger.info(f"🔍 실패한 AI 응답 전체: {ai_response}")
            
            # 기본값으로 설정
            self._set_default_enhancement_values(issue_batch)
            
        except Exception as e:
            self.logger.error(f"AI 개선 적용 중 오류: {str(e)}", exc_info=True)
            # 기본값으로 설정
            self._set_default_enhancement_values(issue_batch)

    def _set_default_enhancement_values(self, issue_batch: List[ConditionIssue]) -> None:
        """
        이슈 배치에 기본 AI 개선 값을 설정
        
        Args:
            issue_batch (List[ConditionIssue]): 기본값을 설정할 이슈 배치
        """
        for issue in issue_batch:
            issue.ai_explanation = issue.ai_explanation or "(D) AI 분석을 완료하지 못했습니다. 수동 검토가 필요합니다."
            issue.ai_suggestion = issue.ai_suggestion or "(D) 전문가 검토를 통해 적절한 해결 방안을 찾아보시기 바랍니다."
            issue.impact_level = issue.impact_level or "medium"
            issue.affected_scenarios = issue.affected_scenarios or ["(D) 표준 운영 환경"]

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
                ai_call_start_time = asyncio.get_event_loop().time()
                response = await self.llm_service.generate_text(prompt, model_id)
                ai_call_end_time = asyncio.get_event_loop().time()
                ai_call_time_ms = int((ai_call_end_time - ai_call_start_time) * 1000)

                # 🟢 통계 수집
                self.last_model_used = model_id
                self.total_latency_ms += ai_call_time_ms
                
                self.logger.info(f"📊 AI Insights 통계 업데이트: 모델={model_id}, 소요시간={ai_call_time_ms}ms")

                # 빈 응답 체크
                if not response or response.strip() == "":
                    self.logger.warning("AI 통찰 응답이 비어있음. 기본값을 반환합니다.")
                    return self._get_default_insights(rule_summary)

                try:
                    insights = json.loads(response)
                    
                    # 🟢 AI 응답 디버깅 로그 추가
                    self.logger.info(f"🔍 AI Insights 원본 응답 (92자 또는 280자인 경우): {response}")
                    self.logger.info(f"🔍 파싱된 insights 키들: {list(insights.keys()) if insights else 'None'}")
                    
                    # 필수 필드 검증 및 기본값 설정
                    insights = self._validate_and_fix_insights(insights, rule_summary)
                    
                    self.logger.info("AI 통찰 생성 완료")
                    return insights
                except json.JSONDecodeError as e:
                    self.logger.warning(f"AI 통찰 JSON 파싱 실패: {str(e)}")
                    self.logger.info(f"🔍 실패한 AI 통찰 응답: {response}")
                    
                    # 기본값 반환
                    return self._get_default_insights(rule_summary, fallback_text=response)
            else:
                self.logger.warning("사용 가능한 LLM 모델이 없어 기본 통찰을 반환합니다.")
                return self._get_default_insights(rule_summary)

        except Exception as e:
            self.logger.error(f"AI 통찰 생성 중 오류: {str(e)}", exc_info=True)
            return self._get_default_insights(rule_summary)

    def _get_default_insights(self, rule_summary: dict, fallback_text: Optional[str] = None) -> Dict[str, Any]:
        """
        기본 AI 통찰 값을 생성
        
        Args:
            rule_summary (dict): 룰 요약 정보
            fallback_text (Optional[str]): 파싱 실패한 경우의 원본 텍스트
            
        Returns:
            Dict[str, Any]: 기본 통찰 정보
        """
        error_count = rule_summary.get("error_count", 0)
        issues_count = rule_summary.get("issues_count", 0)
        condition_count = rule_summary.get("condition_count", 0)
        
        # 복잡도 분석
        if condition_count > 20:
            complexity = "(D) 높은 복잡도의 룰입니다. 조건 수가 많아 유지보수가 어려울 수 있습니다."
        elif condition_count > 10:
            complexity = "(D) 중간 복잡도의 룰입니다. 적절한 구조화가 필요합니다."
        else:
            complexity = "(D) 낮은 복잡도의 룰입니다. 비교적 관리하기 쉬운 구조입니다."
            
        # 디자인 패턴 추론
        design_patterns = []
        if condition_count > 15:
            design_patterns.append("(D) 복합 조건 패턴: 다수의 조건을 조합하여 복잡한 비즈니스 로직을 구현")
        if error_count > 0:
            design_patterns.append("(D) 오류 검증 패턴: 입력 데이터의 유효성을 검사하는 구조")
        if condition_count > 5:
            design_patterns.append("(D) 계층적 조건 패턴: 조건들이 계층적으로 구성된 구조")
        
        if not design_patterns:
            design_patterns.append("(D) 단순 조건 패턴: 기본적인 조건 검사 구조")
            
        # 개선 제안
        potential_improvements = []
        if error_count > 0:
            potential_improvements.append("(D) 발견된 오류들을 우선적으로 수정하여 룰의 안정성을 향상시키세요")
        if condition_count > 20:
            potential_improvements.append("(D) 조건 수가 많으므로 논리적 그룹으로 분할하는 것을 고려하세요")
        if issues_count > condition_count * 0.3:
            potential_improvements.append("(D) 이슈 비율이 높으므로 전체적인 구조 검토가 필요합니다")
            
        if not potential_improvements:
            potential_improvements.append("(D) 현재 구조가 양호하므로 정기적인 검토를 통해 품질을 유지하세요")
            
        # 비즈니스 영향 분석
        if error_count > 0:
            business_impact = "(D) 오류가 있어 비즈니스 로직의 정확성에 영향을 줄 수 있습니다."
        elif issues_count > 0:
            business_impact = "(D) 경고 수준의 이슈들이 있어 운영 효율성에 영향을 줄 수 있습니다."
        else:
            business_impact = "(D) 현재 상태가 양호하여 비즈니스 운영에 안정적입니다."
            
        default_insights = {
            "complexity_analysis": complexity,
            "design_patterns": design_patterns,
            "potential_improvements": potential_improvements,
            "business_impact": business_impact
        }
        
        # 파싱 실패한 텍스트가 있으면 추가 정보로 포함
        if fallback_text:
            default_insights["raw_analysis"] = fallback_text[:500] + "..." if len(fallback_text) > 500 else fallback_text
            
        return default_insights

    def _validate_and_fix_insights(self, insights: Dict[str, Any], rule_summary: dict) -> Dict[str, Any]:
        """
        AI 통찰 데이터를 검증하고 누락된 필드에 기본값을 설정
        
        Args:
            insights (Dict[str, Any]): 원본 통찰 데이터
            rule_summary (dict): 룰 요약 정보
            
        Returns:
            Dict[str, Any]: 검증 및 보완된 통찰 데이터
        """
        # 필수 필드 목록 - 배열 필드는 AI가 의도적으로 비울 수 있으므로 빈 배열 유지
        required_fields = {
            "complexity_analysis": "(D) 분석 중 오류가 발생했습니다.",
            "design_patterns": [],  # AI가 누락하면 빈 배열 유지
            "potential_improvements": [],  # AI가 누락하면 빈 배열 유지
            "business_impact": "(D) 영향 분석을 완료하지 못했습니다."
        }
        
        # 누락된 필드에만 기본값 설정 (배열 필드는 빈 배열로 유지)
        for field, default_value in required_fields.items():
            if field not in insights or insights[field] is None:
                insights[field] = default_value
            # 빈 배열은 AI가 의도적으로 비운 것으로 간주하여 기본값 추가하지 않음
                    
        return insights

    def _create_insights_prompt(self, rule_summary: dict) -> str:
        """
        통찰 생성용 프롬프트 생성

        Args:
            rule_summary (dict): 룰 요약 정보

        Returns:
            str: 생성된 프롬프트
        """
        return f"""
아래 요약을 참고하여 심층 통찰을 생성하세요. 반드시 아래 JSON 형식만 반환하세요.

📌 **중요**: 
1. 모든 응답은 반드시 한국어로 작성하세요.
2. 마크다운, 주석, 추가 텍스트 없이 오직 JSON만 반환하세요.
3. 아래 4개 필드를 모두 포함해야 합니다.

룰 요약:
- 이름: {rule_summary['name']}
- 조건 수: {rule_summary['condition_count']}
- 중첩 깊이: {rule_summary['depth']}
- 사용된 필드 수: {rule_summary['unique_fields']}
- 발견된 이슈 수: {rule_summary['issues_count']} (오류: {rule_summary['error_count']})

반드시 이 정확한 형식으로 반환하세요:

{{
  "complexity_analysis": "복잡도 분석 텍스트를 한국어로...",
  "design_patterns": ["패턴1", "패턴2"],
  "potential_improvements": ["개선점1", "개선점2"],
  "business_impact": "비즈니스 영향 분석을 한국어로..."
}}

주의: design_patterns와 potential_improvements는 배열이며, 해당 사항이 없으면 빈 배열 []을 반환하세요.
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
                ai_call_start_time = asyncio.get_event_loop().time()
                response = await self.llm_service.generate_text(prompt, model_id)
                ai_call_end_time = asyncio.get_event_loop().time()
                ai_call_time_ms = int((ai_call_end_time - ai_call_start_time) * 1000)

                # 🟢 통계 수집
                self.last_model_used = model_id
                self.total_latency_ms += ai_call_time_ms
                
                self.logger.info(f"📊 AI Recommendations 통계 업데이트: 모델={model_id}, 소요시간={ai_call_time_ms}ms")

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
            ai_call_start_time = asyncio.get_event_loop().time()
            ai_comment = await self.llm_service.generate_text(prompt, model_id)
            ai_call_end_time = asyncio.get_event_loop().time()
            ai_call_time_ms = int((ai_call_end_time - ai_call_start_time) * 1000)

            # 🟢 통계 수집
            self.last_model_used = model_id
            self.total_latency_ms += ai_call_time_ms
            
            self.logger.info(f"📊 AI Comment 통계 업데이트: 모델={model_id}, 소요시간={ai_call_time_ms}ms")
            
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
