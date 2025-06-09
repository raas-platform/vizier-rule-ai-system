#!/usr/bin/env python3
import asyncio
import json
import os
import sys

# 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.models.rule_models import RuleJsonV2
from app.models.rule_parser import RuleParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


def test_new_format():
    """새로운 JSON 형식 테스트"""
    # 테스트 JSON 파일 로드
    try:
        with open("test_all_errors_combined.json", "r", encoding="utf-8") as f:
            test_json = json.load(f)

        logger.info("✅ 테스트 JSON 파일 로드 성공")
        logger.info(f"📄 JSON 타입: {type(test_json)}")

        if isinstance(test_json, list):
            logger.info(f"📊 배열 크기: {len(test_json)}")
            first_item = test_json[0]
            logger.info(f"🔍 첫 번째 아이템 키: {list(first_item.keys())}")

    except Exception as e:
        logger.error(f"❌ JSON 파일 로드 실패: {str(e)}")
        return False

    # RuleParser 테스트
    try:
        parser = RuleParser()
        logger.info("✅ RuleParser 인스턴스 생성 성공")

        # 새로운 형식 파싱
        rule = parser.parse_rule_json_v2(test_json)
        logger.info("✅ 룰 파싱 성공!")

        # 룰 정보 출력
        if hasattr(rule, "ruleUuid"):
            logger.info(f"🏷️  룰 UUID: {rule.ruleUuid}")
        logger.info(f"📝 룰 이름: {rule.ruleName}")
        logger.info(f"💬 룰 메시지: {rule.ruleMsg}")
        logger.info(f"🌲 조건 트리 타입: {rule.conditionTree.logicType}")
        logger.info(f"📊 조건 개수: {len(rule.conditionTree.condition)}")

        # 조건 상세 정보
        for i, condition in enumerate(rule.conditionTree.condition):
            if hasattr(condition, "logicType"):
                logger.info(
                    f"  조건 {i+1}: {condition.logicType} 그룹 ({len(condition.condition)}개 하위 조건)"
                )
            else:
                logger.info(
                    f"  조건 {i+1}: {condition.keyName} {condition.operator} {condition.value} ({condition.fieldDataType})"
                )

        return True

    except Exception as e:
        logger.error(f"❌ 룰 파싱 실패: {str(e)}")
        return False


def test_legacy_format():
    """기존 형식 호환성 테스트"""
    # 기존 형식 데이터 (예시)
    legacy_data = {
        "id": "TEST_001",
        "name": "레거시 테스트 룰",
        "description": "기존 형식 호환성 테스트",
        "conditions": [{"field": "age", "operator": ">=", "value": 20}],
        "actions": [{"type": "approve", "message": "승인"}],
        "priority": 1,
        "enabled": True,
    }

    try:
        parser = RuleParser()
        # 기존 형식으로 파싱 시도
        rule = parser.parse_legacy_format(legacy_data)

        logger.info("✅ 기존 형식 파싱 성공!")
        logger.info(f"🏷️  룰 ID: {rule.id}")
        logger.info(f"📝 룰 이름: {rule.name}")
        logger.info(f"📊 조건 개수: {len(rule.conditions) if rule.conditions else 0}")

        return True

    except Exception as e:
        logger.error(f"❌ 기존 형식 파싱 실패: {str(e)}")
        return False


def main():
    """메인 테스트 함수"""
    logger.info("🚀 새로운 JSON 형식 룰 파서 테스트 시작\n")

    logger.info("=" * 50)
    logger.info("1. 새로운 형식 테스트")
    logger.info("=" * 50)
    new_test_result = test_new_format()

    logger.info("\n" + "=" * 50)
    logger.info("2. 기존 형식 호환성 테스트")
    logger.info("=" * 50)
    legacy_test_result = test_legacy_format()

    logger.info("\n" + "=" * 50)
    logger.info("테스트 결과 요약")
    logger.info("=" * 50)
    logger.info(f"새로운 형식: {'✅ 성공' if new_test_result else '❌ 실패'}")
    logger.info(f"기존 형식: {'✅ 성공' if legacy_test_result else '❌ 실패'}")

    if new_test_result and legacy_test_result:
        logger.info("\n🎉 모든 테스트 통과!")
        return True
    else:
        logger.warning("\n💥 일부 테스트 실패")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
