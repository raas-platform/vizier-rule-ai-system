# RaaS Rule Analyzer

Universal rule analyzer module for validating and analyzing business rules.

## Features

- **Rule Parsing**: Parse rules from various formats (JSON, dict, objects)
- **Condition Analysis**: Analyze rule conditions and structure
- **Issue Detection**: Detect 7 types of issues in rules
- **Performance Metrics**: Estimate execution time and memory usage
- **Quality Metrics**: Calculate maintainability, readability, and complexity scores
- **Field Type Inference**: Automatically infer field types from conditions

## Installation

```bash
pip install raas-rule-analyzer
```

## Quick Start

```python
from raas_rule_analyzer import RuleParser, RuleAnalyzer

# Parse a rule
parser = RuleParser()
rule = parser.parse({
    "ruleName": "Sample Rule",
    "conditionTree": {
        "condition": [
            {
                "keyName": "age",
                "operator": ">=",
                "value": 18,
                "fieldDataType": "Number"
            }
        ]
    }
})

# Analyze the rule
analyzer = RuleAnalyzer()
result = await analyzer.analyze_rule(rule)

print(f"Valid: {result.is_valid}")
print(f"Summary: {result.summary}")
print(f"Issues: {len(result.issues)}")
```

## Components

### RuleParser
Parse rules from various formats:
- JSON strings
- Python dictionaries  
- Rule objects

### ConditionAnalyzer
- Parse condition trees
- Infer field types
- Calculate structure metrics

### IssueDetector
Detect 7 types of issues:
1. `duplicate_condition` - Duplicate conditions
2. `type_mismatch` - Type mismatches
3. `invalid_operator` - Invalid operators
4. `self_contradiction` - Self-contradictions
5. `missing_condition` - Missing conditions
6. `ambiguous_branch` - Ambiguous branches
7. `complexity_warning` - Complexity warnings

### MetricsGenerator
Generate metrics:
- **Performance**: Execution time, memory usage estimates
- **Quality**: Maintainability, readability, complexity scores

### RuleAnalyzer
Main analyzer that orchestrates all analysis components.

## API Reference

### RuleAnalyzer

```python
analyzer = RuleAnalyzer()
result = await analyzer.analyze_rule(rule, include_ai_analysis=False)
```

**Parameters:**
- `rule`: Rule object to analyze
- `include_ai_analysis`: Whether to include AI analysis (optional)

**Returns:** `ValidationResult` object with:
- `is_valid`: Whether the rule is valid
- `summary`: Analysis summary
- `issues`: List of detected issues
- `structure`: Structure information
- `performance_metrics`: Performance metrics
- `quality_metrics`: Quality metrics

### RuleParser

```python
parser = RuleParser()
rule = parser.parse(rule_data)
```

**Parameters:**
- `rule_data`: Rule data (JSON string, dict, or Rule object)

**Returns:** Parsed `Rule` object

## Data Models

### Rule
Represents a business rule with conditions.

### RuleCondition  
Represents an individual condition within a rule.

### ValidationResult
Contains the complete analysis result.

### ConditionIssue
Represents an issue found in the rule.

## License

MIT License 