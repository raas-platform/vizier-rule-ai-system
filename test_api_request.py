import requests
import json

# API 테스트 데이터 (배열 형태)
test_data = [{
    "ruleUuid": "test-uuid",
    "ruleName": "Test Rule",
    "ruleMsg": "Test Message", 
    "conditionTree": {
        "logicType": "AND",
        "condition": [
            {
                "condUuid": "123-456",
                "keyName": "testField",
                "dispName": "Test Field",
                "operator": "==",
                "value": "testValue",
                "fieldDataType": "String"
            }
        ]
    }
}]

try:
    response = requests.post(
        "http://localhost:8888/rules/validate-json",
        json=test_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
except Exception as e:
    print(f"Error: {e}") 