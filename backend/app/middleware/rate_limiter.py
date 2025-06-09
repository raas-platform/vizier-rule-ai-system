import os
import time
from datetime import datetime, timedelta
from typing import Dict

from fastapi import Request
from fastapi.responses import JSONResponse

from ..utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate Limiting을 위한 클래스"""

    def __init__(self):
        # 환경 변수에서 제한값 가져오기
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))
        self.rate_limit_per_hour = int(os.getenv("RATE_LIMIT_PER_HOUR", 1000))
        self.rate_limit_per_day = int(os.getenv("RATE_LIMIT_PER_DAY", 10000))

        # 메모리 기반 저장소 (프로덕션에서는 Redis 사용 권장)
        self.requests: Dict[str, Dict] = {}

        # 정리 작업을 위한 마지막 정리 시간
        self.last_cleanup = datetime.now()

        logger.info(
            f"Rate Limiter 초기화: {self.rate_limit_per_minute}/분, "
            f"{self.rate_limit_per_hour}/시간, {self.rate_limit_per_day}/일"
        )

    def _get_client_key(self, request: Request) -> str:
        """클라이언트 식별을 위한 키 생성"""
        # X-Forwarded-For 헤더 확인 (프록시 뒤에 있는 경우)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 첫 번째 IP가 실제 클라이언트 IP
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        # API 키가 있는 경우 더 세분화된 제한 (선택사항)
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"{client_ip}:{api_key[:8]}"  # IP + API키 일부

        return client_ip

    def _cleanup_old_requests(self):
        """오래된 요청 기록 정리"""
        now = datetime.now()

        # 5분마다 정리
        if now - self.last_cleanup < timedelta(minutes=5):
            return

        cutoff_time = now - timedelta(days=1)
        keys_to_remove = []

        for client_key, data in self.requests.items():
            # 1일 이상 된 기록 제거
            data["requests"] = [
                req_time for req_time in data["requests"] if req_time > cutoff_time
            ]

            if not data["requests"]:
                keys_to_remove.append(client_key)

        for key in keys_to_remove:
            del self.requests[key]

        self.last_cleanup = now

        if keys_to_remove:
            logger.debug(
                f"Rate Limiter 정리: {len(keys_to_remove)}개 클라이언트 기록 제거"
            )

    def _get_rate_limit_status(self, client_key: str) -> Dict[str, int]:
        """현재 Rate Limit 상태 확인"""
        now = datetime.now()

        if client_key not in self.requests:
            self.requests[client_key] = {"requests": []}

        client_data = self.requests[client_key]
        request_times = client_data["requests"]

        # 시간대별 요청 수 계산
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        requests_last_minute = sum(
            1 for req_time in request_times if req_time > minute_ago
        )
        requests_last_hour = sum(1 for req_time in request_times if req_time > hour_ago)
        requests_last_day = sum(1 for req_time in request_times if req_time > day_ago)

        return {
            "requests_last_minute": requests_last_minute,
            "requests_last_hour": requests_last_hour,
            "requests_last_day": requests_last_day,
        }

    def is_allowed(self, request: Request) -> tuple[bool, Dict[str, any]]:
        """요청이 허용되는지 확인"""
        client_key = self._get_client_key(request)

        # 오래된 기록 정리
        self._cleanup_old_requests()

        # 현재 상태 확인
        status = self._get_rate_limit_status(client_key)

        # 제한 확인
        if status["requests_last_minute"] >= self.rate_limit_per_minute:
            return False, {
                "error": "Rate limit exceeded",
                "message": f"분당 {self.rate_limit_per_minute}회 제한 초과",
                "reset_time": 60,
                "current_usage": status["requests_last_minute"],
            }

        if status["requests_last_hour"] >= self.rate_limit_per_hour:
            return False, {
                "error": "Rate limit exceeded",
                "message": f"시간당 {self.rate_limit_per_hour}회 제한 초과",
                "reset_time": 3600,
                "current_usage": status["requests_last_hour"],
            }

        if status["requests_last_day"] >= self.rate_limit_per_day:
            return False, {
                "error": "Rate limit exceeded",
                "message": f"일일 {self.rate_limit_per_day}회 제한 초과",
                "reset_time": 86400,
                "current_usage": status["requests_last_day"],
            }

        # 요청 기록
        now = datetime.now()
        self.requests[client_key]["requests"].append(now)

        # 응답 헤더 정보
        return True, {
            "remaining_minute": self.rate_limit_per_minute
            - status["requests_last_minute"]
            - 1,
            "remaining_hour": self.rate_limit_per_hour
            - status["requests_last_hour"]
            - 1,
            "remaining_day": self.rate_limit_per_day - status["requests_last_day"] - 1,
            "reset_minute": 60,
            "reset_hour": 3600,
            "reset_day": 86400,
        }


# 전역 Rate Limiter 인스턴스
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Rate Limiting 미들웨어"""

    # 헬스체크와 정적 파일은 제외
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
        response = await call_next(request)
        return response

    # Rate Limit 확인
    is_allowed, limit_info = rate_limiter.is_allowed(request)

    if not is_allowed:
        logger.warning(
            f"Rate limit 초과: {rate_limiter._get_client_key(request)} - "
            f"{limit_info['message']}"
        )

        return JSONResponse(
            status_code=429,
            content=limit_info,
            headers={
                "Retry-After": str(limit_info["reset_time"]),
                "X-RateLimit-Limit": str(rate_limiter.rate_limit_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(
                    int(time.time()) + limit_info["reset_time"]
                ),
            },
        )

    # 요청 처리
    response = await call_next(request)

    # Rate Limit 정보를 응답 헤더에 추가
    response.headers["X-RateLimit-Limit-Minute"] = str(
        rate_limiter.rate_limit_per_minute
    )
    response.headers["X-RateLimit-Limit-Hour"] = str(rate_limiter.rate_limit_per_hour)
    response.headers["X-RateLimit-Limit-Day"] = str(rate_limiter.rate_limit_per_day)
    response.headers["X-RateLimit-Remaining-Minute"] = str(
        limit_info["remaining_minute"]
    )
    response.headers["X-RateLimit-Remaining-Hour"] = str(limit_info["remaining_hour"])
    response.headers["X-RateLimit-Remaining-Day"] = str(limit_info["remaining_day"])

    return response
