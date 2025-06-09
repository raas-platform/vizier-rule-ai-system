"""
프롬프트 관련 데이터 모델
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptCategory(str, Enum):
    """프롬프트 카테고리"""

    RULE_GENERATION = "rule_generation"  # 룰 생성
    RULE_ANALYSIS = "rule_analysis"  # 룰 분석
    CODE_REVIEW = "code_review"  # 코드 리뷰
    DOCUMENTATION = "documentation"  # 문서화
    TESTING = "testing"  # 테스트
    DEBUGGING = "debugging"  # 디버깅
    OPTIMIZATION = "optimization"  # 최적화
    CUSTOM = "custom"  # 사용자 정의


class PromptBase(BaseModel):
    """프롬프트 기본 모델"""

    title: str = Field(..., min_length=1, max_length=200, description="프롬프트 제목")
    description: Optional[str] = Field(
        None, max_length=500, description="프롬프트 설명"
    )
    category: PromptCategory = Field(..., description="프롬프트 카테고리")
    content: str = Field(..., min_length=1, description="프롬프트 내용")
    variables: Optional[List[str]] = Field(
        default_factory=list,
        description="프롬프트 변수들 (예: {variable_name})",
    )
    tags: Optional[List[str]] = Field(default_factory=list, description="검색용 태그들")
    is_system_prompt: bool = Field(default=False, description="시스템 프롬프트 여부")
    is_active: bool = Field(default=True, description="활성화 상태")


class PromptCreate(PromptBase):
    """프롬프트 생성 모델"""

    pass


class PromptUpdate(BaseModel):
    """프롬프트 업데이트 모델"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[PromptCategory] = None
    content: Optional[str] = Field(None, min_length=1)
    variables: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_system_prompt: Optional[bool] = None
    is_active: Optional[bool] = None


class Prompt(PromptBase):
    """프롬프트 전체 모델"""

    id: int = Field(..., description="프롬프트 ID")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")
    usage_count: int = Field(default=0, description="사용 횟수")

    class Config:
        from_attributes = True


class PromptExecuteRequest(BaseModel):
    """프롬프트 실행 요청 모델"""

    prompt_id: int = Field(..., description="프롬프트 ID")
    variables: Dict[str, str] = Field(
        default_factory=dict, description="프롬프트 변수 값들"
    )
    model_id: str = Field(..., description="사용할 LLM 모델 ID")
    custom_content: Optional[str] = Field(
        None, description="커스텀 프롬프트 내용 (프롬프트 ID 대신 사용)"
    )


class PromptExecuteResponse(BaseModel):
    """프롬프트 실행 응답 모델"""

    result: str = Field(..., description="생성된 결과")
    prompt_used: str = Field(..., description="실제 사용된 프롬프트")
    model_used: str = Field(..., description="사용된 모델")
    execution_time: float = Field(..., description="실행 시간 (초)")
    token_count: Optional[int] = Field(None, description="토큰 수")


class PromptSearchRequest(BaseModel):
    """프롬프트 검색 요청 모델"""

    query: Optional[str] = Field(None, description="검색 쿼리")
    category: Optional[PromptCategory] = Field(None, description="카테고리 필터")
    tags: Optional[List[str]] = Field(None, description="태그 필터")
    is_system_prompt: Optional[bool] = Field(None, description="시스템 프롬프트 필터")
    is_active: Optional[bool] = Field(True, description="활성화 상태 필터")
    limit: int = Field(default=50, ge=1, le=100, description="결과 제한")
    offset: int = Field(default=0, ge=0, description="결과 오프셋")


class PromptListResponse(BaseModel):
    """프롬프트 목록 응답 모델"""

    prompts: List[Prompt] = Field(..., description="프롬프트 목록")
    total: int = Field(..., description="전체 개수")
    has_more: bool = Field(..., description="추가 결과 존재 여부")


class PromptStats(BaseModel):
    """프롬프트 통계 모델"""

    total_prompts: int = Field(..., description="전체 프롬프트 수")
    prompts_by_category: Dict[str, int] = Field(
        ..., description="카테고리별 프롬프트 수"
    )
    most_used_prompts: List[Prompt] = Field(
        ..., description="가장 많이 사용된 프롬프트들"
    )
    recent_prompts: List[Prompt] = Field(..., description="최근 생성된 프롬프트들")
