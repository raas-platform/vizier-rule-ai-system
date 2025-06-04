from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class RuleCondition(BaseModel):
    """룰 조건 모델"""
    field: str
    operator: str
    value: Any
    conditions: Optional[List['RuleCondition']] = None
    parent_operator: Optional[str] = None

class RuleAction(BaseModel):
    """Rule action model"""
    action_type: str = Field(..., description="Type of action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")

class Rule(BaseModel):
    """룰 모델"""
    name: str
    description: Optional[str] = None
    conditions: List[RuleCondition]
    action: Optional[Dict[str, Any]] = None
    id: Optional[str] = Field(None, description="Rule unique identifier")
    priority: int = Field(default=1, description="Rule execution priority (lower means higher priority)")
    enabled: bool = Field(default=True, description="Whether the rule is enabled or not")
    
    class Config:
        from_attributes = True

# 순환 참조 해결
RuleCondition.model_rebuild() 