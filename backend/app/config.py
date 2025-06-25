"""
VizierAI Rule Validation API - 설정 관리
환경변수 기반 중앙집중식 설정
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Union

# .env 자동 로드를 위해 python-dotenv 사용 (프로젝트 루트 또는 backend 디렉터리)
from dotenv import load_dotenv

from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from functools import lru_cache

# --- .env 파일 자동 로드 ---------------------------------------------
# backend/.env 가 우선, 없으면 프로젝트 루트 .env 사용
_env_candidates = [
    Path(__file__).resolve().parent.parent / ".env",  # backend/.env
    Path(__file__).resolve().parents[2] / ".env",     # 프로젝트 루트 .env
]

for _c in _env_candidates:
    if _c.exists():
        load_dotenv(dotenv_path=_c)
        break


class LLMModelConfig(BaseModel):
    """LLM 모델 설정 클래스"""
    provider: str
    model_name: str
    display_name: str
    description: str
    max_tokens: int
    temperature: float = 0.7
    
    model_config = {"protected_namespaces": ()}


# === 지원되는 LLM 모델 설정 ===
SUPPORTED_MODELS: Dict[str, LLMModelConfig] = {
    # OpenAI 모델들
    "gpt-4o": LLMModelConfig(
        provider="openai",
        model_name="gpt-4o",
        display_name="GPT-4 Omni",
        description="최신 GPT-4 모델, 텍스트와 이미지 처리 가능",
        max_tokens=8192,
        temperature=0.7
    ),
    "gpt-4-turbo": LLMModelConfig(
        provider="openai",
        model_name="gpt-4-turbo",
        display_name="GPT-4 Turbo",
        description="빠르고 효율적인 GPT-4 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    "gpt-3.5-turbo": LLMModelConfig(
        provider="openai",
        model_name="gpt-3.5-turbo",
        display_name="GPT-3.5 Turbo",
        description="빠르고 비용 효율적인 GPT 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    
    # Anthropic 모델들
    "claude-3-opus-20240229": LLMModelConfig(
        provider="anthropic",
        model_name="claude-3-opus-20240229",
        display_name="Claude 3 Opus",
        description="가장 강력한 Claude 3 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    "claude-3-sonnet-20240229": LLMModelConfig(
        provider="anthropic",
        model_name="claude-3-sonnet-20240229",
        display_name="Claude 3 Sonnet",
        description="균형잡힌 성능의 Claude 3 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    "claude-3-haiku-20240307": LLMModelConfig(
        provider="anthropic",
        model_name="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        description="빠르고 효율적인 Claude 3 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    "claude-4-sonnet-20241022": LLMModelConfig(
        provider="anthropic",
        model_name="claude-4-sonnet-20241022",
        display_name="Claude 4 Sonnet",
        description="최신 Claude 4 Sonnet 모델 (2024-10-22)",
        max_tokens=8192,
        temperature=0.7
    ),
    
    # Google 모델들
    "gemini-1.5-pro": LLMModelConfig(
        provider="google",
        model_name="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        description="Google의 고성능 멀티모달 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    "gemini-1.5-flash": LLMModelConfig(
        provider="google",
        model_name="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        description="빠른 응답의 Gemini 모델",
        max_tokens=8192,
        temperature=0.7
    ),
    
    # 추가: 2025-05-14 릴리스 Claude 4 Sonnet (역순 네이밍 호환)
    "claude-sonnet-4-20250514": LLMModelConfig(
        provider="anthropic",
        model_name="claude-sonnet-4-20250514",
        display_name="Claude 4 Sonnet (20250514)",
        description="Claude 4 Sonnet – 2025-05-14 릴리스 버전",
        max_tokens=8192,
        temperature=0.7
    ),
}


class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""
    
    # === 기본 환경 설정 ===
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    app_name: str = Field(default="VizierAI Rule Validation API", alias="APP_NAME")
    app_version: str = Field(default="2.1.0", alias="APP_VERSION")
    
    # === 서버 설정 ===
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=1, alias="WORKERS")
    
    # === 보안 설정 ===
    secret_key: str = Field(default="dev-secret-key", alias="SECRET_KEY")
    allowed_hosts: Union[str, List[str]] = Field(default=["localhost", "127.0.0.1"], alias="ALLOWED_HOSTS")
    
    # === CORS 설정 ===
    allowed_origins: Union[str, List[str]] = Field(
        default=["*"], 
        alias="ALLOWED_ORIGINS"
    )
    
    @field_validator('allowed_hosts', mode='before')
    @classmethod
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(',') if host.strip()]
        return v
    
    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # === AI 서비스 API 키 ===
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    
    # === 데이터베이스 설정 ===
    database_url: str = Field(default="sqlite:///./vizierai.db", alias="DATABASE_URL")
    
    # === 로깅 설정 ===
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/vizierai.log", alias="LOG_FILE")
    max_log_size: str = Field(default="50MB", alias="MAX_LOG_SIZE")
    log_backup_count: int = Field(default=5, alias="LOG_BACKUP_COUNT")
    
    # === 성능 설정 ===
    max_request_size: int = Field(default=10485760, alias="MAX_REQUEST_SIZE")
    request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT")
    ai_timeout: int = Field(default=60, alias="AI_TIMEOUT")
    max_concurrent_requests: int = Field(default=100, alias="MAX_CONCURRENT_REQUESTS")
    
    # === AI 모델 설정 ===
    # 모델 우선순위: Claude 4 → Claude 3 → OpenAI
    default_model: str = Field(default="claude-4-sonnet-20241022", alias="DEFAULT_MODEL")
    fallback_model: str = Field(default="claude-3-opus-20240229", alias="FALLBACK_MODEL")
    max_tokens: int = Field(default=4000, alias="MAX_TOKENS")
    temperature: float = Field(default=0.7, alias="TEMPERATURE")
    
    # --- 세분화: 분석용 · 리포트용 모델 우선순위 ---
    analysis_default_model: str = Field(default="gpt-4o", alias="ANALYSIS_DEFAULT_MODEL")
    analysis_fallback_model: str = Field(default="gpt-3.5-turbo", alias="ANALYSIS_FALLBACK_MODEL")

    report_default_model: str = Field(default="claude-4-sonnet-20241022", alias="REPORT_DEFAULT_MODEL")
    report_fallback_model: str = Field(default="claude-3-opus-20240229", alias="REPORT_FALLBACK_MODEL")
    
    # === Rate Limiting ===
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")
    rate_limit_per_day: int = Field(default=10000, alias="RATE_LIMIT_PER_DAY")
    
    # === 캐싱 설정 ===
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    cache_ttl: int = Field(default=3600, alias="CACHE_TTL")  # 1시간
    
    # === SSL/TLS 설정 ===
    ssl_cert_path: Optional[str] = Field(default=None, alias="SSL_CERT_PATH")
    ssl_key_path: Optional[str] = Field(default=None, alias="SSL_KEY_PATH")
    
    # === 외부 서비스 URL ===
    production_url: str = Field(default="http://vizierai.duckdns.org:8000", alias="PRODUCTION_URL")
    staging_url: str = Field(default="http://vizierai.duckdns.org:8001", alias="STAGING_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        use_enum_values = True
        validate_assignment = True
        extra = "ignore"  # 추가 환경변수 무시
    
    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부 확인"""
        return self.environment.lower() == "production"
    
    @property
    def is_staging(self) -> bool:
        """스테이징 환경 여부 확인"""
        return self.environment.lower() == "staging"
    
    @property
    def is_development(self) -> bool:
        """개발 환경 여부 확인"""
        return self.environment.lower() == "development"
    
    def get_cors_origins(self) -> List[str]:
        """환경별 CORS Origins 반환"""
        if self.is_production:
            return [
                self.production_url,
                "https://vizierai.duckdns.org",
                "https://vizierai.duckdns.org:8000",
            ]
        elif self.is_staging:
            return [
                self.staging_url,
                "https://vizierai.duckdns.org:8001",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        else:
            # 개발 환경 - 모든 Origin 허용
            return [
                "http://localhost:3000",
                "http://localhost:3001", 
                "http://127.0.0.1:3000",
                "http://localhost:8888",
                "*",
            ]
    
    def get_uvicorn_config(self) -> dict:
        """환경별 Uvicorn 설정 반환"""
        config = {
            "host": self.host,
            "port": self.port,
            "reload": self.is_development,
            "workers": 1 if self.is_development else self.workers,
            "log_level": self.log_level.lower(),
        }
        
        # SSL 설정이 있는 경우 추가
        if self.ssl_cert_path and self.ssl_key_path:
            config.update({
                "ssl_certfile": self.ssl_cert_path,
                "ssl_keyfile": self.ssl_key_path,
            })
        
        return config


@lru_cache()
def get_settings() -> Settings:
    """설정 인스턴스 캐시된 반환"""
    return Settings()


# 전역 설정 인스턴스
settings = get_settings()
