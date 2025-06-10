import sys
import json
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule
import asyncio

async def debug_missing_issues():
    """ambiguous_branch와 missing_condition이 왜 검출되지 않는지 분석"""
    
    print("=== 누락된 이슈 디버깅 ===")
    
    # JSON 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    rule_json = rules_data[0]
    test_rule = Rule(**rule_json)
    
    # RuleAnalyzerV2 생성
    analyzer = RuleAnalyzerV2()
    conditions = analyzer.condition_analyzer.parse_rule_conditions(test_rule)
    
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    print(f"📋 파싱된 조건 수: {len(conditions)}")
    
    print("\n=== ambiguous_branch 검출 테스트 ===")
    ambiguous_issues = analyzer.issue_detector.detect_ambiguous_branches(conditions)
    print(f"발견된 분기 불명확성: {len(ambiguous_issues)}건")
    for issue in ambiguous_issues:
        print(f"  - {issue.field}: {issue.explanation}")
        print(f"    위치: {issue.location}")
        print(f"    제안: {issue.suggestion}")
    
    print("\n=== missing_condition 검출 테스트 ===")
    missing_issues = analyzer.issue_detector.detect_missing_conditions(test_rule, conditions)
    print(f"발견된 누락 조건: {len(missing_issues)}건")
    for issue in missing_issues:
        print(f"  - {issue.field}: {issue.explanation}")
        print(f"    위치: {issue.location}")
        print(f"    제안: {issue.suggestion}")
    
    print("\n=== 필드별 조건 상세 분석 ===")
    # 필드별 조건 수집 및 분석
    field_conditions = {}
    
    def collect_detailed_conditions(cond_list, path="", parent_operator=None):
        for i, cond in enumerate(cond_list):
            current_path = f"{path}/{i+1}" if path else f"{i+1}"
            
            if cond.keyName and cond.keyName != "placeholder":
                if cond.keyName not in field_conditions:
                    field_conditions[cond.keyName] = []
                
                field_conditions[cond.keyName].append({
                    "path": current_path,
                    "operator": cond.operator,
                    "value": cond.value,
                    "type": cond.fieldDataType,
                    "parent_operator": parent_operator
                })
            
            if cond.conditions:
                # 논리 연산자 정보 전달
                op = cond.operator.upper() if cond.operator and cond.operator.upper() in ["AND", "OR"] else parent_operator
                collect_detailed_conditions(cond.conditions, current_path, op)
    
    collect_detailed_conditions(conditions)
    
    # 분기 불명확성 체크를 위한 상세 분석
    print("\n🔍 분기 불명확성 상세 분석:")
    for field, conds in field_conditions.items():
        if len(conds) >= 2:
            print(f"\n📋 {field} 필드 ({len(conds)}개 조건):")
            
            # OR 그룹별 분류
            or_groups = {}
            for cond in conds:
                parent_op = cond.get("parent_operator", "AND")
                if parent_op not in or_groups:
                    or_groups[parent_op] = []
                or_groups[parent_op].append(cond)
            
            for op, group_conds in or_groups.items():
                print(f"  {op} 그룹: {len(group_conds)}개")
                for cond in group_conds:
                    print(f"    - [{cond['path']}] {cond['operator']} {cond['value']}")
                    
                # 숫자 필드의 경우 범위 겹침 체크
                if field in ["MBL_ACT_MEM_PCNT", "IOT_MEM_PCNT", "MVNO_ACT_MEM_PCNT", "ITNT_ACT_MEM_PCNT"]:
                    print(f"    🔢 숫자 필드 범위 분석:")
                    for i, cond1 in enumerate(group_conds):
                        for j, cond2 in enumerate(group_conds[i+1:], i+1):
                            print(f"      비교: {cond1['operator']} {cond1['value']} vs {cond2['operator']} {cond2['value']}")
                            
                            # 범위 겹침 체크
                            try:
                                val1, val2 = float(cond1['value']), float(cond2['value'])
                                op1, op2 = cond1['operator'], cond2['operator']
                                
                                # 간단한 겹침 체크
                                overlaps = False
                                if op1 == ">=" and op2 == "==":
                                    overlaps = val2 >= val1
                                elif op1 == "==" and op2 == ">=":
                                    overlaps = val1 >= val2
                                elif op1 == ">=" and op2 == ">=":
                                    overlaps = True  # 둘 다 범위라서 겹칠 수 있음
                                
                                if overlaps:
                                    print(f"        ⚠️  겹침 가능성 있음")
                                else:
                                    print(f"        ✅ 겹침 없음")
                            except:
                                print(f"        🔤 숫자 비교 불가")
    
    print("\n=== 누락 조건 상세 분석 ===")
    # 숫자 필드들의 범위 분석
    number_fields = ["MBL_ACT_MEM_PCNT", "IOT_MEM_PCNT", "MVNO_ACT_MEM_PCNT", "ITNT_ACT_MEM_PCNT"]
    
    for field in number_fields:
        if field in field_conditions:
            conds = field_conditions[field]
            print(f"\n🔢 {field} 범위 분석:")
            
            values = []
            operators = []
            for cond in conds:
                try:
                    val = float(cond['value'])
                    values.append(val)
                    operators.append(cond['operator'])
                    print(f"  - {cond['operator']} {val}")
                except:
                    print(f"  - {cond['operator']} {cond['value']} (숫자 아님)")
            
            # 0이 빠져있는지 체크
            if 0 not in values and any(op in [">", ">="] for op in operators):
                min_val = min(v for v in values if v > 0) if values else None
                if min_val and min_val > 0:
                    print(f"    ⚠️  0 값에 대한 조건이 없음 (최소값: {min_val})")
            
            # 범위 누락 체크
            if len(values) >= 2:
                values.sort()
                for i in range(len(values)-1):
                    gap = values[i+1] - values[i]
                    if gap > 1:
                        print(f"    ⚠️  {values[i]}와 {values[i+1]} 사이 누락 가능성")
    
    print("\n=== 전체 분석 결과 ===")
    result = await analyzer.analyze_rule(test_rule)
    print(f"최종 이슈 수: {len(result.issues)}건")
    print(f"이슈 타입: {[issue.issue_type for issue in result.issues]}")
    
    expected_types = ["complexity_warning", "ambiguous_branch", "missing_condition"]
    found_types = [issue.issue_type for issue in result.issues]
    missing_types = [t for t in expected_types if t not in found_types]
    
    if missing_types:
        print(f"❌ 누락된 이슈 타입: {missing_types}")
    else:
        print(f"✅ 모든 예상 이슈 타입 검출됨")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(debug_missing_issues())
    print("\n🎯 누락 이슈 디버깅 완료!") 