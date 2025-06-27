"""
LLM 서비스 관리자
다양한 LLM 제공업체의 모델을 통합 관리
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List

import anthropic
import google.generativeai as genai
import openai

from ..config import SUPPORTED_MODELS, LLMModelConfig, settings
from ..utils.logger import get_logger


class BaseLLMProvider(ABC):
    """LLM 제공업체 기본 클래스"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = get_logger(__name__)

    @abstractmethod
    async def generate_text(self, prompt: str, model_config: LLMModelConfig) -> str:
        """텍스트 생성"""
        pass

    @abstractmethod
    async def generate_stream(
        self, prompt: str, model_config: LLMModelConfig
    ) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성"""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 제공업체"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_text(self, prompt: str, model_config: LLMModelConfig) -> str:
        """OpenAI API를 사용한 텍스트 생성"""
        try:
            response = await self.client.chat.completions.create(
                model=model_config.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            self.logger.error(f"OpenAI API 오류: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, prompt: str, model_config: LLMModelConfig
    ) -> AsyncGenerator[str, None]:
        """OpenAI API를 사용한 스트리밍 생성"""
        try:
            stream = await self.client.chat.completions.create(
                model=model_config.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self.logger.error(f"OpenAI 스트리밍 오류: {str(e)}", exc_info=True)
            raise


class AnthropicProvider(BaseLLMProvider):
    """Anthropic 제공업체"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        
        # Anthropic 클라이언트 버전 호환성 확인
        if not hasattr(self.client, 'messages'):
            self.logger.error(f"Anthropic 클라이언트 버전이 호환되지 않습니다. 현재 버전: {anthropic.__version__}")
            raise RuntimeError(f"Anthropic 패키지 버전 {anthropic.__version__}은 지원되지 않습니다. 최소 0.50.0 이상이 필요합니다.")

    async def generate_text(self, prompt: str, model_config: LLMModelConfig) -> str:
        """Anthropic API를 사용한 텍스트 생성"""
        try:
            # 버전 호환성 확인
            if hasattr(self.client, 'messages'):
                # 신버전 API (0.50.0+)
                response = await self.client.messages.create(
                    model=model_config.model_name,
                    max_tokens=model_config.max_tokens,
                    temperature=model_config.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                
                # TextBlock에서 텍스트 추출
                content_block = response.content[0]
                if hasattr(content_block, 'text'):
                    return content_block.text
                else:
                    return str(content_block)
                    
            else:
                # 구버전 API (0.24.0 ~ 0.49.x)
                response = await self.client.completions.create(
                    model=model_config.model_name,
                    max_tokens_to_sample=model_config.max_tokens,
                    temperature=model_config.temperature,
                    prompt=f"{anthropic.HUMAN_PROMPT} {prompt}{anthropic.AI_PROMPT}",
                )
                return response.completion.strip()
                
        except Exception as e:
            self.logger.error(f"Anthropic API 오류: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, prompt: str, model_config: LLMModelConfig
    ) -> AsyncGenerator[str, None]:
        """Anthropic API를 사용한 스트리밍 생성"""
        try:
            async with self.client.messages.stream(
                model=model_config.model_name,
                max_tokens=model_config.max_tokens,
                temperature=model_config.temperature,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            self.logger.error(f"Anthropic 스트리밍 오류: {str(e)}", exc_info=True)
            raise


class GoogleProvider(BaseLLMProvider):
    """Google Gemini 제공업체"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        genai.configure(api_key=api_key)

    async def generate_text(self, prompt: str, model_config: LLMModelConfig) -> str:
        """Google Gemini API를 사용한 텍스트 생성"""
        try:
            model = genai.GenerativeModel(model_config.model_name)
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=model_config.max_tokens,
                    temperature=model_config.temperature,
                ),
            )
            return response.text
        except Exception as e:
            self.logger.error(f"Google API 오류: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, prompt: str, model_config: LLMModelConfig
    ) -> AsyncGenerator[str, None]:
        """Google Gemini API를 사용한 스트리밍 생성"""
        try:
            model = genai.GenerativeModel(model_config.model_name)
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=model_config.max_tokens,
                    temperature=model_config.temperature,
                ),
                stream=True,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            self.logger.error(f"Google 스트리밍 오류: {str(e)}", exc_info=True)
            raise


class LLMService:
    """LLM 서비스 통합 관리자"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.providers: Dict[str, BaseLLMProvider] = {}
        # Anthropic 계정에서 조회한 사용 가능 모델 ID 집합
        self._anthropic_available_models: set[str] = set()
        self._initialize_providers()

    def _initialize_providers(self):
        """제공업체 초기화"""
        # OpenAI
        if settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(settings.openai_api_key)
            self.logger.info("OpenAI 제공업체 초기화 완료")

        # Anthropic
        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
            self.logger.info("Anthropic 제공업체 초기화 완료")

            # 계정에 실제로 열려 있는 모델 목록 조회 (동기 호출, 실패 시 무시)
            try:
                sync_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                models_info = sync_client.models.list()
                self._anthropic_available_models = {m.id for m in models_info}
                self.logger.info(
                    f"Anthropic 사용 가능 모델: {', '.join(sorted(self._anthropic_available_models))}"
                )
            except Exception as e:
                self.logger.warning(f"Anthropic 모델 목록 조회 실패: {e}")

        # Google
        if settings.google_api_key:
            self.providers["google"] = GoogleProvider(settings.google_api_key)
            self.logger.info("Google 제공업체 초기화 완료")

    def get_available_models(self) -> List[Dict[str, str]]:
        """사용 가능한 모델 목록 반환"""
        available_models = []
        for model_id, config in SUPPORTED_MODELS.items():
            if config.provider in self.providers:
                available_models.append(
                    {
                        "id": model_id,
                        "provider": config.provider,
                        "display_name": config.display_name,
                        "description": config.description,
                        "max_tokens": config.max_tokens,
                    }
                )
        return available_models

    def is_model_available(self, model_id: str) -> bool:
        """모델 사용 가능 여부 확인"""
        if model_id not in SUPPORTED_MODELS:
            return False
        config = SUPPORTED_MODELS[model_id]
        if config.provider not in self.providers:
            return False

        # Anthropic 의 경우 실제 계정에 열려 있는 모델인지 추가 확인
        if config.provider == "anthropic":
            # 목록이 비어 있으면 즉시 새로고침 시도 (lazy refresh)
            if not self._anthropic_available_models:
                self.refresh_anthropic_models()
            return model_id in self._anthropic_available_models

        return True

    async def generate_text(self, prompt: str, model_id: str) -> str:
        """선택된 모델로 텍스트 생성"""
        self.logger.info(f"🎯 generate_text 호출됨 - 요청 모델: {model_id}")
        
        # 🔥 임시 디버그: 모든 요청을 Claude 4로 강제 리디렉션
        if model_id.startswith("claude"):
            original_model = model_id
            model_id = "claude-sonnet-4-20250514"
            self.logger.info(f"🔥 모델 강제 변경: {original_model} → {model_id}")
        
        if not self.is_model_available(model_id):
            self.logger.error(f"❌ 모델 '{model_id}' 사용 불가능!")
            raise ValueError(f"모델 '{model_id}'을(를) 사용할 수 없습니다.")

        config = SUPPORTED_MODELS[model_id]
        provider = self.providers[config.provider]

        self.logger.info(f"🚀 텍스트 생성 시작: {config.display_name} (실제 모델: {model_id})")
        result = await provider.generate_text(prompt, config)
        self.logger.info(f"✅ 텍스트 생성 완료: {len(result)}자 (모델: {model_id})")

        return result

    async def generate_stream(
        self, prompt: str, model_id: str
    ) -> AsyncGenerator[str, None]:
        """선택된 모델로 스트리밍 텍스트 생성"""
        if not self.is_model_available(model_id):
            raise ValueError(f"모델 '{model_id}'을(를) 사용할 수 없습니다.")

        config = SUPPORTED_MODELS[model_id]
        provider = self.providers[config.provider]

        self.logger.info(f"스트리밍 생성 시작: {config.display_name}")
        async for chunk in provider.generate_stream(prompt, config):
            yield chunk

    def refresh_anthropic_models(self) -> dict:
        """Anthropic 계정의 사용 가능 모델 목록을 강제로 새로 고칩니다.

        Returns
        -------
        dict
            {"success": bool, "models": list[str], "error": str | None}
        """
        if "anthropic" not in self.providers:
            return {"success": False, "models": [], "error": "Anthropic provider not configured"}

        try:
            sync_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            models_info = sync_client.models.list()
            self._anthropic_available_models = {m.id for m in models_info}
            self.logger.info(
                f"Anthropic 모델 목록 새로고침 완료: {', '.join(sorted(self._anthropic_available_models))}"
            )
            return {"success": True, "models": sorted(self._anthropic_available_models), "error": None}
        except Exception as e:
            self.logger.error(f"Anthropic 모델 새로고침 실패: {e}", exc_info=True)
            return {"success": False, "models": [], "error": str(e)}


# 전역 LLM 서비스 인스턴스
llm_service = LLMService()
