"""
보고서 생성기 (ReportGenerator)

보고서 및 요약 생성을 담당합니다.
- 룰 요약 생성
- 이슈 요약 생성
- 전체 보고서 요약
- 이슈 최적화
"""

from typing import Any, Dict, List, Optional

from ...models.rule import Rule, RuleCondition
from ...models.validation_result import ConditionIssue, StructureInfo
from ...utils.logger import get_logger
from .condition_analyzer import ConditionAnalyzer


class ReportGenerator:
    """
    보고서 및 요약 생성을 담당하는 클래스

    이 클래스는 다음 기능들을 제공합니다:
    - 룰 구조 및 내용 요약
    - 이슈 검출 결과 요약
    - 최종 보고서 요약
    - 이슈 중복 제거 및 최적화
    """

    def __init__(self, condition_analyzer: ConditionAnalyzer):
        """
        ReportGenerator 초기화

        Args:
            condition_analyzer (ConditionAnalyzer): 조건 분석기 인스턴스
        """
        self.logger = get_logger(__name__)
        self.condition_analyzer = condition_analyzer

    def generate_rule_summary(
        self, rule: Rule, conditions: List[RuleCondition] = None
    ) -> str:
        """
        룰 요약 생성

        Args:
            rule (Rule): 요약할 룰
            conditions (List[RuleCondition], optional): 파싱된 조건들

        Returns:
            str: 생성된 룰 요약
        """
        try:
            if conditions is None:
                conditions = self.condition_analyzer.parse_rule_conditions(
                    rule
                )

            if not conditions:
                return "이 룰에는 조건이 없습니다."

            def format_condition(
                condition: RuleCondition, indent: int = 0
            ) -> str:
                """조건을 사람이 읽기 쉬운 형태로 포맷"""
                # 논리 연산자 블록인지 확인
                is_logical_block = condition.field == "placeholder" or (
                    condition.field is None
                    and condition.conditions is not None
                )

                if condition.conditions:
                    # 중첩 조건이 있는 경우
                    nested_conditions = [
                        format_condition(c, indent + 1)
                        for c in condition.conditions
                    ]

                    if condition.operator.lower() == "and":
                        return (
                            f"{'  ' * indent}모든 조건이 만족해야 합니다:\n"
                            + "\n".join(nested_conditions)
                        )
                    else:
                        return (
                            f"{'  ' * indent}다음 조건 중 하나가 만족해야 합니다:\n"
                            + "\n".join(nested_conditions)
                        )
                else:
                    # 실제 필드 조건인 경우
                    if (
                        not is_logical_block
                        and condition.field
                        and condition.field != "placeholder"
                    ):
                        field_desc = self._get_field_type_description(
                            condition.field
                        )
                        operator_desc = self._get_human_readable_operator(
                            condition.operator
                        )
                        return (
                            f"{'  ' * indent}{field_desc} '{condition.field}'이(가) "
                            f"'{condition.value}'와(과) {operator_desc}"
                        )
                    else:
                        return f"{'  ' * indent}조건 구조 오류: 필드 정보가 없습니다."

            conditions_summary = [
                format_condition(condition) for condition in conditions
            ]
            summary = "이 룰은 다음과 같은 조건을 가집니다:\n" + "\n".join(
                conditions_summary
            )

            self.logger.debug("룰 요약 생성 완료")
            return summary

        except Exception as e:
            self.logger.error(f"룰 요약 생성 중 오류: {str(e)}", exc_info=True)
            return "룰 요약을 생성할 수 없습니다."

    def generate_issues_summary(
        self, issues: List[ConditionIssue], rule_name: str = "Unknown"
    ) -> str:
        """
        이슈 검출 결과 요약 생성

        Args:
            issues (List[ConditionIssue]): 검출된 이슈들
            rule_name (str): 룰 이름

        Returns:
            str: 생성된 이슈 요약
        """
        try:
            # 이슈 타입별 카운트
            issue_type_counts = {}
            error_count = 0
            warning_count = 0

            for issue in issues:
                # 심각도별 카운트
                if issue.severity == "error":
                    error_count += 1
                elif issue.severity == "warning":
                    warning_count += 1

                # 타입별 카운트
                if issue.issue_type not in issue_type_counts:
                    issue_type_counts[issue.issue_type] = 0
                issue_type_counts[issue.issue_type] += 1

            # 기본 요약 정보
            total_issue_count = len(issues)
            issue_type_count = len(issue_type_counts)

            if total_issue_count == 0:
                return f"룰 '{rule_name}' 검증이 완료되었습니다. 문제가 발견되지 않았습니다."

            # 요약 문장 구성
            summary_parts = []

            # 전체 이슈 요약
            summary_parts.append(
                f"룰 '{rule_name}'에 총 {issue_type_count}가지 유형, {total_issue_count}건의 오류가 발견되었습니다."
            )

            # 심각도별 요약
            if error_count > 0:
                summary_parts.append(
                    f"심각한 {error_count}개의 오류를 수정해야 룰이 정상 작동합니다."
                )

            if error_count == 0 and warning_count > 0:
                summary_parts.append(
                    f"{warning_count}개의 경고가 있지만 룰은 작동 가능합니다."
                )

            summary = " ".join(summary_parts)

            self.logger.debug(f"이슈 요약 생성 완료: {total_issue_count}건")
            return summary

        except Exception as e:
            self.logger.error(
                f"이슈 요약 생성 중 오류: {str(e)}", exc_info=True
            )
            return f"룰 '{rule_name}' 이슈 요약을 생성할 수 없습니다."

    def optimize_issues(
        self, issues: List[ConditionIssue]
    ) -> List[ConditionIssue]:
        """
        이슈 중복 제거 및 우선순위 최적화

        Args:
            issues (List[ConditionIssue]): 최적화할 이슈들

        Returns:
            List[ConditionIssue]: 최적화된 이슈들
        """
        try:
            # 필드별로 이슈 그룹화
            field_issues: Dict[str, List[ConditionIssue]] = {}

            for issue in issues:
                field_key = (
                    str(issue.field) if issue.field is not None else "null"
                )
                if field_key not in field_issues:
                    field_issues[field_key] = []
                field_issues[field_key].append(issue)

            # 최적화된 이슈 목록
            optimized = []

            for field_key, field_issue_list in field_issues.items():
                # 같은 타입의 이슈 합치기
                issue_by_type: Dict[str, List[ConditionIssue]] = {}

                # 모순 이슈 존재 여부 확인
                has_contradiction = any(
                    issue.issue_type == "self_contradiction"
                    for issue in field_issue_list
                )

                for issue in field_issue_list:
                    # 같은 필드에 모순과 중복이 함께 있는 경우, 중복은 제외
                    if (
                        has_contradiction
                        and issue.issue_type == "duplicate_condition"
                    ):
                        continue

                    if issue.issue_type not in issue_by_type:
                        issue_by_type[issue.issue_type] = []
                    issue_by_type[issue.issue_type].append(issue)

                # 각 타입별로 중요도를 고려하여 이슈 추가
                issue_type_priority = self._get_issue_type_priority()

                # 우선순위에 따라 이슈 타입 정렬
                sorted_issue_types = sorted(
                    issue_by_type.keys(),
                    key=lambda x: issue_type_priority.get(x, 999),
                )

                for issue_type in sorted_issue_types:
                    type_issues = issue_by_type[issue_type]

                    if len(type_issues) == 1:
                        # 단일 이슈는 그대로 추가
                        optimized.append(type_issues[0])
                    else:
                        # 여러 개의 같은 타입 이슈는 합쳐서 추가
                        combined_issue = self._combine_similar_issues(
                            type_issues
                        )
                        optimized.append(combined_issue)

            # 최종 정렬: 심각도(error > warning)와 이슈 타입 우선순위로
            issue_type_priority = self._get_issue_type_priority()
            final_sorted = sorted(
                optimized,
                key=lambda x: (
                    0 if x.severity == "error" else 1,  # error가 먼저
                    issue_type_priority.get(
                        x.issue_type, 999
                    ),  # 이슈 타입 우선순위
                ),
            )

            self.logger.info(
                f"이슈 최적화 완료: {len(issues)} → {len(final_sorted)}건"
            )
            return final_sorted

        except Exception as e:
            self.logger.error(f"이슈 최적화 중 오류: {str(e)}", exc_info=True)
            return issues  # 오류 시 원본 반환

    def _get_issue_type_priority(self) -> Dict[str, int]:
        """
        이슈 타입별 우선순위 반환

        Returns:
            Dict[str, int]: 이슈 타입과 우선순위 매핑 (낮을수록 높은 우선순위)
        """
        return {
            "self_contradiction": 0,  # 가장 높은 우선순위
            "invalid_operator": 1,
            "type_mismatch": 2,
            "ambiguous_branch": 3,
            "missing_condition": 4,
            "complexity_warning": 5,
            "duplicate_condition": 6,  # 가장 낮은 우선순위
        }

    def _combine_similar_issues(
        self, issues: List[ConditionIssue]
    ) -> ConditionIssue:
        """
        유사한 이슈들을 하나로 통합

        Args:
            issues (List[ConditionIssue]): 통합할 이슈들

        Returns:
            ConditionIssue: 통합된 이슈
        """
        if not issues:
            raise ValueError("통합할 이슈가 없습니다")

        if len(issues) == 1:
            return issues[0]

        # 첫 번째 이슈를 기반으로 통합
        base_issue = issues[0]

        # 위치 정보 통합
        locations = []
        explanations = []

        for issue in issues:
            if issue.location and issue.location not in locations:
                locations.append(issue.location)
            if issue.explanation and issue.explanation not in explanations:
                explanations.append(issue.explanation)

        # 통합된 이슈 생성
        combined_issue = ConditionIssue(
            field=base_issue.field,
            issue_type=base_issue.issue_type,
            severity=base_issue.severity,
            location=", ".join(locations),
            explanation=". ".join([e.rstrip(";,. ") for e in explanations]),
            suggestion=base_issue.suggestion,
            ai_explanation=base_issue.ai_explanation,
            ai_suggestion=base_issue.ai_suggestion,
            impact_level=base_issue.impact_level,
            affected_scenarios=base_issue.affected_scenarios,
        )

        return combined_issue

    def _get_field_type_description(self, field: str) -> str:
        """
        필드 타입에 대한 설명 반환

        Args:
            field (str): 필드명

        Returns:
            str: 필드 타입 설명
        """
        field_type = self.condition_analyzer.get_field_type(field)

        type_descriptions = {
            "string": "문자열",
            "number": "숫자",
            "boolean": "참/거짓",
            "date": "날짜",
            "array": "배열",
            "logical": "논리 연산자",
        }

        return type_descriptions.get(field_type, "알 수 없는 타입")

    def _get_human_readable_operator(self, operator: str) -> str:
        """
        연산자를 사람이 이해하기 쉬운 표현으로 변환

        Args:
            operator (str): 연산자

        Returns:
            str: 사람이 읽기 쉬운 연산자 표현
        """
        operator_map = {
            "eq": "같다(==)",
            "==": "같다(==)",
            "neq": "같지 않다(!=)",
            "!=": "같지 않다(!=)",
            "gt": "보다 크다(>)",
            ">": "보다 크다(>)",
            "gte": "보다 크거나 같다(>=)",
            ">=": "보다 크거나 같다(>=)",
            "lt": "보다 작다(<)",
            "<": "보다 작다(<)",
            "lte": "보다 작거나 같다(<=)",
            "<=": "보다 작거나 같다(<=)",
            "in": "목록에 포함됨(in)",
            "not_in": "목록에 포함되지 않음(not_in)",
            "contains": "포함한다(contains)",
            "starts_with": "로 시작한다(starts_with)",
            "ends_with": "로 끝난다(ends_with)",
            "and": "그리고(and)",
            "or": "또는(or)",
        }

        return operator_map.get(operator, operator)

    def calculate_issue_counts(
        self, issues: List[ConditionIssue]
    ) -> Dict[str, int]:
        """
        이슈 타입별 개수 계산

        Args:
            issues (List[ConditionIssue]): 계산할 이슈들

        Returns:
            Dict[str, int]: 이슈 타입별 개수
        """
        issue_counts = {}

        for issue in issues:
            if issue.issue_type not in issue_counts:
                issue_counts[issue.issue_type] = 0
            issue_counts[issue.issue_type] += 1

        return issue_counts
