#!/usr/bin/env python3
"""
간단한 디버깅용 테스트
"""

import asyncio
import os
import sys

# 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.models.rule import Rule, RuleCondition
from app.models.rule_models import RuleJsonV2
from app.services.rule_analyzer_service_v2 import RuleAnalyzerV2 as NewRuleAnalyzerV2
from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.utils.logger import get_logger

logger = get_logger(__name__)

# RuleAnalyzer 인스턴스 생성
analyzer = RuleAnalyzerV2()


async def test_duplicate_conditions():
    analyzer = RuleAnalyzerV2()

    conditions = [
        RuleCondition(keyName="age", operator=">=", value=18, fieldDataType="number"),
        RuleCondition(keyName="age", operator=">=", value=18, fieldDataType="number"),
    ]

    rule = Rule(
        ruleName="중복 조건 테스트",
        ruleMsg="중복 조건이 있는 테스트 룰",
        conditions=conditions,
    )

    result = await analyzer.analyze_rule(rule)

    logger.info(f"is_valid: {result.is_valid}")
    logger.info(f"summary: {result.summary}")
    logger.info(f"issues count: {len(result.issues)}")
    logger.info(f"issue_counts: {result.issue_counts}")

    if result.issues:
        for issue in result.issues:
            logger.info(
                f"- Issue: {issue.issue_type} | {issue.field} | {issue.explanation}"
            )

    return result


async def test_simple_rule():
    """간단한 룰로 분석기 테스트"""

    # 테스트용 룰 생성
    test_rule = RuleJsonV2(
        ruleName="간단한 테스트 룰",
        ruleMsg="테스트를 위한 간단한 룰입니다",
        conditionTree={
            "logicType": "AND",
            "condition": [
                {
                    "keyName": "age",
                    "operator": ">=",
                    "value": "20",
                    "fieldDataType": "NUMBER",
                },
                {
                    "keyName": "status",
                    "operator": "=",
                    "value": "ACTIVE",
                    "fieldDataType": "STRING",
                },
            ],
        },
        priority=1,
    )

    # 분석기 생성 및 실행
    analyzer = NewRuleAnalyzerV2()
    result = await analyzer.analyze_rule(test_rule)

    # 결과 출력
    logger.info(f"is_valid: {result.is_valid}")
    logger.info(f"summary: {result.summary}")
    logger.info(f"issues count: {len(result.issues)}")
    logger.info(f"issue_counts: {result.issue_counts}")

    if result.issues:
        for issue in result.issues:
            logger.info(
                f"- Issue: {issue.issue_type} | {issue.field} | {issue.explanation}"
            )


if __name__ == "__main__":
    asyncio.run(test_simple_rule())
