"""
메트릭 생성기 (MetricsGenerator)

성능 및 품질 메트릭 생성을 담당합니다.
- 필드별 분석 메트릭
- 논리 흐름 분석
- 성능 메트릭
- 품질 메트릭
- 보고서 메타데이터
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ...models.rule import Rule, RuleCondition
from ...models.validation_result import (
    ConditionIssue,
    FieldAnalysis,
    LogicFlow,
    PerformanceMetrics,
    QualityMetrics,
    ReportMetadata,
    StructureInfo,
)
from ...utils.logger import get_logger
from .condition_analyzer import ConditionAnalyzer


class MetricsGenerator:
    """
    성능 및 품질 메트릭 생성을 담당하는 클래스

    이 클래스는 다음 메트릭들을 생성합니다:
    - 필드별 상세 분석 메트릭
    - 논리 흐름 분석 메트릭
    - 성능 예측 메트릭
    - 코드 품질 메트릭
    - 보고서 메타데이터
    """

    def __init__(self, condition_analyzer: ConditionAnalyzer):
        """
        MetricsGenerator 초기화

        Args:
            condition_analyzer (ConditionAnalyzer): 조건 분석기 인스턴스
        """
        self.logger = get_logger(__name__)
        self.condition_analyzer = condition_analyzer

    async def generate_field_analysis(
        self, conditions: List[RuleCondition], issues: List[ConditionIssue]
    ) -> List[FieldAnalysis]:
        """
        필드별 상세 분석 메트릭 생성

        Args:
            conditions (List[RuleCondition]): 분석할 조건들
            issues (List[ConditionIssue]): 검출된 이슈들

        Returns:
            List[FieldAnalysis]: 필드별 분석 결과
        """
        field_stats = {}

        def analyze_conditions(condition_list):
            """조건 리스트를 순회하며 필드별 통계 수집"""
            for condition in condition_list:
                if condition is None:
                    continue

                field = self.condition_analyzer._get_condition_field(condition)
                if field and field != "placeholder":
                    if field not in field_stats:
                        field_stats[field] = {
                            "condition_count": 0,
                            "operators": set(),
                            "values": [],
                            "issues_count": 0,
                            "complexity": 0,
                            "condition_uuids": [],
                        }

                    # 기본 통계 수집
                    field_stats[field]["condition_count"] += 1
                    field_stats[field]["operators"].add(condition.operator)
                    if condition.value is not None:
                        field_stats[field]["values"].append(condition.value)
                    
                    # condUuid 수집 (있는 경우)
                    if hasattr(condition, 'condUuid') and condition.condUuid:
                        field_stats[field]["condition_uuids"].append(condition.condUuid)

                    # 복잡성 점수 계산 (중첩 레벨 등 고려)
                    field_stats[field]["complexity"] += 1

                # 중첩 조건 재귀 처리
                if hasattr(condition, "conditions") and condition.conditions:
                    analyze_conditions(condition.conditions)

        # 조건 분석 실행
        analyze_conditions(conditions)

        # 이슈 카운트 계산
        for issue in issues:
            if issue.keyName and issue.keyName in field_stats:
                field_stats[issue.keyName]["issues_count"] += 1

        # FieldAnalysis 객체 생성
        field_analyses = []
        for field_name, stats in field_stats.items():
            field_analyses.append(
                FieldAnalysis(
                    keyName=field_name,
                    field_type=self.condition_analyzer.get_field_type(field_name),
                    condition_count=stats["condition_count"],
                    operators_used=list(stats["operators"]),
                    values_range=self._calculate_values_range(field_name, stats["values"]),
                    issues_count=stats["issues_count"],
                    complexity_score=min(stats["complexity"] * 2, 10),  # 0-10 스케일
                    condition_uuids=stats["condition_uuids"],
                )
            )

        self.logger.info(f"필드 분석 메트릭 생성 완료: {len(field_analyses)}개 필드")
        return field_analyses

    def _calculate_values_range(
        self, field_name: str, values: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        필드 값 범위 계산

        Args:
            field_name (str): 필드명
            values (List[Any]): 값 리스트

        Returns:
            Optional[Dict[str, Any]]: 값 범위 정보
        """
        if not values:
            return None

        field_type = self.condition_analyzer.get_field_type(field_name)

        if field_type == "number":
            # 숫자 타입: 최소/최대값과 예시
            numeric_values = []
            for v in values:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass

            if numeric_values:
                return {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "examples": values[:3],
                }
        else:
            # 기타 타입: 고유값 예시
            unique_values = list(set(str(v) for v in values))
            return {"examples": unique_values[:5]}

        return {"examples": values[:3]}

    def generate_logic_flow_analysis(
        self, conditions: List[RuleCondition]
    ) -> LogicFlow:
        """
        논리 흐름 분석 메트릭 생성

        Args:
            conditions (List[RuleCondition]): 분석할 조건들

        Returns:
            LogicFlow: 논리 흐름 분석 결과
        """
        logical_operators = {"AND": 0, "OR": 0}
        nesting_levels = []

        def analyze_logic(condition_list, level=0):
            """논리 구조를 재귀적으로 분석"""
            # 레벨별 카운트 초기화
            if level >= len(nesting_levels):
                nesting_levels.append(0)

            for condition in condition_list:
                if condition is None:
                    continue

                nesting_levels[level] += 1

                # 논리 연산자 카운트
                if condition.operator and condition.operator.upper() in [
                    "AND",
                    "OR",
                ]:
                    logical_operators[condition.operator.upper()] += 1

                # 중첩 조건 재귀 분석
                if hasattr(condition, "conditions") and condition.conditions:
                    analyze_logic(condition.conditions, level + 1)

        analyze_logic(conditions)

        # 분기 커버리지 계산 (간단한 휴리스틱)
        total_conditions = sum(nesting_levels) if nesting_levels else 0
        branch_coverage_percentage = (
            min(85 + (total_conditions * 2), 100) if total_conditions > 0 else 0
        )

        logic_flow = LogicFlow(
            logical_operators=logical_operators,
            nesting_levels=nesting_levels,
            branch_coverage={
                "analyzed": True,
                "coverage_percentage": branch_coverage_percentage,
            },
            potential_dead_code=[],  # 추후 구현 가능
        )

        self.logger.debug(
            f"논리 흐름 분석 완료: AND={logical_operators['AND']}, OR={logical_operators['OR']}"
        )
        return logic_flow

    def generate_performance_metrics(
        self, conditions: List[RuleCondition], complexity_score: int
    ) -> PerformanceMetrics:
        """
        성능 메트릭 생성

        Args:
            conditions (List[RuleCondition]): 분석할 조건들
            complexity_score (int): 복잡성 점수

        Returns:
            PerformanceMetrics: 성능 메트릭 결과
        """
        condition_count = len(conditions) if conditions else 0

        # 복잡성 등급 결정 (0-100 점수 스케일에 맞춰 조정)
        # 2025-06-30: 이전 임계값(5,10,15)은 계산식과 불일치해 작은 점수도 "complex" 로 분류되었습니다.
        # 신규 기준: 0-15 simple, 16-35 moderate, 36-60 complex, 61+ very_complex
        if complexity_score <= 15:
            complexity_rating = "simple"
            estimated_time = "< 1ms"
        elif complexity_score <= 35:
            complexity_rating = "moderate"
            estimated_time = "1-5ms"
        elif complexity_score <= 60:
            complexity_rating = "complex"
            estimated_time = "5-10ms"
        else:
            complexity_rating = "very_complex"
            estimated_time = "> 10ms"

        # 최적화 기회 탐지
        optimization_opportunities = []
        if condition_count > 10:
            optimization_opportunities.append(
                "조건 수가 많습니다. 룰을 분할하는 것을 고려하세요."
            )

        if complexity_score > 20:
            optimization_opportunities.append(
                "복잡성이 높습니다. 조건 구조를 단순화하세요."
            )

        # 깊이가 깊은 경우
        depth = (
            self.condition_analyzer._calculate_depth(conditions) if conditions else 1
        )
        if depth > 4:
            optimization_opportunities.append(
                "중첩 깊이가 깊습니다. 평면적인 구조로 리팩토링을 고려하세요."
            )

        performance_metrics = PerformanceMetrics(
            estimated_execution_time=estimated_time,
            complexity_rating=complexity_rating,
            optimization_opportunities=optimization_opportunities,
            bottleneck_conditions=[],  # 추후 구현 가능
        )

        self.logger.debug(f"성능 메트릭 생성 완료: {complexity_rating} 등급")
        return performance_metrics

    def generate_quality_metrics(
        self,
        issues: List[ConditionIssue],
        structure: StructureInfo,
        conditions: List[RuleCondition],
    ) -> QualityMetrics:
        """
        품질 메트릭 생성

        Args:
            issues (List[ConditionIssue]): 검출된 이슈들
            structure (StructureInfo): 구조 정보
            conditions (List[RuleCondition]): 조건들

        Returns:
            QualityMetrics: 품질 메트릭 결과
        """
        # 기본 점수 100에서 이슈에 따라 차감
        base_score = 100

        # 오류 심각도별 차감
        error_count = len([i for i in issues if i.severity == "error"])
        warning_count = len([i for i in issues if i.severity == "warning"])

        # 각 품질 측면별 점수 계산
        maintainability_score = max(
            0, base_score - (error_count * 15) - (warning_count * 5)
        )
        readability_score = max(0, base_score - (structure.depth - 1) * 10)
        completeness_score = max(0, base_score - error_count * 20)
        consistency_score = max(
            0, base_score - (error_count * 10) - (warning_count * 3)
        )

        # 추가 품질 요소들
        # 조건 수가 많으면 가독성 점수 차감
        if len(conditions) > 20:
            readability_score = max(0, readability_score - 10)

        # 논리 연산자가 복잡하면 일관성 점수 차감
        logical_operators = {"and": 0, "or": 0}
        for condition in conditions:
            if condition and condition.operator:
                op = condition.operator.lower()
                if op in logical_operators:
                    logical_operators[op] += 1

        if logical_operators["or"] > logical_operators["and"] * 2:
            consistency_score = max(0, consistency_score - 5)

        # 전체 점수는 각 측면의 평균
        overall_score = int(
            (
                maintainability_score
                + readability_score
                + completeness_score
                + consistency_score
            )
            / 4
        )

        quality_metrics = QualityMetrics(
            maintainability_score=maintainability_score,
            readability_score=readability_score,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            overall_score=overall_score,
        )

        self.logger.info(f"품질 메트릭 생성 완료: 전체 점수 {overall_score}/100")
        return quality_metrics

    def generate_report_metadata(
        self, rule: Rule, analysis_start_time: float, analysis_end_time: float
    ) -> ReportMetadata:
        """
        보고서 메타데이터 생성

        Args:
            rule (Rule): 분석된 룰
            analysis_start_time (float): 분석 시작 시간
            analysis_end_time (float): 분석 종료 시간

        Returns:
            ReportMetadata: 보고서 메타데이터
        """
        # 룰 정보 추출
        rule_name = getattr(rule, "ruleName", getattr(rule, "name", "Unknown Rule"))
        rule_id = getattr(rule, "ruleUuid", getattr(rule, "id", None))

        # 분석 시간 계산
        analysis_time_ms = int((analysis_end_time - analysis_start_time) * 1000)

        metadata = ReportMetadata(
            analysis_timestamp=datetime.now().isoformat(),
            ruleUuid=rule_id,
            ruleName=rule_name,
            total_analysis_time_ms=analysis_time_ms,
        )

        self.logger.debug(f"보고서 메타데이터 생성 완료: {analysis_time_ms}ms")
        return metadata
