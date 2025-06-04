from fastapi import APIRouter
from app.api.rule_validator import router as rule_validator_router
from app.api.rule_report import router as rule_report_router

api_router = APIRouter(prefix="/api/v1/rules")
api_router.include_router(rule_validator_router, tags=["rule-validator"])
api_router.include_router(rule_report_router, tags=["rule-report"])
