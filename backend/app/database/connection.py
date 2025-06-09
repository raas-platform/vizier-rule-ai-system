"""
데이터베이스 연결 설정
"""

import json
import os
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import settings
from ..models.prompt import Prompt
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 데이터베이스 URL 설정
DATABASE_URL = settings.database_url

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    connect_args=({"check_same_thread": False} if "sqlite" in DATABASE_URL else {}),
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base 클래스 (SQLAlchemy 2.0 방식)
class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """
    데이터베이스 세션 의존성
    FastAPI 의존성 주입에 사용
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    데이터베이스 초기화
    테이블 생성 및 초기 데이터 삽입
    """
    from .schemas import Base

    try:
        # 테이블 생성
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 데이터베이스 테이블 생성 완료")

        # 기본 프롬프트 데이터 삽입
        create_default_prompts()
        logger.info("✅ 기본 프롬프트 데이터 초기화 완료")

    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
        raise


def create_default_prompts():
    """기본 프롬프트 템플릿들을 데이터베이스에 삽입"""
    from ..models.prompt import PromptCategory
    from .schemas import PromptDB

    try:
        with Session(engine) as session:
            # 기존 프롬프트 확인
            existing_prompts = session.exec(select(Prompt)).all()

            if not existing_prompts:
                # 기본 프롬프트 템플릿들
                default_prompts = [
                    {
                        "title": "비즈니스 룰 생성",
                        "description": "비즈니스 요구사항을 기반으로 룰을 생성합니다",
                        "category": PromptCategory.RULE_GENERATION.value,
                        "content": """비즈니스 요구사항: {business_requirement}

위 요구사항을 바탕으로 다음 형식의 비즈니스 룰을 생성해주세요:

1. 룰 이름: 명확하고 간결한 룰 이름
2. 조건: 룰이 적용되는 조건들
3. 액션: 조건이 만족될 때 수행할 액션
4. 예외사항: 특별히 고려해야 할 예외사항들

JSON 형식으로 응답해주세요.""",
                        "variables": json.dumps(["business_requirement"]),
                        "tags": json.dumps(["rule", "business", "generation"]),
                        "is_system_prompt": False,
                    },
                    {
                        "title": "룰 분석 및 검증",
                        "description": "기존 룰을 분석하고 잠재적 문제점을 찾습니다",
                        "category": PromptCategory.RULE_ANALYSIS.value,
                        "content": """다음 룰을 분석해주세요:

{rule_content}

분석 항목:
1. 룰의 명확성: 조건과 액션이 명확하게 정의되어 있는가?
2. 완전성: 모든 케이스가 다뤄지고 있는가?
3. 일관성: 다른 룰들과 충돌하지 않는가?
4. 성능: 실행 성능에 문제가 없는가?
5. 개선사항: 어떤 부분을 개선할 수 있는가?

상세한 분석 보고서를 작성해주세요.""",
                        "variables": json.dumps(["rule_content"]),
                        "tags": json.dumps(["rule", "analysis", "validation"]),
                        "is_system_prompt": False,
                    },
                    {
                        "title": "코드 리뷰 어시스턴트",
                        "description": "코드 품질을 검토하고 개선사항을 제안합니다",
                        "category": PromptCategory.CODE_REVIEW.value,
                        "content": """다음 코드를 리뷰해주세요:

```{language}
{code_content}
```

리뷰 관점:
1. 코드 품질: 가독성, 유지보수성
2. 성능: 최적화 가능한 부분
3. 보안: 잠재적 보안 취약점
4. 베스트 프랙티스: 코딩 컨벤션 준수
5. 버그: 잠재적 버그나 에러

구체적인 개선사항과 함께 점수(1-10)를 매겨주세요.""",
                        "variables": json.dumps(["language", "code_content"]),
                        "tags": json.dumps(["code", "review", "quality"]),
                        "is_system_prompt": False,
                    },
                    {
                        "title": "API 문서 생성기",
                        "description": "코드를 분석하여 API 문서를 자동 생성합니다",
                        "category": PromptCategory.DOCUMENTATION.value,
                        "content": """다음 API 코드를 분석하여 문서를 생성해주세요:

{api_code}

생성할 문서 항목:
1. API 개요
2. 엔드포인트 목록
3. 요청/응답 스키마
4. 예제 코드
5. 에러 코드 설명

Markdown 형식으로 작성해주세요.""",
                        "variables": json.dumps(["api_code"]),
                        "tags": json.dumps(["documentation", "api", "markdown"]),
                        "is_system_prompt": False,
                    },
                    {
                        "title": "테스트 케이스 생성기",
                        "description": "함수나 클래스에 대한 테스트 케이스를 생성합니다",
                        "category": PromptCategory.TESTING.value,
                        "content": """다음 {test_framework} 함수/클래스에 대한 테스트 케이스를 생성해주세요:

{code_to_test}

테스트 케이스 요구사항:
1. 정상 케이스 테스트
2. 경계값 테스트
3. 예외 상황 테스트
4. 성능 테스트 (필요시)

완전한 테스트 코드를 작성해주세요.""",
                        "variables": json.dumps(["test_framework", "code_to_test"]),
                        "tags": json.dumps(["testing", "unittest", "automation"]),
                        "is_system_prompt": False,
                    },
                    {
                        "title": "시스템 프롬프트 - 코드 어시스턴트",
                        "description": "코딩 작업을 도와주는 AI 어시스턴트 역할",
                        "category": PromptCategory.CUSTOM.value,
                        "content": """당신은 경험이 풍부한 소프트웨어 개발자입니다. 다음 역할을 수행해주세요:

1. 코드 작성 및 리뷰
2. 디버깅 및 문제 해결
3. 최적화 제안
4. 베스트 프랙티스 가이드
5. 기술 문서 작성

항상 명확하고 실용적인 조언을 제공하며, 코드 예제와 함께 설명해주세요.""",
                        "variables": json.dumps([]),
                        "tags": json.dumps(["system", "assistant", "coding"]),
                        "is_system_prompt": True,
                    },
                ]

                # 데이터베이스에 삽입
                for prompt_data in default_prompts:
                    prompt = PromptDB(**prompt_data)
                    session.add(prompt)

                session.commit()
                logger.info(
                    f"✅ {len(default_prompts)}개의 기본 프롬프트가 생성되었습니다."
                )
            else:
                logger.info("기본 프롬프트가 이미 존재합니다.")
    except Exception as e:
        logger.error(f"❌ 기본 프롬프트 생성 실패: {e}")
        raise
