"""
프롬프트 관련 API 엔드포인트
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..models.prompt import (
    Prompt,
    PromptCreate,
    PromptExecuteRequest,
    PromptExecuteResponse,
    PromptListResponse,
    PromptSearchRequest,
    PromptStats,
    PromptUpdate,
)
from ..services.prompt_service import prompt_service
from ..utils.logger import get_logger

router = APIRouter(prefix="/prompts", tags=["prompts"])
logger = get_logger(__name__)


@router.post("/", response_model=Prompt, summary="프롬프트 생성")
async def create_prompt(prompt: PromptCreate, db: Session = Depends(get_db)):
    """
    새로운 프롬프트 템플릿을 생성합니다.

    - **title**: 프롬프트 제목 (필수)
    - **description**: 프롬프트 설명 (선택)
    - **category**: 프롬프트 카테고리 (필수)
    - **content**: 프롬프트 내용 (필수)
    - **variables**: 변수 목록 (자동 추출됨)
    - **tags**: 검색용 태그들 (선택)
    - **is_system_prompt**: 시스템 프롬프트 여부 (기본: false)
    - **is_active**: 활성화 상태 (기본: true)
    """
    try:
        return prompt_service.create_prompt(db, prompt)
    except Exception as e:
        logger.error(f"프롬프트 생성 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 생성에 실패했습니다."
        )


@router.get("/{prompt_id}", response_model=Prompt, summary="프롬프트 조회")
async def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    ID로 특정 프롬프트를 조회합니다.
    """
    try:
        prompt = prompt_service.get_prompt(db, prompt_id)
        if not prompt:
            raise HTTPException(
                status_code=404, detail="프롬프트를 찾을 수 없습니다."
            )
        return prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 조회 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 조회에 실패했습니다."
        )


@router.put("/{prompt_id}", response_model=Prompt, summary="프롬프트 수정")
async def update_prompt(
    prompt_id: int, prompt_update: PromptUpdate, db: Session = Depends(get_db)
):
    """
    기존 프롬프트를 수정합니다.
    """
    try:
        prompt = prompt_service.update_prompt(db, prompt_id, prompt_update)
        if not prompt:
            raise HTTPException(
                status_code=404, detail="프롬프트를 찾을 수 없습니다."
            )
        return prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 수정 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 수정에 실패했습니다."
        )


@router.delete("/{prompt_id}", summary="프롬프트 삭제")
async def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    프롬프트를 삭제합니다.
    """
    try:
        success = prompt_service.delete_prompt(db, prompt_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="프롬프트를 찾을 수 없습니다."
            )
        return {"message": "프롬프트가 성공적으로 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 삭제 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 삭제에 실패했습니다."
        )


@router.post(
    "/search", response_model=PromptListResponse, summary="프롬프트 검색"
)
async def search_prompts(
    search_request: PromptSearchRequest, db: Session = Depends(get_db)
):
    """
    조건에 따라 프롬프트를 검색합니다.

    - **query**: 검색어 (제목, 설명, 내용에서 검색)
    - **category**: 카테고리 필터
    - **tags**: 태그 필터
    - **is_system_prompt**: 시스템 프롬프트 필터
    - **is_active**: 활성화 상태 필터
    - **limit**: 결과 제한 (기본: 50, 최대: 100)
    - **offset**: 결과 오프셋 (기본: 0)
    """
    try:
        return prompt_service.search_prompts(db, search_request)
    except Exception as e:
        logger.error(f"프롬프트 검색 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 검색에 실패했습니다."
        )


@router.get(
    "/", response_model=PromptListResponse, summary="프롬프트 목록 조회"
)
async def list_prompts(
    query: str = Query(None, description="검색어"),
    category: str = Query(None, description="카테고리"),
    is_system_prompt: bool = Query(None, description="시스템 프롬프트 필터"),
    is_active: bool = Query(True, description="활성화 상태 필터"),
    limit: int = Query(50, ge=1, le=100, description="결과 제한"),
    offset: int = Query(0, ge=0, description="결과 오프셋"),
    db: Session = Depends(get_db),
):
    """
    쿼리 파라미터로 프롬프트 목록을 조회합니다.
    """
    try:
        from ..models.prompt import PromptCategory

        # 카테고리 변환
        category_enum = None
        if category:
            try:
                category_enum = PromptCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"잘못된 카테고리: {category}"
                )

        search_request = PromptSearchRequest(
            query=query,
            category=category_enum,
            is_system_prompt=is_system_prompt,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

        return prompt_service.search_prompts(db, search_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 목록 조회 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 목록 조회에 실패했습니다."
        )


@router.get(
    "/categories/list",
    response_model=List[Dict[str, str]],
    summary="카테고리 목록 조회",
)
async def get_categories():
    """
    사용 가능한 프롬프트 카테고리 목록을 조회합니다.
    """
    try:
        return prompt_service.get_categories()
    except Exception as e:
        logger.error(f"카테고리 조회 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="카테고리 조회에 실패했습니다."
        )


@router.get(
    "/stats/overview", response_model=PromptStats, summary="프롬프트 통계 조회"
)
async def get_prompt_stats(db: Session = Depends(get_db)):
    """
    프롬프트 관련 통계 정보를 조회합니다.
    """
    try:
        return prompt_service.get_prompt_stats(db)
    except Exception as e:
        logger.error(f"프롬프트 통계 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 통계 조회에 실패했습니다."
        )


@router.post(
    "/execute", response_model=PromptExecuteResponse, summary="프롬프트 실행"
)
async def execute_prompt(
    execute_request: PromptExecuteRequest, db: Session = Depends(get_db)
):
    """
    프롬프트를 실행하여 LLM으로 텍스트를 생성합니다.

    - **prompt_id**: 실행할 프롬프트 ID (custom_content 미사용시 필수)
    - **variables**: 프롬프트 변수 값들
    - **model_id**: 사용할 LLM 모델 ID
    - **custom_content**: 커스텀 프롬프트 내용 (prompt_id 대신 사용 가능)
    """
    try:
        return await prompt_service.execute_prompt(db, execute_request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"프롬프트 실행 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 실행에 실패했습니다."
        )


@router.post(
    "/{prompt_id}/duplicate", response_model=Prompt, summary="프롬프트 복제"
)
async def duplicate_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    기존 프롬프트를 복제하여 새로운 프롬프트를 생성합니다.
    """
    try:
        # 원본 프롬프트 조회
        original = prompt_service.get_prompt(db, prompt_id)
        if not original:
            raise HTTPException(
                status_code=404, detail="프롬프트를 찾을 수 없습니다."
            )

        # 복제용 데이터 생성
        duplicate_data = PromptCreate(
            title=f"{original.title} (복제)",
            description=original.description,
            category=original.category,
            content=original.content,
            variables=original.variables,
            tags=original.tags,
            is_system_prompt=original.is_system_prompt,
            is_active=True,
        )

        return prompt_service.create_prompt(db, duplicate_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 복제 API 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="프롬프트 복제에 실패했습니다."
        )
