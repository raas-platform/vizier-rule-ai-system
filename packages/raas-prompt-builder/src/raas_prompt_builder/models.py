"""
Universal Prompt Builder Models

프롬프트 생성을 위한 데이터 모델들을 정의합니다.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field


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
    RULE_DOCUMENTATION = "rule_documentation"
    PERFORMANCE_METRICS = "performance_metrics"


class CustomizationOptions(BaseModel):
    """커스터마이징 옵션"""
    tone: str = Field(default="professional", description="프롬프트 톤 (professional, casual, formal)")
    detail_level: str = Field(default="medium", description="상세도 수준 (low, medium, high)")
    language: str = Field(default="korean", description="언어 (korean, english)")
    include_emoji: bool = Field(default=True, description="이모지 포함 여부")
    include_statistics: bool = Field(default=True, description="통계 포함 여부")
    include_recommendations: bool = Field(default=False, description="권장사항 포함 여부")
    max_length: Optional[int] = Field(default=None, description="최대 길이 제한")


class TemplateConfig(BaseModel):
    """템플릿 설정"""
    template_name: str = Field(..., description="템플릿 이름")
    version: str = Field(default="1.0", description="템플릿 버전")
    token_limit: int = Field(default=4000, description="토큰 제한")
    required_fields: List[str] = Field(default_factory=list, description="필수 필드 목록")
    optional_fields: List[str] = Field(default_factory=list, description="선택적 필드 목록")


class PromptInput(BaseModel):
    """프롬프트 입력 데이터"""
    aggregated_data: Dict[str, Any] = Field(..., description="집계된 데이터")
    prompt_type: PromptType = Field(..., description="프롬프트 유형")
    target_developer: str = Field(..., description="대상 개발자")
    customization: Optional[CustomizationOptions] = Field(default=None, description="커스터마이징 옵션")
    context: Optional[str] = Field(default=None, description="추가 컨텍스트")
    
    def __init__(self, **data):
        if data.get('customization') is None:
            data['customization'] = CustomizationOptions()
        super().__init__(**data)


class PromptMetadata(BaseModel):
    """프롬프트 메타데이터"""
    template_version: str = Field(..., description="사용된 템플릿 버전")
    token_count: int = Field(..., description="토큰 수")
    generation_time: datetime = Field(default_factory=datetime.now, description="생성 시간")
    estimated_cost: float = Field(default=0.0, description="예상 비용")
    language: str = Field(default="korean", description="언어")
    customizations_applied: List[str] = Field(default_factory=list, description="적용된 커스터마이징")


class PromptResult(BaseModel):
    """프롬프트 결과 데이터"""
    prompt: str = Field(..., description="생성된 프롬프트")
    metadata: PromptMetadata = Field(..., description="메타데이터")
    context_data: Dict[str, Any] = Field(..., description="컨텍스트 데이터")
    template_used: str = Field(..., description="사용된 템플릿")
    
    @property
    def is_valid(self) -> bool:
        """프롬프트 유효성 확인"""
        return bool(self.prompt and self.prompt.strip())
    
    @property
    def summary(self) -> str:
        """프롬프트 요약"""
        lines = self.prompt.split('\n')
        return lines[0] if lines else ""


# 룰 검증 시스템 전용 모델들 (새로 추가)
class RuleValidationInput(BaseModel):
    """룰 검증 입력 데이터"""
    rule_json: Dict[str, Any] = Field(..., description="검증할 룰 JSON 데이터")
    validation_type: str = Field(..., description="검증 유형 (syntax, logic, performance)")
    context: Optional[str] = Field(default=None, description="추가 컨텍스트")
    customization: Optional[CustomizationOptions] = Field(default=None, description="커스터마이징 옵션")


class HtmlReportInput(BaseModel):
    """HTML 리포트 입력 데이터"""
    analysis_result: Dict[str, Any] = Field(..., description="분석 결과 데이터")
    report_title: str = Field(..., description="리포트 제목")
    include_charts: bool = Field(default=True, description="차트 포함 여부")
    theme: str = Field(default="modern", description="테마 (modern, classic, minimal)")
    customization: Optional[CustomizationOptions] = Field(default=None, description="커스터마이징 옵션")


class IssueDetectionInput(BaseModel):
    """이슈 검출 입력 데이터"""
    rule_data: Dict[str, Any] = Field(..., description="룰 데이터")
    detection_scope: List[str] = Field(..., description="검출 범위 (syntax, logic, performance, security)")
    severity_filter: Optional[str] = Field(default=None, description="심각도 필터 (low, medium, high, critical)")
    customization: Optional[CustomizationOptions] = Field(default=None, description="커스터마이징 옵션") 