"""
LLM Service Module

AI/LLM 통합 서비스를 제공합니다.
PyPI rass-llm-service 모듈과 로컬 fallback을 지원합니다.
"""

from .service import LLMService, llm_service

__all__ = [
    "LLMService",
    "llm_service"
] 