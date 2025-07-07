"""
API Gateway Module

모든 API 엔드포인트와 라우팅을 관리합니다.
"""

from fastapi import APIRouter

from .llm_endpoints import router as llm_router
from .prompt_endpoints import router as prompt_router
from .rule_validator import router as rule_validator_router
from .streaming_dashboard import router as streaming_dashboard_router

api_router = APIRouter(prefix="/api/v1")

# 룰 관련 엔드포인트 (rule_report 제거)
rules_router = APIRouter(prefix="/rules")
rules_router.include_router(rule_validator_router, tags=["rule-validator"])

# 메인 라우터에 포함 (태그 중복 제거)
api_router.include_router(rules_router)
api_router.include_router(llm_router)  # 태그는 llm_endpoints.py에서 설정
api_router.include_router(prompt_router)  # 태그는 prompt_endpoints.py에서 설정
api_router.include_router(streaming_dashboard_router)  # 태그는 streaming_dashboard.py에서 설정

__all__ = [
    "llm_endpoints",
    "prompt_endpoints", 
    "rule_validator",
    "streaming_dashboard"
]
