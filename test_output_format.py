import asyncio
import json
from backend.app.services.rule_analyzer_v2 import RuleAnalyzerV2
from backend.app.models.rule import Rule

async def test_output():
    rule_json = {
        'ruleUuid': 'test-uuid',
        'ruleName': 'Test Rule',
        'ruleMsg': 'Test Message',
        'conditionTree': {
            'logicType': 'AND',
            'condition': [
                {
                    'condUuid': '123-456',
                    'keyName': 'testField',
                    'dispName': 'Test Field',
                    'operator': '==',
                    'value': 'testValue',
                    'fieldDataType': 'String'
                }
            ]
        }
    }
    
    analyzer = RuleAnalyzerV2()
    rule = Rule(**rule_json)
    result = await analyzer.analyze_rule(rule)
    
    # ValidationResult를 dict로 변환해서 확인
    result_dict = result.model_dump()
    print('=== 출력 JSON 구조 확인 ===')
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(test_output()) 