import json
import asyncio
from app.models.rule import Rule
from app.services.rule_analyzer import RuleAnalyzer
from app.services.rule_report_service import RuleReportService

async def test_korean_report():
    """한국어 리포트 생성 테스트"""
    # 간단한 테스트 룰 생성
    rule_json = {
        "name": "테스트 룰",
        "description": "테스트용 간단한 룰입니다",
        "priority": 5,
        "enabled": True,
        "conditions": [
            {"field": "age", "operator": "==", "value": 30},
            {"field": "age", "operator": "==", "value": 30},  # 중복 조건
            {"field": "name", "operator": ">", "value": "Kim"},  # 잘못된 연산자
            {"field": "score", "operator": "==", "value": "100"}  # 타입 불일치
        ],
        "action": {"type": "notification", "message": "테스트 알림"}
    }
    
    rule = Rule(**rule_json)
    
    # 룰 분석
    analyzer = RuleAnalyzer()
    result = await analyzer.analyze_rule(rule)
    
    # 리포트 생성
    report_service = RuleReportService()
    report = await report_service.generate_report(rule, result)
    
    # 리포트 출력
    print("\n======= 한국어 리포트 확인 (오류 포함) =======")
    print(report["report"])
    print("\n==================================")

if __name__ == "__main__":
    asyncio.run(test_korean_report()) 