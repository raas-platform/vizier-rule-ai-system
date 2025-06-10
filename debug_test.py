import sys
import json
import asyncio
import logging
sys.path.append('./backend')

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule

async def debug_complex_rule():
    """복잡한 룰 디버깅"""
    
    # test_new_rule.json 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    # 첫 번째 룰 사용
    rule_json = rules_data[0]
    
    print("=== 디버깅 시작 ===")
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    
    # RuleAnalyzer 생성
    analyzer = RuleAnalyzerV2()
    
    # Pydantic 모델로 변환
    test_rule = Rule(**rule_json)
    
    # 조건 파싱 테스트
    print("\n=== 조건 파싱 과정 ===")
    conditions = analyzer.condition_analyzer.parse_rule_conditions(test_rule)
    print(f"파싱된 조건 수: {len(conditions)}")
    
    def print_condition_tree(conds, level=0):
        indent = "  " * level
        for i, cond in enumerate(conds):
            print(f"{indent}조건 {i+1}: keyName='{cond.keyName}', operator='{cond.operator}', value='{cond.value}'")
            if hasattr(cond, 'conditions') and cond.conditions:
                print(f"{indent}  하위 조건 수: {len(cond.conditions)}")
                print_condition_tree(cond.conditions, level + 1)
    
    print_condition_tree(conditions)
    
    # 구조 메트릭
    structure_metrics = analyzer.condition_analyzer.calculate_structure_metrics(conditions, test_rule)
    print(f"\n구조 메트릭: {structure_metrics}")
    
    # 이슈 검출 프로세스 상세 분석
    print("\n=== 이슈 검출 과정 ===")
    
    # 필드별 조건 수집 과정 분석
    field_conditions = {}
    
    def collect_field_conditions(condition_list, parent_logic="", path=""):
        for i, condition in enumerate(condition_list):
            if condition is None:
                continue
                
            current_path = f"{path}.{i}" if path else str(i)
            print(f"조건 수집: path='{current_path}', keyName='{condition.keyName}', parent_logic='{parent_logic}'")
            
            if condition.keyName and condition.keyName != "placeholder":
                if condition.keyName not in field_conditions:
                    field_conditions[condition.keyName] = []
                
                field_conditions[condition.keyName].append({
                    'condition': condition,
                    'path': current_path,
                    'parent_logic': parent_logic
                })
            
            if condition.conditions:
                collect_field_conditions(
                    condition.conditions, 
                    condition.operator or "AND", 
                    current_path
                )
    
    collect_field_conditions(conditions)
    
    print(f"\n수집된 필드별 조건:")
    for field_name, conds in field_conditions.items():
        print(f"  {field_name}: {len(conds)}개 조건")
        for cond_info in conds:
            cond = cond_info['condition']
            print(f"    - {cond.operator} {cond.value} (path: {cond_info['path']})")
    
    # 겹침 검사 과정 분석
    print(f"\n=== 겹침 검사 과정 ===")
    for field_name, field_conds in field_conditions.items():
        if len(field_conds) < 2:
            print(f"{field_name}: 조건이 1개뿐이므로 건너뜀")
            continue
        
        print(f"{field_name}: {len(field_conds)}개 조건 비교")
        for i, cond1_info in enumerate(field_conds):
            for j, cond2_info in enumerate(field_conds[i+1:], i+1):
                cond1 = cond1_info['condition']
                cond2 = cond2_info['condition']
                
                # is_contradictory = analyzer.issue_detector._are_contradictory(cond1, cond2)
                # is_overlapping = analyzer.issue_detector._are_overlapping(cond1, cond2)
                
                print(f"  비교: {cond1.operator} {cond1.value} vs {cond2.operator} {cond2.value}")
                # print(f"    모순: {is_contradictory}, 겹침: {is_overlapping}")
    
    # 최종 이슈 검출
    issues = await analyzer.issue_detector.detect_all_issues(
        test_rule, conditions, structure_metrics["complexity_score"]
    )
    print(f"\n최종 검출된 이슈 수: {len(issues)}")
    for issue in issues:
        print(f"  - {issue.issue_type}: {issue.explanation}")

    print("\n=== 실제 값 타입 확인 ===")
    for i, condition in enumerate(conditions[:5]):  # 처음 5개만 확인
        print(f"조건 {i+1}: {condition.keyName}")
        print(f"  fieldDataType: {getattr(condition, 'fieldDataType', 'None')}")
        print(f"  value: {condition.value} (type: {type(condition.value).__name__})")
        print(f"  operator: {condition.operator}")
        print()

    print("\n=== 값 변환 테스트 ===")
    for i, condition in enumerate(conditions[:3]):  # 처음 3개만 테스트
        field_data_type = getattr(condition, 'fieldDataType', 'String')
        print(f"조건 {i+1}: {condition.keyName}")
        print(f"  원본 값: {condition.value} (type: {type(condition.value).__name__})")
        print(f"  fieldDataType: {field_data_type}")
        
        # 수동으로 변환 테스트
        converted = analyzer.condition_analyzer._convert_value_by_type(condition.value, field_data_type)
        print(f"  변환된 값: {converted} (type: {type(converted).__name__})")
        print()

    print("\n=== condUuid 확인 ===")
    for i, condition in enumerate(conditions[:5]):  # 처음 5개만 확인
        print(f"조건 {i+1}: {condition.keyName}")
        print(f"  condUuid: {getattr(condition, 'condUuid', 'None')}")
        print(f"  operator: {condition.operator}")
        print(f"  value: {condition.value}")
        print()

    print("\\n=== Ambiguous Branch 이슈 검출 테스트 ===")
    ambiguous_issues = analyzer.issue_detector.detect_ambiguous_branches(conditions)
    print(f"발견된 Ambiguous Branch 이슈: {len(ambiguous_issues)}건")
    for issue in ambiguous_issues:
        print(f"  - condUuid: {issue.condUuid}")
        print(f"  - field: {issue.keyName}")
        print(f"  - type: {issue.issue_type}")
        print(f"  - explanation: {issue.explanation}")
        print()

    print("\\n=== Direct Issues 검출 테스트 ===")
    direct_issues = analyzer.issue_detector.detect_issues_from_rule_direct(test_rule)
    print(f"발견된 Direct Issues: {len(direct_issues)}건")
    for issue in direct_issues:
        print(f"  - condUuid: {issue.condUuid}")
        print(f"  - field: {issue.keyName}")
        print(f"  - type: {issue.issue_type}")
        print(f"  - explanation: {issue.explanation}")
        print()

    print("\\n=== 모든 이슈 검출 메서드 테스트 ===")
    print("1. Duplicate Conditions:")
    duplicate_issues = analyzer.issue_detector.detect_duplicate_conditions(conditions)
    for issue in duplicate_issues:
        print(f"   condUuid: {issue.condUuid}, type: {issue.issue_type}")
        
    print("\\n2. Type Mismatch:")
    type_issues = analyzer.issue_detector.detect_type_mismatch(conditions)
    for issue in type_issues:
        print(f"   condUuid: {issue.condUuid}, type: {issue.issue_type}")
        
    print("\\n3. Invalid Operators:")
    operator_issues = analyzer.issue_detector.detect_invalid_operators(conditions)
    for issue in operator_issues:
        print(f"   condUuid: {issue.condUuid}, type: {issue.issue_type}")
        
    print("\\n4. Self Contradiction:")
    contradiction_issues = analyzer.issue_detector.detect_self_contradiction(conditions)
    for issue in contradiction_issues:
        print(f"   condUuid: {issue.condUuid}, type: {issue.issue_type}")
        
    print("\\n5. Missing Conditions:")
    missing_issues = analyzer.issue_detector.detect_missing_conditions(test_rule, conditions)
    for issue in missing_issues:
        print(f"   condUuid: {issue.condUuid}, type: {issue.issue_type}")
        
    print("\\n6. Complexity Warnings:")
    complexity_issues = analyzer.issue_detector.detect_complexity_warnings(conditions, 50)
    for issue in complexity_issues:
        print(f"   condUuid: {issue.condUuid}, type: {issue.issue_type}")

    print("\\n=== Field Conditions 추출 확인 ===")
    from backend.app.services.analyzers.issue_detector import IssueDetector
    from backend.app.services.analyzers.condition_analyzer import ConditionAnalyzer
    
    # IssueDetector의 _extract_field_conditions_recursive 직접 테스트
    condition_analyzer = ConditionAnalyzer()
    issue_detector = IssueDetector(condition_analyzer)
    
    field_conditions = {}
    issue_detector._extract_field_conditions_recursive(
        test_rule.conditionTree, field_conditions
    )
    
    print(f"추출된 필드별 조건:")
    for field_name, conditions in field_conditions.items():
        print(f"\\n{field_name}:")
        for i, condition in enumerate(conditions):
            print(f"  {i+1}. operator: {condition.get('operator')}")
            print(f"     value: {condition.get('value')}")
            print(f"     condUuid: {condition.get('condUuid')}")
            print(f"     path: {condition.get('path')}")
            
    # _get_condition_uuid 메서드 테스트
    print(f"\\n=== _get_condition_uuid 메서드 테스트 ===")
    if field_conditions:
        first_field = list(field_conditions.keys())[0]
        first_condition = field_conditions[first_field][0]
        extracted_uuid = issue_detector._get_condition_uuid(first_condition)
        print(f"첫 번째 조건에서 추출한 UUID: {extracted_uuid}")
        print(f"조건 데이터: {first_condition}")

    print("\\n=== 구조 분석 디버깅 ===")
    depth, condition_node_count = analyzer.condition_analyzer._analyze_original_structure(test_rule.conditionTree)
    print(f"_analyze_original_structure 결과:")
    print(f"  depth: {depth}")
    print(f"  condition_node_count: {condition_node_count}")
    
    # 원본 JSON에서 논리 연산자 노드 수 확인
    print(f"\\n원본 JSON의 논리 연산자 노드:")
    print(f"  루트 logicType: {getattr(test_rule.conditionTree, 'logicType', None)}")
    
    # 재귀적으로 모든 논리 연산자 찾기
    def count_logic_nodes(tree, level=0):
        indent = "  " * level
        count = 0
        
        if hasattr(tree, 'logicType') and tree.logicType:
            print(f"{indent}논리 노드: {tree.logicType}")
            count += 1
            
        if hasattr(tree, 'condition') and tree.condition:
            for item in tree.condition:
                count += count_logic_nodes(item, level + 1)
                
        return count
    
    total_logic_nodes = count_logic_nodes(test_rule.conditionTree)
    print(f"\\n총 논리 연산자 노드 수: {total_logic_nodes}")
    
    # condition 배열의 모든 항목 확인
    def print_all_nodes(tree, level=0):
        indent = "  " * level
        
        if hasattr(tree, 'logicType'):
            print(f"{indent}[논리] logicType: {tree.logicType}")
        
        if hasattr(tree, 'keyName'):
            print(f"{indent}[조건] keyName: {tree.keyName}, operator: {getattr(tree, 'operator', None)}")
            
        if hasattr(tree, 'condition') and tree.condition:
            print(f"{indent}condition 배열 (길이: {len(tree.condition)}):")
            for i, item in enumerate(tree.condition):
                print(f"{indent}  [{i}]:")
                print_all_nodes(item, level + 2)
    
    print(f"\\n=== 전체 구조 트리 ===")
    print_all_nodes(test_rule.conditionTree)

if __name__ == "__main__":
    asyncio.run(debug_complex_rule()) 