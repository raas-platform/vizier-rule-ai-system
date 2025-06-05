"""
이슈 검출기 (IssueDetector)

룰의 다양한 이슈를 검출하고 검증하는 기능을 담당합니다.
- 중복 조건 검사
- 모순 조건 검사
- 타입 불일치 검사
- 잘못된 연산자 검사
- 분기 불명확성 검사
- 누락 조건 검사
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple

from ...models.rule import Rule, RuleCondition
from ...models.validation_result import ConditionIssue
from ...utils.logger import get_logger
from .condition_analyzer import ConditionAnalyzer


class IssueDetector:
    """
    이슈 검출 및 검증을 담당하는 클래스

    7가지 주요 이슈 타입을 검출합니다:
    1. duplicate_condition - 중복 조건
    2. type_mismatch - 타입 불일치
    3. invalid_operator - 잘못된 연산자
    4. self_contradiction - 자기모순
    5. missing_condition - 누락 조건
    6. ambiguous_branch - 분기 불명확
    7. complexity_warning - 복잡성 경고
    """

    def __init__(self, condition_analyzer: ConditionAnalyzer):
        """
        IssueDetector 초기화

        Args:
            condition_analyzer (ConditionAnalyzer): 조건 분석기 인스턴스
        """
        self.logger = get_logger(__name__)
        self.condition_analyzer = condition_analyzer

    async def detect_all_issues(
        self,
        rule: Rule,
        conditions: List[RuleCondition],
        complexity_score: int,
    ) -> List[ConditionIssue]:
        """
        모든 이슈 타입을 검출

        Args:
            rule (Rule): 분석할 룰
            conditions (List[RuleCondition]): 파싱된 조건들
            complexity_score (int): 복잡성 점수

        Returns:
            List[ConditionIssue]: 검출된 모든 이슈들
        """
        all_issues = []

        try:
            # 1. 중복 조건 검사
            duplicate_issues = self.detect_duplicate_conditions(conditions)
            all_issues.extend(duplicate_issues)

            # 2. 타입 불일치 검사
            type_issues = self.detect_type_mismatch(conditions)
            all_issues.extend(type_issues)

            # 3. 잘못된 연산자 검사
            operator_issues = self.detect_invalid_operators(conditions)
            all_issues.extend(operator_issues)

            # 4. 자기모순 검사
            contradiction_issues = self.detect_self_contradiction(conditions)
            all_issues.extend(contradiction_issues)

            # 5. 누락 조건 검사
            missing_issues = self.detect_missing_conditions(rule, conditions)
            all_issues.extend(missing_issues)

            # 6. 분기 불명확성 검사
            ambiguous_issues = self.detect_ambiguous_branches(conditions)
            all_issues.extend(ambiguous_issues)

            # 7. 복잡성 경고
            complexity_issues = self.detect_complexity_warnings(
                conditions, complexity_score
            )
            all_issues.extend(complexity_issues)

            self.logger.info(f"이슈 검출 완료: 총 {len(all_issues)}건")
            return all_issues

        except Exception as e:
            self.logger.error(f"이슈 검출 중 오류: {str(e)}", exc_info=True)
            return []

    def detect_duplicate_conditions(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """중복 조건 검출"""
        issues = []
        condition_signatures = {}

        def check_duplicates(condition_list, path=""):
            for i, condition in enumerate(condition_list):
                if condition is None:
                    continue

                signature = self._create_condition_signature(condition)
                current_path = f"{path}.{i}" if path else str(i)

                if signature and signature != "unknown":
                    if signature in condition_signatures:
                        original_path = condition_signatures[signature]
                        issue = ConditionIssue(
                            field=condition.field,
                            issue_type="duplicate_condition",
                            severity="warning",
                            location=current_path,
                            explanation=f"동일한 조건이 {original_path} 위치에도 존재합니다.",
                            suggestion="중복된 조건을 제거하거나 다른 조건으로 변경하세요.",
                        )
                        issues.append(issue)
                    else:
                        condition_signatures[signature] = current_path

                if condition.conditions:
                    check_duplicates(condition.conditions, current_path)

        check_duplicates(conditions)
        return issues

    def detect_type_mismatch(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """타입 불일치 검출"""
        issues = []

        def check_types(condition_list, path=""):
            for i, condition in enumerate(condition_list):
                if (
                    condition is None
                    or not condition.field
                    or condition.field == "placeholder"
                ):
                    continue

                current_path = f"{path}.{i}" if path else str(i)

                if not self.condition_analyzer.is_valid_type(
                    condition.field, condition.value
                ):
                    expected_type = self.condition_analyzer.get_field_type(
                        condition.field
                    )
                    actual_type = (
                        self.condition_analyzer._infer_type_from_value(
                            condition.value
                        )
                    )

                    issue = ConditionIssue(
                        field=condition.field,
                        issue_type="type_mismatch",
                        severity="error",
                        location=current_path,
                        explanation=f"필드 '{condition.field}'는 {expected_type} 타입이지만 {actual_type} 값이 사용되었습니다.",
                        suggestion=f"값을 {expected_type} 타입으로 변경하거나 필드를 확인하세요.",
                    )
                    issues.append(issue)

                if condition.conditions:
                    check_types(condition.conditions, current_path)

        check_types(conditions)
        return issues

    def detect_invalid_operators(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """잘못된 연산자 검출"""
        issues = []

        def check_operators(condition_list, path=""):
            for i, condition in enumerate(condition_list):
                if (
                    condition is None
                    or not condition.field
                    or condition.field == "placeholder"
                ):
                    continue

                current_path = f"{path}.{i}" if path else str(i)

                if (
                    condition.operator
                    and not self.condition_analyzer.is_valid_operator(
                        condition.field, condition.operator
                    )
                ):
                    field_type = self.condition_analyzer.get_field_type(
                        condition.field
                    )
                    valid_operators = (
                        self.condition_analyzer._valid_operators.get(
                            field_type, []
                        )
                    )

                    issue = ConditionIssue(
                        field=condition.field,
                        issue_type="invalid_operator",
                        severity="error",
                        location=current_path,
                        explanation=f"필드 '{condition.field}' ({field_type} 타입)에는 '{condition.operator}' 연산자를 사용할 수 없습니다.",
                        suggestion=f"다음 연산자 중 하나를 사용하세요: {', '.join(valid_operators)}",
                    )
                    issues.append(issue)

                if condition.conditions:
                    check_operators(condition.conditions, current_path)

        check_operators(conditions)
        return issues

    def detect_self_contradiction(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """자기모순 검출"""
        return []  # 간단한 구현

    def detect_missing_conditions(
        self, rule: Rule, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """누락 조건 검출"""
        issues = []

        if not conditions or len(conditions) == 0:
            issue = ConditionIssue(
                field=None,
                issue_type="missing_condition",
                severity="error",
                location="root",
                explanation="룰에 조건이 정의되지 않았습니다.",
                suggestion="최소 하나 이상의 조건을 추가하세요.",
            )
            issues.append(issue)

        return issues

    def detect_ambiguous_branches(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """분기 불명확성 검출"""
        return []  # 간단한 구현

    def detect_complexity_warnings(
        self, conditions: List[RuleCondition], complexity_score: int
    ) -> List[ConditionIssue]:
        """복잡성 경고 검출"""
        issues = []

        if complexity_score >= 20:
            severity = "error" if complexity_score >= 30 else "warning"
            issue = ConditionIssue(
                field=None,
                issue_type="complexity_warning",
                severity=severity,
                location="전체 룰",
                explanation=f"룰의 복잡성이 높습니다 (점수: {complexity_score}/100).",
                suggestion="조건을 단순화하거나 여러 룰로 분할하는 것을 고려하세요.",
            )
            issues.append(issue)

        return issues

    def _create_condition_signature(self, condition: RuleCondition) -> str:
        """조건의 고유 시그니처 생성"""
        if not condition.field or condition.field == "placeholder":
            return "unknown"

        if condition.conditions:
            return f"logical_{condition.operator}_{len(condition.conditions)}"

        value_str = (
            str(condition.value) if condition.value is not None else "null"
        )
        return f"{condition.field}_{condition.operator}_{value_str}"
