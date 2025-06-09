"""
애플리케이션 설정
"""

from dataclasses import dataclass
from typing import Dict

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# .env 파일 로드
load_dotenv()


class Settings(BaseSettings):
    app_name: str = "Rule AI System"
    debug: bool = False

    # API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./test.db"

    # CORS
    allowed_origins: list = ["*"]

    class Config:
        env_file = ".env"
        extra = "ignore"  # 추가 환경 변수 무시


@dataclass
class LLMModelConfig:
    """LLM 모델 설정"""

    provider: str
    model_name: str
    display_name: str
    description: str
    max_tokens: int
    temperature: float = 0.7
    supports_streaming: bool = True
    api_key_env: str = ""


# 지원하는 LLM 모델 목록
SUPPORTED_MODELS: Dict[str, LLMModelConfig] = {
    "gpt-4": LLMModelConfig(
        provider="openai",
        model_name="gpt-4",
        display_name="GPT-4",
        description="OpenAI의 가장 강력한 언어 모델",
        max_tokens=8192,
        temperature=0.7,
        api_key_env="OPENAI_API_KEY",
    ),
    "gpt-4-turbo": LLMModelConfig(
        provider="openai",
        model_name="gpt-4-turbo-preview",
        display_name="GPT-4 Turbo",
        description="GPT-4의 향상된 버전, 더 빠르고 효율적",
        max_tokens=128000,
        temperature=0.7,
        api_key_env="OPENAI_API_KEY",
    ),
    "gpt-3.5-turbo": LLMModelConfig(
        provider="openai",
        model_name="gpt-3.5-turbo",
        display_name="GPT-3.5 Turbo",
        description="빠르고 효율적인 OpenAI 모델",
        max_tokens=4096,
        temperature=0.7,
        api_key_env="OPENAI_API_KEY",
    ),
    "claude-3-opus": LLMModelConfig(
        provider="anthropic",
        model_name="claude-3-opus-20240229",
        display_name="Claude 3 Opus",
        description="Anthropic의 가장 강력한 모델",
        max_tokens=4096,
        temperature=0.7,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "claude-3-sonnet": LLMModelConfig(
        provider="anthropic",
        model_name="claude-3-sonnet-20240229",
        display_name="Claude 3 Sonnet",
        description="균형잡힌 성능과 효율성",
        max_tokens=4096,
        temperature=0.7,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "claude-3-haiku": LLMModelConfig(
        provider="anthropic",
        model_name="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        description="빠르고 경제적인 모델",
        max_tokens=4096,
        temperature=0.7,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "gemini-pro": LLMModelConfig(
        provider="google",
        model_name="gemini-pro",
        display_name="Gemini Pro",
        description="Google의 고성능 언어 모델",
        max_tokens=32768,
        temperature=0.7,
        api_key_env="GOOGLE_API_KEY",
    ),
}


settings = Settings()
