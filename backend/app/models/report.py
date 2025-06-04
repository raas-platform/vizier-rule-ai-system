from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class RuleReportRequest(BaseModel):
    """룰 리포트 생성 요청 모델"""
    rule_json: dict = Field(..., description="분석할 룰 JSON")
    include_markdown: bool = Field(True, description="마크다운 형식으로 반환할지 여부")
    validation_result: Optional[Dict[str, Any]] = Field(None, description="이미 분석된 룰 검증 결과 (없으면 새로 검증)")

class RuleReportResponse(BaseModel):
    """룰 리포트 응답 모델"""
    report: str = Field(..., description="생성된 리포트 텍스트 (마크다운 또는 HTML)")
    rule_id: Optional[str] = Field(None, description="분석된 룰의 ID")
    rule_name: Optional[str] = Field(None, description="분석된 룰의 이름") 