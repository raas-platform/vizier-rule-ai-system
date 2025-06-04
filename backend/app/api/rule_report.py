from fastapi import APIRouter, HTTPException
from app.models.report import RuleReportRequest, RuleReportResponse
from app.services.rule_report_service import RuleReportService
from app.services.rule_analyzer import RuleAnalyzer
from app.models.rule import Rule, RuleCondition
from typing import List, Dict, Any
import json

router = APIRouter()

def convert_conditions(conditions: Dict[str, Any]) -> List[RuleCondition]:
    """JSON 조건을 RuleCondition 객체로 변환"""
    if not isinstance(conditions, dict):
        return []
        
    result = []
    try:
        if "conditions" in conditions:
            for condition in conditions["conditions"]:
                if not isinstance(condition, dict):
                    continue
                    
                if "field" in condition:
                    # 기본 조건
                    rule_condition = RuleCondition(
                        field=str(condition.get("field", "")),
                        operator=str(condition.get("operator", "")),
                        value=condition.get("value"),
                        conditions=None
                    )
                elif "operator" in condition and "conditions" in condition:
                    # 중첩 조건
                    rule_condition = RuleCondition(
                        field=str(condition.get("operator", "")),  # 연산자를 필드로 사용
                        operator="group",  # 그룹임을 표시
                        value=None,
                        conditions=convert_conditions(condition)
                    )
                else:
                    # 잘못된 형식의 조건은 건너뛰기
                    continue
                    
                result.append(rule_condition)
    except Exception as e:
        print(f"조건 변환 중 오류 발생: {str(e)}")
        return []
        
    return result

@router.post("/report", response_model=RuleReportResponse)
async def generate_rule_report(request: RuleReportRequest):
    """
    룰 JSON에 대한 상세 분석 리포트 생성
    
    - **rule_json**: 분석할 룰 JSON 객체
    
    Returns:
        마크다운/HTML 형식의 리포트와 룰 메타데이터
    """
    try:
        # 데이터 준비
        rule_data = request.rule_json.copy()
        
        # 중첩된 rule_json 처리
        if "rule_json" in rule_data and isinstance(rule_data["rule_json"], dict):
            print("중첩된 rule_json 필드를 발견했습니다. 내부 데이터를 사용합니다.")
            rule_data = rule_data["rule_json"]
        
        # 요청 데이터가 검증 결과 객체인지 확인
        if "is_valid" in rule_data and "issues" in rule_data and "structure" in rule_data:
            print("검증 결과 객체가 전송되었습니다. 원본 룰 데이터를 추출합니다.")
            # 이 경우 원래 룰 데이터는 읽을 수 없음
            # 응급 처리: 기본 오류 리포트 반환
            rule_id = "Unknown"
            rule_name = "Unknown Rule"
            
            error_report = f"""# 🔍 룰 형식 오류

## ⚠️ 데이터 형식 문제
검증 결과 객체가 룰 JSON으로 전송되었습니다. 아래 내용을 확인해 주세요:

1. 텍스트 상자에 검증 결과 객체가 아닌 원본 룰 JSON을 입력하세요.
2. 검증 결과가 아닌 원본 룰 데이터가 필요합니다.

## 🧾 오류 설명
검증 결과 객체는 룰 분석에 사용할 수 없습니다. 원본 룰 JSON을 입력해 주세요.

## 📝 조치 방법
1. 텍스트 상자를 비우고 원본 룰 JSON 데이터만 입력하세요.
2. 원본 룰은 다음과 같은 형식이어야 합니다:
```json
{
  "name": "룰 이름",
  "description": "룰 설명",
  "conditions": [...],
  "id": "R123",
  "priority": 1
}
```
"""
            
            return RuleReportResponse(
                report=error_report,
                rule_id=rule_id,
                rule_name=rule_name
            )
            
        # ruleId를 id로 변환
        if "ruleId" in rule_data:
            rule_data["id"] = rule_data.pop("ruleId")
            
        # message 필드 제거 (Rule 모델에 없음)
        if "message" in rule_data:
            del rule_data["message"]
        
        # conditions 변환 - dict일 경우에만 변환, 이미 리스트면 그대로 사용
        if "conditions" in rule_data:
            if isinstance(rule_data["conditions"], dict):
                rule_data["conditions"] = convert_conditions(rule_data["conditions"])
            elif not isinstance(rule_data["conditions"], list):
                rule_data["conditions"] = []
        else:
            rule_data["conditions"] = []
        
        try:
            # 룰 검증
            rule = Rule(**rule_data)
            analyzer = RuleAnalyzer()
            validation_result = await analyzer.analyze_rule(rule)
            
            # 리포트 생성
            report_service = RuleReportService()
            result = await report_service.generate_report(rule, validation_result)
            
            return RuleReportResponse(
                report=result["report"],
                rule_id=result["rule_id"],
                rule_name=result["rule_name"]
            )
        except Exception as e:
            print(f"룰 처리 실패: {str(e)}")
            
            # 직접 응급 리포트 생성
            rule_id = rule_data.get("id", "Unknown")
            rule_name = rule_data.get("name", "Unnamed Rule")
            description = rule_data.get("description", "No description")
            priority = rule_data.get("priority", "N/A")
            
            error_report = f"""# 🔍 룰 분석 리포트: {rule_id} - {rule_name}

## 📌 기본 정보
- **룰 ID**: {rule_id}
- **룰명**: {rule_name}
- **설명**: {description}
- **우선순위**: {priority}

## ⚠️ 룰 구조 문제
룰 JSON 형식에 문제가 있어 정확한 분석이 어렵습니다. 다음 사항을 확인해 주세요:

1. 모든 필드 이름이 올바른지 확인
2. 데이터 타입이 적절한지 확인 (숫자는 숫자 형식, 문자열은 문자열 형식)
3. 잘못된 연산자가 있는지 확인

## 🧾 오류 메시지
```
{str(e)}
```

## 📝 원본 룰 정보
```json
{json.dumps(rule_data, indent=2, ensure_ascii=False)}
```
"""
            
            return RuleReportResponse(
                report=error_report,
                rule_id=rule_id,
                rule_name=rule_name
            )
    except Exception as e:
        print(f"리포트 생성 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"리포트 생성 중 오류 발생: {str(e)}"
        ) 