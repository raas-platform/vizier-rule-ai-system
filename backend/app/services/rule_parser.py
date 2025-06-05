import uuid
from typing import Any, Dict, List, Optional, Union

from ..models.rule import ConditionTree, Rule, RuleAction, RuleCondition
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RuleParser:
    """룰 JSON 파싱 서비스 - 새로운 형식과 기존 형식 모두 지원"""

    def __init__(self):
        """RuleParser 초기화"""
        pass

    def parse_rule(self, rule_data: Dict[str, Any]) -> Rule:
        """
        JSON 데이터를 Rule 모델로 파싱
        새로운 JSON 형식 (ruleUuid, ruleName, ruleMsg, conditionTree)을 우선 처리
        """
        try:
            logger.debug(f"파싱할 룰 데이터: {rule_data}")

            # 새로운 형식 처리 - conditionTree 필드가 있는 경우
            if "conditionTree" in rule_data and rule_data["conditionTree"]:
                # conditionTree 파싱
                condition_tree_data = rule_data["conditionTree"]
                condition_tree = self._parse_condition_tree(
                    condition_tree_data
                )

                logger.debug(f"파싱된 conditionTree: {condition_tree}")

                # Rule 객체 생성 (새로운 형식)
                rule = Rule(
                    ruleUuid=rule_data.get("ruleUuid"),
                    ruleName=rule_data.get("ruleName", "Unnamed Rule"),
                    ruleMsg=rule_data.get("ruleMsg", ""),
                    conditionTree=condition_tree,
                    rulePriority=rule_data.get("rulePriority", 1),
                    ruleEnabled=rule_data.get("ruleEnabled", True),
                )

                logger.debug(
                    f"생성된 Rule 객체 - ruleName: {rule.ruleName}, ruleUuid: {rule.ruleUuid}"
                )
                logger.debug(
                    f"Rule 객체의 conditionTree: {rule.conditionTree}"
                )

                return rule
            else:
                # 기존 형식 처리로 위임
                logger.warning(
                    "룰 파싱 오류: conditionTree가 없어 기존 형식으로 처리합니다."
                )
                return self._parse_legacy_rule(rule_data)

        except Exception as e:
            logger.error(f"룰 파싱 오류: {str(e)}", exc_info=True)
            raise ValueError(f"룰 파싱 실패: {str(e)}")

    def _parse_condition_tree(
        self, condition_tree_data: Dict[str, Any]
    ) -> ConditionTree:
        """conditionTree JSON을 ConditionTree 모델로 파싱"""

        logic_type = condition_tree_data.get("logicType", "AND")
        conditions_data = condition_tree_data.get("condition", [])

        # condition 배열 파싱
        conditions = []
        for condition_data in conditions_data:
            if isinstance(condition_data, dict):
                condition = self._parse_condition(condition_data)
                if condition:
                    conditions.append(condition)

        return ConditionTree(logicType=logic_type, condition=conditions)

    def _parse_condition(
        self, condition_data: Dict[str, Any]
    ) -> Optional[RuleCondition]:
        """개별 조건 데이터를 RuleCondition 모델로 파싱"""

        try:
            # 중첩된 논리 연산자 블록인지 확인
            if "logicType" in condition_data and "condition" in condition_data:
                # 중첩된 ConditionTree 처리
                nested_conditions = []
                for nested_data in condition_data.get("condition", []):
                    nested_condition = self._parse_condition(nested_data)
                    if nested_condition:
                        nested_conditions.append(nested_condition)

                return RuleCondition(
                    keyName="placeholder",  # 논리 연산자 블록 표시
                    dispName=f"{condition_data['logicType']} 그룹",
                    operator=condition_data["logicType"].lower(),
                    value=None,
                    fieldDataType="logical",
                    conditions=nested_conditions,
                )

            # 일반 필드 조건 처리
            elif "keyName" in condition_data and "operator" in condition_data:
                return RuleCondition(
                    keyName=condition_data.get("keyName"),
                    dispName=condition_data.get(
                        "dispName", condition_data.get("keyName")
                    ),
                    operator=condition_data.get("operator"),
                    value=condition_data.get("value"),
                    fieldDataType=condition_data.get(
                        "fieldDataType", "String"
                    ),
                )

            else:
                logger.warning(f"알 수 없는 조건 형식: {condition_data}")
                return None

        except Exception as e:
            logger.error(f"조건 파싱 오류: {str(e)}", exc_info=True)
            return None

    def _parse_legacy_rule(self, rule_data: Dict[str, Any]) -> Rule:
        """기존 형식의 룰 데이터 파싱"""
        try:
            # 기존 형식에서는 conditions 배열을 직접 처리
            conditions_data = rule_data.get("conditions", [])
            conditions = []

            for condition_data in conditions_data:
                if isinstance(condition_data, dict):
                    # 필드 조건인지 확인
                    if (
                        "field" in condition_data
                        and "operator" in condition_data
                    ):
                        condition = RuleCondition(
                            keyName=condition_data.get("field"),
                            dispName=condition_data.get("field"),
                            operator=condition_data.get("operator"),
                            value=condition_data.get("value"),
                            fieldDataType=condition_data.get(
                                "fieldDataType", "String"
                            ),
                            field=condition_data.get("field"),  # 하위 호환성
                        )
                        conditions.append(condition)

            # 기존 형식 Rule 생성
            return Rule(
                id=rule_data.get("id"),
                name=rule_data.get("name", "Unnamed Rule"),
                description=rule_data.get("description", ""),
                conditions=conditions,
                action=rule_data.get("action", {}),
                priority=rule_data.get("priority", 1),
                enabled=rule_data.get("enabled", True),
            )

        except Exception as e:
            logger.error(f"기존 형식 규칙 파싱 오류: {str(e)}", exc_info=True)
            raise ValueError(f"기존 형식 룰 파싱 실패: {str(e)}")

    def validate_rule_structure(self, rule: Rule) -> bool:
        """룰 구조 유효성 검증"""

        # 기본 필수 필드 체크
        if not hasattr(rule, "ruleName") and not hasattr(rule, "name"):
            logger.warning("룰 이름이 없습니다.")
            return False

        # 조건 존재 여부 체크
        has_conditions = False
        if hasattr(rule, "conditionTree") and rule.conditionTree:
            if (
                rule.conditionTree.condition
                and len(rule.conditionTree.condition) > 0
            ):
                has_conditions = True
        elif hasattr(rule, "conditions") and rule.conditions:
            if len(rule.conditions) > 0:
                has_conditions = True

        if not has_conditions:
            logger.warning("룰에 조건이 없습니다.")
            return False

        return True
