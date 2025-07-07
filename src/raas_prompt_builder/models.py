class PromptType(str, Enum):
    """프롬프트 유형"""
    # 기존 개발자 활동 관련
    DAILY_SUMMARY = "daily_summary"
    CODE_REVIEW = "code_review"
    WORK_PATTERN_ANALYSIS = "work_pattern_analysis"
    TEAM_REPORT = "team_report"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    COMMIT_SUMMARY = "commit_summary"
    BUG_ANALYSIS = "bug_analysis"
    
    # 룰 검증 시스템 관련 (새로 추가)
    RULE_ANALYSIS = "rule_analysis"
    RULE_VALIDATION = "rule_validation"
    RULE_OPTIMIZATION = "rule_optimization"
    HTML_REPORT = "html_report"
    ISSUE_DETECTION = "issue_detection"
    PERFORMANCE_METRICS = "performance_metrics" 