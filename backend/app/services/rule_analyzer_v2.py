"""
룰 분석기 v2 (RuleAnalyzer)

리팩토링된 룰 분석기로 기능별로 분리된 클래스들을 조합하여 사용합니다.

구성 요소:
- ConditionAnalyzer: 조건 분석 및 파싱
- IssueDetector: 이슈 검출 및 검증
- AIEnhancer: AI 기반 개선 및 통찰
- MetricsGenerator: 성능 및 품질 메트릭 생성
- ReportGenerator: 보고서 및 요약 생성

이 버전은 기존 RuleAnalyzer와 호환되는 인터페이스를 제공하면서
내부 구조를 모듈화하여 유지보수성과 확장성을 향상시켰습니다.
"""

import asyncio
import time
from typing import Any, Dict, Optional
from datetime import datetime

from ..models.rule import Rule
from ..models.validation_result import (
    ConditionIssue,
    ReportMetadata,
    StructureInfo,
    ValidationResult,
)
from ..config import settings
from ..utils.logger import get_logger
from .analyzers import (
    AIEnhancer,
    ConditionAnalyzer,
    IssueDetector,
    MetricsGenerator,
    ReportGenerator,
)


class ValidationTimeoutError(Exception):
    """규칙 판정 자체가 검증 시간 상한을 넘김 (API는 504로 응답)."""


