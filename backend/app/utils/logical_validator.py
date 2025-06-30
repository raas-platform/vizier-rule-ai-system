from typing import Any, Dict, List

from app.models.rule import Rule
from app.models.validation_result import ConditionIssue


class LogicalValidator:
    """Utility for validating rule logic and structure"""

    def validate(self, rule: Rule) -> List[ConditionIssue]:
        """
        Validate a rule for logical consistency and structural correctness

        Args:
            rule: The rule to validate

        Returns:
            List of validation issues found
        """
        issues = []

        # Validate basic structure
        issues.extend(self._validate_basic_structure(rule))

        # Validate conditions
        issues.extend(self._validate_conditions(rule))

        # Validate action
        if rule.action:
            issues.extend(self._validate_action(rule))

        # Validate overall logic
        issues.extend(self._validate_rule_logic(rule))

        return issues

    def _validate_basic_structure(self, rule: Rule) -> List[ConditionIssue]:
        """Validate the basic structure of the rule"""
        issues = []

        # Check if rule has a name
        if not rule.name or len(rule.name.strip()) == 0:
            issues.append(
                ConditionIssue(
                    condUuid=None,
                    keyName=None,
                    dispName=None,
                    severity="error",
                    issue_type="missing_name",
                    location="name",
                    explanation="Rule must have a name",
                    suggestion="Provide a descriptive name for the rule",
                )
            )

        # Check if rule has a description
        if not rule.description or len(rule.description.strip()) == 0:
            issues.append(
                ConditionIssue(
                    severity="warning",
                    issue_type="missing_description",
                    location="description",
                    explanation="Rule should have a description",
                    suggestion="Add a description to clarify the rule's purpose",
                    dispName=rule.name if rule.name else "Unnamed Rule",
                    condUuid=rule.ruleUuid,
                    keyName="description"
                )
            )

        # Check if rule has at least one condition
        if not rule.conditions or len(rule.conditions) == 0:
            issues.append(
                ConditionIssue(
                    severity="error",
                    issue_type="missing_conditions",
                    location="conditions",
                    explanation="Rule must have at least one condition",
                    suggestion="Add conditions to define when the rule should apply",
                    dispName=rule.name if rule.name else "Unnamed Rule",
                    condUuid=rule.ruleUuid,
                    keyName="conditions"
                )
            )

        # Check if rule has an action
        if not rule.action:
            issues.append(
                ConditionIssue(
                    severity="error",
                    issue_type="missing_action",
                    location="action",
                    explanation="Rule must have an action",
                    suggestion="Add an action to define what the rule should do",
                    dispName=rule.name if rule.name else "Unnamed Rule",
                    condUuid=rule.ruleUuid,
                    keyName="action"
                )
            )

        return issues

    def _validate_conditions(self, rule: Rule) -> List[ConditionIssue]:
        """Validate the conditions of the rule"""
        issues = []

        for i, condition in enumerate(rule.conditions or []):
            if not condition.keyName:
                issues.append(
                    ConditionIssue(
                        severity="error",
                        issue_type="missing_keyName",
                        location=f"conditions[{i}].keyName",
                        explanation="Condition must have a keyName",
                        suggestion="Specify a keyName for the condition",
                        dispName=rule.name if rule.name else "Unnamed Rule",
                        condUuid=rule.ruleUuid,
                        keyName=f"conditions[{i}].keyName"
                    )
                )

            # Check if condition has an operator
            if not condition.operator:
                issues.append(
                    ConditionIssue(
                        severity="error",
                        issue_type="missing_operator",
                        location=f"conditions[{i}].operator",
                        explanation=f"Condition {i+1} must have an operator",
                        suggestion="Specify a comparison operator (eq, gt, lt, etc.)",
                        dispName=rule.name if rule.name else "Unnamed Rule",
                        condUuid=rule.ruleUuid,
                        keyName=f"conditions[{i}].operator"
                    )
                )

            # Check if operator is valid
            valid_operators = [
                "eq",
                "neq",
                "gt",
                "gte",
                "lt",
                "lte",
                "contains",
                "starts_with",
                "ends_with",
                "matches",
            ]
            if condition.operator and condition.operator not in valid_operators:
                issues.append(
                    ConditionIssue(
                        severity="warning",
                        issue_type="uncommon_operator",
                        location=f"conditions[{i}].operator",
                        explanation=(
                            f"Condition {i+1} has an uncommon operator: "
                            f"{condition.operator}"
                        ),
                        suggestion=(
                            f"Consider using one of the standard operators: "
                            f"{', '.join(valid_operators)}"
                        ),
                        dispName=rule.name if rule.name else "Unnamed Rule",
                        condUuid=rule.ruleUuid,
                        keyName=f"conditions[{i}].operator"
                    )
                )

            # Check if value is present (None is allowed as an explicit value)
            if not hasattr(condition, "value"):
                issues.append(
                    ConditionIssue(
                        severity="error",
                        issue_type="missing_value",
                        location=f"conditions[{i}].value",
                        explanation=f"Condition {i+1} must have a value",
                        suggestion="Provide a value to compare against",
                        dispName=rule.name if rule.name else "Unnamed Rule",
                        condUuid=rule.ruleUuid,
                        keyName=f"conditions[{i}].value"
                    )
                )

        return issues

    def _validate_action(self, rule: Rule) -> List[ConditionIssue]:
        """Validate the action of the rule"""
        issues = []

        action = rule.action
        if action and not action.get("action_type"):
            issues.append(
                ConditionIssue(
                    severity="error",
                    issue_type="missing_action_type",
                    location="action.action_type",
                    explanation="Action must have an action_type",
                    suggestion="Specify the type of action to perform",
                    dispName=rule.name if rule.name else "Unnamed Rule",
                    condUuid=rule.ruleUuid,
                    keyName="action.action_type"
                )
            )

        # Check if action has parameters if needed
        action_type = action.get("action_type", "") if action else ""
        if action_type and action_type not in ["notify", "log", "alert"]:
            parameters = action.get("parameters", {}) if action else {}
            if not parameters:
                issues.append(
                    ConditionIssue(
                        severity="warning",
                        issue_type="missing_parameters",
                        location="action.parameters",
                        explanation=f"Action ({action_type}) might need parameters",
                        suggestion="Consider adding parameters for this action type",
                        dispName=rule.name if rule.name else "Unnamed Rule",
                        condUuid=rule.ruleUuid,
                        keyName="action.parameters"
                    )
                )

        return issues

    def _validate_rule_logic(self, rule: Rule) -> List[ConditionIssue]:
        """Validate the logical structure and potential issues in rule logic"""
        issues = []

        # Check for duplicate conditions (same field and operator)
        field_operator_pairs = [(c.keyName, c.operator) for c in rule.conditions] if rule.conditions else []
        duplicate_pairs = set(
            pair
            for pair in field_operator_pairs
            if field_operator_pairs.count(pair) > 1
        )

        if duplicate_pairs:
            for pair in duplicate_pairs:
                issues.append(
                    ConditionIssue(
                        severity="warning",
                        issue_type="duplicate_condition",
                        location="conditions",
                        explanation=(
                            f"Duplicate condition detected for field '{pair[0]}' "
                            f"with operator '{pair[1]}'"
                        ),
                        suggestion="Review duplicate conditions and consider combining them",
                        dispName=rule.name if rule.name else "Unnamed Rule",
                        condUuid=rule.ruleUuid,
                        keyName="conditions"
                    )
                )

        # Check for contradictory conditions
        # This is a simplified check for common contradictions
        field_value_map: Dict[str, Any] = {}
        for condition in rule.conditions or []:
            key_name = condition.keyName if condition.keyName is not None else ""
            if condition.operator == "eq":
                if key_name in field_value_map:
                    if field_value_map[key_name] != condition.value:
                        issues.append(
                            ConditionIssue(
                                severity="error",
                                issue_type="contradictory_conditions",
                                location="conditions",
                                explanation=(
                                    f"Contradictory conditions detected for field "
                                    f"'{key_name}'"
                                ),
                                suggestion=(
                                    "Review conditions as they contain contradictions "
                                    "that can never be satisfied"
                                ),
                                dispName=rule.name if rule.name else "Unnamed Rule",
                                condUuid=rule.ruleUuid,
                                keyName="conditions"
                            )
                        )
                else:
                    field_value_map[key_name] = condition.value

        return issues
