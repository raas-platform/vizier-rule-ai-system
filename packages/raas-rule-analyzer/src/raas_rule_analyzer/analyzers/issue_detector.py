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

import itertools
import logging
from typing import Any, Dict, List, Optional

from ..models import Rule, RuleCondition, ConditionIssue
from ..exceptions import IssueDetectionError
from .condition_analyzer import ConditionAnalyzer


# 품질 임계값 상수
class QualityThresholds:
    MAX_COMPLEXITY_SCORE = 50
    MAX_DEPTH = 5
    MAX_CONDITIONS_PER_FIELD = 10


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
        self.logger = logging.getLogger(__name__)
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

            # 8. 중복 이슈 제거
            all_issues = self._remove_duplicate_issues(all_issues)

            self.logger.info(f"이슈 검출 완료: 총 {len(all_issues)}건")
            return all_issues

        except Exception as e:
            self.logger.error(f"이슈 검출 중 오류: {str(e)}", exc_info=True)
            raise IssueDetectionError(f"이슈 검출 실패: {str(e)}")

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
                            keyName=condition.keyName,
                            issue_type="duplicate_condition",
                            severity="warning",
                            message=f"동일한 조건이 {original_path} 위치에도 존재합니다.",
                            suggestion="중복된 조건을 제거하거나 다른 조건으로 변경하세요.",
                            details={"location": current_path, "original_location": original_path}
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
                    or not condition.keyName
                    or condition.keyName == "placeholder"
                ):
                    continue

                current_path = f"{path}.{i}" if path else str(i)

                if not self.condition_analyzer.is_valid_type(
                    condition.keyName, condition.value
                ):
                    expected_type = self.condition_analyzer.get_field_type(
                        condition.keyName
                    )
                    actual_type = self.condition_analyzer._infer_type_from_value(
                        condition.value
                    )

                    issue = ConditionIssue(
                        keyName=condition.keyName,
                        issue_type="type_mismatch",
                        severity="error",
                        message=(
                            f"필드 '{condition.keyName}'는 {expected_type} 타입이지만 "
                            f"{actual_type} 값이 사용되었습니다."
                        ),
                        suggestion=f"값을 {expected_type} 타입으로 변경하거나 필드를 확인하세요.",
                        details={
                            "location": current_path,
                            "expected_type": expected_type,
                            "actual_type": actual_type,
                            "value": condition.value
                        }
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
                    or not condition.keyName
                    or condition.keyName == "placeholder"
                    or not condition.operator
                ):
                    continue

                current_path = f"{path}.{i}" if path else str(i)

                if not self.condition_analyzer.is_valid_operator(
                    condition.keyName, condition.operator
                ):
                    field_type = self.condition_analyzer.get_field_type(
                        condition.keyName
                    )
                    valid_operators = self.condition_analyzer._valid_operators.get(
                        field_type, []
                    )

                    issue = ConditionIssue(
                        keyName=condition.keyName,
                        issue_type="invalid_operator",
                        severity="error",
                        message=(
                            f"필드 '{condition.keyName}' ({field_type})에 "
                            f"'{condition.operator}' 연산자는 사용할 수 없습니다."
                        ),
                        suggestion=f"다음 연산자 중 하나를 사용하세요: {', '.join(valid_operators)}",
                        details={
                            "location": current_path,
                            "field_type": field_type,
                            "invalid_operator": condition.operator,
                            "valid_operators": valid_operators
                        }
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
        issues = []

        def collect_field_conditions(condition_list, parent_path=""):
            field_conditions = {}
            
            for i, condition in enumerate(condition_list):
                if condition is None:
                    continue
                    
                current_path = f"{parent_path}.{i}" if parent_path else str(i)
                
                if condition.keyName and condition.keyName != "placeholder":
                    field = condition.keyName
                    if field not in field_conditions:
                        field_conditions[field] = []
                    
                    field_conditions[field].append({
                        "condition": condition,
                        "path": current_path,
                        "operator": condition.operator,
                        "value": condition.value
                    })
                
                if condition.conditions:
                    nested_conditions = collect_field_conditions(condition.conditions, current_path)
                    for field, conds in nested_conditions.items():
                        if field not in field_conditions:
                            field_conditions[field] = []
                        field_conditions[field].extend(conds)
            
            return field_conditions

        field_conditions = collect_field_conditions(conditions)
        
        for field, conds in field_conditions.items():
            if len(conds) < 2:
                continue
                
            # 같은 필드의 조건들 간 모순 검사
            for i in range(len(conds)):
                for j in range(i + 1, len(conds)):
                    cond1 = conds[i]
                    cond2 = conds[j]
                    
                    if self._check_contradiction(cond1, cond2):
                        issue = ConditionIssue(
                            keyName=field,
                            issue_type="self_contradiction",
                            severity="error",
                            message=(
                                f"필드 '{field}'에 모순되는 조건이 있습니다: "
                                f"{cond1['operator']} {cond1['value']} vs "
                                f"{cond2['operator']} {cond2['value']}"
                            ),
                            suggestion="모순되는 조건 중 하나를 제거하거나 수정하세요.",
                            details={
                                "condition1": {"path": cond1["path"], "operator": cond1["operator"], "value": cond1["value"]},
                                "condition2": {"path": cond2["path"], "operator": cond2["operator"], "value": cond2["value"]}
                            }
                        )
                        issues.append(issue)

        return issues

    def _check_contradiction(self, cond1: Dict[str, Any], cond2: Dict[str, Any]) -> bool:
        """두 조건 간의 모순 여부 확인"""
        op1, val1 = cond1["operator"], cond1["value"]
        op2, val2 = cond2["operator"], cond2["value"]
        
        try:
            # 숫자 값인 경우
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # 같은 값에 대한 모순 검사
                if val1 == val2:
                    if (op1 == "==" and op2 == "!=") or (op1 == "!=" and op2 == "=="):
                        return True
                    if (op1 == ">" and op2 == "<=") or (op1 == "<=" and op2 == ">"):
                        return True
                    if (op1 == "<" and op2 == ">=") or (op1 == ">=" and op2 == "<"):
                        return True
                
                # 범위 모순 검사
                if op1 == ">" and op2 == "<" and val1 >= val2:
                    return True
                if op1 == ">=" and op2 == "<=" and val1 > val2:
                    return True
            
            # 문자열 값인 경우
            elif isinstance(val1, str) and isinstance(val2, str):
                if val1 == val2:
                    if (op1 == "==" and op2 == "!=") or (op1 == "!=" and op2 == "=="):
                        return True
                    if (op1 == "contains" and op2 == "not_contains"):
                        return True
        
        except (TypeError, ValueError):
            pass
        
        return False

    def detect_missing_conditions(
        self, rule: Rule, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """누락 조건 검출"""
        issues = []
        
        # 기본적인 누락 조건 검사
        field_conditions = {}
        
        def collect_conditions(condition_list):
            for condition in condition_list:
                if condition.keyName and condition.keyName != "placeholder":
                    field = condition.keyName
                    if field not in field_conditions:
                        field_conditions[field] = []
                    field_conditions[field].append(condition)
                
                if condition.conditions:
                    collect_conditions(condition.conditions)
        
        collect_conditions(conditions)
        
        # 숫자 필드의 범위 누락 검사
        for field, conds in field_conditions.items():
            field_type = self.condition_analyzer.get_field_type(field)
            
            if field_type == "number" and len(conds) > 1:
                # 숫자 범위의 누락 구간 검사
                numeric_conditions = []
                for cond in conds:
                    if isinstance(cond.value, (int, float)):
                        numeric_conditions.append({
                            "operator": cond.operator,
                            "value": cond.value
                        })
                
                if len(numeric_conditions) >= 2:
                    missing_ranges = self._check_missing_ranges(numeric_conditions)
                    for missing_range in missing_ranges:
                        issue = ConditionIssue(
                            keyName=field,
                            issue_type="missing_condition",
                            severity="warning",
                            message=f"필드 '{field}'에서 {missing_range} 범위가 누락되었습니다.",
                            suggestion="누락된 범위에 대한 조건을 추가하세요.",
                            details={"missing_range": missing_range}
                        )
                        issues.append(issue)
        
        return issues

    def _check_missing_ranges(self, conditions: List[Dict[str, Any]]) -> List[str]:
        """숫자 조건에서 누락된 범위 검사"""
        missing_ranges = []
        
        # 간단한 범위 누락 검사 (예시)
        values = []
        for cond in conditions:
            if cond["operator"] in ["==", ">=", "<=", ">", "<"]:
                values.append(cond["value"])
        
        if len(values) >= 2:
            values.sort()
            # 연속된 값들 사이의 간격이 큰 경우 누락으로 간주
            for i in range(len(values) - 1):
                if values[i + 1] - values[i] > 100:  # 임계값
                    missing_ranges.append(f"{values[i]} ~ {values[i + 1]}")
        
        return missing_ranges

    def detect_ambiguous_branches(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """분기 불명확성 검출"""
        issues = []
        
        # OR 조건에서의 불명확성 검사
        def check_ambiguity(condition_list, path=""):
            for i, condition in enumerate(condition_list):
                if condition is None:
                    continue
                
                current_path = f"{path}.{i}" if path else str(i)
                
                # OR 논리 연산자인 경우
                if (condition.operator == "or" or condition.logicType == "OR") and condition.conditions:
                    # OR 조건 내의 필드들이 겹치는지 확인
                    fields_in_or = set()
                    for or_condition in condition.conditions:
                        if or_condition.keyName and or_condition.keyName != "placeholder":
                            fields_in_or.add(or_condition.keyName)
                    
                    # 같은 필드가 OR 조건에 여러 번 나타나는 경우
                    if len(fields_in_or) < len([c for c in condition.conditions if c.keyName and c.keyName != "placeholder"]):
                        issue = ConditionIssue(
                            keyName=None,
                            issue_type="ambiguous_branch",
                            severity="warning",
                            message="OR 조건에서 같은 필드가 여러 번 사용되어 분기가 불명확합니다.",
                            suggestion="OR 조건을 단순화하거나 필드별로 조건을 정리하세요.",
                            details={"location": current_path, "fields": list(fields_in_or)}
                        )
                        issues.append(issue)
                
                if condition.conditions:
                    check_ambiguity(condition.conditions, current_path)
        
        check_ambiguity(conditions)
        return issues

    def detect_complexity_warnings(
        self, conditions: List[RuleCondition], complexity_score: int
    ) -> List[ConditionIssue]:
        """복잡성 경고 검출"""
        issues = []
        
        # 복잡도 점수 기반 경고
        if complexity_score > QualityThresholds.MAX_COMPLEXITY_SCORE:
            issue = ConditionIssue(
                keyName=None,
                issue_type="complexity_warning",
                severity="warning",
                message=f"룰의 복잡도가 높습니다 (점수: {complexity_score})",
                suggestion="룰을 더 간단한 여러 룰로 분리하는 것을 고려하세요.",
                details={"complexity_score": complexity_score, "threshold": QualityThresholds.MAX_COMPLEXITY_SCORE}
            )
            issues.append(issue)
        
        # 깊이 기반 경고
        max_depth = self._calculate_depth(conditions)
        if max_depth > QualityThresholds.MAX_DEPTH:
            issue = ConditionIssue(
                keyName=None,
                issue_type="complexity_warning",
                severity="warning",
                message=f"룰의 중첩 깊이가 너무 깊습니다 (깊이: {max_depth})",
                suggestion="중첩된 조건을 평면화하거나 룰을 분리하세요.",
                details={"max_depth": max_depth, "threshold": QualityThresholds.MAX_DEPTH}
            )
            issues.append(issue)
        
        # 필드별 조건 수 기반 경고
        field_counts = {}
        self._count_field_conditions(conditions, field_counts)
        
        for field, count in field_counts.items():
            if count > QualityThresholds.MAX_CONDITIONS_PER_FIELD:
                issue = ConditionIssue(
                    keyName=field,
                    issue_type="complexity_warning",
                    severity="warning",
                    message=f"필드 '{field}'에 너무 많은 조건이 있습니다 (개수: {count})",
                    suggestion="조건을 통합하거나 다른 필드로 분산하세요.",
                    details={"condition_count": count, "threshold": QualityThresholds.MAX_CONDITIONS_PER_FIELD}
                )
                issues.append(issue)
        
        return issues

    def _calculate_depth(
        self, conditions: List[RuleCondition], current_depth: int = 1
    ) -> int:
        """조건 트리의 최대 깊이 계산"""
        if not conditions:
            return current_depth

        max_depth = current_depth

        for condition in conditions:
            if condition.conditions:
                nested_depth = self._calculate_depth(
                    condition.conditions, current_depth + 1
                )
                max_depth = max(max_depth, nested_depth)

        return max_depth

    def _count_field_conditions(
        self, conditions: List[RuleCondition], field_counts: Dict[str, int]
    ):
        """필드별 조건 개수 계산"""
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                field = condition.keyName
                field_counts[field] = field_counts.get(field, 0) + 1
            
            if condition.conditions:
                self._count_field_conditions(condition.conditions, field_counts)

    def _create_condition_signature(self, condition: RuleCondition) -> str:
        """조건의 고유 시그니처 생성"""
        if not condition.keyName or condition.keyName == "placeholder":
            return "unknown"
        
        # 기본 시그니처: 필드명 + 연산자 + 값
        signature = f"{condition.keyName}|{condition.operator}|{condition.value}"
        
        # 필드 데이터 타입도 포함
        if condition.fieldDataType:
            signature += f"|{condition.fieldDataType}"
        
        return signature

    def _remove_duplicate_issues(self, issues: List[ConditionIssue]) -> List[ConditionIssue]:
        """중복 이슈 제거"""
        seen = set()
        unique_issues = []
        
        for issue in issues:
            # 이슈 식별자 생성
            identifier = f"{issue.keyName}|{issue.issue_type}|{issue.message}"
            
            if identifier not in seen:
                seen.add(identifier)
                unique_issues.append(issue)
        
        return unique_issues 