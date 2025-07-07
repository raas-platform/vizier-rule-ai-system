"""
RaaS Rule Analyzer Module

Universal rule analyzer module for validating and analyzing business rules.

This module provides:
- Rule parsing and validation
- Condition analysis and detection
- Issue detection and reporting
- Performance metrics generation
- Rule structure analysis
"""

from .models import Rule, RuleCondition, ValidationResult, ConditionIssue
from .analyzers import (
    ConditionAnalyzer,
    IssueDetector,
    MetricsGenerator,
    RuleAnalyzer,
)
from .parser import RuleParser
from .exceptions import (
    RuleAnalyzerError,
    RuleParsingError,
    ValidationError,
)

__version__ = "1.0.0"
__author__ = "Yeonjae"
__email__ = "dev@example.com"

__all__ = [
    # Models
    "Rule",
    "RuleCondition", 
    "ValidationResult",
    "ConditionIssue",
    
    # Analyzers
    "ConditionAnalyzer",
    "IssueDetector",
    "MetricsGenerator",
    "RuleAnalyzer",
    
    # Parser
    "RuleParser",
    
    # Exceptions
    "RuleAnalyzerError",
    "RuleParsingError",
    "ValidationError",
] 