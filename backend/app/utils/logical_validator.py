from typing import List, Dict, Any
from app.models.rule import Rule
from app.models.validation_result import ValidationIssue

class LogicalValidator:
    """Utility for validating the logical structure of rules"""
    
    def validate(self, rule: Rule) -> List[ValidationIssue]:
        """
        Validate a rule and check for logical issues
        
        Args:
            rule: The rule to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Check for essential rule components
        issues.extend(self._validate_basic_structure(rule))
        
        # Validate conditions
        issues.extend(self._validate_conditions(rule))
        
        # Validate actions
        issues.extend(self._validate_actions(rule))
        
        # Validate rule logic
        issues.extend(self._validate_rule_logic(rule))
        
        return issues
    
    def _validate_basic_structure(self, rule: Rule) -> List[ValidationIssue]:
        """Validate the basic structure of the rule"""
        issues = []
        
        # Check if rule has a name
        if not rule.name or len(rule.name.strip()) == 0:
            issues.append(ValidationIssue(
                severity="error",
                message="Rule must have a name",
                location="name",
                suggestion="Provide a descriptive name for the rule"
            ))
        
        # Check if rule has a description
        if not rule.description or len(rule.description.strip()) == 0:
            issues.append(ValidationIssue(
                severity="warning",
                message="Rule should have a description",
                location="description",
                suggestion="Add a description to clarify the rule's purpose"
            ))
        
        # Check if rule has at least one condition
        if not rule.conditions or len(rule.conditions) == 0:
            issues.append(ValidationIssue(
                severity="error",
                message="Rule must have at least one condition",
                location="conditions",
                suggestion="Add conditions to define when the rule should apply"
            ))
        
        # Check if rule has at least one action
        if not rule.actions or len(rule.actions) == 0:
            issues.append(ValidationIssue(
                severity="error",
                message="Rule must have at least one action",
                location="actions",
                suggestion="Add actions to define what the rule should do"
            ))
        
        return issues
    
    def _validate_conditions(self, rule: Rule) -> List[ValidationIssue]:
        """Validate the conditions of the rule"""
        issues = []
        
        for i, condition in enumerate(rule.conditions):
            # Check if condition has a field
            if not condition.field:
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Condition {i+1} must have a field",
                    location=f"conditions[{i}].field",
                    suggestion="Specify a field to compare"
                ))
            
            # Check if condition has an operator
            if not condition.operator:
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Condition {i+1} must have an operator",
                    location=f"conditions[{i}].operator",
                    suggestion="Specify a comparison operator (eq, gt, lt, etc.)"
                ))
            
            # Check if operator is valid
            valid_operators = ["eq", "neq", "gt", "gte", "lt", "lte", "contains", "starts_with", "ends_with", "matches"]
            if condition.operator and condition.operator not in valid_operators:
                issues.append(ValidationIssue(
                    severity="warning",
                    message=f"Condition {i+1} has an uncommon operator: {condition.operator}",
                    location=f"conditions[{i}].operator",
                    suggestion=f"Consider using one of the standard operators: {', '.join(valid_operators)}"
                ))
            
            # Check if value is present (None is allowed as an explicit value)
            if not hasattr(condition, "value"):
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Condition {i+1} must have a value",
                    location=f"conditions[{i}].value",
                    suggestion="Provide a value to compare against"
                ))
        
        return issues
    
    def _validate_actions(self, rule: Rule) -> List[ValidationIssue]:
        """Validate the actions of the rule"""
        issues = []
        
        for i, action in enumerate(rule.actions):
            # Check if action has a type
            if not action.action_type:
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Action {i+1} must have an action_type",
                    location=f"actions[{i}].action_type",
                    suggestion="Specify the type of action to perform"
                ))
            
            # Check if action has parameters if needed
            if action.action_type and action.action_type not in ["notify", "log", "alert"]:
                if not action.parameters or len(action.parameters) == 0:
                    issues.append(ValidationIssue(
                        severity="warning",
                        message=f"Action {i+1} ({action.action_type}) might need parameters",
                        location=f"actions[{i}].parameters",
                        suggestion="Consider adding parameters for this action type"
                    ))
        
        return issues
    
    def _validate_rule_logic(self, rule: Rule) -> List[ValidationIssue]:
        """Validate the logical structure and potential issues in rule logic"""
        issues = []
        
        # Check for duplicate conditions (same field and operator)
        field_operator_pairs = [(c.field, c.operator) for c in rule.conditions]
        duplicate_pairs = set([pair for pair in field_operator_pairs if field_operator_pairs.count(pair) > 1])
        
        if duplicate_pairs:
            for pair in duplicate_pairs:
                issues.append(ValidationIssue(
                    severity="warning",
                    message=f"Duplicate condition detected for field '{pair[0]}' with operator '{pair[1]}'",
                    location="conditions",
                    suggestion="Review duplicate conditions and consider combining them"
                ))
        
        # Check for contradictory conditions
        # This is a simplified check for common contradictions
        field_value_map = {}
        for condition in rule.conditions:
            if condition.operator == "eq":
                if condition.field in field_value_map:
                    if field_value_map[condition.field] != condition.value:
                        issues.append(ValidationIssue(
                            severity="error",
                            message=f"Contradictory conditions detected for field '{condition.field}'",
                            location="conditions",
                            suggestion="Review conditions as they contain contradictions that can never be satisfied"
                        ))
                else:
                    field_value_map[condition.field] = condition.value
        
        # Check for redundant actions (same type and parameters)
        action_pairs = [(a.action_type, str(a.parameters)) for a in rule.actions]
        duplicate_actions = set([pair for pair in action_pairs if action_pairs.count(pair) > 1])
        
        if duplicate_actions:
            for pair in duplicate_actions:
                issues.append(ValidationIssue(
                    severity="info",
                    message=f"Duplicate action detected: {pair[0]}",
                    location="actions",
                    suggestion="Consider removing duplicate actions"
                ))
        
        return issues 