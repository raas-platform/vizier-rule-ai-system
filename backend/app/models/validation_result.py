from typing import List, Dict, Any, Optional, Literal, Set
from pydantic import BaseModel, Field
from app.models.rule import Rule

class ConditionIssue(BaseModel):
    """룰 조건 이슈 모델"""
    field: Optional[str] = None
    issue_type: str
    severity: str
    location: str = ""
    explanation: str = ""
    suggestion: str = ""

class StructureInfo(BaseModel):
    """룰 구조 정보 모델"""
    depth: int
    condition_count: int = 0  # 이전 버전 호환성을 위해 유지
    condition_node_count: int = Field(0, description="전체 조건 노드 수 (논리 연산자 포함)")
    field_condition_count: int = Field(0, description="실제 필드가 있는 비교 조건 수")
    unique_fields: List[str]

class ValidationResult(BaseModel):
    """룰 검증 결과 모델"""
    is_valid: bool
    summary: str
    issue_counts: Dict[str, int] = Field(default_factory=dict)
    issues: List[ConditionIssue]
    structure: StructureInfo
    rule_summary: str = ""
    complexity_score: int = 0
    ai_comment: Optional[str] = None

class RuleJsonValidationRequest(BaseModel):
    """Request model for rule validation from JSON"""
    rule_json: Dict[str, Any]

class RuleValidationResponse(BaseModel):
    """Rule validation response model"""
    is_valid: bool
    summary: str
    issue_counts: Dict[str, int]
    issues: List[ConditionIssue]
    structure: StructureInfo 
    ai_comment: Optional[str] = None 