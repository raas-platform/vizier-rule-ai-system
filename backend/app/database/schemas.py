"""
데이터베이스 스키마 정의
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class PromptDB(Base):
    """프롬프트 테이블"""

    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    category = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    variables = Column(Text, default="[]")  # JSON -> Text로 변경 (SQLite 호환)
    tags = Column(Text, default="[]")  # JSON -> Text로 변경 (SQLite 호환)
    is_system_prompt = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self):
        """딕셔너리로 변환"""
        import json

        # JSON 문자열을 파싱
        try:
            variables = json.loads(self.variables) if self.variables else []
        except:
            variables = []

        try:
            tags = json.loads(self.tags) if self.tags else []
        except:
            tags = []

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "content": self.content,
            "variables": variables,
            "tags": tags,
            "is_system_prompt": self.is_system_prompt,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
