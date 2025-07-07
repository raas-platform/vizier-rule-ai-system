"""
Data models for RaaS Rule Analyzer

This module defines the core data structures used throughout the rule analyzer:
- Rule: Business rule representation
- RuleCondition: Individual condition within a rule
- ValidationResult: Result of rule validation
- ConditionIssue: Issues detected in conditions
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class RuleCondition(BaseModel):
    """
    개별 조건을 나타내는 모델
    """
    keyName: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    fieldDataType: Optional[str] = None
    conditions: Optional[List["RuleCondition"]] = None
    logicType: Optional[str] = None
    condUuid: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class ConditionTree(BaseModel):
    """
    조건 트리를 나타내는 모델
    """
    condition: Optional[List[RuleCondition]] = None
    logicType: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class Rule(BaseModel):
    """
    비즈니스 룰을 나타내는 모델
    """
    ruleUuid: Optional[str] = None
    ruleName: Optional[str] = None
    name: Optional[str] = None
    ruleMsg: Optional[str] = None
    conditionTree: Optional[ConditionTree] = None
    conditions: Optional[List[RuleCondition]] = None
    ruleCondition: Any = None
    
    class Config:
        arbitrary_types_allowed = True


class ConditionIssue(BaseModel):
    """
    조건에서 발견된 이슈를 나타내는 모델
    """
    keyName: Optional[str] = None
    issue_type: str
    severity: str = Field(description="error, warning, info")
    message: str
    suggestion: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        arbitrary_types_allowed = True


class PerformanceMetrics(BaseModel):
    """
    성능 메트릭을 나타내는 모델
    """
    estimated_execution_time_ms: float
    memory_usage_estimate_kb: float
    optimization_suggestions: List[str] = []
    
    class Config:
        arbitrary_types_allowed = True


class QualityMetrics(BaseModel):
    """
    품질 메트릭을 나타내는 모델
    """
    maintainability_score: float = Field(description="유지보수성 점수 (0-100)")
    readability_score: float = Field(description="가독성 점수 (0-100)")
    complexity_level: str = Field(description="복잡성 레벨 (low, medium, high)")
    best_practices_score: float = Field(description="모범 사례 점수 (0-100)")
    
    class Config:
        arbitrary_types_allowed = True


class StructureInfo(BaseModel):
    """
    룰 구조 정보를 나타내는 모델
    """
    total_conditions: int = 0
    field_conditions: int = 0
    logical_operators: int = 0
    max_depth: int = 1
    unique_fields: int = 0
    complexity_score: int = 0
    
    class Config:
        arbitrary_types_allowed = True


class ReportMetadata(BaseModel):
    """
    리포트 메타데이터를 나타내는 모델
    """
    analysis_timestamp: str
    ruleUuid: Optional[str] = None
    ruleName: Optional[str] = None
    total_analysis_time_ms: int = 0
    total_processing_time_ms: int = 0
    
    class Config:
        arbitrary_types_allowed = True


class FieldAnalysis(BaseModel):
    """
    필드별 분석 정보를 나타내는 모델
    """
    field_name: str
    field_type: str
    usage_count: int
    operators_used: List[str] = []
    values_used: List[str] = []
    issues: List[ConditionIssue] = []
    
    class Config:
        arbitrary_types_allowed = True


class ValidationResult(BaseModel):
    """
    룰 검증 결과를 나타내는 모델
    """
    is_valid: bool
    summary: str
    issues: List[ConditionIssue] = []
    issue_counts: Dict[str, int] = {}
    structure: Optional[StructureInfo] = None
    rule_summary: Optional[str] = None
    complexity_score: int = 0
    field_analysis: List[FieldAnalysis] = []
    performance_metrics: Optional[PerformanceMetrics] = None
    quality_metrics: Optional[QualityMetrics] = None
    ai_comment: Optional[str] = None
    report_metadata: Optional[ReportMetadata] = None
    
    class Config:
        arbitrary_types_allowed = True


# Pydantic 모델 업데이트 (순환 참조 해결)
RuleCondition.model_rebuild()
ConditionTree.model_rebuild()
Rule.model_rebuild()
ValidationResult.model_rebuild() 