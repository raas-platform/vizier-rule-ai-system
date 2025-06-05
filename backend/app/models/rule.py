from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class RuleCondition(BaseModel):
    """룰 조건 모델 - 새로운 JSON 형식에 맞게 업데이트"""

    condUuid: str = Field(
        default_factory=lambda: str(uuid4()), description="조건 고유 ID"
    )
    keyName: Optional[str] = Field(None, description="조건 키 이름")
    dispName: Optional[str] = Field(None, description="조건 표시 이름")
    operator: Optional[str] = Field(None, description="연산자")
    value: Optional[Any] = Field(None, description="조건 값")
    fieldDataType: Optional[str] = Field(
        None, description="필드 데이터 타입 (String, Number 등)"
    )

    # 논리 연산자 블록인지 구분하기 위한 필드
    logicType: Optional[str] = Field(
        None, description="논리 타입 (AND, OR) - 논리 연산자 블록인 경우"
    )
    condition: Optional[List["ConditionTreeItem"]] = Field(
        None, description="하위 조건들 - 논리 연산자 블록인 경우"
    )

    # 하위 호환성을 위한 기존 필드들 (선택적)
    field: Optional[str] = None
    conditions: Optional[List["RuleCondition"]] = None
    parent_operator: Optional[str] = None

    def __init__(self, **data):
        # 하위 호환성을 위한 필드 매핑
        if "field" in data and "keyName" not in data:
            data["keyName"] = data["field"]
        if "field" in data and "dispName" not in data:
            data["dispName"] = data["field"]
        if "operator" not in data and "keyName" in data:
            data["operator"] = "=="
        if "value" not in data and "keyName" in data:
            data["value"] = ""
        if "fieldDataType" not in data and "keyName" in data:
            data["fieldDataType"] = "String"

        super().__init__(**data)


# 전방 참조를 위한 타입 별칭
ConditionTreeItem = Union[RuleCondition, "ConditionTree"]


class ConditionTree(BaseModel):
    """조건 트리 구조"""

    logicType: str = Field(..., description="논리 타입 (AND, OR)")
    condition: List[ConditionTreeItem] = Field(
        ..., description="조건 목록 또는 중첩된 조건 트리"
    )


class RuleAction(BaseModel):
    """Rule action model"""

    action_type: str = Field(..., description="Type of action to perform")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Action parameters"
    )


class Rule(BaseModel):
    """룰 모델 - 새로운 JSON 형식에 맞게 업데이트"""

    ruleUuid: str = Field(
        default_factory=lambda: str(uuid4()), description="룰 고유 ID"
    )
    ruleName: str = Field(..., description="룰 이름")
    ruleMsg: str = Field(..., description="룰 메시지")
    conditionTree: Optional[ConditionTree] = Field(
        None, description="조건 트리"
    )

    # 하위 호환성을 위한 기존 필드들 (선택적)
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[RuleCondition]] = None
    action: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    priority: int = Field(
        default=1,
        description="Rule execution priority (lower means higher priority)",
    )
    enabled: bool = Field(
        default=True, description="Whether the rule is enabled or not"
    )

    class Config:
        from_attributes = True

    def __init__(self, **data):
        # 하위 호환성을 위한 필드 매핑
        if "name" in data and "ruleName" not in data:
            data["ruleName"] = data["name"]
        if "ruleName" in data and "name" not in data:
            data["name"] = data["ruleName"]
        if "id" in data and "ruleUuid" not in data:
            data["ruleUuid"] = data["id"]
        if "ruleUuid" in data and "id" not in data:
            data["id"] = data["ruleUuid"]
        if "description" in data and "ruleMsg" not in data:
            data["ruleMsg"] = data["description"] or ""
        if "ruleMsg" in data and "description" not in data:
            data["description"] = data["ruleMsg"] or ""

        super().__init__(**data)


# 순환 참조 해결
RuleCondition.model_rebuild()
ConditionTree.model_rebuild()
