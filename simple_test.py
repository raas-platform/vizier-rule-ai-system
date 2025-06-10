import sys
import json
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule
import asyncio

async def simple_test():
    """간단한 직접 검출 테스트"""
    
    print("=== 간단한 직접 검출 테스트 ===")
    
    # JSON 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    rule_json = rules_data[0]
    test_rule = Rule(**rule_json)
    
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    print(f"🔍 conditionTree 존재: {hasattr(test_rule, 'conditionTree') and test_rule.conditionTree is not None}")
    
    # 직접 검출 메서드 테스트
    analyzer = RuleAnalyzerV2()
    direct_issues = analyzer.issue_detector.detect_issues_from_rule_direct(test_rule)
    
    print(f"📋 직접 검출된 이슈 수: {len(direct_issues)}")
    for issue in direct_issues:
        print(f"  - {issue.issue_type}: {issue.explanation}")
    
    # 필드 조건 추출 테스트
    field_conditions = {}
    analyzer.issue_detector._extract_field_conditions_recursive(test_rule.conditionTree, field_conditions)
    
    print(f"📋 추출된 필드별 조건:")
    for field, conditions in field_conditions.items():
        print(f"  {field}: {len(conditions)}개")
        for cond in conditions:
            print(f"    - {cond['operator']} {cond['value']}")
    
    return direct_issues

if __name__ == "__main__":
    result = asyncio.run(simple_test())
    print("\n🎯 간단 테스트 완료!") 