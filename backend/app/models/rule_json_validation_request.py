from typing import Dict, Any
from pydantic import BaseModel

class RuleJsonValidationRequest(BaseModel):
    """Request model for rule validation from JSON"""
    rule_json: Dict[str, Any] 