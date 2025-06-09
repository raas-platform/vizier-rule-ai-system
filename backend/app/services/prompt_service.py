"""
프롬프트 관리 서비스
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from ..database.schemas import PromptDB
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
from ..services.llm_service import llm_service
from ..utils.logger import get_logger


class PromptService:
    """프롬프트 관리 서비스"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def create_prompt(self, db: Session, prompt: PromptCreate) -> Prompt:
        """새 프롬프트 생성"""
        try:
            # 변수 추출
            variables = self._extract_variables(prompt.content)

            db_prompt = PromptDB(
                title=prompt.title,
                description=prompt.description,
                category=prompt.category.value,
                content=prompt.content,
                variables=json.dumps(variables),  # JSON 문자열로 저장
                tags=json.dumps(prompt.tags or []),  # JSON 문자열로 저장
                is_system_prompt=prompt.is_system_prompt,
                is_active=prompt.is_active,
            )

            db.add(db_prompt)
            db.commit()
            db.refresh(db_prompt)

            self.logger.info(
                f"프롬프트 생성 완료: {db_prompt.title} (ID: {db_prompt.id})"
            )
            return Prompt(**db_prompt.to_dict())

        except Exception as e:
            self.logger.error(f"프롬프트 생성 오류: {str(e)}", exc_info=True)
            db.rollback()
            raise

    def get_prompt(self, db: Session, prompt_id: int) -> Optional[Prompt]:
        """프롬프트 조회"""
        try:
            db_prompt = db.query(PromptDB).filter(PromptDB.id == prompt_id).first()
            if not db_prompt:
                return None

            return Prompt(**db_prompt.to_dict())

        except Exception as e:
            self.logger.error(f"프롬프트 조회 오류: {str(e)}", exc_info=True)
            raise

    def update_prompt(
        self, db: Session, prompt_id: int, prompt_update: PromptUpdate
    ) -> Optional[Prompt]:
        """프롬프트 업데이트"""
        try:
            db_prompt = db.query(PromptDB).filter(PromptDB.id == prompt_id).first()
            if not db_prompt:
                return None

            # 업데이트할 필드들
            update_data = prompt_update.dict(exclude_unset=True)

            # 카테고리 enum을 문자열로 변환
            if "category" in update_data:
                update_data["category"] = update_data["category"].value

            # 변수 재추출 (content가 변경된 경우)
            if "content" in update_data:
                update_data["variables"] = json.dumps(
                    self._extract_variables(update_data["content"])
                )

            # tags를 JSON 문자열로 변환
            if "tags" in update_data:
                update_data["tags"] = json.dumps(update_data["tags"] or [])

            # 업데이트 적용
            for field, value in update_data.items():
                setattr(db_prompt, field, value)

            db.commit()
            db.refresh(db_prompt)

            self.logger.info(
                f"프롬프트 업데이트 완료: {db_prompt.title} (ID: {prompt_id})"
            )
            return Prompt(**db_prompt.to_dict())

        except Exception as e:
            self.logger.error(f"프롬프트 업데이트 오류: {str(e)}", exc_info=True)
            db.rollback()
            raise

    def delete_prompt(self, db: Session, prompt_id: int) -> bool:
        """프롬프트 삭제"""
        try:
            db_prompt = db.query(PromptDB).filter(PromptDB.id == prompt_id).first()
            if not db_prompt:
                return False

            db.delete(db_prompt)
            db.commit()

            self.logger.info(f"프롬프트 삭제 완료: {db_prompt.title} (ID: {prompt_id})")
            return True

        except Exception as e:
            self.logger.error(f"프롬프트 삭제 오류: {str(e)}", exc_info=True)
            db.rollback()
            raise

    def search_prompts(
        self, db: Session, search_request: PromptSearchRequest
    ) -> PromptListResponse:
        """프롬프트 검색"""
        try:
            query = db.query(PromptDB)

            # 필터 조건 적용
            filters = []

            if search_request.is_active is not None:
                filters.append(PromptDB.is_active == search_request.is_active)

            if search_request.category:
                filters.append(PromptDB.category == search_request.category.value)

            if search_request.is_system_prompt is not None:
                filters.append(
                    PromptDB.is_system_prompt == search_request.is_system_prompt
                )

            if search_request.query:
                search_filter = or_(
                    PromptDB.title.contains(search_request.query),
                    PromptDB.description.contains(search_request.query),
                    PromptDB.content.contains(search_request.query),
                )
                filters.append(search_filter)

            if search_request.tags:
                # Text 필드에서 태그 검색
                tag_filters = []
                for tag in search_request.tags:
                    tag_filters.append(PromptDB.tags.contains(f'"{tag}"'))
                filters.append(or_(*tag_filters))

            if filters:
                query = query.filter(and_(*filters))

            # 전체 개수 조회
            total = query.count()

            # 정렬 및 페이징
            prompts = (
                query.order_by(desc(PromptDB.updated_at))
                .offset(search_request.offset)
                .limit(search_request.limit)
                .all()
            )

            # 응답 생성
            prompt_list = [Prompt(**prompt.to_dict()) for prompt in prompts]
            has_more = search_request.offset + len(prompt_list) < total

            return PromptListResponse(
                prompts=prompt_list, total=total, has_more=has_more
            )

        except Exception as e:
            self.logger.error(f"프롬프트 검색 오류: {str(e)}", exc_info=True)
            raise

    def get_prompt_stats(self, db: Session) -> PromptStats:
        """프롬프트 통계 조회"""
        try:
            # 전체 프롬프트 수
            total_prompts = (
                db.query(PromptDB).filter(PromptDB.is_active == True).count()
            )

            # 카테고리별 프롬프트 수 - SQLAlchemy 1.4 문법
            from sqlalchemy import func

            category_stats = (
                db.query(PromptDB.category, func.count(PromptDB.id))
                .filter(PromptDB.is_active == True)
                .group_by(PromptDB.category)
                .all()
            )
            prompts_by_category = {
                category: count for category, count in category_stats
            }

            # 가장 많이 사용된 프롬프트들 (상위 5개)
            most_used = (
                db.query(PromptDB)
                .filter(PromptDB.is_active == True)
                .order_by(desc(PromptDB.usage_count))
                .limit(5)
                .all()
            )
            most_used_prompts = [Prompt(**prompt.to_dict()) for prompt in most_used]

            # 최근 생성된 프롬프트들 (상위 5개)
            recent = (
                db.query(PromptDB)
                .filter(PromptDB.is_active == True)
                .order_by(desc(PromptDB.created_at))
                .limit(5)
                .all()
            )
            recent_prompts = [Prompt(**prompt.to_dict()) for prompt in recent]

            return PromptStats(
                total_prompts=total_prompts,
                prompts_by_category=prompts_by_category,
                most_used_prompts=most_used_prompts,
                recent_prompts=recent_prompts,
            )

        except Exception as e:
            self.logger.error(f"프롬프트 통계 조회 오류: {str(e)}", exc_info=True)
            raise

    async def execute_prompt(
        self, db: Session, execute_request: PromptExecuteRequest
    ) -> PromptExecuteResponse:
        """프롬프트 실행"""
        start_time = time.time()

        try:
            # 프롬프트 내용 가져오기
            if execute_request.custom_content:
                prompt_content = execute_request.custom_content
                prompt_used = prompt_content
            else:
                db_prompt = (
                    db.query(PromptDB)
                    .filter(PromptDB.id == execute_request.prompt_id)
                    .first()
                )
                if not db_prompt:
                    raise ValueError(
                        f"프롬프트 ID {execute_request.prompt_id}를 찾을 수 없습니다."
                    )

                prompt_content = db_prompt.content
                prompt_used = self._replace_variables(
                    prompt_content, execute_request.variables
                )

                # 사용 횟수 증가
                db_prompt.usage_count += 1
                db.commit()

            # LLM으로 텍스트 생성
            result = await llm_service.generate_text(
                prompt_used, execute_request.model_id
            )

            execution_time = time.time() - start_time
            token_count = len(result.split()) if result else 0

            self.logger.info(
                f"프롬프트 실행 완료: {execution_time:.2f}초, {token_count} 토큰"
            )

            return PromptExecuteResponse(
                result=result,
                prompt_used=prompt_used,
                model_used=execute_request.model_id,
                execution_time=execution_time,
                token_count=token_count,
            )

        except Exception as e:
            self.logger.error(f"프롬프트 실행 오류: {str(e)}", exc_info=True)
            raise

    def _extract_variables(self, content: str) -> List[str]:
        """프롬프트 내용에서 변수들 추출 ({variable_name} 형식)"""
        variables = re.findall(r"\{(\w+)\}", content)
        return list(set(variables))  # 중복 제거

    def _replace_variables(self, content: str, variables: Dict[str, str]) -> str:
        """프롬프트 내용의 변수들을 실제 값으로 치환"""
        result = content
        for var_name, var_value in variables.items():
            result = result.replace(f"{{{var_name}}}", var_value)
        return result

    def get_categories(self) -> List[Dict[str, str]]:
        """사용 가능한 프롬프트 카테고리 목록 조회"""
        from ..models.prompt import PromptCategory

        return [
            {
                "value": category.value,
                "label": self._get_category_label(category),
            }
            for category in PromptCategory
        ]

    def _get_category_label(self, category) -> str:
        """카테고리 한글 라벨 반환"""
        labels = {
            "rule_generation": "룰 생성",
            "rule_analysis": "룰 분석",
            "code_review": "코드 리뷰",
            "documentation": "문서화",
            "testing": "테스트",
            "debugging": "디버깅",
            "optimization": "최적화",
            "custom": "사용자 정의",
        }
        return labels.get(category.value, category.value)


# 전역 프롬프트 서비스 인스턴스
prompt_service = PromptService()
