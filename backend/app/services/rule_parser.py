from typing import Dict, Any, List
from app.models.rule import Rule, RuleCondition, RuleAction
import uuid

class RuleParser:
    """Service for parsing rule JSON into Rule objects"""
    
    def parse_rule(self, rule_json: Dict[str, Any]) -> Rule:
        """
        Parse rule JSON into a Rule object
        
        Args:
            rule_json: Rule data in JSON format
            
        Returns:
            Rule object
            
        Raises:
            Exception: If JSON parsing fails
        """
        try:
            # Extract rule data from JSON
            rule_data = rule_json.get("rule", rule_json)
            
            # Generate ID if not present
            if not rule_data.get("id"):
                rule_data["id"] = str(uuid.uuid4())
            
            # Parse conditions
            conditions = self._parse_conditions(rule_data.get("conditions", []))
            
            # Parse actions
            actions = self._parse_actions(rule_data.get("actions", []))
            
            # Create Rule object
            rule = Rule(
                id=rule_data.get("id"),
                name=rule_data.get("name", "규칙"),
                description=rule_data.get("description", ""),
                conditions=conditions,
                actions=actions,
                priority=rule_data.get("priority", 1),
                enabled=rule_data.get("enabled", True)
            )
            
            return rule
        except Exception as e:
            print(f"규칙 파싱 오류: {str(e)}")
            raise Exception(f"규칙 JSON을 파싱하는 중 오류가 발생했습니다: {str(e)}")
    
    def _parse_conditions(self, conditions_json: List[Dict[str, Any]]) -> List[RuleCondition]:
        """
        Parse conditions from JSON
        
        Args:
            conditions_json: List of condition data in JSON format
            
        Returns:
            List of RuleCondition objects
        """
        conditions = []
        
        for condition_data in conditions_json:
            condition = RuleCondition(
                field=condition_data.get("field", ""),
                operator=condition_data.get("operator", "equals"),
                value=condition_data.get("value", "")
            )
            conditions.append(condition)
        
        return conditions
    
    def _parse_actions(self, actions_json: List[Dict[str, Any]]) -> List[RuleAction]:
        """
        Parse actions from JSON
        
        Args:
            actions_json: List of action data in JSON format
            
        Returns:
            List of RuleAction objects
        """
        actions = []
        
        for action_data in actions_json:
            action = RuleAction(
                action_type=action_data.get("action_type", ""),
                parameters=action_data.get("parameters", {})
            )
            actions.append(action)
        
        return actions 