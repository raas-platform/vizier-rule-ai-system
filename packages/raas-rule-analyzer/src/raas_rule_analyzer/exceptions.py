"""
Exception classes for RaaS Rule Analyzer

This module defines custom exceptions used throughout the rule analyzer.
"""


class RuleAnalyzerError(Exception):
    """
    Base exception for all rule analyzer errors
    """
    pass


class RuleParsingError(RuleAnalyzerError):
    """
    Exception raised when rule parsing fails
    """
    def __init__(self, message: str, rule_data: dict = None):
        super().__init__(message)
        self.rule_data = rule_data


class ValidationError(RuleAnalyzerError):
    """
    Exception raised when rule validation fails
    """
    def __init__(self, message: str, issues: list = None):
        super().__init__(message)
        self.issues = issues or []


class ConditionAnalysisError(RuleAnalyzerError):
    """
    Exception raised when condition analysis fails
    """
    def __init__(self, message: str, condition_data: dict = None):
        super().__init__(message)
        self.condition_data = condition_data


class IssueDetectionError(RuleAnalyzerError):
    """
    Exception raised when issue detection fails
    """
    def __init__(self, message: str, detection_context: dict = None):
        super().__init__(message)
        self.detection_context = detection_context


class MetricsGenerationError(RuleAnalyzerError):
    """
    Exception raised when metrics generation fails
    """
    def __init__(self, message: str, metrics_context: dict = None):
        super().__init__(message)
        self.metrics_context = metrics_context


class ConfigurationError(RuleAnalyzerError):
    """
    Exception raised when configuration is invalid
    """
    pass


class DataTypeError(RuleAnalyzerError):
    """
    Exception raised when data type conversion or validation fails
    """
    def __init__(self, message: str, expected_type: str = None, actual_type: str = None):
        super().__init__(message)
        self.expected_type = expected_type
        self.actual_type = actual_type 