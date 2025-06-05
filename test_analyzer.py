import sys
import json
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule, RuleCondition, ConditionTree
import asyncio

async def test_complex_rule():
    """복잡한 conditionTree 구조의 룰 테스트"""
    
    print("=== 복잡한 conditionTree 룰 분석 테스트 ===")
    
    # 제공된 JSON 데이터
    rule_json = {
        "ruleUuid": "R002",
        "ruleName": "참 쉬운 가족 결합 결합유형",
        "ruleMsg": "LGT 고객이고, 무선 회선 수 및 특수 회선 조건을 만족하는 경우 결합 할인 적용.",
        "conditionTree": {
            "logicType": "AND",
            "condition": [
                {
                    "condUuid": "c1",
                    "keyName": "MRKT_CD",
                    "dispName": "마켓코드",
                    "operator": "==",
                    "value": "LGT",
                    "fieldDataType": "String"
                },
                {
                    "logicType": "OR",
                    "condition": [
                        {
                            "logicType": "AND",
                            "condition": [
                                {
                                    "condUuid": "c2",
                                    "keyName": "MBL_ACT_MEM_PCNT",
                                    "dispName": "개통모바일 구성원개수",
                                    "operator": ">=",
                                    "value": "1",
                                    "fieldDataType": "Number"
                                },
                                {
                                    "logicType": "OR",
                                    "condition": [
                                        {
                                            "condUuid": "c3",
                                            "keyName": "MVNO_ACT_MEM_PCNT",
                                            "dispName": "개통상태 MVNO 구성원 개수",
                                            "operator": ">",
                                            "value": "0",
                                            "fieldDataType": "Number"
                                        },
                                        {
                                            "condUuid": "c4",
                                            "keyName": "IOT_MEM_PCNT",
                                            "dispName": "IOT 구성원 개수",
                                            "operator": ">",
                                            "value": "0",
                                            "fieldDataType": "Number"
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "logicType": "AND",
                            "condition": [
                                {
                                    "condUuid": "c5",
                                    "keyName": "MBL_ACT_MEM_PCNT",
                                    "dispName": "개통모바일 구성원개수",
                                    "operator": ">=",
                                    "value": "2",
                                    "fieldDataType": "Number"
                                }
                            ]
                        }
                    ]
                },
                {
                    "logicType": "OR",
                    "condition": [
                        {
                            "condUuid": "c6",
                            "keyName": "ENTR_STUS_CD",
                            "dispName": "가입상태",
                            "operator": "==",
                            "value": "정지",
                            "fieldDataType": "String"
                        },
                        {
                            "condUuid": "c7",
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
    
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    print(f"📝 룰 설명: {rule_json['ruleMsg']}")
    print(f"🔍 conditionTree 깊이: {_calculate_tree_depth(rule_json['conditionTree'])}")
    
    # RuleAnalyzer 실행
    analyzer = RuleAnalyzerV2()
    
    try:
        # Pydantic 모델로 변환
        test_rule = Rule(**rule_json)
        
        print(f"\n🔍 디버깅 정보:")
        print(f"- 룰에 conditionTree가 있는가: {hasattr(test_rule, 'conditionTree') and test_rule.conditionTree is not None}")
        print(f"- 룰에 conditions가 있는가: {hasattr(test_rule, 'conditions') and test_rule.conditions is not None}")
        
        if hasattr(test_rule, 'conditionTree') and test_rule.conditionTree:
            print(f"- conditionTree 타입: {type(test_rule.conditionTree)}")
            print(f"- conditionTree logicType: {test_rule.conditionTree.logicType}")
            print(f"- conditionTree condition 개수: {len(test_rule.conditionTree.condition) if test_rule.conditionTree.condition else 0}")
            
            # 변환된 conditions 디버깅
            processed_conditions = analyzer._process_condition_tree(test_rule.conditionTree)
            print(f"- 변환된 conditions 개수: {len(processed_conditions)}")
            
            for i, cond in enumerate(processed_conditions):
                field = analyzer._get_condition_field(cond)
                print(f"  조건 {i+1}: field='{field}', operator='{cond.operator}', value='{cond.value}'")
                if hasattr(cond, 'conditions') and cond.conditions:
                    print(f"    - 하위 조건 수: {len(cond.conditions)}")
            
        # 룰 분석 실행
        result = await analyzer.analyze_rule(test_rule)
        
        print(f"\n✅ 분석 완료!")
        print(f"- 유효성: {'🟢 유효' if result.is_valid else '🔴 오류 있음'}")
        print(f"- 요약: {result.summary}")
        print(f"- 이슈 수: {len(result.issues)}")
        print(f"- 구조 정보:")
        print(f"  * 깊이: {result.structure.depth}")
        print(f"  * 전체 조건 노드 수: {result.structure.condition_node_count}")
        print(f"  * 필드 조건 수: {result.structure.field_condition_count}")
        print(f"  * 고유 필드 수: {len(result.structure.unique_fields)}")
        print(f"  * 필드 목록: {result.structure.unique_fields}")
        print(f"- 복잡도 점수: {result.complexity_score}")
        
        if result.issues:
            print(f"\n📋 발견된 이슈들 ({len(result.issues)}건):")
            
            # 심각도별로 그룹화
            errors = [i for i in result.issues if i.severity == "error"]
            warnings = [i for i in result.issues if i.severity == "warning"]
            
            if errors:
                print(f"  🔴 오류 ({len(errors)}건):")
                for i, issue in enumerate(errors, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.explanation}")
                    print(f"       위치: {issue.location}")
                    
            if warnings:
                print(f"  🟡 경고 ({len(warnings)}건):")
                for i, issue in enumerate(warnings, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.explanation}")
                    print(f"       위치: {issue.location}")
        else:
            print(f"\n🎉 이슈가 발견되지 않았습니다!")
            
        if result.ai_comment:
            print(f"\n🤖 AI 조언: {result.ai_comment}")
            
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def _calculate_tree_depth(condition_tree, current_depth=1):
    """conditionTree의 깊이 계산"""
    if not condition_tree or 'condition' not in condition_tree:
        return current_depth
    
    max_depth = current_depth
    for item in condition_tree['condition']:
        if 'logicType' in item:  # 중첩된 논리 연산자
            nested_depth = _calculate_tree_depth(item, current_depth + 1)
            max_depth = max(max_depth, nested_depth)
    
    return max_depth

if __name__ == "__main__":
    success = asyncio.run(test_complex_rule())
    if success:
        print("\n🎉 복잡한 룰 테스트 성공!")
    else:
        print("\n💥 복잡한 룰 테스트 실패!") 