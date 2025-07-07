"""
룰 분석기 (RuleAnalyzer)

모든 분석 기능을 통합하는 메인 분석기입니다.
- 조건 분석
- 이슈 검출
- 메트릭 생성
- 검증 결과 생성
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models import Rule, RuleCondition, ValidationResult, ConditionIssue, StructureInfo, ReportMetadata
from ..exceptions import RuleAnalyzerError
from .condition_analyzer import ConditionAnalyzer
from .issue_detector import IssueDetector
from .metrics_generator import MetricsGenerator


class RuleAnalyzer:
    """
    룰 분석의 모든 기능을 통합하는 메인 분석기

    이 클래스는 다음 기능들을 제공합니다:
    - 전체 룰 분석 워크플로우 관리
    - 조건 파싱 및 분석
    - 이슈 검출 및 검증
    - 성능/품질 메트릭 생성
    - 종합 검증 결과 생성
    """

    def __init__(self):
        """RuleAnalyzer 초기화"""
        self.logger = logging.getLogger(__name__)
        
        # 하위 분석기들 초기화
        self.condition_analyzer = ConditionAnalyzer()
        self.issue_detector = IssueDetector(self.condition_analyzer)
        self.metrics_generator = MetricsGenerator()

    async def analyze_rule(self, rule: Rule, include_ai_analysis: bool = False) -> ValidationResult:
        """
        룰에 대한 전체 분석 수행

        Args:
            rule (Rule): 분석할 룰
            include_ai_analysis (bool): AI 분석 포함 여부

        Returns:
            ValidationResult: 종합 분석 결과
        """
        start_time = datetime.now()
        
        try:
            self.logger.info(f"룰 분석 시작: {getattr(rule, 'ruleUuid', 'unknown')}")

            # 1. 조건 파싱 및 분석
            conditions = self.condition_analyzer.parse_rule_conditions(rule)
            self.logger.debug(f"파싱된 조건 수: {len(conditions)}")

            # 2. 필드 타입 추론
            field_types = self.condition_analyzer.infer_field_types(rule, conditions)
            self.logger.debug(f"추론된 필드 타입: {len(field_types)}개")

            # 3. 구조 메트릭 계산
            structure_metrics = self.condition_analyzer.calculate_structure_metrics(conditions, rule)
            self.logger.debug(f"구조 메트릭: {structure_metrics}")

            # 4. 이슈 검출
            issues = await self.issue_detector.detect_all_issues(
                rule, conditions, structure_metrics.get("complexity_score", 0)
            )
            self.logger.debug(f"검출된 이슈 수: {len(issues)}")

            # 5. 성능 메트릭 생성
            performance_metrics = self.metrics_generator.generate_performance_metrics(
                rule, conditions, structure_metrics
            )

            # 6. 품질 메트릭 생성
            quality_metrics = self.metrics_generator.generate_quality_metrics(
                rule, conditions, structure_metrics
            )

            # 7. 검증 결과 생성
            validation_result = self._create_validation_result(
                rule, conditions, issues, structure_metrics, 
                performance_metrics, quality_metrics, field_types
            )

            # 8. AI 분석 (옵션)
            if include_ai_analysis:
                ai_comment = await self._generate_ai_analysis(validation_result)
                validation_result.ai_comment = ai_comment

            # 9. 메타데이터 추가
            end_time = datetime.now()
            processing_time = int((end_time - start_time).total_seconds() * 1000)
            
            validation_result.report_metadata = ReportMetadata(
                analysis_timestamp=end_time.isoformat(),
                ruleUuid=getattr(rule, 'ruleUuid', None),
                ruleName=getattr(rule, 'ruleName', getattr(rule, 'name', None)),
                total_analysis_time_ms=processing_time,
                total_processing_time_ms=processing_time
            )

            self.logger.info(f"룰 분석 완료: {processing_time}ms")
            return validation_result

        except Exception as e:
            self.logger.error(f"룰 분석 중 오류: {str(e)}", exc_info=True)
            raise RuleAnalyzerError(f"룰 분석 실패: {str(e)}")

    def _create_validation_result(
        self,
        rule: Rule,
        conditions: List[RuleCondition],
        issues: List[ConditionIssue],
        structure_metrics: Dict[str, Any],
        performance_metrics,
        quality_metrics,
        field_types: Dict[str, str]
    ) -> ValidationResult:
        """검증 결과 생성"""
        
        # 이슈 타입별 개수 계산
        issue_counts = {}
        for issue in issues:
            issue_type = issue.issue_type
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        # 심각도별 개수 계산
        error_count = len([i for i in issues if i.severity == "error"])
        warning_count = len([i for i in issues if i.severity == "warning"])

        # 검증 통과 여부 결정
        is_valid = error_count == 0

        # 요약 메시지 생성
        summary = self._generate_summary(
            is_valid, len(conditions), error_count, warning_count, 
            structure_metrics.get("complexity_score", 0)
        )

        # 룰 요약 생성
        rule_summary = self._generate_rule_summary(rule, conditions, structure_metrics)

        # 구조 정보 생성
        structure_info = StructureInfo(
            total_conditions=structure_metrics.get("total_conditions", 0),
            field_conditions=structure_metrics.get("field_conditions", 0),
            logical_operators=structure_metrics.get("logical_operators", 0),
            max_depth=structure_metrics.get("max_depth", 1),
            unique_fields=structure_metrics.get("unique_fields", 0),
            complexity_score=structure_metrics.get("complexity_score", 0)
        )

        # 필드별 분석 생성
        field_analysis = self._generate_field_analysis(conditions, field_types, issues)

        return ValidationResult(
            is_valid=is_valid,
            summary=summary,
            issues=issues,
            issue_counts=issue_counts,
            structure=structure_info,
            rule_summary=rule_summary,
            complexity_score=structure_metrics.get("complexity_score", 0),
            field_analysis=field_analysis,
            performance_metrics=performance_metrics,
            quality_metrics=quality_metrics
        )

    def _generate_summary(
        self, is_valid: bool, condition_count: int, error_count: int, 
        warning_count: int, complexity_score: int
    ) -> str:
        """요약 메시지 생성"""
        
        if is_valid:
            if warning_count == 0:
                return f"✅ 룰이 완벽합니다! {condition_count}개 조건, 복잡도 {complexity_score}점"
            else:
                return f"✅ 룰이 유효합니다. {condition_count}개 조건, {warning_count}개 경고, 복잡도 {complexity_score}점"
        else:
            return f"❌ 룰에 문제가 있습니다. {error_count}개 오류, {warning_count}개 경고 발견"

    def _generate_rule_summary(
        self, rule: Rule, conditions: List[RuleCondition], structure_metrics: Dict[str, Any]
    ) -> str:
        """룰 요약 생성"""
        
        rule_name = getattr(rule, 'ruleName', getattr(rule, 'name', '이름 없음'))
        condition_count = len(conditions)
        unique_fields = structure_metrics.get("unique_fields", 0)
        max_depth = structure_metrics.get("max_depth", 1)
        
        # 주요 필드들 추출
        main_fields = []
        field_usage = {}
        
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                field_usage[condition.keyName] = field_usage.get(condition.keyName, 0) + 1
        
        # 사용 빈도 순으로 정렬하여 상위 3개 필드 선택
        sorted_fields = sorted(field_usage.items(), key=lambda x: x[1], reverse=True)
        main_fields = [field for field, _ in sorted_fields[:3]]
        
        summary = f"'{rule_name}' 룰은 {condition_count}개의 조건으로 구성되어 있으며, "
        summary += f"{unique_fields}개의 고유 필드를 사용합니다. "
        
        if main_fields:
            summary += f"주요 필드: {', '.join(main_fields)}. "
        
        summary += f"최대 중첩 깊이는 {max_depth}레벨입니다."
        
        return summary

    def _generate_field_analysis(
        self, conditions: List[RuleCondition], field_types: Dict[str, str], 
        issues: List[ConditionIssue]
    ) -> List:
        """필드별 분석 생성"""
        
        field_analysis = []
        field_usage = {}
        field_operators = {}
        field_values = {}
        
        # 필드별 사용 정보 수집
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                field = condition.keyName
                
                # 사용 횟수
                field_usage[field] = field_usage.get(field, 0) + 1
                
                # 연산자 수집
                if field not in field_operators:
                    field_operators[field] = set()
                if condition.operator:
                    field_operators[field].add(condition.operator)
                
                # 값 수집
                if field not in field_values:
                    field_values[field] = set()
                if condition.value is not None:
                    field_values[field].add(str(condition.value)[:50])  # 길이 제한
        
        # 필드별 이슈 그룹화
        field_issues = {}
        for issue in issues:
            if issue.keyName:
                field = issue.keyName
                if field not in field_issues:
                    field_issues[field] = []
                field_issues[field].append(issue)
        
        # 필드 분석 생성
        for field in field_usage.keys():
            from ..models import FieldAnalysis  # 지연 import로 순환 참조 방지
            
            analysis = FieldAnalysis(
                field_name=field,
                field_type=field_types.get(field, "unknown"),
                usage_count=field_usage[field],
                operators_used=list(field_operators.get(field, set())),
                values_used=list(field_values.get(field, set()))[:10],  # 최대 10개
                issues=field_issues.get(field, [])
            )
            field_analysis.append(analysis)
        
        # 사용 빈도순으로 정렬
        field_analysis.sort(key=lambda x: x.usage_count, reverse=True)
        
        return field_analysis

    async def _generate_ai_analysis(self, validation_result: ValidationResult) -> str:
        """AI 분석 코멘트 생성 (옵션)"""
        
        # 현재는 간단한 규칙 기반 분석으로 대체
        # 실제 구현에서는 LLM API 호출
        
        try:
            ai_comment = "🤖 AI 분석: "
            
            if validation_result.is_valid:
                if validation_result.quality_metrics:
                    if validation_result.quality_metrics.maintainability_score > 80:
                        ai_comment += "룰의 유지보수성이 우수합니다. "
                    if validation_result.quality_metrics.complexity_level == "low":
                        ai_comment += "적절한 복잡도를 유지하고 있습니다. "
                
                ai_comment += "전반적으로 잘 구성된 룰입니다."
            else:
                error_issues = [i for i in validation_result.issues if i.severity == "error"]
                if error_issues:
                    main_issue_types = list(set([i.issue_type for i in error_issues]))
                    ai_comment += f"주요 문제: {', '.join(main_issue_types)}. "
                
                ai_comment += "이슈를 해결하여 룰의 품질을 향상시키세요."
            
            return ai_comment
            
        except Exception as e:
            self.logger.warning(f"AI 분석 생성 실패: {str(e)}")
            return "AI 분석을 생성할 수 없습니다."

    def get_analyzer_info(self) -> Dict[str, Any]:
        """분석기 정보 반환"""
        return {
            "version": "1.0.0",
            "analyzers": {
                "condition_analyzer": "조건 파싱 및 구조 분석",
                "issue_detector": "이슈 검출 및 검증",
                "metrics_generator": "성능/품질 메트릭 생성"
            },
            "supported_features": [
                "조건 트리 파싱",
                "필드 타입 추론",
                "이슈 검출",
                "성능 메트릭",
                "품질 메트릭",
                "최적화 제안"
            ]
        } 