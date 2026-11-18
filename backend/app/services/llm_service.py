"""
LLM 서비스 관리자
다양한 LLM 제공업체의 모델을 통합 관리
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import anthropic
import google.generativeai as genai

from ..config import SUPPORTED_MODELS, LLMModelConfig, settings
from ..utils.logger import get_logger


def _sampling_kwargs(model_config: LLMModelConfig) -> dict:
    """temperature가 설정된 모델에만 전달 (claude-sonnet-5-5는 미지원)"""
    if model_config.temperature is None:
        return {}
    return {"temperature": model_config.temperature}


def extract_text_blocks(response) -> str:
    """Anthropic 응답에서 type == "text" 블록만 이어 붙인다.

    thinking 등 다른 블록이 앞에 올 수 있어 content[0].text를 쓰면 안 된다.
    """
    parts = [
        getattr(block, "text", "") or ""
        for block in (getattr(response, "content", None) or [])
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts)


def classify_llm_error(exc: BaseException) -> str:
    """LLM 호출 예외를 한국어 사유로 변환한다.

    예외 메시지에는 키 등 민감한 값이 들어갈 수 있으므로 메시지는 쓰지 않고
    예외 종류와 HTTP 상태 코드만 사용한다.
    """
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "시간 초과"
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status in (401, 403):
            return f"API 키 오류(인증 실패, 코드 {status})"
        if status == 404:
            return "모델 사용 불가(모델을 찾을 수 없음, 코드 404)"
        if status == 429:
            return "API 오류(요청 한도 초과, 코드 429)"
        return f"API 오류(코드 {status})"
    name = type(exc).__name__
    if "Timeout" in name:
        return "시간 초과"
    if "Connection" in name:
        return "API 오류(연결 실패)"
    return f"API 오류({name})"


class BaseLLMProvider(ABC):
    """LLM 제공업체 기본 클래스"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = get_logger(__name__)

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        model_config: LLMModelConfig,
        fast: bool = False,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """텍스트 생성.

        fast=True면 짧은 작업용으로 effort를 낮춰 빠르게 응답.
        schema(JSON 스키마)가 있으면 그 형태의 JSON만 출력하도록 고정(지원하는 공급자만).
        """
        pass

    @abstractmethod
    async def generate_stream(
        self, prompt: str, model_config: LLMModelConfig
    ) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성"""
        pass


class AnthropicProvider(BaseLLMProvider):
    """Anthropic 제공업체"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_text(
        self,
        prompt: str,
        model_config: LLMModelConfig,
        fast: bool = False,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Anthropic API를 사용한 텍스트 생성

        - schema가 있으면 output_config.format(json_schema)으로 응답 형태를 고정한다.
        - fast면 effort를 low로 낮춘다. thinking은 건드리지 않는다
          (Sonnet 5.5에서 thinking {"type": "disabled"}는 400이므로 보내지 않는다).
        - 이 옵션들이 400으로 거부되면 옵션 없이 한 번만 다시 시도한다.
        """
        kwargs = dict(
            model=model_config.model_name,
            max_tokens=model_config.max_tokens,
            **_sampling_kwargs(model_config),
            messages=[{"role": "user", "content": prompt}],
        )
        output_config: Dict[str, Any] = {}
        if fast:
            output_config["effort"] = "low"
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            if output_config:
                try:
                    response = await self.client.messages.create(
                        **kwargs, output_config=output_config
                    )
                except anthropic.BadRequestError as e:
                    self.logger.warning(
                        "output_config(format/effort)가 거부되어 기본 옵션으로 재시도: "
                        f"{type(e).__name__}"
                    )
                    response = await self.client.messages.create(**kwargs)
            else:
                response = await self.client.messages.create(**kwargs)
            return extract_text_blocks(response)
        except Exception as e:
            self.logger.error(
                f"Anthropic API 오류: {type(e).__name__}", exc_info=True
            )
            raise

    async def generate_stream(
        self, prompt: str, model_config: LLMModelConfig
    ) -> AsyncGenerator[str, None]:
        """Anthropic API를 사용한 스트리밍 생성"""
        try:
            async with self.client.messages.stream(
                model=model_config.model_name,
                max_tokens=model_config.max_tokens,
                **_sampling_kwargs(model_config),
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

    async def generate_text(
        self,
        prompt: str,
        model_config: LLMModelConfig,
        fast: bool = False,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Google Gemini API를 사용한 텍스트 생성 (schema는 아직 적용하지 않음)"""
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
        self._initialize_providers()

    def _initialize_providers(self):
        """제공업체 초기화"""
        # OpenAI(GPT)는 사용하지 않는다: 제공업체를 만들지 않아 호출 경로가 없다.

        # Anthropic
        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
            self.logger.info("Anthropic 제공업체 초기화 완료")

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

    def unavailable_reason(self, model_id: str) -> Optional[str]:
        """모델을 쓸 수 없는 이유(한국어). 쓸 수 있으면 None"""
        if model_id not in SUPPORTED_MODELS:
            return f"모델 사용 불가(지원하지 않는 모델: {model_id})"
        if SUPPORTED_MODELS[model_id].provider not in self.providers:
            return "API 키 없음"
        return None

    def is_model_available(self, model_id: str) -> bool:
        """모델 사용 가능 여부 확인"""
        if model_id not in SUPPORTED_MODELS:
            return False
        config = SUPPORTED_MODELS[model_id]
        return config.provider in self.providers

    async def generate_text(
        self,
        prompt: str,
        model_id: str,
        fast: bool = False,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """선택된 모델로 텍스트 생성 (fast: 빠른 모드, schema: 응답 JSON 스키마 고정)"""
        if not self.is_model_available(model_id):
            raise ValueError(f"모델 '{model_id}'을(를) 사용할 수 없습니다.")

        config = SUPPORTED_MODELS[model_id]
        provider = self.providers[config.provider]

        self.logger.info(f"텍스트 생성 시작: {config.display_name}")
        result = await provider.generate_text(prompt, config, fast=fast, schema=schema)
        self.logger.info(f"텍스트 생성 완료: {len(result)}자")

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


# 전역 LLM 서비스 인스턴스
llm_service = LLMService()