class RuleAnalyzerV2:
    """
    리팩토링된 룰 분석 서비스 v2

    이 클래스는 룰 분석 기능을 여러 전문화된 컴포넌트로 분리하여
    각각의 책임을 명확히 하고 유지보수성을 향상시켰습니다.

    주요 특징:
    - 단일 책임 원칙 준수
    - 모듈화된 구조
    - 확장 가능한 아키텍처
    - 기존 API와 완전 호환
    """

    def __init__(self):
        """RuleAnalyzerV2 초기화"""
        self.logger = get_logger(__name__)

        # 각 분석 컴포넌트 초기화
        self.condition_analyzer = ConditionAnalyzer()
        self.issue_detector = IssueDetector(self.condition_analyzer)
        self.ai_enhancer = AIEnhancer()
        self.metrics_generator = MetricsGenerator(self.condition_analyzer)
        self.report_generator = ReportGenerator(self.condition_analyzer)

        # 검증 시간 상한 (VALIDATION_TIMEOUT_SECONDS, 기본 50초)
        self.time_limit_seconds = float(settings.validation_timeout_seconds)
        # AI 단계가 시간 상한에 걸려 생략됐는지 (생략돼도 규칙 판정 결과는 반환)
        self.ai_timed_out = False

        self.logger.info("RuleAnalyzerV2 초기화 완료 - 모듈화된 구조")

    async def _ai_step(self, coro, deadline: float, default=None):
        """AI 호출 한 단계를 남은 시간 안에서만 실행. 넘기면 AI만 포기하고 default 반환."""
        remaining = deadline - time.time()
        if self.ai_timed_out or remaining <= 0:
            coro.close()
            self.ai_timed_out = True
            return default
        try:
            return await asyncio.wait_for(coro, timeout=remaining)
        except asyncio.TimeoutError:
            self.ai_timed_out = True
            self.logger.warning(
                f"AI 단계가 검증 시간 상한({self.time_limit_seconds:g}초)을 넘겨 생략합니다."
            )
            return default

    async def analyze_rule(self, rule: Rule) -> ValidationResult:
        """
        룰을 분석하고 검증 결과를 반환

        Args:
            rule (Rule): 분석할 룰 객체

        Returns:
            ValidationResult: 종합적인 검증 결과
        """
        analysis_start_time = time.time()
        deadline = analysis_start_time + self.time_limit_seconds
        self.ai_timed_out = False

        try:
            # 룰 기본 정보 추출
            rule_name = self._extract_rule_name(rule)
            _ = self._extract_rule_id(rule)

            self.logger.info(f"룰 분석 시작 (v2): {rule_name}")

            # 파싱 과정에서 값이 변환되므로(예: Boolean 'maybe' -> False)
            # 원본 트리(AND/OR 구조와 원래 값)를 따로 보존해 둔다.
            raw_rule = rule.model_copy(deep=True)

            stage_times: Dict[str, float] = {}
            stage_start = time.time()

            # 1단계: 조건 파싱 및 분석
            conditions = self.condition_analyzer.parse_rule_conditions(rule)
            _ = self.condition_analyzer.infer_field_types(rule, conditions)
            structure_metrics = self.condition_analyzer.calculate_structure_metrics(
                conditions, rule
            )

            stage_times["파싱"] = time.time() - stage_start
            stage_start = time.time()

            # 2단계: 이슈 검출
            issues = await self.issue_detector.detect_all_issues(
                rule,
                conditions,
                structure_metrics["complexity_score"],
                raw_rule=raw_rule,
            )

            # 3단계: 이슈 최적화
            optimized_issues = self.report_generator.optimize_issues(issues)

            stage_times["규칙 판정"] = time.time() - stage_start

            # 규칙 판정 자체가 시간 상한을 넘기면 504
            if time.time() >= deadline:
                raise ValidationTimeoutError()

            # 구조 정보 생성
            structure_info = StructureInfo(
                depth=structure_metrics["depth"],
                condition_count=structure_metrics["condition_count"],
                condition_node_count=structure_metrics["condition_node_count"],
                field_condition_count=structure_metrics["field_condition_count"],
                unique_fields=structure_metrics["unique_fields"],
            )

            # 4단계: AI 기반 개선 - 이슈 설명, 종합 통찰, 개선 제안을 동시에 실행
            # (통찰·제안은 규칙 판정 결과만 입력으로 쓰므로 서로 기다릴 필요가 없다)
            ai_start = time.time()
            ai_times: Dict[str, float] = {}

            async def timed(name, coro):
                t0 = time.time()
                try:
                    return await coro
                finally:
                    ai_times[name] = time.time() - t0

            # AI 단계는 남은 시간(검증 시간 상한) 안에서만 실행한다.
            # 넘긴 단계만 포기하고, 규칙 판정 결과와 끝난 AI 결과는 그대로 반환한다.
            issues_before_ai = [i.model_copy(deep=True) for i in optimized_issues]
            issue_step_timed_out = object()

            (
                issue_step,
                ai_insights,
                improvement_recommendations,
                rule_description,
            ) = await asyncio.gather(
                self._ai_step(
                    timed("이슈 설명", self.ai_enhancer.enhance_issues_batch(optimized_issues, rule)),
                    deadline,
                    default=issue_step_timed_out,
                ),
                self._ai_step(
                    timed(
                        "종합 통찰",
                        self.ai_enhancer.generate_ai_insights(
                            rule, optimized_issues, structure_info, conditions
                        ),
                    ),
                    deadline,
                ),
                self._ai_step(
                    timed(
                        "개선 제안",
                        self.ai_enhancer.generate_improvement_recommendations(
                            rule, optimized_issues, conditions
                        ),
                    ),
                    deadline,
                ),
                # 룰 이름·메시지·조건 트리만 입력 (이슈와 무관)이라 다른 호출과 동시에 실행
                self._ai_step(
                    timed("룰 설명", self.ai_enhancer.generate_rule_description(raw_rule)),
                    deadline,
                ),
            )
            if issue_step is issue_step_timed_out:
                # 이슈 설명이 도중에 끊겼으면 일부만 바뀐 이슈 대신 AI 이전 이슈를 쓴다
                optimized_issues = issues_before_ai
            stage_times["AI"] = time.time() - ai_start

            # 5단계: 메트릭 생성 (AI 단계까지 포함한 전체 소요시간 기준)
            analysis_end_time = time.time()

            # 필드 분석
            field_analysis = await self.metrics_generator.generate_field_analysis(
                conditions, optimized_issues
            )

            # 논리 흐름 분석
            logic_flow = self.metrics_generator.generate_logic_flow_analysis(conditions)

            # 성능 메트릭
            performance_metrics = self.metrics_generator.generate_performance_metrics(
                conditions, structure_metrics["complexity_score"]
            )

            # 품질 메트릭
            quality_metrics = self.metrics_generator.generate_quality_metrics(
                optimized_issues, structure_info, conditions
            )

            # 보고서 메타데이터
            report_metadata = self.metrics_generator.generate_report_metadata(
                rule, analysis_start_time, analysis_end_time
            )

            # 6단계: 보고서 생성
            rule_summary = self.report_generator.generate_rule_summary(rule, conditions)
            issues_summary = self.report_generator.generate_issues_summary(
                optimized_issues, rule_name
            )
            issue_counts = self.report_generator.calculate_issue_counts(
                optimized_issues
            )

            # AI 기반 콘텐츠 생성
            ai_comment = self.ai_enhancer.generate_ai_comment(
                rule, optimized_issues, structure_info, conditions
            )
            risk_assessment = await self.ai_enhancer.generate_risk_assessment(
                optimized_issues, structure_info
            )

            # 7단계: 최종 결과 조합
            is_valid = len([i for i in optimized_issues if i.severity == "error"]) == 0

            ai_status, ai_error = self.ai_enhancer.get_ai_status()
            if self.ai_timed_out:
                # 검증 시간 상한에 걸려 생략된 AI 단계가 있으면 실패로 알린다
                ai_status = "failed"
                ai_error = ", ".join(r for r in ("AI 응답 시간 초과", ai_error) if r)

            result = ValidationResult(
                is_valid=is_valid,
                summary=issues_summary,
                issue_counts=issue_counts,
                issues=optimized_issues,
                structure=structure_info,
                rule_summary=rule_summary,
                complexity_score=structure_metrics["complexity_score"],
                ai_comment=ai_comment,
                # 확장된 분석 정보
                field_analysis=field_analysis,
                logic_flow=logic_flow,
                performance_metrics=performance_metrics,
                quality_metrics=quality_metrics,
                report_metadata=report_metadata,
                # AI 생성 콘텐츠
                ai_insights=ai_insights,
                improvement_recommendations=improvement_recommendations,
                risk_assessment=risk_assessment,
                ai_status=ai_status,
                ai_error=ai_error,
                rule_description=rule_description,
            )

            total_ms = int((time.time() - analysis_start_time) * 1000)
            stages = ", ".join(f"{k} {int(v * 1000)}ms" for k, v in stage_times.items())
            ai_detail = ", ".join(f"{k} {int(v * 1000)}ms" for k, v in ai_times.items())
            self.logger.info(
                f"룰 분석 완료 (v2): {rule_name}, 이슈 {len(optimized_issues)}건, "
                f"전체 {total_ms}ms [{stages}] (AI 세부: {ai_detail}) "
                f"ai_status={ai_status}"
            )

            return result

        except ValidationTimeoutError:
            raise
        except Exception as e:
            self.logger.error(f"룰 분석 중 치명적 오류 (v2): {str(e)}", exc_info=True)
            return self._create_error_result(rule, str(e), analysis_start_time)

    def _extract_rule_name(self, rule: Rule) -> str:
        """룰에서 이름 추출"""
        if hasattr(rule, "ruleName") and rule.ruleName:
            return rule.ruleName
        elif hasattr(rule, "name") and rule.name:
            return rule.name
        return "Unknown Rule"

    def _extract_rule_id(self, rule: Rule) -> Optional[str]:
        """룰에서 ID 추출"""
        if hasattr(rule, "ruleUuid") and rule.ruleUuid:
            return rule.ruleUuid
        elif hasattr(rule, "id") and rule.id:
            return rule.id
        return None

    def _create_error_result(
        self, rule: Rule, error_message: str, start_time: float
    ) -> ValidationResult:
        """
        오류 발생 시 기본 ValidationResult 생성

        Args:
            rule (Rule): 분석하려던 룰
            error_message (str): 오류 메시지
            start_time (float): 분석 시작 시간

        Returns:
            ValidationResult: 오류 정보가 포함된 결과
        """
        rule_name = self._extract_rule_name(rule)
        rule_id = self._extract_rule_id(rule)
        analysis_time_ms = int((time.time() - start_time) * 1000)

        # 조건 개수를 안전하게 계산
        condition_count = 0
        try:
            conditions = self.condition_analyzer.parse_rule_conditions(rule)
            condition_count = len(conditions) if conditions else 0
        except Exception:
            pass  # 오류 시 0으로 유지

        error_issue = ConditionIssue(
            condUuid=None,
            keyName=None,
            issue_type="missing_condition",
            severity="error",
            location="전체 룰",
            explanation=f"룰 분석 중 오류: {error_message}",
            suggestion="룰의 형식과 조건을 확인하세요.",
        )

        return ValidationResult(
            is_valid=False,
            summary=f"룰 '{rule_name}'에 오류 1건이 발견되었습니다.",
            issue_counts={"missing_condition": 1},
            issues=[error_issue],
            structure=StructureInfo(
                depth=1,
                condition_count=condition_count,
                condition_node_count=condition_count,
                field_condition_count=0,
                unique_fields=[],
            ),
            rule_summary="룰 분석 중 오류가 발생하여 요약을 생성할 수 없습니다.",
            complexity_score=0,
            ai_comment=None,
            # 기본값으로 설정
            field_analysis=[],
            logic_flow=None,
            performance_metrics=None,
            quality_metrics=None,
            report_metadata=ReportMetadata(
                analysis_timestamp=datetime.now().isoformat(),
                ruleUuid=rule_id,
                ruleName=rule_name,
                total_analysis_time_ms=analysis_time_ms,
            ),
            ai_insights=None,
            improvement_recommendations=None,
            risk_assessment=None,
        )

    # === 기존 API 호환성을 위한 메서드들 ===

    def get_field_type(self, field: str) -> str:
        """
        필드 타입 조회 (기존 API 호환성)

        Args:
            field (str): 필드명

        Returns:
            str: 필드 타입
        """
        return self.condition_analyzer.get_field_type(field)

    def is_valid_operator(self, field: str, operator: str) -> bool:
        """
        연산자 유효성 확인 (기존 API 호환성)

        Args:
            field (str): 필드명
            operator (str): 연산자

        Returns:
            bool: 유효성 여부
        """
        return self.condition_analyzer.is_valid_operator(field, operator)

    def is_valid_type(self, field: str, value: Any) -> bool:
        """
        타입 유효성 확인 (기존 API 호환성)

        Args:
            field (str): 필드명
            value (Any): 값

        Returns:
            bool: 유효성 여부
        """
        return self.condition_analyzer.is_valid_type(field, value)

    # === 성능 및 디버깅 정보 ===

    def get_component_info(self) -> Dict[str, str]:
        """
        각 컴포넌트의 정보 반환

        Returns:
            Dict[str, str]: 컴포넌트 정보
        """
        return {
            "condition_analyzer": "조건 분석 및 파싱 담당",
            "issue_detector": "7가지 이슈 타입 검출 담당",
            "ai_enhancer": "AI 기반 개선 및 통찰 담당",
            "metrics_generator": "성능 및 품질 메트릭 생성 담당",
            "report_generator": "보고서 및 요약 생성 담당",
        }

    def get_analysis_statistics(self) -> Dict[str, Any]:
        """
        분석 통계 정보 반환

        Returns:
            Dict[str, Any]: 통계 정보
        """
        return {
            "version": "2.0",
            "architecture": "modular",
            "components": 5,
            "supported_issue_types": 7,
            "ai_enhanced": True,
            "performance_optimized": True,
        }
