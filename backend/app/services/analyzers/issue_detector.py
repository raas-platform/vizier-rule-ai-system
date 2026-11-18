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

from typing import Any, Dict, List, Optional

from ...constants import QualityThresholds
from ...models.rule import Rule, RuleCondition
from ...models.validation_result import ConditionIssue
from ...utils.logger import get_logger
from ...utils.operators import (
    display_operator,
    is_list_operator,
    normalize_operator,
    split_list_value,
    to_number,
)
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
        raw_rule: Optional[Rule] = None,
    ) -> List[ConditionIssue]:
        """
        모든 이슈 타입을 검출

        Args:
            rule (Rule): 분석할 룰
            conditions (List[RuleCondition]): 파싱된 조건들
            complexity_score (int): 복잡성 점수
            raw_rule (Rule, optional): 파싱 전 원본 룰 (AND/OR 구조·원래 값 보존용)

        Returns:
            List[ConditionIssue]: 검출된 모든 이슈들
        """
        all_issues = []

        try:
            # 1. 중복 조건 검사
            duplicate_issues = self.detect_duplicate_conditions(conditions)
            all_issues.extend(duplicate_issues)

            # 1-1. JSON 직접 분석으로 누락된 이슈 검출 (긴급 패치)
            direct_issues = self.detect_issues_from_rule_direct(rule)
            all_issues.extend(direct_issues)

            # 2. 타입 불일치 검사
            type_issues = self.detect_type_mismatch(conditions)
            all_issues.extend(type_issues)

            # 3. 잘못된 연산자 검사
            operator_issues = self.detect_invalid_operators(conditions)
            all_issues.extend(operator_issues)

            # 4. 자기모순 검사 (AND/OR 구조를 보존한 트리 기준)
            tree_root = self._build_logic_tree(raw_rule or rule, conditions)
            contradiction_issues = self.detect_self_contradiction(
                conditions, tree_root=tree_root
            )
            all_issues.extend(contradiction_issues)

            # 4-1. 트리 구조 검사: 빈 하위 그룹, 빈 필드 키, 불리언 값
            structure_issues = self.detect_tree_structure_issues(tree_root)
            if any(i.explanation.startswith("필드 키가 비어") for i in structure_issues):
                # '조건이 정의되지 않았습니다'(root)보다 구체적인 원인이 있으면 대체
                all_issues = [
                    i
                    for i in all_issues
                    if not (i.issue_type == "missing_condition" and i.location == "root")
                ]
            all_issues.extend(structure_issues)

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

            # 8. 중복 이슈 제거 (같은 조건·같은 유형은 하나로, 서로 다른 조건의 이슈는 각각 유지)
            all_issues = self._remove_duplicate_issues(all_issues)

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
                            condUuid=self._get_condition_uuid(condition),
                            keyName=condition.keyName,
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
                    or not condition.keyName
                    or condition.keyName == "placeholder"
                ):
                    continue

                current_path = f"{path}.{i}" if path else str(i)

                if is_list_operator(condition.operator):
                    # IN / NOT IN: 콤마로 나눈 항목마다 검사
                    issues.extend(self._list_value_issues(condition, current_path))
                elif not self.condition_analyzer.is_valid_type(
                    condition.keyName, condition.value
                ):
                    expected_type = self.condition_analyzer.get_field_type(
                        condition.keyName
                    )
                    actual_type = self.condition_analyzer._infer_type_from_value(
                        condition.value
                    )

                    issue = ConditionIssue(
                        condUuid=self._get_condition_uuid(condition),
                        keyName=condition.keyName,
                        issue_type="type_mismatch",
                        severity="error",
                        location=current_path,
                        explanation=(
                            f"필드 '{condition.keyName}'는 {expected_type} 타입이지만 "
                            f"{actual_type} 값이 사용되었습니다."
                        ),
                        suggestion=f"값을 {expected_type} 타입으로 변경하거나 필드를 확인하세요.",
                    )
                    issues.append(issue)

                if condition.conditions:
                    check_types(condition.conditions, current_path)

        check_types(conditions)
        return issues

    def _list_value_issues(
        self, condition: RuleCondition, path: str
    ) -> List[ConditionIssue]:
        """IN / NOT IN 값 검사: 빈 항목(오류), 숫자 필드의 숫자 아닌 항목(오류), 중복 항목(경고)"""
        issues: List[ConditionIssue] = []
        key = condition.keyName
        op_text = display_operator(condition.operator)
        field_type = self.condition_analyzer.get_field_type(key)
        items = split_list_value(condition.value)
        cond_uuid = self._get_condition_uuid(condition)

        empty_positions = [str(n + 1) for n, item in enumerate(items) if item == ""]
        if empty_positions:
            if len(items) == 1:
                where = "값이 비어 있습니다"
            else:
                where = (
                    f"{len(items)}개 항목 중 {', '.join(empty_positions)}번째 항목이 "
                    f"비어 있습니다 (값: '{condition.value}')"
                )
            issues.append(
                ConditionIssue(
                    condUuid=cond_uuid,
                    keyName=key,
                    issue_type="type_mismatch",
                    severity="error",
                    location=path,
                    explanation=f"필드 '{key}'의 {op_text} 값에 빈 항목이 있습니다: {where}.",
                    suggestion=(
                        f"{op_text} 값은 '값1,값2,값3'처럼 콤마로 구분하고, "
                        "빈 항목이 없게 입력하세요."
                    ),
                )
            )

        filled = [item for item in items if item != ""]
        if field_type == "number":
            bad = [item for item in filled if to_number(item) is None]
            if bad:
                bad_text = ", ".join(f"'{b}'" for b in bad)
                issues.append(
                    ConditionIssue(
                        condUuid=cond_uuid,
                        keyName=key,
                        issue_type="type_mismatch",
                        severity="error",
                        location=path,
                        explanation=(
                            f"필드 '{key}'는 number 타입이지만 {op_text} 값에 숫자가 "
                            f"아닌 항목이 있습니다: {bad_text}."
                        ),
                        suggestion=f"{op_text} 값의 모든 항목을 숫자로 입력하세요.",
                    )
                )
            pairs = [(item, to_number(item)) for item in filled if to_number(item) is not None]
        else:
            pairs = [(item, item) for item in filled]

        # 중복 항목 (숫자 필드는 1과 1.0도 같은 값으로 본다)
        seen, dups = set(), []
        for item, k in pairs:
            if k in seen and item not in dups:
                dups.append(item)
            seen.add(k)
        if dups:
            dup_text = ", ".join(f"'{d}'" for d in dups)
            issues.append(
                ConditionIssue(
                    condUuid=cond_uuid,
                    keyName=key,
                    issue_type="duplicate_condition",
                    severity="warning",
                    location=path,
                    explanation=(
                        f"필드 '{key}'의 {op_text} 값에 같은 항목이 두 번 이상 있습니다: "
                        f"{dup_text}."
                    ),
                    suggestion="중복된 항목을 하나만 남기세요.",
                )
            )
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
                ):
                    continue

                current_path = f"{path}.{i}" if path else str(i)

                if (
                    condition.operator
                    and not self.condition_analyzer.is_valid_operator(
                        condition.keyName, condition.operator
                    )
                ):
                    field_type = self.condition_analyzer.get_field_type(
                        condition.keyName
                    )
                    valid_operators = self.condition_analyzer._valid_operators.get(
                        field_type, []
                    )

                    issue = ConditionIssue(
                        condUuid=self._get_condition_uuid(condition),
                        keyName=condition.keyName,
                        issue_type="invalid_operator",
                        severity="error",
                        location=current_path,
                        explanation=(
                            f"필드 '{condition.keyName}' ({field_type} 타입)에는 "
                            f"'{condition.operator}' 연산자를 사용할 수 없습니다."
                        ),
                        suggestion=(
                            "다음 연산자 중 하나를 사용하세요: "
                            f"{', '.join(display_operator(op) for op in valid_operators)}"
                        ),
                    )
                    issues.append(issue)

                if condition.conditions:
                    check_operators(condition.conditions, current_path)

        check_operators(conditions)
        return issues

    # ------------------------------------------------------------------
    # 논리 트리 (AND/OR 구조 보존)
    # ------------------------------------------------------------------
    @staticmethod
    def _attr(node: Any, name: str) -> Any:
        if node is None:
            return None
        if isinstance(node, dict):
            return node.get(name)
        return getattr(node, name, None)

    def _normalize_node(self, node: Any, path: str) -> Dict[str, Any]:
        """조건/그룹 노드를 {'kind': 'group'|'leaf', ...} 형태로 정규화"""
        key_name = self._attr(node, "keyName")
        logic = self._attr(node, "logicType")
        children = self._attr(node, "condition")
        if children is None:
            children = self._attr(node, "conditions")

        if not logic and key_name == "placeholder":
            op = str(self._attr(node, "operator") or "").upper()
            logic = op if op in ("AND", "OR") else "AND"

        if logic or (not key_name and children is not None):
            logic = str(logic or "AND").upper()
            return {
                "kind": "group",
                "logic": "OR" if logic == "OR" else "AND",
                "path": path,
                "children": [
                    self._normalize_node(child, f"{path}/{i + 1}" if path else str(i + 1))
                    for i, child in enumerate(children or [])
                    if child is not None
                ],
            }

        return {
            "kind": "leaf",
            "path": path,
            "keyName": key_name or "",
            "operator": self._attr(node, "operator"),
            "value": self._attr(node, "value"),
            "fieldDataType": self._attr(node, "fieldDataType"),
            "condUuid": self._attr(node, "condUuid"),
        }

    def _build_logic_tree(
        self, rule: Rule, conditions: List[RuleCondition]
    ) -> Dict[str, Any]:
        """룰의 conditionTree에서 AND/OR 구조를 보존한 트리를 만든다."""
        tree = getattr(rule, "conditionTree", None)
        if tree is not None:
            root = self._normalize_node(tree, "")
            if root["kind"] == "group":
                return root
        # conditionTree가 없으면 파싱된 조건(중첩 포함)을 AND로 묶어 사용
        return {
            "kind": "group",
            "logic": "AND",
            "path": "",
            "children": [
                self._normalize_node(c, str(i + 1))
                for i, c in enumerate(conditions or [])
                if c is not None
            ],
        }

    # ------------------------------------------------------------------
    # 자기모순 검사
    # ------------------------------------------------------------------
    def detect_self_contradiction(
        self,
        conditions: List[RuleCondition],
        tree_root: Optional[Dict[str, Any]] = None,
    ) -> List[ConditionIssue]:
        """
        자기모순 검출.

        '동시에 만족해야 하는' 조건끼리만 비교한다.
        - 같은 AND 그룹(및 그 안에 중첩된 AND 그룹)의 조건들은 한 묶음(AND 체인)
        - OR의 각 가지는 서로 독립된 묶음이므로 가지 사이의 조건은 비교하지 않는다.
        """
        if tree_root is None:
            tree_root = {
                "kind": "group",
                "logic": "AND",
                "path": "",
                "children": [
                    self._normalize_node(c, str(i + 1))
                    for i, c in enumerate(conditions or [])
                    if c is not None
                ],
            }

        issues: List[ConditionIssue] = []

        def analyze_chain(leaves: List[Dict[str, Any]]) -> None:
            by_field: Dict[str, List[Dict[str, Any]]] = {}
            for leaf in leaves:
                key = leaf["keyName"]
                if key and key != "placeholder":
                    by_field.setdefault(key, []).append(leaf)

            for field, field_leaves in by_field.items():
                if len(field_leaves) < 2:
                    continue
                found = self._find_field_contradiction(field, field_leaves)
                if not found:
                    continue
                explanation, involved = found
                # 트리에서 앞선 조건이 먼저 오도록 정렬 (condUuid = 충돌 조건 중 첫 번째)
                involved = sorted(involved, key=lambda leaf: leaves.index(leaf))
                first = involved[0]
                issues.append(
                    ConditionIssue(
                        condUuid=first.get("condUuid"),
                        keyName=field,
                        issue_type="self_contradiction",
                        severity="error",
                        location=", ".join(leaf["path"] for leaf in involved),
                        explanation=f"자기모순: {explanation}",
                        suggestion=(
                            f"'{field}' 필드에 모순되는 조건이 있습니다. "
                            "충돌하는 조건을 검토하고 수정하세요."
                        ),
                    )
                )

        def process(node: Dict[str, Any]) -> None:
            if node["kind"] != "group":
                return
            if node["logic"] == "OR":
                for child in node["children"]:
                    process(child)
                return

            chain: List[Dict[str, Any]] = []

            def flatten(group: Dict[str, Any]) -> None:
                for child in group["children"]:
                    if child["kind"] == "leaf":
                        chain.append(child)
                    elif child["logic"] == "AND":
                        flatten(child)
                    else:  # OR 그룹: 각 가지는 별도 묶음
                        process(child)

            flatten(node)
            analyze_chain(chain)

        process(tree_root)
        self.logger.debug(f"Total contradiction issues found: {len(issues)}")
        return issues

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if isinstance(value, bool) or value is None:
            return None
        try:
            if isinstance(value, str) and not value.strip():
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _norm_text(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value).strip()

    def _find_field_contradiction(
        self, field: str, leaves: List[Dict[str, Any]]
    ):
        """한 AND 체인 안의 같은 필드 조건들이 동시에 성립할 수 없는지 판정.

        Returns:
            (설명, 관련 조건 목록) 또는 None
        """
        field_type = self.condition_analyzer.get_field_type(field)
        declared = str(leaves[0].get("fieldDataType") or "").lower()
        is_number = field_type == "number" or declared in ("number", "num", "int", "float")
        is_boolean = field_type == "boolean" or declared in ("boolean", "bool")

        if is_number:
            return self._number_contradiction(field, leaves)

        # 문자열/불리언 등: ==, != 만 비교
        eq: Dict[str, Dict[str, Any]] = {}
        ne: Dict[str, Dict[str, Any]] = {}
        for leaf in leaves:
            op = normalize_operator(leaf["operator"])
            if leaf["value"] is None or op not in ("==", "!="):
                continue
            text = self._norm_text(leaf["value"])
            if is_boolean:
                text = text.lower()
            (eq if op == "==" else ne).setdefault(text, leaf)

        if len(eq) > 1:
            (v1, l1), (v2, l2) = list(eq.items())[:2]
            return (
                f"{field} 필드가 '{v1}'와 '{v2}' 두 값과 동시에 같을 수 없음",
                [l1, l2],
            )
        for text, leaf in eq.items():
            if text in ne:
                return (
                    f"{field} 필드가 '{text}'와 같고 같지 않아야 함",
                    [leaf, ne[text]],
                )
        if is_boolean and "true" in ne and "false" in ne:
            return (
                f"{field} 필드가 true도 false도 아니어야 함",
                [ne["true"], ne["false"]],
            )
        if is_boolean:
            return None
        return self._list_contradiction(field, leaves, eq, is_number=False)

    def _number_contradiction(self, field: str, leaves: List[Dict[str, Any]]):
        """숫자 조건을 구간(하한/상한/포함 여부/==/!=)으로 합쳐 공집합인지 판정"""
        ops = {">", ">=", "<", "<=", "==", "!="}
        lo = hi = None  # (값, 포함 여부, leaf)
        eqs: Dict[float, Dict[str, Any]] = {}
        nes: Dict[float, Dict[str, Any]] = {}

        for leaf in leaves:
            num = self._to_float(leaf["value"])
            op = normalize_operator(leaf["operator"])
            if num is None or op not in ops:
                continue
            if op == "==":
                eqs.setdefault(num, leaf)
            elif op == "!=":
                nes.setdefault(num, leaf)
            elif op in (">", ">="):
                inclusive = op == ">="
                if lo is None or num > lo[0] or (num == lo[0] and lo[1] and not inclusive):
                    lo = (num, inclusive, leaf)
            else:
                inclusive = op == "<="
                if hi is None or num < hi[0] or (num == hi[0] and hi[1] and not inclusive):
                    hi = (num, inclusive, leaf)

        def fmt(n: float) -> str:
            return str(int(n)) if float(n).is_integer() else str(n)

        if len(eqs) > 1:
            (n1, l1), (n2, l2) = list(eqs.items())[:2]
            return (
                f"{field} 필드가 {fmt(n1)}와 {fmt(n2)} 두 값과 동시에 같을 수 없음",
                [l1, l2],
            )

        for n, leaf in eqs.items():
            if n in nes:
                return (
                    f"{field} 필드가 {fmt(n)}와 같고 같지 않아야 함",
                    [leaf, nes[n]],
                )
            if lo and (n < lo[0] or (n == lo[0] and not lo[1])):
                return (
                    f"{field} 필드가 {fmt(n)}와 같으면서 {fmt(lo[0])}"
                    f"{'보다 크거나 같을' if lo[1] else '보다 클'} 수 없음",
                    [lo[2], leaf],
                )
            if hi and (n > hi[0] or (n == hi[0] and not hi[1])):
                return (
                    f"{field} 필드가 {fmt(n)}와 같으면서 {fmt(hi[0])}"
                    f"{'보다 작거나 같을' if hi[1] else '보다 작을'} 수 없음",
                    [hi[2], leaf],
                )

        if lo and hi:
            empty = lo[0] > hi[0] or (lo[0] == hi[0] and not (lo[1] and hi[1]))
            if empty:
                return (
                    f"{field} 필드가 {fmt(lo[0])}"
                    f"{' 이상' if lo[1] else ' 초과'}이면서 {fmt(hi[0])}"
                    f"{' 이하' if hi[1] else ' 미만'}일 수 없음",
                    [lo[2], hi[2]],
                )
            if lo[0] == hi[0] and lo[0] in nes:
                return (
                    f"{field} 필드가 {fmt(lo[0])}와 같으면서 같지 않아야 함",
                    [lo[2], nes[lo[0]]],
                )
        return self._list_contradiction(field, leaves, eqs, is_number=True, lo=lo, hi=hi)

    @staticmethod
    def _fmt_value(value: Any, is_number: bool) -> str:
        if is_number:
            return str(int(value)) if float(value).is_integer() else str(value)
        return f"'{value}'"

    def _list_contradiction(
        self,
        field: str,
        leaves: List[Dict[str, Any]],
        eqs: Dict[Any, Dict[str, Any]],
        is_number: bool,
        lo: Optional[tuple] = None,
        hi: Optional[tuple] = None,
    ):
        """IN / NOT IN 조건과 다른 조건이 동시에 성립할 수 없는지 판정.

        - IN 집합과 == 값이 겹치지 않음
        - NOT IN 집합에 == 값이 들어 있음
        - (숫자) IN 집합의 모든 값이 범위 조건 밖
        - IN 두 개의 교집합이 없음
        값에 빈 항목이나(숫자 필드의) 숫자 아닌 항목이 있는 조건은 비교하지 않는다
        (그 조건은 type_mismatch로 따로 보고된다).
        """
        in_sets: List[tuple] = []  # (set, leaf)
        not_in_sets: List[tuple] = []
        for leaf in leaves:
            op = normalize_operator(leaf["operator"])
            if op not in ("in", "not_in"):
                continue
            items = split_list_value(leaf["value"])
            if any(item == "" for item in items):
                continue
            if is_number:
                nums = [to_number(item) for item in items]
                if any(n is None for n in nums):
                    continue
                values = set(nums)
            else:
                values = set(items)
            (in_sets if op == "in" else not_in_sets).append((values, leaf))

        if not in_sets and not not_in_sets:
            return None

        fmt = lambda v: self._fmt_value(v, is_number)  # noqa: E731

        def fmt_set(values) -> str:
            return "{" + ", ".join(fmt(v) for v in sorted(values)) + "}"

        for value, eq_leaf in eqs.items():
            for values, in_leaf in in_sets:
                if value not in values:
                    return (
                        f"{field} 필드가 {fmt(value)}와 같으면서 IN {fmt_set(values)} 중 "
                        "하나일 수 없음",
                        [in_leaf, eq_leaf],
                    )
            for values, nin_leaf in not_in_sets:
                if value in values:
                    return (
                        f"{field} 필드가 {fmt(value)}와 같으면서 NOT IN "
                        f"{fmt_set(values)}일 수 없음",
                        [nin_leaf, eq_leaf],
                    )

        if is_number and (lo or hi):
            def in_range(n: float) -> bool:
                if lo and (n < lo[0] or (n == lo[0] and not lo[1])):
                    return False
                if hi and (n > hi[0] or (n == hi[0] and not hi[1])):
                    return False
                return True

            for values, in_leaf in in_sets:
                if not any(in_range(n) for n in values):
                    bounds = []
                    if lo:
                        bounds.append(f"{fmt(lo[0])}{' 이상' if lo[1] else ' 초과'}")
                    if hi:
                        bounds.append(f"{fmt(hi[0])}{' 이하' if hi[1] else ' 미만'}")
                    involved = [in_leaf] + [b[2] for b in (lo, hi) if b]
                    return (
                        f"{field} 필드의 IN {fmt_set(values)} 값이 모두 "
                        f"범위({', '.join(bounds)}) 밖이라 동시에 성립할 수 없음",
                        involved,
                    )

        for a in range(len(in_sets)):
            for b in range(a + 1, len(in_sets)):
                (va, la), (vb, lb) = in_sets[a], in_sets[b]
                if not (va & vb):
                    return (
                        f"{field} 필드가 IN {fmt_set(va)}와 IN {fmt_set(vb)}를 동시에 "
                        "만족할 수 없음 (겹치는 값 없음)",
                        [la, lb],
                    )
        return None

    # ------------------------------------------------------------------
    # 트리 구조 검사 (빈 하위 그룹, 빈 필드 키, 불리언 값)
    # ------------------------------------------------------------------
    def detect_tree_structure_issues(
        self, tree_root: Dict[str, Any]
    ) -> List[ConditionIssue]:
        issues: List[ConditionIssue] = []

        def visit(node: Dict[str, Any], is_root: bool) -> None:
            if node["kind"] == "group":
                if not node["children"] and not is_root:
                    issues.append(
                        ConditionIssue(
                            condUuid=None,
                            keyName=None,
                            issue_type="missing_condition",
                            severity="error",
                            location=node["path"],
                            explanation=(
                                f"{node['logic']} 그룹({node['path']})에 조건이 "
                                "하나도 없습니다."
                            ),
                            suggestion="빈 그룹에 조건을 추가하거나 그룹을 삭제하세요.",
                        )
                    )
                for child in node["children"]:
                    visit(child, False)
                return

            key = node["keyName"]
            if not key:
                issues.append(
                    ConditionIssue(
                        condUuid=node.get("condUuid"),
                        keyName=None,
                        issue_type="missing_condition",
                        severity="error",
                        location=node["path"],
                        explanation=f"필드 키가 비어 있습니다 (조건 {node['path']}).",
                        suggestion="조건에 필드를 지정하세요.",
                    )
                )
                return

            if key == "placeholder":
                return
            declared = str(node.get("fieldDataType") or "").lower()
            field_type = self.condition_analyzer.get_field_type(key)
            if (declared in ("boolean", "bool") or field_type == "boolean") and (
                node["operator"] in ("==", "!=")
            ):
                value = node["value"]
                ok = isinstance(value, bool) or (
                    isinstance(value, str) and value.strip().lower() in ("true", "false")
                )
                if not ok:
                    issues.append(
                        ConditionIssue(
                            condUuid=node.get("condUuid"),
                            keyName=key,
                            issue_type="type_mismatch",
                            severity="error",
                            location=node["path"],
                            explanation=(
                                f"필드 '{key}'는 boolean 타입이지만 '{value}' 값이 "
                                "사용되었습니다. true 또는 false만 사용할 수 있습니다."
                            ),
                            suggestion="값을 true 또는 false로 변경하세요.",
                        )
                    )

        visit(tree_root, True)
        return issues

    def _check_number_field_ambiguity(
        self, field: str, conditions: List[Dict[str, Any]]
    ) -> Optional[ConditionIssue]:
        """숫자 필드에 대한 분기 불명확 검사"""
        # 겹치는 조건 검출 (모든 조건을 대상으로)
        overlapping_conditions = []

        # 모든 조건을 수치로 변환하여 범위 분석
        numeric_conditions = []
        for condition in conditions:
            try:
                op = condition["operator"]
                value = float(condition["value"])
                numeric_conditions.append(
                    {
                        "operator": op,
                        "value": value,
                        "location": condition["location"],
                        "original": condition,
                    }
                )
            except (ValueError, TypeError):
                continue

        # 중복/겹침 조건 검사
        for i in range(len(numeric_conditions)):
            for j in range(i + 1, len(numeric_conditions)):
                cond1 = numeric_conditions[i]
                cond2 = numeric_conditions[j]

                op1, val1 = cond1["operator"], cond1["value"]
                op2, val2 = cond2["operator"], cond2["value"]

                # 리던던트 조건 검출
                is_redundant = False
                explanation = ""

                # >= 조건과 == 조건 비교
                if op1 == ">=" and op2 == "==" and val2 >= val1:
                    is_redundant = True
                    explanation = (
                        f"'{field} == {val2}'는 '{field} >= {val1}'에 이미 포함됩니다"
                    )
                elif op2 == ">=" and op1 == "==" and val1 >= val2:
                    is_redundant = True
                    explanation = (
                        f"'{field} == {val1}'는 '{field} >= {val2}'에 이미 포함됩니다"
                    )

                # >= 조건 간 포함 관계
                elif op1 == ">=" and op2 == ">=" and val1 <= val2:
                    is_redundant = True
                    explanation = (
                        f"'{field} >= {val2}'는 '{field} >= {val1}'에 이미 포함됩니다"
                    )
                elif op1 == ">=" and op2 == ">=" and val2 <= val1:
                    is_redundant = True
                    explanation = (
                        f"'{field} >= {val1}'는 '{field} >= {val2}'에 이미 포함됩니다"
                    )

                # > 조건과 >= 조건 비교
                elif op1 == ">" and op2 == ">=" and val1 >= val2:
                    is_redundant = True
                    explanation = (
                        f"'{field} > {val1}'는 '{field} >= {val2}'에 이미 포함됩니다"
                    )
                elif op2 == ">" and op1 == ">=" and val2 >= val1:
                    is_redundant = True
                    explanation = (
                        f"'{field} > {val2}'는 '{field} >= {val1}'에 이미 포함됩니다"
                    )

                if is_redundant:
                    overlapping_conditions.append((cond1, cond2, explanation))

        # 겹치는 조건이 있으면 이슈 생성
        if overlapping_conditions:
            locations = []
            explanations = []
            for cond1, cond2, explanation in overlapping_conditions:
                locations.append(f"{cond1['location']}, {cond2['location']}")
                explanations.append(explanation)

            location_str = "; ".join(locations)
            explanation_str = "; ".join(explanations)

            # 첫 번째 조건에서 condUuid 추출
            first_condition_uuid = None
            if conditions:
                first_condition_uuid = self._get_condition_uuid(conditions[0])

            return ConditionIssue(
                condUuid=first_condition_uuid,
                keyName=field,
                issue_type="ambiguous_branch",
                severity="warning",
                location=location_str,
                explanation=(
                    f"{field} 필드에 리던던트(중복) 조건이 있습니다: {explanation_str}"
                ),
                suggestion="중복되는 조건을 제거하거나 조건을 명확하게 정의하세요.",
            )

        # 사각지대 검출
        all_values = set()
        for condition in conditions:
            op = condition["operator"]
            value = condition["value"]

            if op == "==" and isinstance(value, (int, float)):
                all_values.add(value)

        # 주요 값이 누락되었는지 확인
        key_values = [0, 1]
        missing_values = []

        for key_value in key_values:
            if key_value not in all_values and all(
                not self._value_matches_condition(key_value, condition)
                for condition in conditions
            ):
                missing_values.append(key_value)

        if missing_values:
            values_str = ", ".join([str(v) for v in missing_values])
            # 첫 번째 조건에서 condUuid 추출
            first_condition_uuid = None
            if conditions:
                first_condition_uuid = self._get_condition_uuid(conditions[0])

            return ConditionIssue(
                condUuid=first_condition_uuid,
                keyName=field,
                issue_type="ambiguous_branch",
                severity="warning",
                location=f"필드 '{field}' 조건",
                explanation=(
                    f"{field} 필드가 {values_str} 값일 때는 어느 조건에도 "
                    "해당되지 않아 분기 처리가 불명확합니다."
                ),
                suggestion=f"{field} 필드의 모든 가능한 값에 대한 처리를 정의하세요.",
            )

        return None

    def _check_string_field_ambiguity(
        self, field: str, conditions: List[Dict[str, Any]]
    ) -> Optional[ConditionIssue]:
        """문자열 필드에 대한 분기 불명확 검사"""
        string_values = {}

        for condition in conditions:
            op = condition["operator"]
            value = condition["value"]

            if op == "==" and isinstance(value, str):
                if value not in string_values:
                    string_values[value] = []
                string_values[value].append(condition)

        # 동일 값에 대해 여러 조건이 있는 경우
        for value, value_conditions in string_values.items():
            if len(value_conditions) > 1:
                parent_ops = set(
                    cond.get("parent_operator") for cond in value_conditions
                )
                if len(parent_ops) > 1:
                    locations = [cond["location"] for cond in value_conditions]
                    location_str = ", ".join(locations)

                    # 첫 번째 관련 조건에서 condUuid 추출
                    first_condition_uuid = None
                    if value_conditions:
                        first_cond = value_conditions[0]
                        if isinstance(first_cond, dict) and "condition_obj" in first_cond:
                            first_condition_uuid = self._get_condition_uuid(first_cond["condition_obj"])

                    return ConditionIssue(
                        condUuid=first_condition_uuid,
                        keyName=field,
                        issue_type="ambiguous_branch",
                        severity="warning",
                        location=location_str,
                        explanation=(
                            f"{field} 필드의 '{value}' 값에 대해 여러 분기에서 "
                            "동시에 처리되어 분기가 불명확합니다."
                        ),
                        suggestion=(
                            f"{field} 필드의 '{value}' 값에 대한 처리를 "
                            "하나의 분기로 통합하세요."
                        ),
                    )

        return None

    def _value_matches_condition(self, value: Any, condition: Dict[str, Any]) -> bool:
        """값이 조건에 맞는지 확인"""
        op = condition["operator"]
        cond_value = condition["value"]

        try:
            # 타입 정규화: 숫자 비교를 위해 모든 값을 float로 변환 시도
            normalized_value: float
            normalized_cond_value: float

            # value 정규화
            if isinstance(value, str):
                normalized_value = float(value)
            elif isinstance(value, (int, float)):
                normalized_value = float(value)
            else:
                # 숫자가 아닌 타입은 문자열 비교로 처리
                return self._compare_non_numeric(value, cond_value, op)

            # cond_value 정규화
            if isinstance(cond_value, str):
                normalized_cond_value = float(cond_value)
            elif isinstance(cond_value, (int, float)):
                normalized_cond_value = float(cond_value)
            else:
                # 숫자가 아닌 타입은 문자열 비교로 처리
                return self._compare_non_numeric(value, cond_value, op)

            # 숫자 비교 연산
            if op == "==":
                return normalized_value == normalized_cond_value
            elif op == "!=":
                return normalized_value != normalized_cond_value
            elif op == ">":
                return normalized_value > normalized_cond_value
            elif op == ">=":
                return normalized_value >= normalized_cond_value
            elif op == "<":
                return normalized_value < normalized_cond_value
            elif op == "<=":
                return normalized_value <= normalized_cond_value

        except (ValueError, TypeError):
            # 숫자 변환 실패 시 문자열 비교로 폴백
            return self._compare_non_numeric(value, cond_value, op)

        return False

    def _compare_non_numeric(self, value: Any, cond_value: Any, op: str) -> bool:
        """숫자가 아닌 값들에 대한 비교"""
        try:
            str_value: str = str(value)
            str_cond_value: str = str(cond_value)

            if op == "==":
                return str_value == str_cond_value
            elif op == "!=":
                return str_value != str_cond_value
            # 문자열 간의 크기 비교는 사전순으로 처리
            elif op == ">":
                return str_value > str_cond_value
            elif op == ">=":
                return str_value >= str_cond_value
            elif op == "<":
                return str_value < str_cond_value
            elif op == "<=":
                return str_value <= str_cond_value
        except Exception:
            pass

        return False

    def detect_missing_conditions(
        self, rule: Rule, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """누락된 조건 검출 - 기존 구현 반영"""
        issues = []

        # 빈 조건 체크
        if not conditions or len(conditions) == 0:
            issue = ConditionIssue(
                condUuid=None,  # 조건이 없으므로 None
                keyName=None,
                issue_type="missing_condition",
                severity="error",
                location="root",
                explanation="룰에 조건이 정의되지 않았습니다.",
                suggestion="최소 하나 이상의 조건을 추가하세요.",
            )
            issues.append(issue)
            return issues

        field_conditions = {}

        # 필드별로 조건 그룹화
        for condition in conditions:
            # 논리 연산자 블록 제외, 실제 필드 조건만 검사
            if condition.keyName and condition.keyName != "placeholder":
                if condition.keyName not in field_conditions:
                    field_conditions[condition.keyName] = []

                field_conditions[condition.keyName].append(
                    {
                        "operator": condition.operator,
                        "value": condition.value,
                        "condition_obj": condition,  # RuleCondition 객체 추가
                    }
                )

        # 각 필드별로 누락된 조건 검사
        for field, conditions_list in field_conditions.items():
            # 숫자 타입 필드에 대한 범위 누락 검사
            field_type = self.condition_analyzer.get_field_type(field)
            if field_type == "number":
                missing_ranges = self._check_number_field_missing_ranges(
                    field, conditions_list
                )
                issues.extend(missing_ranges)

        # 중첩 조건에 대해서도 검사
        for condition in conditions:
            if condition.conditions:
                nested_issues = self.detect_missing_conditions(
                    rule, condition.conditions
                )
                issues.extend(nested_issues)

        return issues

    def _check_number_field_missing_ranges(
        self, field: str, conditions: List[Dict[str, Any]]
    ) -> List[ConditionIssue]:
        """숫자 필드에 대한 범위 누락 검사"""
        issues = []

        # 숫자 필드에 대한 조건들을 분석
        min_values = []  # >= 또는 > 연산자의 값들
        max_values = []  # <= 또는 < 연산자의 값들
        exact_values = set()  # == 연산자의 값들
        not_exact_values = set()  # != 연산자의 값들

        # 연산자별로 값 분류
        for condition in conditions:
            try:
                value = (
                    float(condition["value"])
                    if isinstance(condition["value"], str)
                    else condition["value"]
                )

                if condition["operator"] == ">=":
                    min_values.append({"value": value, "inclusive": True})
                elif condition["operator"] == ">":
                    min_values.append({"value": value, "inclusive": False})
                elif condition["operator"] == "<=":
                    max_values.append({"value": value, "inclusive": True})
                elif condition["operator"] == "<":
                    max_values.append({"value": value, "inclusive": False})
                elif condition["operator"] == "==":
                    exact_values.add(value)
                elif condition["operator"] == "!=":
                    not_exact_values.add(value)
            except (ValueError, TypeError):
                # 숫자 변환 실패 시 건너뜀
                continue

        # 0 값에 대한 조건이 누락된 경우 체크
        has_zero_condition = 0 in exact_values
        has_zero_in_range = any(v["value"] == 0 and v["inclusive"] for v in min_values)

        if not has_zero_condition and not has_zero_in_range and min_values:
            min_value = min(v["value"] for v in min_values)

            if min_value > 0:
                # 첫 번째 조건에서 condUuid 가져오기
                first_condition_uuid = None
                if conditions:
                    first_condition_uuid = self._get_condition_uuid(conditions[0])
                
                issues.append(
                    ConditionIssue(
                        condUuid=first_condition_uuid,
                        keyName=field,
                        issue_type="missing_condition",
                        severity="warning",
                        location=f"필드 '{field}' 조건",
                        explanation=(
                            f"{field} = 0인 경우는 어떤 조건에도 해당되지 않으므로 "
                            "누락된 조건 가능성이 있습니다."
                        ),
                        suggestion=(
                            f"'{field}' 필드에 대해 값이 0인 경우의 처리를 "
                            "규칙에 명시적으로 추가하는 것이 좋습니다."
                        ),
                    )
                )

        # 범위 간격이 있는 경우 체크 (더 강화된 누락 검출)
        if exact_values and len(exact_values) >= 2:
            exact_list = sorted(exact_values)
            for i in range(len(exact_list) - 1):
                gap = exact_list[i + 1] - exact_list[i]
                if gap > 1:
                    # 범위에서 커버되지 않는 값들이 있는지 체크
                    covered_by_ranges = False
                    for val in range(int(exact_list[i] + 1), int(exact_list[i + 1])):
                        val_covered = False
                        for min_val in min_values:
                            if (min_val["inclusive"] and val >= min_val["value"]) or (
                                not min_val["inclusive"] and val > min_val["value"]
                            ):
                                val_covered = True
                                break
                        if not val_covered:
                            covered_by_ranges = False
                            break
                        covered_by_ranges = True

                    if not covered_by_ranges:
                        # 첫 번째 조건에서 condUuid 가져오기
                        first_condition_uuid = None
                        if conditions:
                            first_condition_uuid = self._get_condition_uuid(conditions[0])
                        
                        issues.append(
                            ConditionIssue(
                                condUuid=first_condition_uuid,
                                keyName=field,
                                issue_type="missing_condition",
                                severity="warning",
                                location=f"필드 '{field}' 조건",
                                explanation=(
                                    f"{field} 값이 {exact_list[i]}와 {exact_list[i+1]} "
                                    "사이에 있는 경우에 대한 조건이 누락되었을 수 있습니다."
                                ),
                                suggestion=(
                                    f"'{field}' 필드에 대해 누락된 범위의 값들에 "
                                    "대한 처리를 추가하세요."
                                ),
                            )
                        )

        return issues

    def _calculate_depth(
        self, conditions: List[RuleCondition], current_depth: int = 1
    ) -> int:
        """조건의 최대 중첩 깊이 계산"""
        if not conditions:
            return current_depth - 1

        max_depth = current_depth
        for condition in conditions:
            if condition.conditions:
                depth = self._calculate_depth(condition.conditions, current_depth + 1)
                max_depth = max(max_depth, depth)

        return max_depth

    def _count_field_conditions(
        self, conditions: List[RuleCondition], field_counts: Dict[str, int]
    ):
        """필드별 조건 개수 계산"""
        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                field_counts[condition.keyName] = (
                    field_counts.get(condition.keyName, 0) + 1
                )

            if condition.conditions:
                self._count_field_conditions(condition.conditions, field_counts)

    def detect_ambiguous_branches(
        self, conditions: List[RuleCondition]
    ) -> List[ConditionIssue]:
        """분기 불명확성 검출 - 기존 구현 반영"""
        issues = []

        # 필드별 조건 정보 수집
        field_conditions = {}
        condition_index_map = {}
        global_condition_index = 0

        def assign_indices(condition_list, parent_operator=None):
            nonlocal global_condition_index
            for condition in condition_list:
                global_condition_index += 1
                condition_index_map[id(condition)] = global_condition_index

                if condition.conditions:
                    assign_indices(condition.conditions, condition.operator)

        def collect_condition_info(
            condition_list, parent_path="", parent_operator=None
        ):
            for idx, condition in enumerate(condition_list):
                # 필드가 있고 논리 연산자가 아닌 경우만 처리
                if condition.keyName and condition.keyName != "placeholder":
                    if condition.keyName not in field_conditions:
                        field_conditions[condition.keyName] = []

                    # 조건 인덱스와 위치 기록
                    condition_id = (
                        f"{parent_path}/{idx+1}" if parent_path else f"{idx+1}"
                    )
                    global_index = condition_index_map.get(id(condition), 0)
                    condition_location = (
                        f"조건 {global_index}" if global_index else condition_id
                    )

                    # 상위 논리 연산자 정보와 함께 조건 정보 저장
                    field_conditions[condition.keyName].append(
                        {
                            "field": condition.keyName,
                            "operator": condition.operator,
                            "value": condition.value,
                            "location": condition_location,
                            "parent_operator": parent_operator,
                            "condition_obj": condition,  # 조건 객체 추가
                        }
                    )

                # 중첩 조건이 있는 경우 재귀 처리
                if condition.conditions:
                    # 현재 조건이 논리 연산자인 경우
                    current_operator = None
                    if hasattr(condition, "logicType") and condition.logicType:
                        current_operator = condition.logicType.upper()
                    elif condition.operator and condition.operator.upper() in [
                        "AND",
                        "OR",
                    ]:
                        current_operator = condition.operator.upper()

                    # 기본값은 AND
                    if not current_operator:
                        current_operator = "AND"

                    new_path = f"{parent_path}/{idx+1}" if parent_path else f"{idx+1}"
                    collect_condition_info(
                        condition.conditions, new_path, current_operator
                    )

        # 인덱스 할당 및 조건 정보 수집
        assign_indices(conditions)
        collect_condition_info(conditions)

        # 각 필드별로 분기 불명확 검사
        for field, conditions_list in field_conditions.items():
            if len(conditions_list) < 2:
                continue

            # 필드 타입 확인
            field_type = self.condition_analyzer.get_field_type(field)

            # 타입별 검사
            if field_type == "number":
                ambiguous_issue = self._check_number_field_ambiguity(
                    field, conditions_list
                )
                if ambiguous_issue:
                    issues.append(ambiguous_issue)
            elif field_type == "string":
                ambiguous_issue = self._check_string_field_ambiguity(
                    field, conditions_list
                )
                if ambiguous_issue:
                    issues.append(ambiguous_issue)

        # 중첩 조건에 대해서도 검사
        for condition in conditions:
            if condition.conditions:
                nested_issues = self.detect_ambiguous_branches(condition.conditions)
                issues.extend(nested_issues)

        return issues

    def detect_complexity_warnings(
        self, conditions: List[RuleCondition], complexity_score: int
    ) -> List[ConditionIssue]:
        """복잡성 경고 검출"""
        issues = []

        if complexity_score >= QualityThresholds.COMPLEXITY_WARNING_THRESHOLD:
            # 복잡하다는 이유만으로 오류가 되지는 않는다 (항상 경고)
            severity = "warning"

            # 첫 번째 조건에서 condUuid 가져오기
            first_condition_uuid = None
            if conditions:
                first_condition_uuid = self._get_condition_uuid(conditions[0])
            
            issue = ConditionIssue(
                condUuid=first_condition_uuid,
                keyName=None,
                issue_type="complexity_warning",
                severity=severity,
                location="전체 룰",
                explanation=(
                    f"룰의 복잡성이 높습니다 "
                    f"(점수: {complexity_score}/"
                    f"{QualityThresholds.COMPLEXITY_MAX_SCORE})."
                ),
                suggestion="조건을 단순화하거나 여러 룰로 분할하는 것을 고려하세요.",
            )
            issues.append(issue)

        return issues

    def detect_issues_from_rule_direct(self, rule: Rule) -> List[ConditionIssue]:
        """룰 JSON을 직접 분석하여 누락된 이슈들을 검출"""
        issues = []

        try:
            # conditionTree에서 직접 조건 추출
            if hasattr(rule, "conditionTree") and rule.conditionTree:
                field_conditions = {}
                self._extract_field_conditions_recursive(
                    rule.conditionTree, field_conditions
                )

                # 모든 필드에 대해 일반화된 이슈 검출
                for field_name, conditions in field_conditions.items():
                    # 숫자 필드인지 확인
                    if self._is_numeric_field(conditions):
                        # 리던던트 조건 검출
                        redundant_issues = self._detect_field_redundant_conditions(
                            field_name, conditions
                        )
                        issues.extend(redundant_issues)

                        # 누락된 조건 검출 (0값, 음수값 등)
                        missing_issues = self._detect_field_missing_edge_cases(
                            field_name, conditions
                        )
                        issues.extend(missing_issues)

        except Exception as e:
            self.logger.error(f"직접 이슈 검출 중 오류: {str(e)}")

        return issues

    def _is_numeric_field(self, conditions: List[Dict[str, Any]]) -> bool:
        """필드가 숫자 타입인지 확인"""
        for condition in conditions:
            try:
                float(condition["value"])
                return True
            except (ValueError, TypeError):
                continue
        return False

    def _detect_field_redundant_conditions(
        self, field_name: str, conditions: List[Dict[str, Any]]
    ) -> List[ConditionIssue]:
        """필드의 리던던트 조건 검출"""
        issues = []
        redundant_pairs = []

        for i, cond1 in enumerate(conditions):
            for j, cond2 in enumerate(conditions[i + 1 :], i + 1):
                try:
                    val1, val2 = float(cond1["value"]), float(cond2["value"])
                    op1, op2 = cond1["operator"], cond2["operator"]

                    # 리던던트 조건 패턴 검사
                    redundant_explanation = self._check_redundant_pattern(
                        field_name, op1, val1, op2, val2
                    )

                    if redundant_explanation:
                        redundant_pairs.append((cond1, cond2, redundant_explanation))
                        break
                except (ValueError, TypeError):
                    continue

        if redundant_pairs:
            for cond1, cond2, explanation in redundant_pairs:
                # 첫 번째 조건에서 condUuid 가져오기 (cond1에서)
                first_condition_uuid = None
                if isinstance(cond1, dict):
                    first_condition_uuid = self._get_condition_uuid(cond1)
                
                issues.append(
                    ConditionIssue(
                        condUuid=first_condition_uuid,
                        keyName=field_name,
                        issue_type="ambiguous_branch",
                        severity="warning",
                        location=f"{field_name} 필드 조건들",
                        explanation=(
                            f"{field_name} 필드에 리던던트(중복) 조건이 있습니다: "
                            f"{explanation}"
                        ),
                        suggestion="중복되는 조건을 제거하거나 조건을 명확하게 정의하세요.",
                    )
                )

        return issues

    def _check_redundant_pattern(
        self, field_name: str, op1: str, val1: float, op2: str, val2: float
    ) -> str:
        """리던던트 패턴 검사 및 설명 반환"""
        # >= 조건과 == 조건 비교
        if op1 == ">=" and op2 == "==" and val2 >= val1:
            return f"== {val2} 조건이 >= {val1} 조건에 이미 포함됩니다"
        elif op2 == ">=" and op1 == "==" and val1 >= val2:
            return f"== {val1} 조건이 >= {val2} 조건에 이미 포함됩니다"

        # > 조건과 >= 조건 비교
        elif op1 == ">" and op2 == ">=" and val1 >= val2:
            return f"> {val1} 조건이 >= {val2} 조건에 이미 포함됩니다"
        elif op2 == ">" and op1 == ">=" and val2 >= val1:
            return f"> {val2} 조건이 >= {val1} 조건에 이미 포함됩니다"

        # <= 조건과 == 조건 비교
        elif op1 == "<=" and op2 == "==" and val2 <= val1:
            return f"== {val2} 조건이 <= {val1} 조건에 이미 포함됩니다"
        elif op2 == "<=" and op1 == "==" and val1 <= val2:
            return f"== {val1} 조건이 <= {val2} 조건에 이미 포함됩니다"

        # 동일한 == 조건
        elif op1 == "==" and op2 == "==" and val1 == val2:
            return f"동일한 == {val1} 조건이 중복됩니다"

        return ""

    def _detect_field_missing_edge_cases(
        self, field_name: str, conditions: List[Dict[str, Any]]
    ) -> List[ConditionIssue]:
        """필드의 누락된 엣지 케이스 검출"""
        issues = []

        try:
            # 0값 조건 체크
            has_zero_condition = any(
                cond["operator"] == "==" and float(cond["value"]) == 0
                for cond in conditions
            )
            has_zero_range = any(
                cond["operator"] in [">=", ">"] and float(cond["value"]) == 0
                for cond in conditions
            )

            # 최소값 확인
            numeric_conditions = [
                float(cond["value"])
                for cond in conditions
                if (
                    cond["operator"] in [">=", ">"]
                    and self._is_numeric_value(cond["value"])
                )
            ]

            if numeric_conditions:
                min_value = min(numeric_conditions)

                # 0값이 처리되지 않는 경우
                if not has_zero_condition and not has_zero_range and min_value > 0:
                    # 첫 번째 조건에서 condUuid 가져오기
                    first_condition_uuid = None
                    if conditions:
                        first_condition_uuid = self._get_condition_uuid(conditions[0])
                    
                    issues.append(
                        ConditionIssue(
                            condUuid=first_condition_uuid,
                            keyName=field_name,
                            issue_type="missing_condition",
                            severity="warning",
                            location=f"{field_name} 필드 조건",
                            explanation=(
                                f"{field_name} = 0인 경우는 어떤 조건에도 "
                                "해당되지 않으므로 누락된 조건 가능성이 있습니다."
                            ),
                            suggestion=(
                                f"{field_name} 필드에 대해 값이 0인 경우의 처리를 "
                                "규칙에 명시적으로 추가하는 것이 좋습니다."
                            ),
                        )
                    )

        except Exception as e:
            self.logger.debug(f"{field_name} 필드 엣지 케이스 검출 중 오류: {str(e)}")

        return issues

    def _is_numeric_value(self, value: Any) -> bool:
        """값이 숫자인지 확인"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _extract_field_conditions_recursive(self, tree, field_conditions, path=""):
        """조건 트리에서 필드별 조건을 재귀적으로 추출"""
        try:
            if tree is None:
                return

            if isinstance(tree, dict):
                # 일반 필드 조건
                if "keyName" in tree and "operator" in tree and "value" in tree:
                    field = tree["keyName"]
                    if field not in field_conditions:
                        field_conditions[field] = []
                    
                    # condUuid 추출 (있는 경우)
                    cond_uuid = tree.get("condUuid", None)
                    
                    field_conditions[field].append(
                        {
                            "operator": tree["operator"],
                            "value": tree["value"],
                            "path": path,
                            "condUuid": cond_uuid,  # condUuid 추가
                        }
                    )

                # 논리 연산자 블록
                elif "logicType" in tree and "condition" in tree:
                    for i, sub_tree in enumerate(tree["condition"]):
                        new_path = f"{path}/{i+1}" if path else f"{i+1}"
                        self._extract_field_conditions_recursive(
                            sub_tree, field_conditions, new_path
                        )

                # 다른 구조의 논리 블록도 처리
                elif "condition" in tree:
                    for i, sub_tree in enumerate(tree["condition"]):
                        new_path = f"{path}/{i+1}" if path else f"{i+1}"
                        self._extract_field_conditions_recursive(
                            sub_tree, field_conditions, new_path
                        )

            elif hasattr(tree, "__dict__"):
                # 객체 형태 처리

                # 필드 조건인 경우 기록
                if (
                    hasattr(tree, "keyName")
                    and hasattr(tree, "operator")
                    and hasattr(tree, "value")
                    and tree.keyName
                ):
                    field = tree.keyName
                    if field not in field_conditions:
                        field_conditions[field] = []
                    
                    # condUuid 추출 (있는 경우)
                    cond_uuid = getattr(tree, "condUuid", None)
                    
                    field_conditions[field].append(
                        {
                            "operator": tree.operator,
                            "value": tree.value,
                            "path": path,
                            "condUuid": cond_uuid,  # condUuid 추가
                        }
                    )

                # 논리 연산자 블록인 경우 (필드 조건과 별개로 처리)
                if (
                    hasattr(tree, "logicType")
                    and hasattr(tree, "condition")
                    and tree.condition
                ):
                    for i, sub_tree in enumerate(tree.condition):
                        new_path = f"{path}/{i+1}" if path else f"{i+1}"
                        self._extract_field_conditions_recursive(
                            sub_tree, field_conditions, new_path
                        )

                # 일반 조건 배열인 경우
                elif hasattr(tree, "condition") and tree.condition:
                    condition_list = tree.condition
                    for i, sub_tree in enumerate(condition_list):
                        new_path = f"{path}/{i+1}" if path else f"{i+1}"
                        self._extract_field_conditions_recursive(
                            sub_tree, field_conditions, new_path
                        )

            elif isinstance(tree, list):
                for i, sub_tree in enumerate(tree):
                    new_path = f"{path}/{i+1}" if path else f"{i+1}"
                    self._extract_field_conditions_recursive(
                        sub_tree, field_conditions, new_path
                    )

        except Exception as e:
            self.logger.debug(f"조건 추출 중 오류: {str(e)}")

    def _create_condition_signature(self, condition: RuleCondition) -> str:
        """조건의 고유 시그니처 생성"""
        if not condition.keyName or condition.keyName == "placeholder":
            return "unknown"

        if condition.conditions:
            return f"logical_{condition.operator}_{len(condition.conditions)}"

        value_str = str(condition.value) if condition.value is not None else "null"
        return f"{condition.keyName}_{condition.operator}_{value_str}"

    def _get_condition_uuid(self, condition_info) -> Optional[str]:
        """
        조건 정보에서 condUuid를 추출하는 헬퍼 메서드
        
        Args:
            condition_info: 조건 정보 (dict 또는 RuleCondition)
            
        Returns:
            Optional[str]: 추출된 condUuid
        """
        if condition_info is None:
            return None
            
        # RuleCondition 객체인 경우
        if hasattr(condition_info, 'condUuid'):
            return getattr(condition_info, 'condUuid', None)
            
        # 딕셔너리인 경우
        if isinstance(condition_info, dict):
            # condition_obj가 있는 경우
            if "condition_obj" in condition_info:
                return getattr(condition_info["condition_obj"], "condUuid", None)
            # 직접 condUuid가 있는 경우
            elif "condUuid" in condition_info:
                return condition_info["condUuid"]
                
        return None

    def _remove_duplicate_issues(self, issues: List[ConditionIssue]) -> List[ConditionIssue]:
        """
        중복 이슈 제거.

        같은 조건(condUuid)의 같은 유형 이슈는 하나만 남기고(설명이 더 자세한 것),
        서로 다른 조건의 이슈는 각각 유지한다. condUuid가 없는 이슈는 같은
        keyName+유형의 condUuid 있는 이슈가 있으면 그쪽으로 흡수하고, 없으면 하나만 남긴다.
        """
        if not issues:
            return issues

        groups: Dict[tuple, List[ConditionIssue]] = {}
        for issue in issues:
            groups.setdefault((issue.keyName, issue.issue_type), []).append(issue)

        final_issues: List[ConditionIssue] = []
        for group_issues in groups.values():
            by_uuid: Dict[str, ConditionIssue] = {}
            without_uuid: Optional[ConditionIssue] = None

            for issue in group_issues:
                if issue.condUuid is None:
                    if without_uuid is None or len(issue.explanation) > len(
                        without_uuid.explanation
                    ):
                        without_uuid = issue
                    continue
                best = by_uuid.get(issue.condUuid)
                if best is None or len(issue.explanation) > len(best.explanation):
                    by_uuid[issue.condUuid] = issue

            if by_uuid:
                final_issues.extend(by_uuid.values())
            elif without_uuid is not None:
                final_issues.append(without_uuid)

        return final_issues
