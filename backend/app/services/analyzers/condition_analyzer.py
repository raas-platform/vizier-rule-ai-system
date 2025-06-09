"""
조건 분석기 (ConditionAnalyzer)

룰의 조건을 분석하고 파싱하는 기능을 담당합니다.
- 조건 트리 파싱
- 필드 타입 추론
- 조건 구조 분석
- 깊이 및 복잡성 계산
"""

from typing import Any, Dict, List, Optional

from ...models.rule import Rule, RuleCondition
from ...utils.logger import get_logger


class ConditionAnalyzer:
    """
    조건 분석 및 파싱을 담당하는 클래스

    이 클래스는 다음 기능들을 제공합니다:
    - 조건 트리 파싱 및 변환
    - 필드 타입 자동 추론
    - 조건 구조 분석
    - 복잡성 및 깊이 계산
    """

    def __init__(self):
        """ConditionAnalyzer 초기화"""
        self.logger = get_logger(__name__)
        self.field_types: Dict[str, str] = {}
        self.global_condition_index = 0
        self.condition_index_map = {}

        # 타입별 허용 연산자 정의
        self._valid_operators = {
            "string": [
                "==",
                "!=",
                "contains",
                "starts_with",
                "ends_with",
                "in",
                "not_in",
            ],
            "number": ["==", "!=", ">", ">=", "<", "<=", "in", "not_in"],
            "boolean": ["==", "!="],
            "date": ["==", "!=", ">", ">=", "<", "<="],
            "array": ["contains", "in", "not_in"],
            "logical": ["and", "or"],
        }

        # 성능 최적화를 위한 캐시
        self._field_analysis_cache: Dict[str, Any] = {}
        self._complexity_cache: Dict[str, int] = {}
        self._analysis_cache: Dict[str, Any] = {}

    def parse_rule_conditions(self, rule: Rule) -> List[RuleCondition]:
        """
        룰에서 조건들을 파싱하여 RuleCondition 리스트로 변환

        Args:
            rule (Rule): 파싱할 룰 객체

        Returns:
            List[RuleCondition]: 파싱된 조건들
        """
        try:
            # 캐시 확인
            rule_id = getattr(rule, "ruleUuid", getattr(rule, "id", "unknown"))
            cache_key = f"parse_{rule_id}"

            if cache_key in self._analysis_cache:
                return self._analysis_cache[cache_key]

            conditions = []

            # 다양한 룰 형식 지원
            if hasattr(rule, "conditionTree") and rule.conditionTree:
                conditions = self._parse_condition_tree(rule.conditionTree)
            elif hasattr(rule, "conditions") and rule.conditions:
                conditions = self._parse_conditions_list(rule.conditions)
            elif hasattr(rule, "ruleCondition") and rule.ruleCondition:
                conditions = self._parse_condition_tree(rule.ruleCondition)
            else:
                self.logger.warning(f"룰에서 조건을 찾을 수 없음: {rule}")

            # 캐시에 저장
            self._analysis_cache[cache_key] = conditions

            self.logger.debug(f"조건 파싱 완료: {len(conditions)}개 조건")
            return conditions

        except Exception as e:
            self.logger.error(f"조건 파싱 중 오류: {str(e)}", exc_info=True)
            return []

    def _parse_condition_tree(self, tree: Any) -> List[RuleCondition]:
        """
        조건 트리를 파싱하여 조건 리스트로 변환

        Args:
            tree: 조건 트리 객체

        Returns:
            List[RuleCondition]: 파싱된 조건들
        """
        conditions = []

        try:
            if tree is None:
                return conditions

            # 딕셔너리 형태의 트리
            if isinstance(tree, dict):
                # 논리 연산자 블록인 경우
                if "logicType" in tree and "condition" in tree:
                    # 하위 조건들을 재귀적으로 파싱
                    nested_conditions = []
                    for nested_data in tree.get("condition", []):
                        nested_conditions.extend(
                            self._parse_condition_tree(nested_data)
                        )

                    # 논리 연산자 블록 생성
                    logic_condition = RuleCondition(
                        keyName="placeholder",
                        dispName=f"{tree['logicType']} 그룹",
                        operator=tree["logicType"].lower(),
                        value=None,
                        fieldDataType="logical",
                        logicType=tree["logicType"],
                        conditions=nested_conditions,
                    )
                    conditions.append(logic_condition)
                else:
                    # 일반 필드 조건
                    condition = self._parse_dict_condition(tree)
                    if condition:
                        conditions.append(condition)

            # 객체 형태의 트리
            elif hasattr(tree, "__dict__"):
                # ConditionTree 객체인 경우
                if hasattr(tree, "logicType") and hasattr(tree, "condition"):
                    # 하위 조건들을 재귀적으로 파싱
                    nested_conditions = []
                    if tree.condition:
                        for item in tree.condition:
                            nested_conditions.extend(self._parse_condition_tree(item))

                    # 논리 연산자 블록 생성
                    logic_condition = RuleCondition(
                        keyName="placeholder",
                        dispName=f"{tree.logicType} 그룹",
                        operator=tree.logicType.lower() if tree.logicType else "and",
                        value=None,
                        fieldDataType="logical",
                        logicType=tree.logicType,
                        conditions=nested_conditions,
                    )
                    conditions.append(logic_condition)
                else:
                    condition = self._parse_object_condition(tree)
                    if condition:
                        conditions.append(condition)

            # 리스트 형태
            elif isinstance(tree, list):
                for item in tree:
                    conditions.extend(self._parse_condition_tree(item))

        except Exception as e:
            self.logger.error(f"조건 트리 파싱 중 오류: {str(e)}", exc_info=True)

        return conditions

    def _parse_dict_condition(self, condition_dict: dict) -> Optional[RuleCondition]:
        """
        딕셔너리 형태의 조건을 RuleCondition으로 변환

        Args:
            condition_dict (dict): 조건 딕셔너리

        Returns:
            Optional[RuleCondition]: 변환된 조건
        """
        try:
            # 일반 필드 조건 처리
            if "keyName" in condition_dict and "operator" in condition_dict:
                return RuleCondition(
                    keyName=condition_dict.get("keyName"),
                    dispName=condition_dict.get(
                        "dispName", condition_dict.get("keyName")
                    ),
                    operator=condition_dict.get("operator"),
                    value=condition_dict.get("value"),
                    fieldDataType=condition_dict.get("fieldDataType", "String"),
                )

            # 기본 필드 추출 (하위 호환성)
            else:
                field = condition_dict.get("field") or condition_dict.get("keyName")
                operator = condition_dict.get("operator") or condition_dict.get("op")
                value = condition_dict.get("value") or condition_dict.get("val")

                # 중첩 조건 처리
                nested_conditions = None
                if "conditions" in condition_dict:
                    nested_conditions = self._parse_conditions_list(
                        condition_dict["conditions"]
                    )
                elif "children" in condition_dict:
                    nested_conditions = self._parse_conditions_list(
                        condition_dict["children"]
                    )

                # RuleCondition 생성
                condition = RuleCondition(
                    keyName=field,
                    operator=operator,
                    value=value,
                    conditions=nested_conditions,
                )

                return condition

        except Exception as e:
            self.logger.error(f"딕셔너리 조건 파싱 오류: {str(e)}")
            return None

    def _parse_object_condition(self, condition_obj: Any) -> Optional[RuleCondition]:
        """
        객체 형태의 조건을 RuleCondition으로 변환

        Args:
            condition_obj: 조건 객체

        Returns:
            Optional[RuleCondition]: 변환된 조건
        """
        try:
            # 일반 RuleCondition 객체 처리
            if True:
                # 필드 추출
                field = getattr(condition_obj, "field", None) or getattr(
                    condition_obj, "keyName", None
                )
                operator = getattr(condition_obj, "operator", None) or getattr(
                    condition_obj, "op", None
                )
                value = getattr(condition_obj, "value", None) or getattr(
                    condition_obj, "val", None
                )

                # fieldDataType 정보도 추출
                field_data_type = getattr(condition_obj, "fieldDataType", None)

                # 중첩 조건 처리
                nested_conditions = None
                if hasattr(condition_obj, "conditions") and condition_obj.conditions:
                    nested_conditions = self._parse_conditions_list(
                        condition_obj.conditions
                    )
                elif hasattr(condition_obj, "children") and condition_obj.children:
                    nested_conditions = self._parse_conditions_list(
                        condition_obj.children
                    )
                elif hasattr(condition_obj, "condition") and condition_obj.condition:
                    # condition 속성도 확인
                    nested_conditions = self._parse_conditions_list(
                        condition_obj.condition
                    )

                condition = RuleCondition(
                    keyName=field,
                    operator=operator,
                    value=value,
                    conditions=nested_conditions,
                    fieldDataType=field_data_type,  # fieldDataType 정보 추가
                )

                # keyName이 None이면 다른 필드에서 가져오기
                if (
                    not condition.keyName
                    and hasattr(condition_obj, "keyName")
                    and condition_obj.keyName
                ):
                    condition.keyName = condition_obj.keyName

                return condition

        except Exception as e:
            self.logger.error(f"객체 조건 파싱 오류: {str(e)}")
            return None

    def _parse_conditions_list(self, conditions_list: List[Any]) -> List[RuleCondition]:
        """
        조건 리스트를 파싱

        Args:
            conditions_list (List[Any]): 조건 리스트

        Returns:
            List[RuleCondition]: 파싱된 조건들
        """
        conditions = []

        if not conditions_list:
            return conditions

        for item in conditions_list:
            if isinstance(item, dict):
                condition = self._parse_dict_condition(item)
                if condition:
                    conditions.append(condition)
            elif hasattr(item, "__dict__"):
                condition = self._parse_object_condition(item)
                if condition:
                    conditions.append(condition)

        return conditions

    def infer_field_types(
        self, rule: Rule, conditions: List[RuleCondition]
    ) -> Dict[str, str]:
        """
        조건들로부터 필드 타입을 추론

        Args:
            rule (Rule): 룰 객체
            conditions (List[RuleCondition]): 조건들

        Returns:
            Dict[str, str]: 필드명 -> 타입 매핑
        """
        try:
            field_types = {}

            def analyze_condition(condition: RuleCondition):
                """조건을 분석하여 타입 추론"""
                if condition.keyName and condition.keyName != "placeholder":
                    field_type = self._infer_type_from_value(
                        condition.value, condition.operator
                    )
                    if field_type:
                        field_types[condition.keyName] = field_type

                # 중첩 조건 재귀 분석
                if condition.conditions:
                    for nested in condition.conditions:
                        analyze_condition(nested)

            # 모든 조건 분석
            for condition in conditions:
                analyze_condition(condition)

            # 결과를 인스턴스 변수에 저장
            self.field_types.update(field_types)

            self.logger.debug(f"필드 타입 추론 완료: {len(field_types)}개 필드")
            return field_types

        except Exception as e:
            self.logger.error(f"필드 타입 추론 중 오류: {str(e)}", exc_info=True)
            return {}

    def _infer_type_from_value(self, value: Any, operator: str = None) -> str:
        """
        값과 연산자로부터 타입 추론

        Args:
            value (Any): 값
            operator (str, optional): 연산자

        Returns:
            str: 추론된 타입
        """
        if value is None:
            return "unknown"

        # 연산자 기반 추론
        if operator:
            if operator in ["contains", "starts_with", "ends_with"]:
                return "string"
            elif operator in [">", ">=", "<", "<="]:
                return "number"

        # 값 타입 기반 추론
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, str):
            # 날짜 형식인지 확인
            if self._is_date_string(value):
                return "date"
            return "string"
        elif isinstance(value, list):
            return "array"

        return "unknown"

    def _is_date_string(self, value: str) -> bool:
        """
        문자열이 날짜 형식인지 확인

        Args:
            value (str): 확인할 문자열

        Returns:
            bool: 날짜 형식 여부
        """
        import re

        # 간단한 날짜 패턴들
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY
            r"\d{4}/\d{2}/\d{2}",  # YYYY/MM/DD
        ]

        for pattern in date_patterns:
            if re.match(pattern, value):
                return True

        return False

    def calculate_structure_metrics(
        self, conditions: List[RuleCondition]
    ) -> Dict[str, Any]:
        """
        조건 구조의 다양한 메트릭 계산

        Args:
            conditions (List[RuleCondition]): 분석할 조건들

        Returns:
            Dict[str, Any]: 구조 메트릭들
        """
        try:
            if not conditions:
                return {
                    "depth": 1,
                    "condition_count": 0,
                    "field_condition_count": 0,
                    "unique_fields": [],
                    "complexity_score": 0,
                }

            # 기본 메트릭 계산
            depth = self._calculate_depth(conditions)
            condition_count = self._count_all_conditions(conditions)
            field_condition_count = self._count_field_conditions(conditions)
            unique_fields = self._extract_unique_fields(conditions)
            complexity_score = self._calculate_complexity_score(conditions)

            metrics = {
                "depth": depth,
                "condition_count": condition_count,
                "field_condition_count": field_condition_count,
                "unique_fields": unique_fields,
                "complexity_score": complexity_score,
            }

            self.logger.debug(
                f"구조 메트릭 계산 완료: 깊이={depth}, 조건수={condition_count}"
            )
            return metrics

        except Exception as e:
            self.logger.error(f"구조 메트릭 계산 중 오류: {str(e)}", exc_info=True)
            return {
                "depth": 1,
                "condition_count": 0,
                "field_condition_count": 0,
                "unique_fields": [],
                "complexity_score": 0,
            }

    def _calculate_depth(
        self, conditions: List[RuleCondition], current_depth: int = 1
    ) -> int:
        """
        조건 트리의 최대 깊이 계산

        Args:
            conditions (List[RuleCondition]): 조건들
            current_depth (int): 현재 깊이

        Returns:
            int: 최대 깊이
        """
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

    def _count_all_conditions(self, conditions: List[RuleCondition]) -> int:
        """
        모든 조건의 개수 계산 (중첩 포함)

        Args:
            conditions (List[RuleCondition]): 조건들

        Returns:
            int: 총 조건 개수
        """
        count = len(conditions)

        for condition in conditions:
            if condition.conditions:
                count += self._count_all_conditions(condition.conditions)

        return count

    def _count_field_conditions(self, conditions: List[RuleCondition]) -> int:
        """
        실제 필드 조건의 개수 계산 (논리 연산자 제외)

        Args:
            conditions (List[RuleCondition]): 조건들

        Returns:
            int: 필드 조건 개수
        """
        count = 0

        for condition in conditions:
            if condition.keyName and condition.keyName != "placeholder":
                count += 1

            if condition.conditions:
                count += self._count_field_conditions(condition.conditions)

        return count

    def _extract_unique_fields(self, conditions: List[RuleCondition]) -> List[str]:
        """
        조건에서 사용된 고유 필드들 추출

        Args:
            conditions (List[RuleCondition]): 조건들

        Returns:
            List[str]: 고유 필드 리스트
        """
        unique_fields = set()

        def extract_fields(condition_list):
            for condition in condition_list:
                if condition.keyName and condition.keyName != "placeholder":
                    unique_fields.add(condition.keyName)

                if condition.conditions:
                    extract_fields(condition.conditions)

        extract_fields(conditions)
        return list(unique_fields)

    def _calculate_complexity_score(self, conditions: List[RuleCondition]) -> int:
        """
        조건 복잡성 점수 계산

        Args:
            conditions (List[RuleCondition]): 조건들

        Returns:
            int: 복잡성 점수 (0-100)
        """
        try:
            # 캐시 확인
            cache_key = f"complexity_{len(conditions)}"
            if cache_key in self._complexity_cache:
                return self._complexity_cache[cache_key]

            base_score = 0

            # 기본 점수: 조건 개수
            condition_count = self._count_all_conditions(conditions)
            base_score += condition_count * 2

            # 깊이 가중치
            depth = self._calculate_depth(conditions)
            base_score += (depth - 1) * 5

            # 논리 연산자 복잡도
            logical_operators = self._count_logical_operators(conditions)
            base_score += logical_operators.get("or", 0) * 3  # OR가 더 복잡
            base_score += logical_operators.get("and", 0) * 2

            # 고유 필드 수
            unique_fields = len(self._extract_unique_fields(conditions))
            base_score += unique_fields * 1

            # 최대 100점으로 제한
            complexity_score = min(base_score, 100)

            # 캐시에 저장
            self._complexity_cache[cache_key] = complexity_score

            return complexity_score

        except Exception as e:
            self.logger.error(f"복잡성 점수 계산 중 오류: {str(e)}")
            return 50  # 기본값

    def _count_logical_operators(
        self, conditions: List[RuleCondition]
    ) -> Dict[str, int]:
        """
        논리 연산자 개수 계산

        Args:
            conditions (List[RuleCondition]): 조건들

        Returns:
            Dict[str, int]: 연산자별 개수
        """
        counts = {"and": 0, "or": 0}

        for condition in conditions:
            if condition.operator:
                op = condition.operator.lower()
                if op in counts:
                    counts[op] += 1

            if condition.conditions:
                nested_counts = self._count_logical_operators(condition.conditions)
                counts["and"] += nested_counts["and"]
                counts["or"] += nested_counts["or"]

        return counts

    # === 유틸리티 메서드들 ===

    def get_field_type(self, field: str) -> str:
        """
        필드의 타입 반환

        Args:
            field (str): 필드명

        Returns:
            str: 필드 타입
        """
        return self.field_types.get(field, "unknown")

    def is_valid_operator(self, field: str, operator: str) -> bool:
        """
        필드와 연산자 조합이 유효한지 확인

        Args:
            field (str): 필드명
            operator (str): 연산자

        Returns:
            bool: 유효성 여부
        """
        field_type = self.get_field_type(field)
        valid_ops = self._valid_operators.get(field_type, [])
        return operator in valid_ops

    def is_valid_type(self, field: str, value: Any) -> bool:
        """
        필드와 값의 타입이 일치하는지 확인

        Args:
            field (str): 필드명
            value (Any): 값

        Returns:
            bool: 타입 일치 여부
        """
        expected_type = self.get_field_type(field)
        actual_type = self._infer_type_from_value(value)

        # 타입 호환성 확인
        if expected_type == actual_type:
            return True

        # 숫자 타입 호환성 (int <-> float)
        if expected_type == "number" and actual_type == "number":
            return True

        # 문자열은 대부분 호환
        if expected_type == "string" and actual_type in ["string", "unknown"]:
            return True

        return False

    def _get_condition_field(self, condition: RuleCondition) -> Optional[str]:
        """
        조건에서 필드명 추출

        Args:
            condition (RuleCondition): 조건

        Returns:
            Optional[str]: 필드명
        """
        if hasattr(condition, "keyName") and condition.keyName:
            return condition.keyName
        elif hasattr(condition, "field") and condition.field:
            return condition.field
        return None
