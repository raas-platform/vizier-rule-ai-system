"""
VizierAI Rule Validation API - 설정 관리
환경변수 기반 중앙집중식 설정
"""

import os
from typing import List, Optional, Dict, Union
from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from functools import lru_cache


class LLMModelConfig(BaseModel):
    """LLM 모델 설정 클래스"""
    provider: str
    model_name: str
    display_name: str
    description: str
    max_tokens: int
    # None이면 temperature를 보내지 않음 (gpt-6.1-sol, claude-sonnet-5-5는 sampling 파라미터 미지원)
    temperature: Optional[float] = 0.7
    
    model_config = {"protected_namespaces": ()}


# === 지원되는 LLM 모델 설정 ===
SUPPORTED_MODELS: Dict[str, LLMModelConfig] = {
    # OpenAI 모델들
    "gpt-6.1-sol": LLMModelConfig(
        provider="openai",
        model_name="gpt-6.1-sol",
        display_name="GPT-6.1 Sol",
        description="복잡한 코딩/전문 업무용 OpenAI 추론 모델",
        # 추론 토큰도 이 한도에 포함되므로 충분히 크게 설정
        max_tokens=16384,
        temperature=None,
    ),

    # Anthropic 모델들
    "claude-sonnet-5-5": LLMModelConfig(
        provider="anthropic",
        model_name="claude-sonnet-5-5",
        display_name="Claude Sonnet 5.5",
        description="균형잡힌 성능의 Claude Sonnet 5.5 모델",
        max_tokens=4096,
        temperature=None,
    ),

    # Google 모델들
    "gemini-1.5-pro": LLMModelConfig(
        provider="google",
        model_name="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        description="Google의 고성능 멀티모달 모델",
        max_tokens=4096,
        temperature=0.7
    ),
    "gemini-1.5-flash": LLMModelConfig(
        provider="google",
        model_name="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        description="빠른 응답의 Gemini 모델",
        max_tokens=4096,
        temperature=0.7
    ),
}


# CORS 기본 허용 Origin (Vizier dev/demo/prod 화면). https 스킴은 판정관 추측이며
# CORS_ALLOWED_ORIGINS 환경변수로 바꿀 수 있다.
DEFAULT_CORS_ALLOWED_ORIGINS = (
    "https://dev.vizier-service.com,"
    "https://demo.vizier-service.com,"
    "https://prod.vizier-service.com"
)

# CORS 허용 헤더 / 메서드
CORS_ALLOWED_HEADERS = ["Content-Type", "X-User-Id", "A-TOKEN", "X-API-Key"]
CORS_ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]


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
    
    # Vizier 화면에서 브라우저로 호출하는 Origin 목록 (콤마 구분).
    # 비어 있으면 DEFAULT_CORS_ALLOWED_ORIGINS를 쓴다.
    cors_allowed_origins: Optional[str] = Field(default=None, alias="CORS_ALLOWED_ORIGINS")

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
    default_model: str = Field(default="gpt-6.1-sol", alias="DEFAULT_MODEL")
    fallback_model: str = Field(default="claude-sonnet-5-5", alias="FALLBACK_MODEL")
    max_tokens: int = Field(default=4000, alias="MAX_TOKENS")
    temperature: float = Field(default=0.7, alias="TEMPERATURE")
    
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
    production_url: str = Field(default="http://localhost:8000", alias="PRODUCTION_URL")
    staging_url: str = Field(default="http://localhost:8001", alias="STAGING_URL")
    
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
    
    def get_cors_allowed_origins(self) -> List[str]:
        """CORS 허용 Origin 목록 (CORS_ALLOWED_ORIGINS, 없으면 기본값).

        '*'는 받지 않는다 (credentials 허용과 함께 쓰면 모든 사이트가 호출할 수 있게 되므로).
        """
        raw = self.cors_allowed_origins
        if raw is None or not raw.strip():
            raw = DEFAULT_CORS_ALLOWED_ORIGINS
        origins: List[str] = []
        for origin in raw.split(","):
            origin = origin.strip().rstrip("/")
            if origin and origin != "*" and origin not in origins:
                origins.append(origin)
        return origins

    def get_cors_dev_origin_regex(self) -> Optional[str]:
        """운영(production)이 아닐 때만 로컬 테스트 화면용 localhost / 127.0.0.1 (모든 포트) 허용."""
        if self.is_production:
            return None
        return r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

    def get_cors_origins(self) -> List[str]:
        """환경별 CORS Origins 반환"""
        if self.is_production:
            return [
                self.production_url,
            ]
        elif self.is_staging:
            return [
                self.staging_url,
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
