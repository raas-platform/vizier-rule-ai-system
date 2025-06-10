import sys
import json
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule
import asyncio

async def debug_detailed_analysis():
    """첨부된 JSON 파일의 조건 구조를 자세히 분석"""
    
    print("=== 첨부된 JSON 파일 상세 분석 ===")
    
    # JSON 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    rule_json = rules_data[0]
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    
    # Pydantic 모델로 변환
    test_rule = Rule(**rule_json)
    
    # RuleAnalyzerV2 생성
    analyzer = RuleAnalyzerV2()
    
    print("\n=== 조건 파싱 과정 ===")
    conditions = analyzer.condition_analyzer.parse_rule_conditions(test_rule)
    print(f"파싱된 총 조건 수: {len(conditions)}")
    
    # 모든 조건을 재귀적으로 출력
    def print_conditions(cond_list, depth=0):
        indent = "  " * depth
        for i, cond in enumerate(cond_list):
            print(f"{indent}{i+1}. {cond.keyName} {cond.operator} {cond.value} ({cond.fieldDataType})")
            if cond.conditions:
                print(f"{indent}   └─ 하위 조건들:")
                print_conditions(cond.conditions, depth + 2)
    
    print_conditions(conditions)
    
    print("\n=== 필드별 조건 정리 ===")
    field_conditions = {}
    
    def collect_field_conditions(cond_list, path=""):
        for i, cond in enumerate(cond_list):
            current_path = f"{path}/{i+1}" if path else f"{i+1}"
            
            if cond.keyName and cond.keyName != "placeholder":
                if cond.keyName not in field_conditions:
                    field_conditions[cond.keyName] = []
                
                field_conditions[cond.keyName].append({
                    "path": current_path,
                    "operator": cond.operator,
                    "value": cond.value,
                    "type": cond.fieldDataType
                })
            
            if cond.conditions:
                collect_field_conditions(cond.conditions, current_path)
    
    collect_field_conditions(conditions)
    
    for field, conds in field_conditions.items():
        print(f"\n📋 {field} 필드:")
        for j, cond in enumerate(conds):
            print(f"  {j+1}. [{cond['path']}] {cond['operator']} {cond['value']} ({cond['type']})")
    
    print("\n=== 개별 이슈 검출 테스트 ===")
    
    # 중복 조건 검출
    print("\n🔄 중복 조건 검출:")
    duplicate_issues = analyzer.issue_detector.detect_duplicate_conditions(conditions)
    print(f"발견된 중복 조건: {len(duplicate_issues)}건")
    for issue in duplicate_issues:
        print(f"  - {issue.field}: {issue.explanation}")
    
    # 자기모순 검출
    print("\n🔄 자기모순 검출:")
    contradiction_issues = analyzer.issue_detector.detect_self_contradiction(conditions)
    print(f"발견된 자기모순: {len(contradiction_issues)}건")
    for issue in contradiction_issues:
        print(f"  - {issue.field}: {issue.explanation}")
    
    # 타입 불일치 검출
    print("\n🔄 타입 불일치 검출:")
    type_issues = analyzer.issue_detector.detect_type_mismatch(conditions)
    print(f"발견된 타입 불일치: {len(type_issues)}건")
    for issue in type_issues:
        print(f"  - {issue.field}: {issue.explanation}")
    
    # 분기 불명확성 검출
    print("\n🔄 분기 불명확성 검출:")
    ambiguous_issues = analyzer.issue_detector.detect_ambiguous_branches(conditions)
    print(f"발견된 분기 불명확성: {len(ambiguous_issues)}건")
    for issue in ambiguous_issues:
        print(f"  - {issue.field}: {issue.explanation}")
    
    # 누락 조건 검출
    print("\n🔄 누락 조건 검출:")
    missing_issues = analyzer.issue_detector.detect_missing_conditions(test_rule, conditions)
    print(f"발견된 누락 조건: {len(missing_issues)}건")
    for issue in missing_issues:
        print(f"  - {issue.field}: {issue.explanation}")
    
    print("\n=== MBL_ACT_MEM_PCNT 조건 분석 ===")
    mbl_conditions = field_conditions.get('MBL_ACT_MEM_PCNT', [])
    print(f"MBL_ACT_MEM_PCNT 조건 수: {len(mbl_conditions)}개")
    
    if len(mbl_conditions) >= 2:
        print("🔍 중복/모순 가능성 분석:")
        for i, cond1 in enumerate(mbl_conditions):
            for j, cond2 in enumerate(mbl_conditions[i+1:], i+1):
                print(f"  비교: [{cond1['path']}] {cond1['operator']} {cond1['value']} vs [{cond2['path']}] {cond2['operator']} {cond2['value']}")
                
                # 리던던트 조건 체크
                val1, val2 = cond1['value'], cond2['value']
                op1, op2 = cond1['operator'], cond2['operator']
                
                try:
                    num_val1 = float(val1)
                    num_val2 = float(val2)
                    
                    is_redundant = False
                    explanation = ""
                    
                    # 리던던트 패턴 검사
                    if op1 == ">=" and op2 == "==" and num_val2 >= num_val1:
                        is_redundant = True
                        explanation = f"== {num_val2}는 이미 >= {num_val1}에 포함됨 (리던던트)"
                    elif op2 == ">=" and op1 == "==" and num_val1 >= num_val2:
                        is_redundant = True
                        explanation = f"== {num_val1}는 이미 >= {num_val2}에 포함됨 (리던던트)"
                    elif op1 == ">=" and op2 == ">=" and num_val1 != num_val2:
                        is_redundant = True
                        min_val = min(num_val1, num_val2)
                        explanation = f">= {num_val1}와 >= {num_val2} 중 >= {min_val}가 더 포괄적 (리던던트)"
                    
                    if is_redundant:
                        print(f"    ⚠️  리던던트: {explanation}")
                    else:
                        print(f"    ✅ 유효한 조건 조합")
                        
                except ValueError:
                    print(f"    🔤 문자열 값이라 숫자 비교 불가")
    
    print("\n=== 전체 분석 실행 ===")
    result = await analyzer.analyze_rule(test_rule)
    print(f"최종 이슈 수: {len(result.issues)}건")
    print(f"이슈 타입: {[issue.issue_type for issue in result.issues]}")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(debug_detailed_analysis())
    print("\n🎯 상세 분석 완료!") 