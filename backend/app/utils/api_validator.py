import os
import asyncio
from typing import Dict, Optional, Tuple
import httpx
import json
from datetime import datetime, timedelta

from .logger import get_logger

logger = get_logger(__name__)


class APIKeyValidator:
    """AI 서비스 API 키 유효성 검증"""
    
    def __init__(self):
        self.cache = {}  # 검증 결과 캐시 (5분간 유효)
        self.cache_ttl = timedelta(minutes=5)
        
    def _get_cache_key(self, service: str, api_key: str) -> str:
        """캐시 키 생성 (API 키의 일부만 사용)"""
        key_preview = api_key[:12] + "..." if len(api_key) > 12 else api_key
        return f"{service}:{key_preview}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시가 유효한지 확인"""
        if cache_key not in self.cache:
            return False
        
        cached_time = self.cache[cache_key].get("timestamp")
        if not cached_time:
            return False
        
        return datetime.now() - cached_time < self.cache_ttl
    
    async def validate_openai_key(self, api_key: str) -> Tuple[bool, str]:
        """OpenAI API 키 검증"""
        if not api_key or not api_key.startswith("sk-"):
            return False, "OpenAI API 키는 'sk-'로 시작해야 합니다."
        
        cache_key = self._get_cache_key("openai", api_key)
        
        # 캐시 확인
        if self._is_cache_valid(cache_key):
            cached_result = self.cache[cache_key]
            return cached_result["valid"], cached_result["message"]
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    # 사용 가능한 모델 확인
                    models = response.json().get("data", [])
                    model_names = [model.get("id") for model in models]
                    
                    result = (True, f"유효한 OpenAI API 키 (모델: {len(model_names)}개 사용 가능)")
                    
                    # 캐시에 저장
                    self.cache[cache_key] = {
                        "valid": True,
                        "message": result[1],
                        "timestamp": datetime.now(),
                        "models": model_names[:5]  # 첫 5개만 저장
                    }
                    
                    logger.info(f"OpenAI API 키 검증 성공: {len(model_names)}개 모델 사용 가능")
                    return result
                    
                elif response.status_code == 401:
                    result = (False, "OpenAI API 키가 유효하지 않습니다.")
                elif response.status_code == 429:
                    result = (False, "OpenAI API 호출 한도 초과")
                else:
                    result = (False, f"OpenAI API 오류: {response.status_code}")
                
                # 실패 결과도 짧게 캐시 (1분)
                self.cache[cache_key] = {
                    "valid": False,
                    "message": result[1],
                    "timestamp": datetime.now() - timedelta(minutes=4)  # 1분만 캐시
                }
                
                return result
                
        except Exception as e:
            error_msg = f"OpenAI API 키 검증 중 오류: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def validate_anthropic_key(self, api_key: str) -> Tuple[bool, str]:
        """Anthropic API 키 검증"""
        if not api_key or not api_key.startswith("sk-ant-"):
            return False, "Anthropic API 키는 'sk-ant-'로 시작해야 합니다."
        
        cache_key = self._get_cache_key("anthropic", api_key)
        
        # 캐시 확인
        if self._is_cache_valid(cache_key):
            cached_result = self.cache[cache_key]
            return cached_result["valid"], cached_result["message"]
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Anthropic API는 직접적인 키 검증 엔드포인트가 없으므로
                # 작은 테스트 요청을 보내서 확인
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "test"}]
                    }
                )
                
                if response.status_code == 200:
                    result = (True, "유효한 Anthropic API 키")
                    
                    # 캐시에 저장
                    self.cache[cache_key] = {
                        "valid": True,
                        "message": result[1],
                        "timestamp": datetime.now()
                    }
                    
                    logger.info("Anthropic API 키 검증 성공")
                    return result
                    
                elif response.status_code == 401:
                    result = (False, "Anthropic API 키가 유효하지 않습니다.")
                elif response.status_code == 429:
                    result = (False, "Anthropic API 호출 한도 초과")
                else:
                    result = (False, f"Anthropic API 오류: {response.status_code}")
                
                # 실패 결과도 짧게 캐시
                self.cache[cache_key] = {
                    "valid": False,
                    "message": result[1],
                    "timestamp": datetime.now() - timedelta(minutes=4)
                }
                
                return result
                
        except Exception as e:
            error_msg = f"Anthropic API 키 검증 중 오류: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def validate_google_key(self, api_key: str) -> Tuple[bool, str]:
        """Google AI API 키 검증"""
        if not api_key:
            return False, "Google API 키가 없습니다."
        
        cache_key = self._get_cache_key("google", api_key)
        
        # 캐시 확인
        if self._is_cache_valid(cache_key):
            cached_result = self.cache[cache_key]
            return cached_result["valid"], cached_result["message"]
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Google AI Studio API 엔드포인트 사용
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                )
                
                if response.status_code == 200:
                    models_data = response.json()
                    models = models_data.get("models", [])
                    
                    result = (True, f"유효한 Google AI API 키 (모델: {len(models)}개 사용 가능)")
                    
                    # 캐시에 저장
                    self.cache[cache_key] = {
                        "valid": True,
                        "message": result[1],
                        "timestamp": datetime.now()
                    }
                    
                    logger.info(f"Google AI API 키 검증 성공: {len(models)}개 모델 사용 가능")
                    return result
                    
                elif response.status_code == 400:
                    result = (False, "Google AI API 키가 유효하지 않습니다.")
                elif response.status_code == 429:
                    result = (False, "Google AI API 호출 한도 초과")
                else:
                    result = (False, f"Google AI API 오류: {response.status_code}")
                
                # 실패 결과도 짧게 캐시
                self.cache[cache_key] = {
                    "valid": False,
                    "message": result[1],
                    "timestamp": datetime.now() - timedelta(minutes=4)
                }
                
                return result
                
        except Exception as e:
            error_msg = f"Google AI API 키 검증 중 오류: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def validate_all_keys(self) -> Dict[str, Tuple[bool, str]]:
        """모든 설정된 API 키 검증"""
        results = {}
        
        # 환경 변수에서 API 키 가져오기
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        google_key = os.getenv("GOOGLE_API_KEY")
        
        # 병렬로 검증 실행
        tasks = []
        
        if openai_key and not openai_key.startswith("your_"):
            tasks.append(("openai", self.validate_openai_key(openai_key)))
        
        if anthropic_key and not anthropic_key.startswith("your_"):
            tasks.append(("anthropic", self.validate_anthropic_key(anthropic_key)))
        
        if google_key and not google_key.startswith("your_"):
            tasks.append(("google", self.validate_google_key(google_key)))
        
        if not tasks:
            logger.warning("설정된 AI API 키가 없습니다.")
            return {"warning": (False, "설정된 AI API 키가 없습니다.")}
        
        # 병렬 검증 실행
        completed_tasks = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
        
        for i, (service_name, _) in enumerate(tasks):
            if isinstance(completed_tasks[i], Exception):
                results[service_name] = (False, f"검증 중 예외 발생: {str(completed_tasks[i])}")
            else:
                results[service_name] = completed_tasks[i]
        
        return results
    
    def get_validation_summary(self, results: Dict[str, Tuple[bool, str]]) -> Dict[str, any]:
        """검증 결과 요약"""
        valid_count = sum(1 for valid, _ in results.values() if valid)
        total_count = len(results)
        
        return {
            "total_keys": total_count,
            "valid_keys": valid_count,
            "invalid_keys": total_count - valid_count,
            "all_valid": valid_count == total_count and total_count > 0,
            "details": results
        }


