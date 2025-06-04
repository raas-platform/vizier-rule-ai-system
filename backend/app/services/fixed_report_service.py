from typing import Dict, Any, List
import json
from app.services.llm_service import LLMService
from app.models.validation_result import ValidationResult, ConditionIssue
from app.models.rule import Rule

class RuleReportService:
    """Service for generating rule analysis reports"""

    def __init__(self):
        """Initialize rule report service with LLM service"""
        self.llm_service = LLMService()

    async def generate_report(self, rule: Rule, validation_result: ValidationResult) -> Dict[str, Any]:
        """룰에 대한 상세 리포트 생성"""
        try:
            # LLM을 사용한 리포트 생성
            rule_json = rule.model_dump()
            prompt = self._create_report_prompt(rule_json, validation_result)
            system_message = self._get_system_message()
            
            report = await self.llm_service.call_llm(prompt, system_message)
            
            return {
                "report": report,
                "rule_id": rule.id or "N/A",
                "rule_name": rule.name
            }
        except Exception as e:
            # LLM 서비스 호출 실패 시 대체 리포트 생성
            return self._generate_fallback_report(rule, validation_result)

