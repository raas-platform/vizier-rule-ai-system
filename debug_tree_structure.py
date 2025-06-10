import sys
import json
sys.path.append('./backend')

from app.models.rule import Rule

def analyze_tree_structure():
    """조건 트리 구조를 자세히 분석"""
    
    print("=== 조건 트리 구조 분석 ===")
    
    # JSON 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    rule_json = rules_data[0]
    test_rule = Rule(**rule_json)
    
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    
    def analyze_recursive(tree, depth=0, path=""):
        indent = "  " * depth
        current_path = f"{path}/{depth+1}" if path else f"{depth+1}"
        
        print(f"{indent}🔍 분석 중 (깊이 {depth}, 경로: {current_path})")
        print(f"{indent}타입: {type(tree)}")
        
        if hasattr(tree, '__dict__'):
            attrs = {k: v for k, v in tree.__dict__.items() if not k.startswith('_')}
            print(f"{indent}속성: {list(attrs.keys())}")
            
            if hasattr(tree, 'keyName') and tree.keyName:
                print(f"{indent}✅ 필드 조건: {tree.keyName} {getattr(tree, 'operator', 'NO_OP')} {getattr(tree, 'value', 'NO_VALUE')}")
            
            if hasattr(tree, 'logicType'):
                print(f"{indent}📋 논리 블록: {tree.logicType}")
                
            if hasattr(tree, 'condition') and tree.condition:
                condition_list = tree.condition
                print(f"{indent}🔗 하위 조건 수: {len(condition_list)}")
                
                for i, sub_condition in enumerate(condition_list):
                    print(f"{indent}  --- 하위 조건 {i+1} ---")
                    analyze_recursive(sub_condition, depth + 1, current_path)
            
        elif isinstance(tree, dict):
            print(f"{indent}딕셔너리 키: {list(tree.keys())}")
            
            if 'keyName' in tree:
                print(f"{indent}✅ 필드 조건: {tree['keyName']} {tree.get('operator', 'NO_OP')} {tree.get('value', 'NO_VALUE')}")
            
            if 'logicType' in tree:
                print(f"{indent}📋 논리 블록: {tree['logicType']}")
                
            if 'condition' in tree:
                condition_list = tree['condition']
                print(f"{indent}🔗 하위 조건 수: {len(condition_list)}")
                
                for i, sub_condition in enumerate(condition_list):
                    print(f"{indent}  --- 하위 조건 {i+1} ---")
                    analyze_recursive(sub_condition, depth + 1, current_path)
                    
        else:
            print(f"{indent}기타 타입: {tree}")
    
    # 조건 트리 분석
    analyze_recursive(test_rule.conditionTree)

if __name__ == "__main__":
    analyze_tree_structure()
    print("\n🎯 구조 분석 완료!") 