import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import llm_endpoints, prompt_endpoints, rule_validator
from .config import settings
from .middleware.rate_limiter import rate_limit_middleware
from .services.prompt_service import PromptService
from .utils.api_validator import get_api_key_status, validate_api_keys_on_startup
from .utils.logger import get_logger

logger = get_logger(__name__)


# 환경별 CORS 설정
def get_cors_origins() -> List[str]:
    """환경에 따른 CORS Origin 설정"""
    cors_origins = settings.get_cors_origins()
    logger.info(f"{settings.environment} 환경 CORS Origins: {cors_origins}")
    return cors_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # 시작 시 초기화
    logger.info("🚀 VizierAI 룰 검증 시스템을 시작합니다...")

    # API 키 검증
    try:
        api_key_status = await validate_api_keys_on_startup()
        app.state.api_key_status = api_key_status

        if api_key_status.get("all_valid", False):
            logger.info("✅ 모든 API 키 검증 완료")
        else:
            logger.warning(
                "⚠️ 일부 API 키에 문제가 있습니다. 제한된 기능으로 동작합니다."
            )
    except Exception as e:
        logger.error(f"❌ API 키 검증 실패: {str(e)}")
        app.state.api_key_status = {"error": str(e)}

    # 프롬프트 서비스 초기화
    try:
        prompt_service = PromptService()
        app.state.prompt_service = prompt_service
        logger.info("✅ 프롬프트 서비스 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 프롬프트 서비스 초기화 실패: {str(e)}")
        raise

    # 환경 정보 로깅
    env = os.getenv("ENVIRONMENT", "development")
    logger.info(f"📍 실행 환경: {env}")

    yield

    # 종료 시 정리
    logger.info("🛑 VizierAI 룰 검증 시스템을 종료합니다...")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 생성 및 설정"""

    # 프로덕션에서도 docs 활성화 (CSP 수정으로 문제 해결)
    app = FastAPI(
        title="VizierAI Rule Validation API",
        description="AI 기반 하이브리드 룰 검증 및 분석 시스템",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",  # 명시적으로 설정
        lifespan=lifespan,
    )

    # CORS 미들웨어 설정 (환경별)
    cors_origins = get_cors_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        # 보안 헤더 추가
        expose_headers=["X-Request-ID", "X-Response-Time"],
    )

    # Rate Limiting 미들웨어 추가
    @app.middleware("http")
    async def rate_limiting_middleware(request, call_next):
        return await rate_limit_middleware(request, call_next)

    # 보안 헤더 미들웨어
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)

        # 보안 헤더 추가
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP 헤더 (Swagger UI를 위한 CDN 허용)
        if settings.is_production:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "font-src 'self' https://cdn.jsdelivr.net"
            )

        return response

    # 라우터 등록
    app.include_router(rule_validator.router, prefix="/rules", tags=["Rule Validation"])
    app.include_router(llm_endpoints.router, prefix="/api/llm")
    app.include_router(prompt_endpoints.router, prefix="/api/prompts")

    # API 문서 링크를 루트에서 제공하므로 별도 웹 엔드포인트 불필요

    # 루트 엔드포인트
    @app.get("/")
    async def root():
        """API 상태 확인"""
        return {
            "message": "VizierAI Rule Validation API",
            "version": "2.0.0",
            "status": "healthy",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "docs": "/docs",
        }

    # 헬스체크 엔드포인트
    @app.get("/health")
    async def health_check():
        """서버 상태 확인"""
        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "environment": os.getenv("ENVIRONMENT", "development"),
        }

    @app.get("/api/health")
    async def api_health_check():
        """API 서비스 상태 확인"""
        return {"status": "healthy", "service": "api"}

    # API 키 상태 확인 엔드포인트 (관리자용)
    @app.get("/admin/api-keys")
    async def api_keys_status():
        """API 키 상태 확인 (관리자용)"""
        try:
            status = await get_api_key_status()
            return status
        except Exception as e:
            logger.error(f"API 키 상태 확인 실패: {str(e)}")
            return {"error": str(e), "status": "error"}

    # 글로벌 예외 핸들러
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"처리되지 않은 예외: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "내부 서버 오류",
                "message": "요청을 처리하는 중 오류가 발생했습니다.",
            },
        )

    return app


# 애플리케이션 인스턴스 생성
app = create_app()

if __name__ == "__main__":
    import uvicorn

    # 환경별 설정 (새로운 config 시스템 사용)
    uvicorn_config = settings.get_uvicorn_config()
    uvicorn.run("app.main:app", **uvicorn_config)
