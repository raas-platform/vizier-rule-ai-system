#!/usr/bin/env python3
"""
8개의 테스트 JSON 파일을 모두 테스트하는 스크립트
"""

import sys
import json
import asyncio
import os
from pathlib import Path

sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule

async def test_json_file(file_path: str, analyzer: RuleAnalyzerV2):
    """개별 JSON 파일 테스트"""
    print(f"\n{'='*60}")
    print(f"테스트 파일: {file_path}")
    print(f"{'='*60}")
    
    try:
        # JSON 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
        
        # 여러 룰이 있는 경우 첫 번째 룰만 테스트
        if isinstance(rules_data, list):
            rule_data = rules_data[0]
        else:
            rule_data = rules_data
        
        print(f"룰 이름: {rule_data.get('ruleName', 'N/A')}")
        print(f"룰 메시지: {rule_data.get('ruleMsg', 'N/A')}")
        
        # Pydantic 모델로 변환
        test_rule = Rule(**rule_data)
        
        # 조건 파싱
        conditions = analyzer.condition_analyzer.parse_rule_conditions(test_rule)
        print(f"\n파싱된 조건 수: {len(conditions)}")
        
        # 구조 메트릭 계산
        structure_metrics = analyzer.condition_analyzer.calculate_structure_metrics(conditions)
        print(f"구조 메트릭:")
        print(f"  - 깊이: {structure_metrics['depth']}")
        print(f"  - 조건 수: {structure_metrics['condition_count']}")
        print(f"  - 필드 조건 수: {structure_metrics['field_condition_count']}")
        print(f"  - 고유 필드: {structure_metrics['unique_fields']}")
        print(f"  - 복잡성 점수: {structure_metrics['complexity_score']}")
        
        # 이슈 검출
        issues = await analyzer.issue_detector.detect_all_issues(
            test_rule, conditions, structure_metrics["complexity_score"]
        )
        
        print(f"\n검출된 이슈 수: {len(issues)}")
        if issues:
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. [{issue.issue_type}] {issue.explanation}")
                if hasattr(issue, 'fields') and issue.fields:
                    print(f"     관련 필드: {issue.fields}")
                if hasattr(issue, 'recommendation') and issue.recommendation:
                    print(f"     권장사항: {issue.recommendation}")
        else:
            print("  문제가 발견되지 않았습니다.")
        
        # 추가 정보: 필드별 조건 수집
        field_conditions = {}
        
        def collect_field_conditions(condition_list):
            for condition in condition_list:
                if condition is None:
                    continue
                    
                if condition.keyName and condition.keyName != "placeholder":
                    if condition.keyName not in field_conditions:
                        field_conditions[condition.keyName] = []
                    field_conditions[condition.keyName].append(condition)
                
                if condition.conditions:
                    collect_field_conditions(condition.conditions)
        
        collect_field_conditions(conditions)
        
        if field_conditions:
            print(f"\n필드별 조건 상세:")
            for field_name, field_conds in field_conditions.items():
                print(f"  {field_name}: {len(field_conds)}개")
                for cond in field_conds:
                    print(f"    - {cond.operator} {cond.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 80)
    print("8개 테스트 JSON 파일 전체 테스트")
    print("=" * 80)
    
    # 테스트 JSON 파일 목록
    test_files = [
        "test_missing_condition.json",
        "test_type_mismatch.json", 
        "test_duplicate_condition.json",
        "test_invalid_operator.json",
        "test_ambiguous_branch.json",
        "test_complexity_warning.json",
        "test_self_contradiction.json",
        "test_all_errors_combined.json"
    ]
    
    # RuleAnalyzer 생성
    analyzer = RuleAnalyzerV2()
    
    # 각 파일 테스트
    success_count = 0
    total_count = len(test_files)
    
    for file_path in test_files:
        if os.path.exists(file_path):
            success = await test_json_file(file_path, analyzer)
            if success:
                success_count += 1
        else:
            print(f"\n❌ 파일을 찾을 수 없습니다: {file_path}")
    
    # 결과 요약
    print(f"\n{'='*80}")
    print(f"테스트 결과 요약")
    print(f"{'='*80}")
    print(f"총 테스트 파일: {total_count}개")
    print(f"성공: {success_count}개")
    print(f"실패: {total_count - success_count}개")
    print(f"성공률: {success_count/total_count*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(main()) 