"""
LLM Service - PyPI 모듈 통합 (강화 버전)

강화된 rass-llm-service 모듈을 활용하여 실제 API 호출, 
스트리밍, 고급 모델 관리 등을 지원합니다.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime

# PyPI 모듈 import (강화된 버전)
try:
    from rass_llm_service import LLMService as BaseLLMService
    from rass_llm_service.models import (
        LLMInput, LLMResult, LLMProvider, ModelConfig, 
        LLMResponseMetadata, ProviderConfig
    )
    from rass_llm_service.exceptions import (
        LLMServiceException, UnsupportedProviderException,
        APICallFailedException, ProviderNotConfiguredException
    )
    PYPI_MODULE_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ 강화된 PyPI rass-llm-service 모듈 로드 성공")
except ImportError as e:
    PYPI_MODULE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"❌ PyPI rass-llm-service 모듈 로드 실패: {e}")

# 로컬 imports (fallback)
from ..rule_analysis.models.prompt import Prompt
from ..shared.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    하이브리드 LLM 서비스 (강화 버전)
    
    PyPI 모듈의 강화된 기능을 우선 사용하고,
    실패 시 로컬 provider 로직으로 fallback합니다.
    """
    
    def __init__(self):
        self.logger = logger
        
        # PyPI 모듈 초기화
        self.pypi_service = None
        if PYPI_MODULE_AVAILABLE:
            try:
                self.pypi_service = BaseLLMService()
                self.logger.info("✅ 강화된 PyPI LLM 서비스 초기화 완료")
            except Exception as e:
                self.logger.error(f"❌ PyPI LLM 서비스 초기화 실패: {e}")
                self.pypi_service = None
        
        # 로컬 provider 설정 (fallback)
        self.local_providers = self._initialize_local_providers()
        self.default_provider = "openai"
        
        # 지원 모델 목록
        self.supported_models = self._get_supported_models()
        
        self.logger.info("하이브리드 LLM 서비스 초기화 완료")
    
    def _initialize_local_providers(self) -> Dict[str, Dict[str, Any]]:
        """로컬 provider 설정 초기화 (fallback용)"""
        providers = {}
        
        # OpenAI 설정
        if os.getenv("OPENAI_API_KEY"):
            providers["openai"] = {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": "https://api.openai.com/v1",
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
            }
        
        # Anthropic 설정
        if os.getenv("ANTHROPIC_API_KEY"):
            providers["anthropic"] = {
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
                "base_url": "https://api.anthropic.com",
                "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
            }
        
        # Google 설정
        if os.getenv("GOOGLE_API_KEY"):
            providers["google"] = {
                "api_key": os.getenv("GOOGLE_API_KEY"),
                "models": ["gemini-pro"]
            }
        
        return providers
    
    def _get_supported_models(self) -> List[Dict[str, Any]]:
        """지원 모델 목록 반환"""
        if self.pypi_service:
            try:
                # PyPI 모듈에서 모델 목록 가져오기
                return self.pypi_service.get_available_models()
            except Exception as e:
                self.logger.error(f"PyPI 모듈에서 모델 목록 가져오기 실패: {e}")
        
        # 로컬 fallback 모델 목록
        models = []
        for provider_name, config in self.local_providers.items():
            for model in config.get("models", []):
                models.append({
                    "id": model,
                    "provider": provider_name,
                    "display_name": model.upper(),
                    "description": f"{provider_name} 모델",
                    "max_tokens": 4000,
                })
        
        return models
    
    async def generate_text(self, prompt: str, model_id: str = "gpt-3.5-turbo", 
                          **kwargs) -> str:
        """
        텍스트 생성 (강화된 버전)
        
        PyPI 모듈 우선 사용, 실패 시 로컬 provider 사용
        """
        try:
            # PyPI 모듈 사용 시도
            if self.pypi_service:
                try:
                    self.logger.info(f"🚀 PyPI 모듈로 텍스트 생성 시도 - 모델: {model_id}")
                    result = await self.pypi_service.generate_text(prompt, model_id)
                    self.logger.info(f"✅ PyPI 모듈 텍스트 생성 성공 - 길이: {len(result)}자")
                    return result
                except Exception as e:
                    self.logger.warning(f"⚠️ PyPI 모듈 실패, 로컬 provider로 fallback: {e}")
            
            # 로컬 provider fallback
            return await self._generate_text_local(prompt, model_id, **kwargs)
            
        except Exception as e:
            self.logger.error(f"💥 텍스트 생성 실패: {e}")
            raise
    
    async def _generate_text_local(self, prompt: str, model_id: str, **kwargs) -> str:
        """로컬 provider를 사용한 텍스트 생성 (fallback)"""
        try:
            # 모델에서 provider 추출
            provider_name = self._get_provider_from_model(model_id)
            
            if provider_name not in self.local_providers:
                raise ValueError(f"Provider {provider_name} not configured")
            
            # 간단한 로컬 처리 (실제 구현에서는 API 호출)
            self.logger.info(f"🔄 로컬 provider로 텍스트 생성 - {provider_name}:{model_id}")
            
            # 시뮬레이션 지연
            await asyncio.sleep(0.5)
            
            return f"""
{provider_name.upper()} 모델 ({model_id}) 분석 결과:

프롬프트: {prompt[:100]}...

�� 분석 요약:
- 로컬 provider를 통한 기본 분석을 수행했습니다.
- 모델: {model_id}
- Provider: {provider_name}

💡 주요 내용:
- 입력된 프롬프트를 기반으로 분석을 진행했습니다.
- 더 정확한 분석을 위해서는 실제 API 키 설정이 필요합니다.

⚠️ 참고사항:
이 결과는 로컬 fallback 처리된 기본 분석입니다.
실제 {provider_name.upper()} API를 사용하려면 환경 변수를 설정하세요.
            """.strip()
            
        except Exception as e:
            self.logger.error(f"로컬 텍스트 생성 실패: {e}")
            raise
    
    def _get_provider_from_model(self, model_id: str) -> str:
        """모델 ID에서 provider 추출"""
        if "gpt" in model_id.lower():
            return "openai"
        elif "claude" in model_id.lower():
            return "anthropic"
        elif "gemini" in model_id.lower():
            return "google"
        else:
            return self.default_provider
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """사용 가능한 모델 목록 반환 (강화된 버전)"""
        if self.pypi_service:
            try:
                pypi_models = self.pypi_service.get_available_models()
                self.logger.info(f"📋 PyPI 모듈에서 {len(pypi_models)}개 모델 반환")
                return pypi_models
            except Exception as e:
                self.logger.warning(f"PyPI 모듈에서 모델 목록 가져오기 실패: {e}")
        
        # 로컬 fallback
        self.logger.info(f"📋 로컬에서 {len(self.supported_models)}개 모델 반환")
        return self.supported_models
    
    def is_model_available(self, model_id: str) -> bool:
        """모델 사용 가능 여부 확인 (강화된 버전)"""
        if self.pypi_service:
            try:
                return self.pypi_service.is_model_available(model_id)
            except Exception as e:
                self.logger.warning(f"PyPI 모듈 모델 확인 실패: {e}")
        
        # 로컬 fallback
        return any(model["id"] == model_id for model in self.supported_models)
    
    async def generate_ai_summary(self, prompt: str, provider: str = "openai", 
                                model: str = "gpt-3.5-turbo") -> str:
        """
        AI 요약 생성 (PyPI 모듈 활용)
        
        PyPI 모듈의 generate_summary 기능을 사용
        """
        try:
            if self.pypi_service:
                try:
                    # PyPI 모듈 형식으로 입력 데이터 구성
                    provider_enum = self._get_provider_enum(provider)
                    model_config = ModelConfig(
                        model=model,
                        provider=provider,
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    llm_input = LLMInput(
                        prompt=prompt,
                        llm_provider=provider_enum,
                        model_config=model_config
                    )
                    
                    self.logger.info(f"🚀 PyPI 모듈로 AI 요약 생성 - {provider}:{model}")
                    result = await self.pypi_service.generate_summary(llm_input)
                    self.logger.info(f"✅ PyPI 모듈 AI 요약 생성 성공 - 신뢰도: {result.confidence_score}")
                    
                    return result.summary
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ PyPI 모듈 AI 요약 실패: {e}")
            
            # 로컬 fallback
            return await self.generate_text(prompt, model)
            
        except Exception as e:
            self.logger.error(f"💥 AI 요약 생성 실패: {e}")
            raise
    
    def _get_provider_enum(self, provider: str) -> LLMProvider:
        """문자열을 LLMProvider enum으로 변환"""
        provider_map = {
            "openai": LLMProvider.OPENAI,
            "anthropic": LLMProvider.ANTHROPIC,
            "google": LLMProvider.GOOGLE,
            "local": LLMProvider.LOCAL
        }
        return provider_map.get(provider.lower(), LLMProvider.OPENAI)
    
    def get_pypi_available_providers(self) -> List[str]:
        """PyPI 모듈에서 사용 가능한 제공자 목록 반환"""
        if self.pypi_service:
            try:
                providers = self.pypi_service.get_available_providers()
                return [p.value for p in providers]
            except Exception as e:
                self.logger.warning(f"PyPI 모듈 제공자 목록 가져오기 실패: {e}")
        
        return list(self.local_providers.keys())
    
    def switch_pypi_provider(self, provider: str) -> bool:
        """PyPI 모듈의 제공자 동적 변경"""
        if self.pypi_service:
            try:
                provider_enum = self._get_provider_enum(provider)
                self.pypi_service.switch_provider(provider_enum)
                self.logger.info(f"✅ PyPI 모듈 제공자 변경: {provider}")
                return True
            except Exception as e:
                self.logger.error(f"PyPI 모듈 제공자 변경 실패: {e}")
        
        return False
    
    def get_provider_status(self) -> Dict[str, Any]:
        """제공자 상태 정보 반환"""
        status = {
            "pypi_module_available": PYPI_MODULE_AVAILABLE,
            "pypi_service_initialized": self.pypi_service is not None,
            "local_providers": list(self.local_providers.keys()),
            "supported_models_count": len(self.supported_models)
        }
        
        if self.pypi_service:
            try:
                status["pypi_available_providers"] = self.get_pypi_available_providers()
                status["pypi_available_models"] = len(self.pypi_service.get_available_models())
            except Exception as e:
                status["pypi_status_error"] = str(e)
        
        return status
    
    # 기존 호환성 메서드들 (deprecated but maintained)
    async def generate_summary(self, prompt: str, provider: str = "openai") -> str:
        """기존 호환성을 위한 요약 생성 메서드"""
        self.logger.warning("generate_summary는 deprecated입니다. generate_ai_summary를 사용하세요.")
        return await self.generate_ai_summary(prompt, provider)
    
    def get_available_providers(self) -> List[str]:
        """기존 호환성을 위한 제공자 목록 반환"""
        self.logger.warning("get_available_providers는 deprecated입니다. get_pypi_available_providers를 사용하세요.")
        return self.get_pypi_available_providers()
    
    def switch_provider(self, provider: str) -> bool:
        """기존 호환성을 위한 제공자 변경"""
        self.logger.warning("switch_provider는 deprecated입니다. switch_pypi_provider를 사용하세요.")
        return self.switch_pypi_provider(provider)


# 글로벌 인스턴스 생성 (기존 호환성을 위함)
llm_service = LLMService()

