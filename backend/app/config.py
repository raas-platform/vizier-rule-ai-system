import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Rule AI System"
    
    # LLM 설정
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4")
    
    # 개발 환경 설정
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # 프론트엔드 설정 (선택 사항)
    VITE_API_URL: str = os.getenv("VITE_API_URL", "http://localhost:8000")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 추가 필드를 무시합니다

settings = Settings() 