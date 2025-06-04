export interface RuleCondition {
  field: string;
  operator: string;
  value: any;
}

export interface RuleAction {
  action_type: string;
  parameters: Record<string, any>;
}

export interface Rule {
  id?: string;
  name: string;
  description: string;
  conditions: RuleCondition[];
  actions: RuleAction[];
  priority: number;
  enabled: boolean;
}

export interface ValidationIssue {
  severity: 'error' | 'warning' | 'info';
  message?: string;
  explanation?: string;
  location?: string;
  suggestion?: string;
  field?: string;
  issue_type?: string;
}

export interface ValidationResult {
  is_valid: boolean;
  summary: string;
  issues: ValidationIssue[];
  issue_counts?: Record<string, number>;
  structure?: {
    depth: number;
    condition_count: number;
    unique_fields: string[];
  };
  complexity_score?: number;
  rule_summary?: string;
}

export interface RuleValidationResponse {
  validation_result: ValidationResult;
  rule_summary: string;
}

export interface RuleReportRequest {
  rule_json: Record<string, any>;
  include_markdown?: boolean;
}

export interface RuleReportResponse {
  report: string;
  rule_id?: string;
  rule_name?: string;
} 