import sys
import json
import asyncio
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule

async def debug_complex_rule():
    """복잡한 룰 디버깅"""
    
    # 제공된 JSON 데이터 (간단한 버전)
    rule_json = {
        "ruleUuid": "09a6845a-4d21-40de-9320-1d97ae91d34e",
        "ruleName": "LGZ0000058_LDZ0002389",
        "ruleMsg": "참 쉬운 가족 결합할인_무무선_0원",
        "conditionTree": {
            "logicType": "AND",
            "condition": [
                {
                    "condUuid": "16971007-cce5-4311-ae6f-db9b5b3334a8",
                    "keyName": "DCNT_TRGT_SVC",
                    "dispName": "할인대상서비스",
                    "operator": "==",
                    "value": "LZP0000001",
                    "fieldDataType": "String"
                },
                {
                    "logicType": "OR",
                    "condition": [
                        {
                            "condUuid": "85435b8c-ae1c-4643-8e19-163d9ede66fa",
                            "keyName": "MBL_ACT_MEM_PCNT",
                            "dispName": "개통모바일 구성원개수",
                            "operator": ">=",
                            "value": "2",
                            "fieldDataType": "Number"
                        },
                        {
                            "condUuid": "333aba08-7191-4994-86c8-aec26658b92e",
                            "keyName": "MBL_ACT_MEM_PCNT",
                            "dispName": "개통모바일 구성원개수",
                            "operator": ">=",
                            "value": "1",
                            "fieldDataType": "Number"
                        },
                        {
                            "condUuid": "43d7787c-c7c9-4a0c-8095-3f7c4ecd9dea",
                            "keyName": "MBL_ACT_MEM_PCNT",
                            "dispName": "개통모바일 구성원개수",
                            "operator": "==",
                            "value": "1",
                            "fieldDataType": "Number"
                        }
                    ]
                }
            ]
        }
    }
    
    print("=== 디버깅 시작 ===")
    
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
    structure_metrics = analyzer.condition_analyzer.calculate_structure_metrics(conditions)
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
                
                is_contradictory = analyzer.issue_detector._are_contradictory(cond1, cond2)
                is_overlapping = analyzer.issue_detector._are_overlapping(cond1, cond2)
                
                print(f"  비교: {cond1.operator} {cond1.value} vs {cond2.operator} {cond2.value}")
                print(f"    모순: {is_contradictory}, 겹침: {is_overlapping}")
    
    # 최종 이슈 검출
    issues = await analyzer.issue_detector.detect_all_issues(
        test_rule, conditions, structure_metrics["complexity_score"]
    )
    print(f"\n최종 검출된 이슈 수: {len(issues)}")
    for issue in issues:
        print(f"  - {issue.issue_type}: {issue.explanation}")

if __name__ == "__main__":
    asyncio.run(debug_complex_rule()) 