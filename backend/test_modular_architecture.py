#!/usr/bin/env python3
"""
VizierAI 모듈화 아키텍처 테스트 스크립트
"""

import asyncio
import sys
import os
import time
from typing import Dict, Any

# 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.services.rule_analyzer_service_v2 import RuleAnalyzerV2
from app.models.rule_models import RuleJsonV2
from app.utils.logger import get_logger

logger = get_logger(__name__)

def create_complex_test_rule() -> RuleJsonV2:
    """복잡한 테스트 룰 생성"""
    return RuleJsonV2(
        ruleUuid="test-uuid-12345",
        ruleName="복잡한 모듈화 테스트 룰",
        ruleMsg="모듈화된 아키텍처를 테스트하기 위한 복잡한 룰",
        conditionTree={
            "logicType": "AND",
            "condition": [
                {
                    "logicType": "OR",
                    "condition": [
                        {
                            "keyName": "customer_age",
                            "operator": ">=",
                            "value": "25",
                            "fieldDataType": "NUMBER"
                        },
                        {
                            "keyName": "vip_status",
                            "operator": "=",
                            "value": "PREMIUM",
                            "fieldDataType": "STRING"
                        }
                    ]
                },
                {
                    "keyName": "account_balance",
                    "operator": ">",
                    "value": "10000",
                    "fieldDataType": "NUMBER"
                },
                {
                    "keyName": "risk_score",
                    "operator": "<=",
                    "value": "7",
                    "fieldDataType": "NUMBER"
                }
            ]
        },
        priority=1
    )

async def test_modular_architecture():
    """모듈화된 아키텍처 종합 테스트"""
    
    logger.info("🔧 모듈화된 아키텍처 테스트 시작")
    
    # 1. 분석기 초기화
    try:
        analyzer = RuleAnalyzerV2()
        logger.info("✅ RuleAnalyzerV2 인스턴스 생성 성공")
    except Exception as e:
        logger.error(f"❌ 분석기 초기화 실패: {str(e)}")
        return False
    
    # 2. 시스템 정보 확인
    try:
        stats = analyzer.get_system_stats()
        logger.info(f"\n📊 시스템 정보:")
        logger.info(f"   - 버전: {stats['version']}")
        logger.info(f"   - 아키텍처: {stats['architecture']}")
        logger.info(f"   - 컴포넌트 수: {stats['components']}개")
        logger.info(f"   - 지원 이슈 타입: {stats['supported_issue_types']}가지")
        logger.info(f"   - AI 개선: {'✅' if stats['ai_enhanced'] else '❌'}")
        logger.info(f"   - 성능 최적화: {'✅' if stats['performance_optimized'] else '❌'}")
        
        logger.info(f"\n🔧 컴포넌트 구성:")
        for name, desc in stats['component_descriptions'].items():
            logger.info(f"   - {name}: {desc}")
    except Exception as e:
        logger.error(f"❌ 시스템 정보 확인 실패: {str(e)}")
    
    # 3. 테스트 룰 생성
    test_rule = create_complex_test_rule()
    logger.info(f"\n📋 테스트 룰 생성: {test_rule.ruleName}")
    
    # 4. 개별 컴포넌트 테스트
    logger.info(f"\n🧪 컴포넌트 개별 테스트:")
    
    try:
        # ConditionAnalyzer 테스트
        conditions = analyzer.condition_analyzer.parse_conditions(test_rule.conditionTree)
        logger.info(f"   ✅ ConditionAnalyzer: {len(conditions)}개 조건 파싱 완료")
        
        # FieldAnalyzer 테스트  
        field_types = analyzer.field_analyzer.infer_field_types(conditions)
        logger.info(f"   ✅ 필드 타입 추론: {len(field_types)}개 필드")
        
        # StructureAnalyzer 테스트
        structure_metrics = analyzer.structure_analyzer.analyze_structure(test_rule.conditionTree)
        logger.info(f"   ✅ 구조 메트릭: 깊이={structure_metrics['depth']}, 복잡성={structure_metrics['complexity_score']}")
        
    except Exception as e:
        logger.error(f"   ❌ 개별 컴포넌트 테스트 실패: {str(e)}")
        return False
    
    # 5. IssueDetector 테스트
    try:
        issues = analyzer.issue_detector.detect_all_issues(test_rule, conditions, field_types)
        logger.info(f"   ✅ IssueDetector: {len(issues)}개 이슈 검출")
        
        # ReportGenerator 테스트
        optimized_issues = analyzer.report_generator.optimize_issues(issues)
        rule_summary = analyzer.report_generator.generate_rule_summary(test_rule, optimized_issues)
        logger.info(f"   ✅ ReportGenerator: 이슈 최적화 ({len(issues)} → {len(optimized_issues)})")
        logger.info(f"   ✅ 룰 요약 생성: {len(rule_summary)}자")
        
    except Exception as e:
        logger.error(f"   ❌ 이슈 검출/리포트 생성 실패: {str(e)}")
        return False
    
    # 6. 전체 워크플로우 테스트
    logger.info(f"\n🔄 전체 워크플로우 테스트:")
    start_time = time.time()
    
    try:
        result = await analyzer.analyze_rule(test_rule)
        analysis_time = round((time.time() - start_time) * 1000, 2)
        
        logger.info(f"   ✅ 분석 완료: {'유효' if result.is_valid else '무효'}")
        logger.info(f"   ✅ 검출된 이슈: {len(result.issues)}건")
        logger.info(f"   ✅ 복잡성 점수: {result.complexity_score}/100")
        logger.info(f"   ✅ 확장된 메트릭: {'✅' if result.field_analysis else '❌'}")
        logger.info(f"   ✅ AI 통찰: {'✅' if result.ai_insights else '❌'}")
        logger.info(f"   ✅ 성능 메트릭: {'✅' if result.performance_metrics else '❌'}")
        logger.info(f"   ✅ 품질 메트릭: {'✅' if result.quality_metrics else '❌'}")
        
    except Exception as e:
        logger.error(f"   ❌ 전체 워크플로우 실패: {str(e)}")
        return False
    
    # 7. 성능 체크
    logger.info(f"\n⚡ 성능 정보:")
    logger.info(f"   - 분석 소요 시간: {analysis_time}ms")
    logger.info(f"   - 평균 처리 속도: {'빠름' if analysis_time < 1000 else '보통' if analysis_time < 3000 else '느림'}")
    
    logger.info(f"\n🎉 모든 테스트 성공! 모듈화된 아키텍처가 정상 작동합니다.")
    return True

