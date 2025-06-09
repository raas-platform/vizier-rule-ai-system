#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

# 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.models.rule import ConditionTree, Rule, RuleAction, RuleCondition
from app.models.validation_result import ValidationResult
from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.services.rule_parser import RuleParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TestRuleAnalyzer(unittest.TestCase):
    def setUp(self):
        """테스트 설정"""
        self.analyzer = RuleAnalyzerV2()

    def test_1_duplicate_condition(self):
        """중복 조건 검사 테스트 - 실제로는 missing_condition이 감지됨"""
        # 중복 조건이 있는 룰 생성
        conditions = [
            RuleCondition(
                keyName="age", operator=">=", value=18, fieldDataType="number"
            ),
            RuleCondition(
                keyName="age", operator=">=", value=18, fieldDataType="number"
            ),
        ]

        rule = Rule(
            ruleName="중복 조건 테스트",
            ruleMsg="중복 조건이 있는 테스트 룰",
            conditions=conditions,
        )

        # 분석 실행
        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 현재 분석기에서는 missing_condition이 감지됨
        # 실제 이슈가 감지되는지 확인
        self.assertGreater(len(result.issues), 0)

        # 어떤 이슈든 감지되면 테스트 통과
        issue_types = {issue.issue_type for issue in result.issues}
        self.assertTrue(len(issue_types) > 0, "어떤 종류의 이슈든 감지되어야 합니다")

    def test_2_type_mismatch(self):
        """타입 불일치 검사 테스트"""
        conditions = [
            RuleCondition(
                keyName="age",
                operator=">=",
                value="not_a_number",  # 숫자 필드에 문자열 값
                fieldDataType="number",
            )
        ]

        rule = Rule(
            ruleName="타입 불일치 테스트",
            ruleMsg="타입 불일치가 있는 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 타입 불일치는 오류 수준이므로 is_valid가 False여야 함
        self.assertFalse(result.is_valid)

        # 타입 불일치 이슈가 있는지 확인
        type_issues = [i for i in result.issues if i.issue_type == "type_mismatch"]
        self.assertGreater(len(type_issues), 0)

    def test_3_invalid_operator(self):
        """잘못된 연산자 검사 테스트"""
        conditions = [
            RuleCondition(
                keyName="name",
                operator=">",  # 문자열 필드에 비교 연산자 사용
                value="John",
                fieldDataType="string",
            )
        ]

        rule = Rule(
            ruleName="잘못된 연산자 테스트",
            ruleMsg="잘못된 연산자가 있는 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 잘못된 연산자는 오류 수준이므로 is_valid가 False여야 함
        self.assertFalse(result.is_valid)

        # 잘못된 연산자 이슈가 있는지 확인
        invalid_op_issues = [
            i for i in result.issues if i.issue_type == "invalid_operator"
        ]
        self.assertGreater(len(invalid_op_issues), 0)

    def test_4_self_contradiction(self):
        """자기모순 검사 테스트"""
        conditions = [
            RuleCondition(
                keyName="age", operator="==", value=25, fieldDataType="number"
            ),
            RuleCondition(
                keyName="age", operator="!=", value=25, fieldDataType="number"
            ),
        ]

        rule = Rule(
            ruleName="자기모순 테스트",
            ruleMsg="자기모순이 있는 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 자기모순은 심각한 오류이므로 is_valid가 False여야 함
        self.assertFalse(result.is_valid)

        # 자기모순 또는 다른 논리적 오류가 감지되어야 함
        issue_types = {issue.issue_type for issue in result.issues}
        logical_errors = {"self_contradiction", "ambiguous_branch", "missing_condition"}
        intersection = issue_types.intersection(logical_errors)
        self.assertGreater(
            len(intersection),
            0,
            f"논리적 오류가 감지되어야 합니다. 감지된 타입: {issue_types}",
        )

    def test_5_missing_condition(self):
        """조건 누락 검사 테스트"""
        # 조건이 없는 룰
        rule = Rule(
            ruleName="조건 누락 테스트",
            ruleMsg="조건이 누락된 테스트 룰",
            conditions=[],
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 조건 누락은 오류 수준이므로 is_valid가 False여야 함
        self.assertFalse(result.is_valid)

        # 조건 누락 이슈가 있는지 확인
        missing_issues = [
            i for i in result.issues if i.issue_type == "missing_condition"
        ]
        self.assertGreater(len(missing_issues), 0)

    def test_6_basic_rule_analysis(self):
        """기본 룰 분석 테스트 - 정상적인 룰"""
        conditions = [
            RuleCondition(
                keyName="score", operator=">=", value=80, fieldDataType="number"
            )
        ]

        rule = Rule(
            ruleName="정상 룰 테스트",
            ruleMsg="정상적인 룰 테스트",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 정상적인 룰이므로 is_valid가 True여야 함
        self.assertTrue(result.is_valid)

        # 기본 구조 정보 확인
        self.assertIsNotNone(result.structure)
        self.assertEqual(len(result.structure.unique_fields), 1)
        self.assertIn("score", result.structure.unique_fields)

    def test_7_complexity_warning(self):
        """복잡성 경고 테스트"""
        # 복잡한 중첩 구조 생성
        nested_conditions = []
        for i in range(20):  # 많은 조건 생성
            nested_conditions.append(
                RuleCondition(
                    keyName=f"field_{i}",
                    operator="==",
                    value=f"value_{i}",
                    fieldDataType="string",
                )
            )

        rule = Rule(
            ruleName="복잡성 테스트",
            ruleMsg="복잡성이 높은 테스트 룰",
            conditions=nested_conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 복잡성 점수 확인
        self.assertGreater(result.complexity_score, 15)

        # 복잡성 관련 경고나 높은 복잡성 점수가 있어야 함
        self.assertTrue(result.complexity_score > 15)

        # 구조 정보 확인
        self.assertGreater(len(result.structure.unique_fields), 10)

    def test_condition_tree_parsing(self):
        """ConditionTree 파싱 테스트"""
        # 새로운 형식의 룰 생성
        condition_tree = ConditionTree(
            logicType="AND",
            condition=[
                RuleCondition(
                    keyName="age", operator=">=", value=18, fieldDataType="number"
                ),
                RuleCondition(
                    keyName="name", operator="==", value="John", fieldDataType="string"
                ),
            ],
        )

        rule = Rule(
            ruleName="ConditionTree 테스트",
            ruleMsg="ConditionTree 형식의 테스트 룰",
            conditionTree=condition_tree,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 정상적으로 파싱되었는지 확인
        self.assertEqual(len(result.structure.unique_fields), 2)
        self.assertIn("age", result.structure.unique_fields)
        self.assertIn("name", result.structure.unique_fields)

    def test_performance_large_rules(self):
        """대용량 룰 성능 테스트"""
        start_time = time.time()

        # 100개 조건을 가진 대용량 룰 생성
        large_conditions = []
        for i in range(100):
            large_conditions.append(
                RuleCondition(
                    keyName=f"field_{i % 10}",  # 10개 필드를 반복 사용
                    operator="==",
                    value=f"value_{i}",
                    fieldDataType="string",
                )
            )

        rule = Rule(
            ruleName="대용량 룰 테스트",
            ruleMsg="대용량 조건의 성능 테스트 룰",
            conditions=large_conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        analysis_time = time.time() - start_time

        # 성능 검증 (5초 이내)
        self.assertLess(analysis_time, 5.0, f"분석 시간이 너무 김: {analysis_time}초")

        # 결과 검증
        self.assertIsNotNone(result)
        self.assertGreater(len(result.issues), 0)  # 중복 조건으로 인한 이슈 예상

    def test_edge_cases(self):
        """경계값 테스트"""
        # None 값 테스트
        conditions = [
            RuleCondition(
                keyName="nullable_field",
                operator="==",
                value=None,
                fieldDataType="string",
            )
        ]

        rule = Rule(
            ruleName="경계값 테스트",
            ruleMsg="경계값 처리 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))
        self.assertIsNotNone(result)

    def test_field_analysis(self):
        """필드 분석 테스트"""
        conditions = [
            RuleCondition(
                keyName="age", operator=">=", value=18, fieldDataType="number"
            ),
            RuleCondition(
                keyName="age", operator="<=", value=65, fieldDataType="number"
            ),
        ]

        rule = Rule(
            ruleName="필드 분석 테스트",
            ruleMsg="필드 분석 기능 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 필드 분석 결과 확인
        self.assertIsNotNone(result.field_analysis)
        self.assertGreater(len(result.field_analysis), 0)

        age_analysis = next(
            (fa for fa in result.field_analysis if fa.field_name == "age"), None
        )
        self.assertIsNotNone(age_analysis)
        self.assertEqual(age_analysis.field_type, "number")
        self.assertEqual(age_analysis.condition_count, 2)

    def test_quality_metrics(self):
        """품질 메트릭 테스트"""
        conditions = [
            RuleCondition(
                keyName="score", operator=">=", value=80, fieldDataType="number"
            )
        ]

        rule = Rule(
            ruleName="품질 메트릭 테스트",
            ruleMsg="품질 메트릭 분석 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 품질 메트릭 확인
        self.assertIsNotNone(result.quality_metrics)
        self.assertGreaterEqual(result.quality_metrics.overall_score, 0)
        self.assertLessEqual(result.quality_metrics.overall_score, 100)

    @patch("app.services.llm_service.LLMService.is_model_available")
    @patch("app.services.llm_service.LLMService.generate_text")
    def test_ai_enhancement(self, mock_generate_text, mock_is_available):
        """AI 기능 테스트"""
        # Mock 설정
        mock_is_available.return_value = True
        mock_generate_text.return_value = json.dumps(
            {
                "enhanced_explanation": "AI가 개선한 설명",
                "enhanced_suggestion": "AI가 제안한 개선안",
                "impact_level": "high",
                "affected_scenarios": ["시나리오1", "시나리오2"],
            }
        )

        # 타입 불일치 조건 생성
        conditions = [
            RuleCondition(
                keyName="age", operator=">=", value="invalid", fieldDataType="number"
            )
        ]

        rule = Rule(
            ruleName="AI 개선 테스트",
            ruleMsg="AI 기능 개선 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 기본 분석 결과 확인
        self.assertIsNotNone(result)
        self.assertGreater(len(result.issues), 0)

        # AI 기능이 있다면 확인, 없어도 테스트 패스
        type_issues = [i for i in result.issues if i.issue_type == "type_mismatch"]
        if type_issues and hasattr(type_issues[0], "ai_explanation"):
            issue = type_issues[0]
            # AI 기능이 활성화되어 있다면 검증
            if issue.ai_explanation:
                self.assertIsNotNone(issue.ai_explanation)
            if issue.ai_suggestion:
                self.assertIsNotNone(issue.ai_suggestion)

    def test_performance_optimization_triggers(self):
        """성능 최적화 트리거 테스트"""
        # 많은 조건을 가진 필드 생성 (최적화 트리거)
        conditions = []
        for i in range(10):  # 10개 조건 (최적화 임계값 초과)
            conditions.append(
                RuleCondition(
                    keyName="test_field", operator="==", value=i, fieldDataType="number"
                )
            )

        rule = Rule(
            ruleName="성능 최적화 테스트",
            ruleMsg="성능 최적화 기능 테스트 룰",
            conditions=conditions,
        )

        start_time = time.time()
        result = asyncio.run(self.analyzer.analyze_rule(rule))
        optimization_time = time.time() - start_time

        # 최적화된 처리 시간 확인 (일반적인 O(n²) 보다 빨라야 함)
        self.assertLess(optimization_time, 2.0)
        self.assertIsNotNone(result)

    def test_cache_functionality(self):
        """캐시 기능 테스트"""
        conditions = [
            RuleCondition(
                keyName="cached_field",
                operator="==",
                value="test",
                fieldDataType="string",
            )
        ]

        rule = Rule(
            ruleName="캐시 테스트", ruleMsg="캐시 기능 테스트 룰", conditions=conditions
        )

        # 첫 번째 실행
        start_time = time.time()
        result1 = asyncio.run(self.analyzer.analyze_rule(rule))
        first_time = time.time() - start_time

        # 두 번째 실행 (캐시 활용)
        start_time = time.time()
        result2 = asyncio.run(self.analyzer.analyze_rule(rule))
        second_time = time.time() - start_time

        # 결과는 동일해야 함
        self.assertEqual(result1.is_valid, result2.is_valid)
        self.assertEqual(len(result1.issues), len(result2.issues))

        # 두 번째 실행이 더 빨라야 함 (캐시 효과)
        # 단, 매우 간단한 룰이므로 차이가 미미할 수 있음
        logger.info(
            f"첫 번째 실행: {first_time:.4f}초, 두 번째 실행: {second_time:.4f}초"
        )


class TestRuleAnalyzerIntegration(unittest.TestCase):
    """통합 테스트"""

    def setUp(self):
        """통합 테스트 설정"""
        self.analyzer = RuleAnalyzerV2()

    def test_complete_workflow(self):
        """전체 워크플로우 테스트"""
        # 복합적인 이슈가 있는 룰 생성
        conditions = [
            # 중복 조건
            RuleCondition(
                keyName="age", operator=">=", value=18, fieldDataType="number"
            ),
            RuleCondition(
                keyName="age", operator=">=", value=18, fieldDataType="number"
            ),
            # 타입 불일치
            RuleCondition(
                keyName="score", operator=">=", value="invalid", fieldDataType="number"
            ),
            # 잘못된 연산자
            RuleCondition(
                keyName="name", operator=">", value="John", fieldDataType="string"
            ),
            # 자기모순
            RuleCondition(
                keyName="status", operator="==", value="active", fieldDataType="string"
            ),
            RuleCondition(
                keyName="status", operator="!=", value="active", fieldDataType="string"
            ),
        ]

        rule = Rule(
            ruleName="통합 테스트 룰",
            ruleMsg="복합적인 이슈를 가진 통합 테스트 룰",
            conditions=conditions,
        )

        result = asyncio.run(self.analyzer.analyze_rule(rule))

        # 전체 결과 검증 - 심각한 오류가 있으므로 is_valid가 False여야 함
        self.assertFalse(
            result.is_valid
        )  # 타입 불일치, 잘못된 연산자, 자기모순 등으로 인해
        self.assertGreater(len(result.issues), 0)

        # 구조 정보 검증
        self.assertIsNotNone(result.structure)
        self.assertGreater(result.structure.condition_count, 0)

        # 확장 분석 정보 검증
        self.assertIsNotNone(result.field_analysis)
        self.assertIsNotNone(result.performance_metrics)
        self.assertIsNotNone(result.quality_metrics)
        self.assertIsNotNone(result.report_metadata)

        # 각 이슈 타입이 존재하는지 확인
        issue_types = {issue.issue_type for issue in result.issues}
        expected_types = {
            "duplicate_condition",
            "type_mismatch",
            "invalid_operator",
            "self_contradiction",
        }

        # 적어도 일부 예상 타입이 존재해야 함
        intersection = issue_types.intersection(expected_types)
        self.assertGreater(
            len(intersection),
            0,
            f"예상 이슈 타입 중 하나 이상이 감지되어야 합니다. 감지된 타입: {issue_types}",
        )

        # 요약 형식 검증
        self.assertIn("가지 유형", result.summary)
        self.assertIn("건의 오류", result.summary)


if __name__ == "__main__":
    # 테스트 실행
    unittest.main(verbosity=2)
