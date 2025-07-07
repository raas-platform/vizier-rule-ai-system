"""
메트릭 생성기 (MetricsGenerator)

룰의 성능 및 품질 메트릭을 생성하는 기능을 담당합니다.
- 성능 메트릭 계산
- 품질 메트릭 계산
- 최적화 제안 생성
"""

import logging
from typing import Any, Dict, List

from ..models import Rule, RuleCondition, PerformanceMetrics, QualityMetrics
from ..exceptions import MetricsGenerationError


class MetricsGenerator:
    """
    성능 및 품질 메트릭 생성을 담당하는 클래스

    이 클래스는 다음 메트릭들을 제공합니다:
    - 성능 메트릭: 실행 시간, 메모리 사용량 추정
    - 품질 메트릭: 유지보수성, 가독성, 복잡성 점수
    - 최적화 제안: 성능 및 품질 개선 방안
    """

    def __init__(self):
        """MetricsGenerator 초기화"""
        self.logger = logging.getLogger(__name__)

    def generate_performance_metrics(
        self, rule: Rule, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> PerformanceMetrics:
        """
        성능 메트릭 생성

        Args:
            rule (Rule): 분석할 룰
            conditions (List[RuleCondition]): 파싱된 조건들
            structure_metrics (Dict[str, Any]): 구조 메트릭

        Returns:
            PerformanceMetrics: 성능 메트릭
        """
        try:
            # 실행 시간 추정 (조건 수와 복잡도 기반)
            estimated_time = self._estimate_execution_time(conditions, structure_metrics)
            
            # 메모리 사용량 추정
            memory_usage = self._estimate_memory_usage(conditions, structure_metrics)
            
            # 최적화 제안 생성
            optimization_suggestions = self._generate_optimization_suggestions(
                conditions, structure_metrics
            )

            return PerformanceMetrics(
                estimated_execution_time_ms=estimated_time,
                memory_usage_estimate_kb=memory_usage,
                optimization_suggestions=optimization_suggestions
            )

        except Exception as e:
            self.logger.error(f"성능 메트릭 생성 중 오류: {str(e)}", exc_info=True)
            raise MetricsGenerationError(f"성능 메트릭 생성 실패: {str(e)}")

    def generate_quality_metrics(
        self, rule: Rule, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> QualityMetrics:
        """
        품질 메트릭 생성

        Args:
            rule (Rule): 분석할 룰
            conditions (List[RuleCondition]): 파싱된 조건들
            structure_metrics (Dict[str, Any]): 구조 메트릭

        Returns:
            QualityMetrics: 품질 메트릭
        """
        try:
            # 유지보수성 점수 계산
            maintainability = self._calculate_maintainability_score(
                conditions, structure_metrics
            )
            
            # 가독성 점수 계산
            readability = self._calculate_readability_score(
                conditions, structure_metrics
            )
            
            # 복잡성 레벨 결정
            complexity_level = self._determine_complexity_level(structure_metrics)
            
            # 모범 사례 점수 계산
            best_practices = self._calculate_best_practices_score(
                conditions, structure_metrics
            )

            return QualityMetrics(
                maintainability_score=maintainability,
                readability_score=readability,
                complexity_level=complexity_level,
                best_practices_score=best_practices
            )

        except Exception as e:
            self.logger.error(f"품질 메트릭 생성 중 오류: {str(e)}", exc_info=True)
            raise MetricsGenerationError(f"품질 메트릭 생성 실패: {str(e)}")

    def _estimate_execution_time(
        self, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> float:
        """실행 시간 추정 (밀리초)"""
        base_time = 1.0  # 기본 1ms
        
        # 조건 수에 따른 시간 증가
        total_conditions = structure_metrics.get("total_conditions", 0)
        condition_time = total_conditions * 0.5  # 조건당 0.5ms
        
        # 깊이에 따른 시간 증가
        max_depth = structure_metrics.get("max_depth", 1)
        depth_time = max_depth * 0.3  # 깊이당 0.3ms
        
        # 복잡한 연산자에 따른 시간 증가
        complex_operator_time = 0
        for condition in conditions:
            if condition.operator in ["contains", "starts_with", "ends_with"]:
                complex_operator_time += 0.2
            elif condition.operator in ["in", "not_in"]:
                complex_operator_time += 0.3
        
        total_time = base_time + condition_time + depth_time + complex_operator_time
        return round(total_time, 2)

    def _estimate_memory_usage(
        self, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> float:
        """메모리 사용량 추정 (KB)"""
        base_memory = 2.0  # 기본 2KB
        
        # 조건 수에 따른 메모리 증가
        total_conditions = structure_metrics.get("total_conditions", 0)
        condition_memory = total_conditions * 0.1  # 조건당 0.1KB
        
        # 고유 필드 수에 따른 메모리 증가
        unique_fields = structure_metrics.get("unique_fields", 0)
        field_memory = unique_fields * 0.05  # 필드당 0.05KB
        
        # 문자열 값에 따른 메모리 증가
        string_memory = 0
        for condition in conditions:
            if isinstance(condition.value, str):
                string_memory += len(condition.value) * 0.001  # 문자당 0.001KB
        
        total_memory = base_memory + condition_memory + field_memory + string_memory
        return round(total_memory, 2)

    def _generate_optimization_suggestions(
        self, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> List[str]:
        """최적화 제안 생성"""
        suggestions = []
        
        # 복잡도 관련 제안
        complexity_score = structure_metrics.get("complexity_score", 0)
        if complexity_score > 50:
            suggestions.append("룰의 복잡도가 높습니다. 여러 개의 간단한 룰로 분리를 고려하세요.")
        
        # 깊이 관련 제안
        max_depth = structure_metrics.get("max_depth", 1)
        if max_depth > 5:
            suggestions.append("중첩 깊이가 깊습니다. 조건을 평면화하여 성능을 개선할 수 있습니다.")
        
        # 조건 수 관련 제안
        total_conditions = structure_metrics.get("total_conditions", 0)
        if total_conditions > 20:
            suggestions.append("조건 수가 많습니다. 자주 사용되는 조건을 앞쪽으로 배치하세요.")
        
        # 연산자 관련 제안
        has_complex_operators = False
        for condition in conditions:
            if condition.operator in ["contains", "starts_with", "ends_with"]:
                has_complex_operators = True
                break
        
        if has_complex_operators:
            suggestions.append("문자열 검색 연산자 사용 시 인덱스 활용을 고려하세요.")
        
        # 필드 중복 관련 제안
        field_usage = {}
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                field_usage[condition.keyName] = field_usage.get(condition.keyName, 0) + 1
        
        frequent_fields = [field for field, count in field_usage.items() if count > 5]
        if frequent_fields:
            suggestions.append(f"자주 사용되는 필드({', '.join(frequent_fields)})에 대한 조건을 통합하세요.")
        
        return suggestions

    def _calculate_maintainability_score(
        self, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> float:
        """유지보수성 점수 계산 (0-100)"""
        score = 100.0
        
        # 복잡도에 따른 감점
        complexity_score = structure_metrics.get("complexity_score", 0)
        score -= min(complexity_score, 30)  # 최대 30점 감점
        
        # 깊이에 따른 감점
        max_depth = structure_metrics.get("max_depth", 1)
        if max_depth > 3:
            score -= (max_depth - 3) * 5  # 깊이 3 초과 시 레벨당 5점 감점
        
        # 조건 수에 따른 감점
        total_conditions = structure_metrics.get("total_conditions", 0)
        if total_conditions > 10:
            score -= (total_conditions - 10) * 2  # 조건 10개 초과 시 개당 2점 감점
        
        return max(0.0, min(100.0, round(score, 1)))

    def _calculate_readability_score(
        self, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> float:
        """가독성 점수 계산 (0-100)"""
        score = 100.0
        
        # 명명 규칙 점수
        naming_score = self._calculate_naming_score(conditions)
        score = score * 0.3 + naming_score * 0.7  # 명명 규칙이 가독성에 큰 영향
        
        # 구조 복잡성에 따른 감점
        max_depth = structure_metrics.get("max_depth", 1)
        if max_depth > 4:
            score -= (max_depth - 4) * 8  # 깊이 4 초과 시 레벨당 8점 감점
        
        # 논리 연산자 복잡성에 따른 감점
        logic_operators = structure_metrics.get("logic_operators", {})
        or_count = logic_operators.get("or", 0)
        if or_count > 3:
            score -= (or_count - 3) * 3  # OR 3개 초과 시 개당 3점 감점
        
        return max(0.0, min(100.0, round(score, 1)))

    def _calculate_naming_score(self, conditions: List[RuleCondition]) -> float:
        """명명 규칙 점수 계산"""
        score = 100.0
        total_fields = 0
        good_names = 0
        
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                total_fields += 1
                
                # 좋은 명명 규칙 체크
                field_name = condition.keyName
                if len(field_name) >= 3:  # 최소 3글자
                    good_names += 1
                if "_" in field_name or field_name[0].islower():  # snake_case 또는 camelCase
                    good_names += 0.5
        
        if total_fields > 0:
            score = (good_names / total_fields) * 100
        
        return round(score, 1)

    def _determine_complexity_level(self, structure_metrics: Dict[str, Any]) -> str:
        """복잡성 레벨 결정"""
        complexity_score = structure_metrics.get("complexity_score", 0)
        max_depth = structure_metrics.get("max_depth", 1)
        total_conditions = structure_metrics.get("total_conditions", 0)
        
        # 복합 지표로 복잡성 레벨 결정
        if complexity_score > 50 or max_depth > 5 or total_conditions > 20:
            return "high"
        elif complexity_score > 25 or max_depth > 3 or total_conditions > 10:
            return "medium"
        else:
            return "low"

    def _calculate_best_practices_score(
        self, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> float:
        """모범 사례 점수 계산 (0-100)"""
        score = 100.0
        
        # 1. 적절한 복잡도 유지
        complexity_score = structure_metrics.get("complexity_score", 0)
        if complexity_score > 40:
            score -= 20
        elif complexity_score > 60:
            score -= 40
        
        # 2. 적절한 깊이 유지
        max_depth = structure_metrics.get("max_depth", 1)
        if max_depth > 4:
            score -= 15
        elif max_depth > 6:
            score -= 30
        
        # 3. 필드 타입 일관성
        type_consistency = self._check_type_consistency(conditions)
        score = score * 0.8 + type_consistency * 0.2
        
        # 4. 연산자 적절성
        operator_appropriateness = self._check_operator_appropriateness(conditions)
        score = score * 0.9 + operator_appropriateness * 0.1
        
        return max(0.0, min(100.0, round(score, 1)))

    def _check_type_consistency(self, conditions: List[RuleCondition]) -> float:
        """타입 일관성 검사"""
        total_conditions = 0
        consistent_conditions = 0
        
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                total_conditions += 1
                
                # fieldDataType이 명시되어 있는 경우 일관성 있음으로 간주
                if condition.fieldDataType:
                    consistent_conditions += 1
        
        if total_conditions == 0:
            return 100.0
        
        return (consistent_conditions / total_conditions) * 100

    def _check_operator_appropriateness(self, conditions: List[RuleCondition]) -> float:
        """연산자 적절성 검사"""
        total_conditions = 0
        appropriate_conditions = 0
        
        # 적절한 연산자 사용 패턴
        appropriate_patterns = {
            "string": ["==", "!=", "contains", "starts_with", "ends_with"],
            "number": ["==", "!=", ">", ">=", "<", "<="],
            "boolean": ["==", "!="],
            "date": ["==", "!=", ">", ">=", "<", "<="]
        }
        
        for condition in conditions:
            if (condition.keyName and condition.keyName != "placeholder" 
                and condition.operator and condition.fieldDataType):
                total_conditions += 1
                
                field_type = condition.fieldDataType.lower()
                if field_type in appropriate_patterns:
                    if condition.operator in appropriate_patterns[field_type]:
                        appropriate_conditions += 1
        
        if total_conditions == 0:
            return 100.0
        
        return (appropriate_conditions / total_conditions) * 100 