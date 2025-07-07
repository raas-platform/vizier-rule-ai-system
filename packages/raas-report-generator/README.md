# RAAS Report Generator

Universal report generator module for creating HTML reports and summaries from rule validation results.

## Features

- **HTML Report Generation**: Create beautiful, responsive HTML reports
- **Template Management**: Flexible Jinja2-based template system
- **Rule Summarization**: Generate human-readable summaries of rule structures
- **Issue Analysis**: Comprehensive issue detection and reporting
- **Metadata Management**: Track analysis performance and model usage

## Installation

```bash
pip install raas-report-generator
```

## Quick Start

```python
from raas_report_generator import ReportGenerator

# Initialize the generator
generator = ReportGenerator()

# Generate HTML report from validation result
validation_result = {
    "structure": {"ruleName": "Test Rule", "conditions": [...]},
    "issues": [{"type": "error", "message": "Invalid condition", "severity": "error"}],
    "report_metadata": {"rule_name": "Test Rule"}
}

report = generator.create_report_from_validation_result(validation_result)
print(report.report)  # HTML content
```

## API Reference

### ReportGenerator

Main class for generating reports and summaries.

#### Methods

- `generate_rule_summary(rule_data)`: Generate human-readable rule summary
- `generate_issues_summary(issues, rule_name)`: Generate issue detection summary
- `generate_html_report(rule_data, issues, metadata)`: Generate HTML report
- `create_report_from_validation_result(validation_result)`: Generate report from validation result

### TemplateManager

Manages Jinja2 templates for HTML generation.

#### Methods

- `generate_html_report(report_data)`: Generate HTML from report data
- `get_default_template()`: Get default HTML template

### Models

- `ReportData`: Input data for report generation
- `ReportResult`: Generated report result
- `ReportMetadata`: Report metadata and performance metrics
- `IssueInfo`: Issue information structure

## Custom Templates

You can provide custom templates by passing a templates directory:

```python
from pathlib import Path
from raas_report_generator import ReportGenerator, TemplateManager

template_manager = TemplateManager(templates_dir=Path("./my_templates"))
generator = ReportGenerator(template_manager=template_manager)
```

Your template should be named `report_template.html` and use the following variables:

- `rule_name`: Rule name
- `summary`: Generated summary
- `is_valid`: Boolean validity status
- `issues`: List of issue objects
- `structure`: Original rule structure
- `metadata`: Report metadata

## License

MIT License 