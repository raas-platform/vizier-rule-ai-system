"""
LLM 관련 API 엔드포인트
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.llm_service import llm_service
from ..utils.logger import get_logger

router = APIRouter(prefix="/llm", tags=["llm"])
logger = get_logger(__name__)


class ModelInfo(BaseModel):
    """모델 정보 스키마"""

    id: str
    provider: str
    display_name: str
    description: str
    max_tokens: int


class GenerateTextRequest(BaseModel):
    """텍스트 생성 요청 스키마"""

    prompt: str
    model_id: str
    system_message: Optional[str] = None


class GenerateTextResponse(BaseModel):
    """텍스트 생성 응답 스키마"""

    result: str
    model_used: str
    token_count: Optional[int] = None


@router.get("/models", response_model=List[ModelInfo])
async def get_available_models():
    """
    사용 가능한 LLM 모델 목록 조회

    Returns:
        사용 가능한 모델 목록
    """
    try:
        models = llm_service.get_available_models()
        logger.info(f"모델 목록 조회: {len(models)}개 모델")
        return [ModelInfo(**model) for model in models]
    except Exception as e:
        logger.error(f"모델 목록 조회 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="모델 목록을 가져오는 중 오류가 발생했습니다.",
        )


@router.post("/generate", response_model=GenerateTextResponse)
async def generate_text(request: GenerateTextRequest):
    """
    선택된 모델로 텍스트 생성

    Args:
        request: 생성 요청 데이터

    Returns:
        생성된 텍스트
    """
    try:
        if not llm_service.is_model_available(request.model_id):
            raise HTTPException(
                status_code=400,
                detail=f"모델 '{request.model_id}'을(를) 사용할 수 없습니다.",
            )

        # 시스템 메시지가 있는 경우 프롬프트에 포함
        full_prompt = request.prompt
        if request.system_message:
            full_prompt = f"System: {request.system_message}\n\nUser: {request.prompt}"

        result = await llm_service.generate_text(full_prompt, request.model_id)

        return GenerateTextResponse(
            result=result,
            model_used=request.model_id,
            token_count=len(result.split()) if result else 0,
        )

    except ValueError as e:
        logger.warning(f"잘못된 요청: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"텍스트 생성 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="텍스트 생성 중 오류가 발생했습니다."
        )


@router.post("/generate/stream")
async def generate_text_stream(request: GenerateTextRequest):
    """
    선택된 모델로 스트리밍 텍스트 생성

    Args:
        request: 생성 요청 데이터

    Returns:
        스트리밍 응답
    """
    try:
        if not llm_service.is_model_available(request.model_id):
            raise HTTPException(
                status_code=400,
                detail=f"모델 '{request.model_id}'을(를) 사용할 수 없습니다.",
            )

        # 시스템 메시지가 있는 경우 프롬프트에 포함
        full_prompt = request.prompt
        if request.system_message:
            full_prompt = f"System: {request.system_message}\n\nUser: {request.prompt}"

        async def generate():
            try:
                async for chunk in llm_service.generate_stream(
                    full_prompt, request.model_id
                ):
                    # Server-Sent Events 형식으로 데이터 전송
                    yield f"data: {json.dumps({'text': chunk, 'done': False})}\n\n"

                # 완료 신호
                yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"

            except Exception as e:
                logger.error(f"스트리밍 생성 오류: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )

    except ValueError as e:
        logger.warning(f"잘못된 스트리밍 요청: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"스트리밍 설정 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="스트리밍 설정 중 오류가 발생했습니다."
        )


@router.get("/models/{model_id}/status")
async def check_model_status(model_id: str):
    """
    특정 모델의 상태 확인

    Args:
        model_id: 확인할 모델 ID

    Returns:
        모델 상태 정보
    """
    try:
        is_available = llm_service.is_model_available(model_id)

        return {
            "model_id": model_id,
            "available": is_available,
            "message": (
                "사용 가능"
                if is_available
                else "사용 불가능 (API 키 미설정 또는 모델 미지원)"
            ),
        }

    except Exception as e:
        logger.error(f"모델 상태 확인 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="모델 상태 확인 중 오류가 발생했습니다."
        )


@router.get("/health")
async def health_check():
    """
    LLM 서비스 상태 확인

    Returns:
        서비스 상태 정보
    """
    try:
        available_models = llm_service.get_available_models()

        return {
            "status": "healthy",
            "available_models_count": len(available_models),
            "providers_initialized": len(llm_service.providers),
            "message": "LLM 서비스가 정상적으로 작동 중입니다.",
        }

    except Exception as e:
        logger.error(f"상태 확인 오류: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "LLM 서비스에 문제가 있습니다.",
        }
