"""
룰 파서 (RuleParser)

다양한 형식의 룰 데이터를 파싱하여 Rule 객체로 변환하는 기능을 제공합니다.
- JSON 형식 룰 파싱
- 딕셔너리 형식 룰 파싱
- 객체 형식 룰 파싱
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from .models import Rule, RuleCondition, ConditionTree
from .exceptions import RuleParsingError


class RuleParser:
    """
    다양한 형식의 룰 데이터를 파싱하는 클래스

    지원하는 입력 형식:
    - JSON 문자열
    - Python 딕셔너리
    - Rule 객체 (검증 및 정규화)
    """

    def __init__(self):
        """RuleParser 초기화"""
        self.logger = logging.getLogger(__name__)

    def parse(self, rule_data: Union[str, dict, Rule]) -> Rule:
        """
        룰 데이터를 파싱하여 Rule 객체로 변환

        Args:
            rule_data: 파싱할 룰 데이터 (JSON 문자열, 딕셔너리, 또는 Rule 객체)

        Returns:
            Rule: 파싱된 룰 객체

        Raises:
            RuleParsingError: 파싱 실패 시
        """
        try:
            if isinstance(rule_data, str):
                return self._parse_json_string(rule_data)
            elif isinstance(rule_data, dict):
                return self._parse_dict(rule_data)
            elif isinstance(rule_data, Rule):
                return self._validate_rule_object(rule_data)
            else:
                raise RuleParsingError(f"지원하지 않는 룰 데이터 타입: {type(rule_data)}")

        except Exception as e:
            if isinstance(e, RuleParsingError):
                raise
            raise RuleParsingError(f"룰 파싱 중 오류 발생: {str(e)}")

    def parse_multiple(self, rules_data: List[Union[str, dict, Rule]]) -> List[Rule]:
        """
        여러 룰 데이터를 일괄 파싱

        Args:
            rules_data: 파싱할 룰 데이터 리스트

        Returns:
            List[Rule]: 파싱된 룰 객체 리스트
        """
        parsed_rules = []
        
        for i, rule_data in enumerate(rules_data):
            try:
                parsed_rule = self.parse(rule_data)
                parsed_rules.append(parsed_rule)
            except RuleParsingError as e:
                self.logger.error(f"룰 #{i} 파싱 실패: {str(e)}")
                # 개별 룰 파싱 실패는 로그만 남기고 계속 진행
                continue
        
        return parsed_rules

    def _parse_json_string(self, json_string: str) -> Rule:
        """JSON 문자열 파싱"""
        try:
            rule_dict = json.loads(json_string)
            return self._parse_dict(rule_dict)
        except json.JSONDecodeError as e:
            raise RuleParsingError(f"유효하지 않은 JSON 형식: {str(e)}")

    def _parse_dict(self, rule_dict: dict) -> Rule:
        """딕셔너리 파싱"""
        try:
            # 필수 필드 확인
            if not rule_dict:
                raise RuleParsingError("빈 룰 데이터")

            # 조건 트리 파싱
            condition_tree = None
            if "conditionTree" in rule_dict:
                condition_tree = self._parse_condition_tree(rule_dict["conditionTree"])
            
            # 조건 리스트 파싱
            conditions = None
            if "conditions" in rule_dict:
                conditions = self._parse_conditions_list(rule_dict["conditions"])

            # Rule 객체 생성
            rule = Rule(
                ruleUuid=rule_dict.get("ruleUuid"),
                ruleName=rule_dict.get("ruleName") or rule_dict.get("name"),
                name=rule_dict.get("name"),
                ruleMsg=rule_dict.get("ruleMsg"),
                conditionTree=condition_tree,
                conditions=conditions,
                ruleCondition=rule_dict.get("ruleCondition")
            )

            return rule

        except Exception as e:
            if isinstance(e, RuleParsingError):
                raise
            raise RuleParsingError(f"딕셔너리 파싱 실패: {str(e)}")

    def _parse_condition_tree(self, tree_data: Any) -> Optional[ConditionTree]:
        """조건 트리 파싱"""
        if not tree_data:
            return None

        try:
            if isinstance(tree_data, dict):
                conditions = None
                if "condition" in tree_data:
                    conditions = self._parse_conditions_list(tree_data["condition"])
                
                return ConditionTree(
                    condition=conditions,
                    logicType=tree_data.get("logicType")
                )
            else:
                # 객체 형태인 경우
                conditions = None
                if hasattr(tree_data, "condition") and tree_data.condition:
                    conditions = self._parse_conditions_list(tree_data.condition)
                
                return ConditionTree(
                    condition=conditions,
                    logicType=getattr(tree_data, "logicType", None)
                )

        except Exception as e:
            self.logger.warning(f"조건 트리 파싱 실패: {str(e)}")
            return None

    def _parse_conditions_list(self, conditions_data: List[Any]) -> List[RuleCondition]:
        """조건 리스트 파싱"""
        if not conditions_data:
            return []

        conditions = []
        
        for condition_data in conditions_data:
            try:
                condition = self._parse_single_condition(condition_data)
                if condition:
                    conditions.append(condition)
            except Exception as e:
                self.logger.warning(f"개별 조건 파싱 실패: {str(e)}")
                continue
        
        return conditions

    def _parse_single_condition(self, condition_data: Any) -> Optional[RuleCondition]:
        """개별 조건 파싱"""
        if not condition_data:
            return None

        try:
            if isinstance(condition_data, dict):
                return self._parse_condition_dict(condition_data)
            elif isinstance(condition_data, RuleCondition):
                return condition_data
            else:
                # 객체 형태인 경우
                return self._parse_condition_object(condition_data)

        except Exception as e:
            self.logger.warning(f"조건 파싱 실패: {str(e)}")
            return None

    def _parse_condition_dict(self, condition_dict: dict) -> RuleCondition:
        """딕셔너리 형태의 조건 파싱"""
        # 하위 조건들 파싱
        nested_conditions = None
        if "conditions" in condition_dict:
            nested_conditions = self._parse_conditions_list(condition_dict["conditions"])
        elif "condition" in condition_dict:
            nested_conditions = self._parse_conditions_list(condition_dict["condition"])

        return RuleCondition(
            keyName=condition_dict.get("keyName"),
            operator=condition_dict.get("operator"),
            value=condition_dict.get("value"),
            fieldDataType=condition_dict.get("fieldDataType"),
            conditions=nested_conditions,
            logicType=condition_dict.get("logicType"),
            condUuid=condition_dict.get("condUuid")
        )

    def _parse_condition_object(self, condition_obj: Any) -> RuleCondition:
        """객체 형태의 조건 파싱"""
        # 하위 조건들 파싱
        nested_conditions = None
        if hasattr(condition_obj, "conditions") and condition_obj.conditions:
            nested_conditions = self._parse_conditions_list(condition_obj.conditions)
        elif hasattr(condition_obj, "condition") and condition_obj.condition:
            nested_conditions = self._parse_conditions_list(condition_obj.condition)

        return RuleCondition(
            keyName=getattr(condition_obj, "keyName", None),
            operator=getattr(condition_obj, "operator", None),
            value=getattr(condition_obj, "value", None),
            fieldDataType=getattr(condition_obj, "fieldDataType", None),
            conditions=nested_conditions,
            logicType=getattr(condition_obj, "logicType", None),
            condUuid=getattr(condition_obj, "condUuid", None)
        )

    def _validate_rule_object(self, rule: Rule) -> Rule:
        """Rule 객체 검증 및 정규화"""
        try:
            # 기본 검증
            if not hasattr(rule, "ruleUuid") and not hasattr(rule, "ruleName") and not hasattr(rule, "name"):
                self.logger.warning("룰에 식별 정보가 없습니다")

            # 조건 데이터 검증
            has_conditions = (
                (hasattr(rule, "conditionTree") and rule.conditionTree) or
                (hasattr(rule, "conditions") and rule.conditions) or
                (hasattr(rule, "ruleCondition") and rule.ruleCondition)
            )

            if not has_conditions:
                self.logger.warning("룰에 조건 데이터가 없습니다")

            return rule

        except Exception as e:
            raise RuleParsingError(f"Rule 객체 검증 실패: {str(e)}")

    def validate_rule_structure(self, rule: Rule) -> Dict[str, Any]:
        """
        룰 구조 유효성 검사

        Args:
            rule: 검사할 룰 객체

        Returns:
            Dict[str, Any]: 검사 결과
        """
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "info": {}
        }

        try:
            # 1. 기본 정보 검사
            if not rule.ruleUuid and not rule.ruleName and not rule.name:
                validation_result["warnings"].append("룰 식별 정보가 없습니다")

            # 2. 조건 데이터 검사
            condition_sources = []
            if rule.conditionTree:
                condition_sources.append("conditionTree")
            if rule.conditions:
                condition_sources.append("conditions")
            if rule.ruleCondition:
                condition_sources.append("ruleCondition")

            if not condition_sources:
                validation_result["errors"].append("조건 데이터가 없습니다")
                validation_result["is_valid"] = False
            elif len(condition_sources) > 1:
                validation_result["warnings"].append(f"여러 조건 소스가 있습니다: {', '.join(condition_sources)}")

            # 3. 조건 구조 검사
            if rule.conditionTree and rule.conditionTree.condition:
                condition_count = len(rule.conditionTree.condition)
                validation_result["info"]["condition_count"] = condition_count
                
                if condition_count == 0:
                    validation_result["warnings"].append("조건 트리가 비어있습니다")

            # 4. 메타데이터 검사
            validation_result["info"]["has_rule_message"] = bool(rule.ruleMsg)
            validation_result["info"]["rule_name"] = rule.ruleName or rule.name or "없음"

        except Exception as e:
            validation_result["errors"].append(f"구조 검사 중 오류: {str(e)}")
            validation_result["is_valid"] = False

        return validation_result

    def normalize_rule(self, rule: Rule) -> Rule:
        """
        룰 객체 정규화

        Args:
            rule: 정규화할 룰 객체

        Returns:
            Rule: 정규화된 룰 객체
        """
        try:
            # name 필드 정규화
            if not rule.name and rule.ruleName:
                rule.name = rule.ruleName
            elif not rule.ruleName and rule.name:
                rule.ruleName = rule.name

            # UUID 정규화
            if not rule.ruleUuid:
                # 간단한 UUID 생성 (실제로는 더 정교한 방법 사용)
                import uuid
                rule.ruleUuid = str(uuid.uuid4())

            return rule

        except Exception as e:
            self.logger.warning(f"룰 정규화 실패: {str(e)}")
            return rule 