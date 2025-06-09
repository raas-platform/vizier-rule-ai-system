import sys
import json
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule
import asyncio

async def test_user_provided_json():
    """사용자가 제공한 JSON 데이터 테스트"""
    
    print("=== 사용자 제공 JSON 룰 분석 테스트 ===")
    
    # 사용자가 제공한 JSON 데이터
    user_rule_json = [
        {
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
                        "condUuid": "387f0de3-a31f-4c20-b6bc-9448a835162e",
                        "keyName": "MRKT_CD",
                        "dispName": "마켓코드",
                        "operator": "==",
                        "value": "LGT",
                        "fieldDataType": "String"
                    },
                    {
                        "condUuid": "f9c4c3a2-5af4-4ea4-8880-f8d2fb5a8d78",
                        "keyName": "ITNT_ACT_MEM_PCNT",
                        "dispName": "개통인터넷 구성원개수",
                        "operator": "==",
                        "value": "0",
                        "fieldDataType": "Number"
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
                                "logicType": "AND",
                                "condition": [
                                    {
                                        "condUuid": "333aba08-7191-4994-86c8-aec26658b92e",
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
                                                "condUuid": "3381efa7-64a9-4ed0-8026-f50cb81e41b9",
                                                "keyName": "IOT_MEM_PCNT",
                                                "dispName": "IOT 구성원 개수",
                                                "operator": ">",
                                                "value": "0",
                                                "fieldDataType": "Number"
                                            },
                                            {
                                                "condUuid": "9f17d156-4459-4d56-bc8b-123044e13bc8",
                                                "keyName": "MVNO_ACT_MEM_PCNT",
                                                "dispName": "개통상태 MVNO 구성원 개수",
                                                "operator": ">",
                                                "value": "0",
                                                "fieldDataType": "Number"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "logicType": "OR",
                        "condition": [
                            {
                                "condUuid": "43d7787c-c7c9-4a0c-8095-3f7c4ecd9dea",
                                "keyName": "MBL_ACT_MEM_PCNT",
                                "dispName": "개통모바일 구성원개수",
                                "operator": "==",
                                "value": "1",
                                "fieldDataType": "Number"
                            },
                            {
                                "condUuid": "b466bc54-fb06-433f-a39b-c74069d5490c",
                                "keyName": "ENTR_STUS_CD",
                                "dispName": "가입상태",
                                "operator": "==",
                                "value": "정지",
                                "fieldDataType": "String"
                            }
                        ]
                    }
                ]
            }
        }
    ]
    
    # 첫 번째 룰 추출
    rule_data = user_rule_json[0]
    
    print(f"📊 테스트 룰: {rule_data['ruleName']}")
    print(f"📝 룰 설명: {rule_data['ruleMsg']}")
    
    # RuleAnalyzer 실행
    analyzer = RuleAnalyzerV2()
    
    try:
        # Pydantic 모델로 변환
        test_rule = Rule(**rule_data)
        
        print(f"\n🔍 디버깅 정보:")
        print(f"- 룰에 conditionTree가 있는가: {hasattr(test_rule, 'conditionTree') and test_rule.conditionTree is not None}")
        
        # 룰 분석 실행
        result = await analyzer.analyze_rule(test_rule)
        
        print(f"\n✅ 분석 완료!")
        print(f"- 유효성: {'🟢 유효' if result.is_valid else '🔴 오류 있음'}")
        print(f"- 요약: {result.summary}")
        print(f"- 이슈 수: {len(result.issues)}")
        print(f"- 복잡도 점수: {result.complexity_score}")
        
        # issue_counts 정보 출력
        print(f"\n📊 이슈 카운트:")
        if hasattr(result, 'issue_counts') and result.issue_counts:
            for issue_type, count in result.issue_counts.items():
                print(f"  - {issue_type}: {count}")
        
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
            
        return result
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_user_provided_json())
    if result and hasattr(result, 'issue_counts') and result.issue_counts:
        print(f"\n🎯 예상된 결과:")
        print(f"- complexity_warning: 1")
        print(f"- ambiguous_branch: 1") 
        print(f"- missing_condition: 1")
        print(f"\n🔍 실제 결과:")
        for issue_type, count in result.issue_counts.items():
            print(f"- {issue_type}: {count}") 