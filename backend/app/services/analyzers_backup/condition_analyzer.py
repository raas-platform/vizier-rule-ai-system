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
                self.logger.debug(f"conditionTree 발견: type={type(rule.conditionTree)}")
                conditions = self._parse_condition_tree(rule.conditionTree)
                self.logger.debug(f"conditionTree 파싱 후 조건 수: {len(conditions)}")
            elif hasattr(rule, "conditions") and rule.conditions:
                self.logger.debug(f"conditions 발견: {len(rule.conditions)}개")
                conditions = self._parse_conditions_list(rule.conditions)
            elif hasattr(rule, "ruleCondition") and getattr(rule, "ruleCondition", None):
                self.logger.debug("ruleCondition 발견")
                conditions = self._parse_condition_tree(getattr(rule, "ruleCondition"))
            else:
                self.logger.warning(f"룰에서 조건을 찾을 수 없음: {rule}")

            # 캐시에 저장
            self._analysis_cache[cache_key] = conditions

            # 값 변환 후처리
            self._post_process_conditions(conditions)

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
                self.logger.debug(f"딕셔너리 형태 트리 파싱: {tree.get('keyName', 'unknown')}")
                # 논리 연산자 블록인 경우
                if "logicType" in tree and "condition" in tree:
                    # 하위 조건들을 재귀적으로 파싱하고 직접 추가
                    for nested_data in tree.get("condition", []):
                        conditions.extend(
                            self._parse_condition_tree(nested_data)
                        )
                else:
                    # 일반 필드 조건
                    condition = self._parse_dict_condition(tree)
                    if condition:
                        conditions.append(condition)

            # 객체 형태의 트리
            elif hasattr(tree, "__dict__"):
                # ConditionTree 객체인지 RuleCondition 객체인지 구분
                tree_type = type(tree).__name__
                self.logger.debug(f"객체 형태 트리 파싱: {tree_type}")
                
                if tree_type == "ConditionTree":
                    # ConditionTree 객체인 경우
                    if tree.condition:
                        for item in tree.condition:
                            conditions.extend(self._parse_condition_tree(item))
                            
                elif tree_type == "RuleCondition":
                    # RuleCondition 객체인 경우
                    # keyName이 None이거나 placeholder인 경우 (논리 연산자 블록)
                    if not tree.keyName or tree.keyName == "placeholder":
                        # 논리 연산자 블록이면 하위 조건들을 처리
                        if hasattr(tree, "condition") and tree.condition:
                            for item in tree.condition:
                                conditions.extend(self._parse_condition_tree(item))
                        elif hasattr(tree, "conditions") and tree.conditions:
                            for item in tree.conditions:
                                conditions.extend(self._parse_condition_tree(item))
                    else:
                        # 실제 필드 조건이면 그대로 추가
                        conditions.append(tree)
                        
                else:
                    # 기타 객체의 경우 기존 방식 사용
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
                # fieldDataType에 따라 값 변환
                raw_value = condition_dict.get("value")
                field_data_type = condition_dict.get("fieldDataType", "String")
                converted_value = self._convert_value_by_type(raw_value, field_data_type)
                
                self.logger.debug(f"_parse_dict_condition: {condition_dict.get('keyName')} - {raw_value} ({type(raw_value).__name__}) -> {converted_value} ({type(converted_value).__name__})")
                
                return RuleCondition(
                    condUuid=condition_dict.get("condUuid"),
                    keyName=condition_dict.get("keyName"),
                    dispName=condition_dict.get(
                        "dispName", condition_dict.get("keyName")
                    ),
                    operator=condition_dict.get("operator"),
                    value=converted_value,
                    fieldDataType=field_data_type,
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
                
                # fieldDataType에 따라 값 변환
                if field_data_type and value is not None:
                    original_value = value
                    value = self._convert_value_by_type(value, field_data_type)
                    self.logger.debug(f"_parse_object_condition: {field} - {original_value} ({type(original_value).__name__}) -> {value} ({type(value).__name__})")

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
                    field_type = None
                    
                    # 1. fieldDataType이 있으면 우선 사용
                    if hasattr(condition, 'fieldDataType') and condition.fieldDataType:
                        # "Number" -> "number", "String" -> "string" 등으로 변환
                        field_type = condition.fieldDataType.lower()
                    
                    # 2. fieldDataType이 없으면 값으로부터 추론
                    if not field_type:
                        field_type = self._infer_type_from_value(
                            condition.value, condition.operator or ""
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

    def _infer_type_from_value(self, value: Any, operator: Optional[str] = None) -> str:
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
        self, conditions: List[RuleCondition], rule: Optional[Rule] = None
    ) -> Dict[str, Any]:
        """
        조건 구조의 다양한 메트릭 계산

        Args:
            conditions (List[RuleCondition]): 분석할 조건들
            rule (Rule, optional): 원본 룰 객체 (구조 분석용)

        Returns:
            Dict[str, Any]: 구조 메트릭들
        """
        try:
            if not conditions:
                return {
                    "depth": 1,
                    "condition_count": 0,
                    "condition_node_count": 0,
                    "field_condition_count": 0,
                    "unique_fields": [],
                    "complexity_score": 0,
                }

            # 기본 메트릭 계산 (펼쳐진 조건들 기준)
            condition_count = len(conditions)  # 실제 필드 조건 수
            field_condition_count = len(conditions)  # 동일
            unique_fields = self._extract_unique_fields(conditions)
            complexity_score = self._calculate_complexity_score(conditions)

            # 원본 구조 분석 (rule이 제공된 경우)
            if rule and hasattr(rule, 'conditionTree') and rule.conditionTree:
                depth, condition_node_count = self._analyze_original_structure(rule.conditionTree)
            else:
                # 폴백: 펼쳐진 조건들로 추정
                depth = 1
                condition_node_count = condition_count

            metrics = {
                "depth": depth,
                "condition_count": condition_count,
                "condition_node_count": condition_node_count,
                "field_condition_count": field_condition_count,
                "unique_fields": unique_fields,
                "complexity_score": complexity_score,
            }

            self.logger.debug(
                f"구조 메트릭 계산 완료: 깊이={depth}, 조건수={condition_count}, 필드조건수={field_condition_count}, 노드수={condition_node_count}"
            )
            return metrics

        except Exception as e:
            self.logger.error(f"구조 메트릭 계산 중 오류: {str(e)}", exc_info=True)
            return {
                "depth": 1,
                "condition_count": 0,
                "condition_node_count": 0,
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

    def _extract_condition_details(self, conditions: List[RuleCondition], depth_level: int = 0, parent_logic: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        조건 상세 정보 추출 (condUuid 포함)

        Args:
            conditions (List[RuleCondition]): 조건들
            depth_level (int): 현재 깊이 레벨
            parent_logic (str, optional): 부모 논리 연산자

        Returns:
            List[Dict[str, Any]]: 조건 상세 정보 리스트
        """
        details = []

        for condition in conditions:
            detail = {
                "condUuid": getattr(condition, "condUuid", None) or getattr(condition, "id", f"auto-{id(condition)}"),
                "keyName": condition.keyName,
                "dispName": getattr(condition, "dispName", None),
                "operator": condition.operator,
                "value": condition.value,
                "fieldDataType": getattr(condition, "fieldDataType", None),
                "depth_level": depth_level,
                "parent_logic": parent_logic
            }
            details.append(detail)

            # 중첩 조건들도 재귀적으로 처리
            if condition.conditions:
                nested_details = self._extract_condition_details(
                    condition.conditions, 
                    depth_level + 1, 
                    condition.operator
                )
                details.extend(nested_details)

        return details

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

    def _analyze_original_structure(self, condition_tree: Any) -> tuple[int, int]:
        """
        원본 conditionTree 구조를 분석하여 정확한 depth와 condition_node_count 계산

        Args:
            condition_tree: ConditionTree 객체

        Returns:
            tuple[int, int]: (depth, condition_node_count)
        """
        try:
            depth = 1
            condition_node_count = 0
            
            def analyze_recursive(tree, current_depth: int) -> tuple[int, int]:
                """재귀적으로 구조 분석"""
                nonlocal depth
                max_depth = current_depth
                node_count = 0
                
                if hasattr(tree, 'condition') and tree.condition:
                    # ConditionTree의 condition 배열 분석
                    for item in tree.condition:
                        if hasattr(item, 'keyName'):
                            if item.keyName and item.keyName != "placeholder":
                                # 실제 필드 조건 - 최종 깊이 +1
                                max_depth = max(max_depth, current_depth + 1)
                            else:
                                # 논리 연산자 블록
                                node_count += 1
                                if hasattr(item, 'condition') and item.condition:
                                    sub_depth, sub_count = analyze_recursive(item, current_depth + 1)
                                    max_depth = max(max_depth, sub_depth)
                                    node_count += sub_count
                
                depth = max(depth, max_depth)
                return max_depth, node_count
            
            # 루트 레벨부터 분석 시작
            _, condition_node_count = analyze_recursive(condition_tree, 1)
            
            # 루트 ConditionTree도 논리 연산자 블록으로 카운트
            if hasattr(condition_tree, 'logicType'):
                condition_node_count += 1
            
            return depth, condition_node_count
            
        except Exception as e:
            self.logger.error(f"원본 구조 분석 중 오류: {str(e)}")
            return 1, 0

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

    def _convert_value_by_type(self, value: Any, field_data_type: str) -> Any:
        """
        값을 주어진 타입으로 변환

        Args:
            value (Any): 값
            field_data_type (str): 필드 타입 ("String", "Number", "Boolean" 등)

        Returns:
            Any: 변환된 값
        """
        if value is None:
            return None

        # 대소문자 구분 없이 처리
        field_type_lower = field_data_type.lower()

        try:
            if field_type_lower in ["string", "str"]:
                return str(value)
            elif field_type_lower in ["number", "num", "int", "float"]:
                if isinstance(value, (int, float)):
                    return value
                elif isinstance(value, str) and value.strip():
                    # 정수인지 실수인지 판단하여 변환
                    try:
                        if '.' in value or 'e' in value.lower():
                            return float(value)
                        else:
                            return int(value)
                    except ValueError:
                        self.logger.warning(f"숫자 변환 실패: '{value}' -> 원본 값 유지")
                        return value
            elif field_type_lower in ["boolean", "bool"]:
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ["true", "1", "yes", "on"]
                elif isinstance(value, (int, float)):
                    return bool(value)
            elif field_type_lower in ["date", "datetime", "timestamp"]:
                return str(value)  # 날짜는 문자열로 유지
            elif field_type_lower in ["array", "list"]:
                if isinstance(value, list):
                    return value
                elif isinstance(value, str):
                    return [v.strip() for v in value.split(',')]
                else:
                    return [value]  # 단일 값을 리스트로 감싸기

            # 변환할 수 없는 경우 원본 값 반환
            return value

        except Exception as e:
            self.logger.warning(f"값 변환 중 오류 (type={field_data_type}, value={value}): {str(e)}")
            return value

    def _post_process_conditions(self, conditions: List[RuleCondition]):
        """
        조건 후처리: fieldDataType에 따라 값 변환
        
        Args:
            conditions (List[RuleCondition]): 후처리할 조건들
        """
        def process_condition(condition: RuleCondition):
            """개별 조건 처리"""
            if condition.keyName and condition.keyName != "placeholder":
                # fieldDataType이 있고 값이 있는 경우 변환
                if hasattr(condition, 'fieldDataType') and condition.fieldDataType and condition.value is not None:
                    original_value = condition.value
                    converted_value = self._convert_value_by_type(condition.value, condition.fieldDataType)
                    
                    # 값이 변환된 경우에만 업데이트
                    if converted_value != original_value:
                        condition.value = converted_value
                        self.logger.debug(f"값 변환: {condition.keyName} - {original_value} ({type(original_value).__name__}) -> {converted_value} ({type(converted_value).__name__})")
            
            # 중첩 조건 재귀 처리
            if condition.conditions:
                for nested in condition.conditions:
                    process_condition(nested)
        
        # 모든 조건 처리
        for condition in conditions:
            process_condition(condition)
