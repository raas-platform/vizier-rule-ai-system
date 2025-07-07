"""
Report Generation Models

리포트 생성에 사용되는 데이터 모델들을 정의합니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    """리포트 메타데이터"""

    analysis_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    rule_uuid: Optional[str] = Field(None, description="룰 고유 ID")
    rule_name: Optional[str] = Field(None, description="룰 이름")
    analysis_version: str = "1.0"
    total_analysis_time_ms: Optional[int] = None

    # 모델 및 성능 정보
    validation_model: Optional[str] = None
    validation_ai_latency_ms: Optional[int] = None
    report_model: Optional[str] = None
    report_generated_by: Optional[str] = None  # "llm" | "template" | "static"
    report_generation_time_ms: Optional[int] = None
    total_processing_time_ms: Optional[int] = None


class IssueInfo(BaseModel):
    """이슈 정보"""
    
    type: str = Field(description="이슈 타입")
    message: str = Field(description="이슈 메시지")
    severity: str = Field(default="info", description="심각도 (error, warning, info)")
    path: Optional[str] = Field(None, description="이슈 발생 경로")


class ReportData(BaseModel):
    """리포트 생성에 필요한 데이터"""
    
    rule_name: str = Field(description="룰 이름")
    summary: str = Field(description="요약")
    is_valid: bool = Field(description="유효성 여부")
    issues: List[IssueInfo] = Field(default_factory=list, description="이슈 목록")
    structure: Dict[str, Any] = Field(default_factory=dict, description="룰 구조")
    metadata: ReportMetadata = Field(default_factory=ReportMetadata, description="메타데이터")


class ReportResult(BaseModel):
    """리포트 생성 결과"""
    
    report: str = Field(description="생성된 HTML 리포트")
    model_used: str = Field(description="사용된 모델")
    generation_time_ms: int = Field(description="생성 시간(ms)")
    report_generated_by: str = Field(description="생성 방식")
    note: Optional[str] = Field(None, description="추가 정보") 