# 전역 인스턴스
api_validator = APIKeyValidator()


async def validate_api_keys_on_startup():
    """애플리케이션 시작시 API 키 검증"""
    logger.info("🔑 API 키 유효성 검증 시작...")
    
    try:
        results = await api_validator.validate_all_keys()
        summary = api_validator.get_validation_summary(results)
        
        if summary["all_valid"]:
            logger.info(f"✅ 모든 API 키 검증 성공 ({summary['valid_keys']}/{summary['total_keys']})")
        else:
            logger.warning(f"⚠️ API 키 검증 완료: {summary['valid_keys']}/{summary['total_keys']} 유효")
            
            for service, (valid, message) in results.items():
                if not valid:
                    logger.warning(f"   - {service}: {message}")
                else:
                    logger.info(f"   - {service}: ✅ {message}")
        
        return summary
        
    except Exception as e:
        logger.error(f"❌ API 키 검증 중 오류: {str(e)}")
        return {"error": str(e)}


async def get_api_key_status() -> Dict[str, any]:
    """현재 API 키 상태 조회 (엔드포인트용)"""
    results = await api_validator.validate_all_keys()
    summary = api_validator.get_validation_summary(results)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy" if summary["all_valid"] else "warning",
        "summary": summary,
        "services": {
            service: {
                "valid": valid,
                "message": message,
                "last_checked": "just_now"
            }
            for service, (valid, message) in results.items()
        }
    } 