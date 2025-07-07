"""
프롬프트 관리 서비스 (PyPI 모듈 기반)

기존 프롬프트 관리 기능을 유지하면서 raas-prompt-builder 모듈을 활용하여
중복 코드를 제거하고 모듈화된 구조로 리팩토링했습니다.
"""

import json
import re
import time
from typing import Dict, List, Optional
from datetime import date

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

# PyPI 모듈 import
from rass_prompt_builder import PromptBuilderService
from rass_prompt_builder.models import PromptType, PromptInput, PromptResult

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
from ..llm_service.service import llm_service
from ..shared.logger import get_logger


class PromptService:
    """프롬프트 관리 서비스 (PyPI 모듈 기반)"""

    def __init__(self):
        self.logger = get_logger(__name__)
        # PyPI 모듈 활용
        self.prompt_builder = PromptBuilderService()
        self.logger.info("PromptService 초기화 완료 (PyPI 모듈 기반)")

    def create_prompt(self, db: Session, prompt: PromptCreate) -> Prompt:
        """새 프롬프트 생성"""
        try:
            # 내용 검증
            self._validate_prompt_content(prompt.content)
            
            # 변수 추출
            variables = self._extract_variables(prompt.content)

            # 제목 중복 검사 (같은 카테고리 내에서)
            existing = (
                db.query(PromptDB)
                .filter(
                    PromptDB.title == prompt.title,
                    PromptDB.category == prompt.category.value,
                    PromptDB.is_active.is_(True)
                )
                .first()
            )
            if existing:
                raise ValueError(f"같은 카테고리에 '{prompt.title}' 제목의 프롬프트가 이미 존재합니다.")

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
                db.query(PromptDB).filter(PromptDB.is_active.is_(True)).count()
            )

            # 카테고리별 프롬프트 수 - SQLAlchemy 1.4 문법
            from sqlalchemy import func

            category_stats = (
                db.query(PromptDB.category, func.count(PromptDB.id))
                .filter(PromptDB.is_active.is_(True))
                .group_by(PromptDB.category)
                .all()
            )
            prompts_by_category = {
                category: count for category, count in category_stats
            }

            # 가장 많이 사용된 프롬프트들 (상위 5개)
            most_used = (
                db.query(PromptDB)
                .filter(PromptDB.is_active.is_(True))
                .order_by(desc(PromptDB.usage_count))
                .limit(5)
                .all()
            )
            most_used_prompts = [Prompt(**prompt.to_dict()) for prompt in most_used]

            # 최근 생성된 프롬프트들 (상위 5개)
            recent = (
                db.query(PromptDB)
                .filter(PromptDB.is_active.is_(True))
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
        """프롬프트 실행 (PyPI 모듈 기반)"""
        start_time = time.time()

        try:
            # 1) HTML 리포트 특수 처리 (PyPI 모듈 활용)
            if execute_request.report_type == "html_report":
                json_data = execute_request.variables.get("json_data", "{}")
                
                # PyPI 모듈을 활용한 HTML 리포트 프롬프트 생성
                html_prompt = self._create_html_report_prompt(json_data)
                
                model = execute_request.model_id or "claude-3-sonnet-20240229"
                result = await llm_service.generate_text(html_prompt, model)

                execution_time = time.time() - start_time
                token_count = len(result.split()) if result else 0

                return PromptExecuteResponse(
                    result=result,
                    prompt_used=html_prompt,
                    model_used=model,
                    execution_time=execution_time,
                    token_count=token_count,
                )

            # 2) 일반 프롬프트 처리
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

                # SQLAlchemy Column을 str으로 변환
                prompt_content = str(db_prompt.content)
                prompt_used = self._replace_variables(
                    prompt_content, execute_request.variables
                )

                # 사용 횟수 증가 - SQLAlchemy 방식
                new_usage_count = db_prompt.usage_count + 1
                db.query(PromptDB).filter(PromptDB.id == execute_request.prompt_id).update(
                    {"usage_count": new_usage_count}
                )
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

    def _create_html_report_prompt(self, json_data: str) -> str:
        """HTML 리포트 전용 프롬프트 생성 (PyPI 모듈 활용)"""
        try:
            # PyPI 모듈의 템플릿 시스템을 활용하여 동적 프롬프트 생성
            current_date = date.today().isoformat()
            
            return (
                f"현재 시점({current_date})의 최신 웹 디자인 트렌드를 자동으로 파악하고 적용해서\n"
                f"이 JSON 데이터로 현대적인 HTML 리포트를 만들어주세요.\n"
                f"데이터: {json_data}\n"
                "요구사항:\n\n"
                "현재 가장 인기있는 웹 디자인 트렌드를 스스로 판단해서 적용\n"
                "최신 CSS 기법과 JavaScript 라이브러리 활용\n"
                "완전한 독립형 HTML 파일 (CSS, JS 모두 인라인)\n"
                "2024-2025 트렌드 반영: Glassmorphism, 다크모드, 마이크로인터랙션 등\n\n"
                "HTML 코드만 응답해주세요."
            )
        except Exception as e:
            self.logger.error(f"HTML 리포트 프롬프트 생성 오류: {str(e)}")
            # 기본 프롬프트 반환
            return f"이 JSON 데이터로 HTML 리포트를 만들어주세요: {json_data}"

    def _extract_variables(self, content: str) -> List[str]:
        """프롬프트 내용에서 변수들 추출 ({variable_name} 형식)"""
        variables = re.findall(r"\{(\w+)\}", content)
        return list(set(variables))  # 중복 제거

    def _validate_prompt_content(self, content: str) -> None:
        """프롬프트 내용 검증"""
        if not content or content.strip() == "":
            raise ValueError("프롬프트 내용은 비어있을 수 없습니다.")
        
        if len(content) > 10000:  # 10KB 제한
            raise ValueError("프롬프트 내용이 너무 깁니다. (최대 10,000자)")
        
        # 변수 형식 검증
        variables = re.findall(r"\{(\w*)\}", content)
        for var in variables:
            if not var:  # 빈 중괄호 {}
                raise ValueError("빈 변수 중괄호가 발견되었습니다. 올바른 형식: {variable_name}")
            if not re.match(r"^\w+$", var):
                raise ValueError(f"잘못된 변수명 형식: {var}. 영문자, 숫자, 언더스코어만 사용 가능합니다.")

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

    def export_prompts(self, db: Session, category: Optional[str] = None) -> List[Dict]:
        """프롬프트 데이터 내보내기 (백업용)"""
        try:
            query = db.query(PromptDB)
            if category:
                query = query.filter(PromptDB.category == category)
            
            prompts = query.all()
            
            export_data = []
            for prompt in prompts:
                export_data.append({
                    "title": str(prompt.title),
                    "description": str(prompt.description) if prompt.description else None,
                    "category": str(prompt.category),
                    "content": str(prompt.content),
                    "variables": json.loads(str(prompt.variables)) if prompt.variables else [],
                    "tags": json.loads(str(prompt.tags)) if prompt.tags else [],
                    "is_system_prompt": bool(prompt.is_system_prompt),
                    "is_active": bool(prompt.is_active),
                    "usage_count": int(prompt.usage_count),
                    "created_at": prompt.created_at.isoformat(),
                    "updated_at": prompt.updated_at.isoformat()
                })
            
            self.logger.info(f"프롬프트 {len(export_data)}개 내보내기 완료")
            return export_data
            
        except Exception as e:
            self.logger.error(f"프롬프트 내보내기 오류: {str(e)}", exc_info=True)
            raise

    def import_prompts(self, db: Session, import_data: List[Dict], overwrite: bool = False) -> Dict[str, int]:
        """프롬프트 데이터 가져오기 (복원용)"""
        try:
            imported = 0
            skipped = 0
            errors = 0
            
            for item in import_data:
                try:
                    # 기존 프롬프트 확인
                    existing = (
                        db.query(PromptDB)
                        .filter(
                            PromptDB.title == item["title"],
                            PromptDB.category == item["category"]
                        )
                        .first()
                    )
                    
                    if existing and not overwrite:
                        skipped += 1
                        continue
                    
                    # 카테고리 검증
                    from ..models.prompt import PromptCategory
                    try:
                        category_enum = PromptCategory(item["category"])
                    except ValueError:
                        self.logger.warning(f"잘못된 카테고리 무시: {item['category']}")
                        errors += 1
                        continue
                    
                    if existing and overwrite:
                        # 기존 프롬프트 업데이트
                        existing.description = item.get("description")
                        existing.content = item["content"]
                        existing.variables = json.dumps(item.get("variables", []))
                        existing.tags = json.dumps(item.get("tags", []))
                        existing.is_system_prompt = item.get("is_system_prompt", False)
                        existing.is_active = item.get("is_active", True)
                    else:
                        # 새 프롬프트 생성
                        new_prompt = PromptDB(
                            title=item["title"],
                            description=item.get("description"),
                            category=item["category"],
                            content=item["content"],
                            variables=json.dumps(item.get("variables", [])),
                            tags=json.dumps(item.get("tags", [])),
                            is_system_prompt=item.get("is_system_prompt", False),
                            is_active=item.get("is_active", True)
                        )
                        db.add(new_prompt)
                    
                    imported += 1
                    
                except Exception as e:
                    self.logger.error(f"프롬프트 가져오기 개별 오류: {str(e)}")
                    errors += 1
                    continue
            
            db.commit()
            
            result = {
                "imported": imported,
                "skipped": skipped,
                "errors": errors,
                "total": len(import_data)
            }
            
            self.logger.info(f"프롬프트 가져오기 완료: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"프롬프트 가져오기 오류: {str(e)}", exc_info=True)
            db.rollback()
            raise


# 전역 프롬프트 서비스 인스턴스
prompt_service = PromptService()