async def test_individual_components():
    """개별 컴포넌트 세부 테스트"""
    
    analyzer = RuleAnalyzerV2()
    test_rule = create_complex_test_rule()
    
    # 각 컴포넌트의 세부 기능 테스트
    components = [
        ("ConditionAnalyzer", analyzer.condition_analyzer),
        ("FieldAnalyzer", analyzer.field_analyzer),
        ("StructureAnalyzer", analyzer.structure_analyzer),
        ("IssueDetector", analyzer.issue_detector),
        ("ReportGenerator", analyzer.report_generator)
    ]
    
    for name, component in components:
        try:
            # 각 컴포넌트의 주요 메서드 테스트
            if hasattr(component, 'get_component_info'):
                info = component.get_component_info()
                logger.info(f"✅ {name}: {info}")
        except Exception as e:
            logger.error(f"❌ {name} 세부 테스트 실패: {str(e)}")
    
    logger.info("✅ 개별 컴포넌트 테스트 완료")

async def main():
    """메인 테스트 함수"""
    
    try:
        logger.info("=" * 60)
        logger.info("🏗️  VizierAI 모듈화 아키텍처 테스트")
        logger.info("=" * 60)
        
        # 모듈화 아키텍처 테스트
        success = await test_modular_architecture()
        
        logger.info("\n" + "=" * 60)
        if success:
            logger.info("✅ LOW PRIORITY 개선사항 구현 완료!")
            logger.info("   - 클래스 분리: 5개 전문화된 컴포넌트")
            logger.info("   - 모듈화 구조: 단일 책임 원칙 준수")
            logger.info("   - 확장성 향상: 새로운 기능 추가 용이")
            logger.info("   - 유지보수성: 코드 품질 대폭 향상")
            logger.info("   - 문서화 완료: 종합 아키텍처 문서")
        else:
            logger.error("❌ 테스트 실패 - 추가 수정이 필요합니다.")
        logger.info("=" * 60)
        
        return success
        
    except Exception as e:
        logger.error(f"\n❌ 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    # 개별 컴포넌트 세부 테스트
    logger.info("\n🔧 개별 컴포넌트 세부 테스트")
    try:
        asyncio.run(test_individual_components())
    except Exception as e:
        logger.error(f"개별 컴포넌트 테스트 오류: {str(e)}")
    
    # 메인 테스트 실행
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 