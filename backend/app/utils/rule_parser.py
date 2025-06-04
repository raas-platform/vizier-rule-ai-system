import json
from typing import Dict, Any, Optional, List, Union
from app.models.rule import Rule, RuleCondition, RuleAction

class RuleParser:
    """Utility for parsing rules from JSON and back"""
    
    @staticmethod
    def parse_json_to_rule(json_str: str) -> Rule:
        """
        Parse a JSON string into a Rule object
        
        Args:
            json_str: JSON string representation of a rule
            
        Returns:
            Rule object
            
        Raises:
            ValueError: If JSON cannot be parsed or is not valid
        """
        try:
            data = json.loads(json_str)
            return RuleParser.parse_dict_to_rule(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
    
    @staticmethod
    def parse_dict_to_rule(data: Dict[str, Any]) -> Rule:
        """
        Parse a dictionary into a Rule object
        
        Args:
            data: Dictionary representation of a rule
            
        Returns:
            Rule object
            
        Raises:
            ValueError: If dictionary format is not valid
        """
        try:
            # Parse conditions
            conditions = []
            for condition_data in data.get("conditions", []):
                conditions.append(RuleCondition(
                    field=condition_data["field"],
                    operator=condition_data["operator"],
                    value=condition_data["value"]
                ))
            
            # Parse actions
            actions = []
            for action_data in data.get("actions", []):
                actions.append(RuleAction(
                    action_type=action_data["action_type"],
                    parameters=action_data.get("parameters", {})
                ))
            
            # Create rule
            rule = Rule(
                id=data.get("id"),
                name=data["name"],
                description=data["description"],
                conditions=conditions,
                actions=actions,
                priority=data.get("priority", 1),
                enabled=data.get("enabled", True)
            )
            
            return rule
        except KeyError as e:
            raise ValueError(f"Missing required field in rule: {str(e)}")
    
    @staticmethod
    def rule_to_dict(rule: Rule) -> Dict[str, Any]:
        """
        Convert a Rule object to a dictionary
        
        Args:
            rule: Rule object
            
        Returns:
            Dictionary representation of the rule
        """
        # Convert conditions
        conditions = []
        for condition in rule.conditions:
            conditions.append({
                "field": condition.field,
                "operator": condition.operator,
                "value": condition.value
            })
        
        # Convert actions
        actions = []
        for action in rule.actions:
            actions.append({
                "action_type": action.action_type,
                "parameters": action.parameters
            })
        
        # Create rule dictionary
        rule_dict = {
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "conditions": conditions,
            "actions": actions,
            "priority": rule.priority,
            "enabled": rule.enabled
        }
        
        return rule_dict
    
    @staticmethod
    def rule_to_json(rule: Rule) -> str:
        """
        Convert a Rule object to a JSON string
        
        Args:
            rule: Rule object
            
        Returns:
            JSON string representation of the rule
        """
        rule_dict = RuleParser.rule_to_dict(rule)
        return json.dumps(rule_dict, indent=2) 