from fastapi import APIRouter, Depends, HTTPException
from app.models.validation_result import RuleJsonValidationRequest, RuleValidationResponse, ValidationResult, ConditionIssue
from app.models.rule import Rule, RuleCondition, RuleAction
from app.services.rule_analyzer import RuleAnalyzer
from typing import List, Dict, Any

router = APIRouter()

@router.post("/validate-json", response_model=RuleValidationResponse)
async def validate_rule_json(request: RuleJsonValidationRequest):
    """
    Validate a rule using the original JSON format and check for logical issues
    
    - **rule_json**: The rule JSON to validate
    """
    try:
        # 원본 JSON 형식에서 Rule 객체로 변환
        rule_json = request.rule_json
        
        # 입력 데이터 검증
        if not rule_json:
            raise ValueError("Rule JSON cannot be empty")
        
        rule = convert_json_to_rule(rule_json)
        
        rule_analyzer = RuleAnalyzer()
        result = await rule_analyzer.analyze_rule(rule)
        
        # 추가 정보 설정
        if result.is_valid:
            result.summary = f"룰 '{rule.name}'은(는) 유효합니다."
        else:
            issue_type_count = len(result.issue_counts)
            total_issue_count = len(result.issues)
            result.summary = f"룰 '{rule.name}'에 {issue_type_count}가지 유형, {total_issue_count}건의 오류가 발견되었습니다."
        
        return RuleValidationResponse(
            is_valid=result.is_valid,
            summary=result.summary,
            issue_counts=result.issue_counts,
            issues=result.issues,
            structure=result.structure,
            ai_comment=result.ai_comment
        )
    except Exception as e:
        # 오류 메시지를 자세히 기록하고 반환
        error_msg = f"Error validating rule: {str(e)}"
        print(f"API 오류: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )

def convert_json_to_rule(rule_json: Dict[str, Any]) -> Rule:
    """원본 JSON 형식을 Rule 모델로 변환"""
    
    # 기본값 설정
    rule_id = rule_json.get("ruleId") or rule_json.get("id")
    rule_name = rule_json.get("name", "Unnamed Rule")
    rule_description = rule_json.get("description", "")
    rule_priority = rule_json.get("priority", 1)
    rule_enabled = rule_json.get("enabled", True)
    
    # 조건 변환
    conditions = extract_conditions(rule_json.get("conditions", {}))
    
    # 액션 변환
    actions = []
    if "message" in rule_json:
        message = rule_json["message"]
        if isinstance(message, list) and len(message) > 0:
            message = message[0]
        
        actions.append(RuleAction(
            action_type="display_message",
            parameters={"message": message}
        ))
    
    # 명시적인 액션이 있으면 추가
    if "actions" in rule_json and isinstance(rule_json["actions"], list):
        for action in rule_json["actions"]:
            if isinstance(action, dict) and "action_type" in action:
                actions.append(RuleAction(
                    action_type=action["action_type"],
                    parameters=action.get("parameters", {})
                ))
    
    # 액션이 하나도 없으면 기본 액션 추가
    if not actions:
        actions.append(RuleAction(
            action_type="no_action",
            parameters={}
        ))
    
    return Rule(
        id=rule_id,
        name=rule_name,
        description=rule_description,
        conditions=conditions,
        actions=actions,
        priority=rule_priority,
        enabled=rule_enabled
    )

def extract_conditions(conditions_data: Dict[str, Any]) -> List[RuleCondition]:
    """중첩된 조건 구조에서 조건 목록 추출"""
    result = []
    
    # 단순 조건인 경우
    if isinstance(conditions_data, dict) and "field" in conditions_data and "operator" in conditions_data:
        # 연산자 변환 (>, < 등의 기호를 gt, lt 등으로 변환)
        operator = map_operator(conditions_data.get("operator", "eq"))
        
        result.append(RuleCondition(
            field=conditions_data["field"],
            operator=operator,
            value=conditions_data.get("value")
        ))
        return result
    
    # conditions 키가 있는 경우 (중첩 구조)
    if isinstance(conditions_data, dict) and "conditions" in conditions_data and isinstance(conditions_data["conditions"], list):
        # 상위 조건 (그룹)이 있는 경우
        if "operator" in conditions_data:
            # 그룹 조건 생성
            group_operator = map_operator(conditions_data.get("operator", "and"))
            nested_conditions = []
            
            # 내부 조건 처리
            for condition in conditions_data["conditions"]:
                if isinstance(condition, dict):
                    # 중첩 조건인 경우
                    if "conditions" in condition:
                        nested_sub_conditions = extract_nested_conditions(condition)
                        if nested_sub_conditions:
                            nested_conditions.extend(nested_sub_conditions)
                    # 단순 조건인 경우
                    elif "field" in condition and "operator" in condition:
                        operator = map_operator(condition.get("operator", "eq"))
                        nested_conditions.append(RuleCondition(
                            field=condition["field"],
                            operator=operator,
                            value=condition.get("value")
                        ))
            
            # 그룹 조건 추가
            if nested_conditions:
                # 현재 필드를 제거하여 논리 연산자 블록으로 처리
                result.append(RuleCondition(
                    field="placeholder",
                    operator=group_operator,
                    value=None,
                    conditions=nested_conditions
                ))
        # 그룹 연산자 없이 조건만 있는 경우
        else:
            for condition in conditions_data["conditions"]:
                if isinstance(condition, dict):
                    if "conditions" in condition:
                        nested_conditions = extract_nested_conditions(condition)
                        if nested_conditions:
                            result.extend(nested_conditions)
                    elif "field" in condition and "operator" in condition:
                        operator = map_operator(condition.get("operator", "eq"))
                        result.append(RuleCondition(
                            field=condition["field"],
                            operator=operator,
                            value=condition.get("value")
                        ))
    
    return result

def extract_nested_conditions(condition_data: Dict[str, Any]) -> List[RuleCondition]:
    """중첩된 조건을 재귀적으로 처리"""
    result = []
    
    if "operator" in condition_data:
        group_operator = map_operator(condition_data.get("operator", "and"))
        nested_conditions = []
        
        # 내부 조건 처리
        if "conditions" in condition_data and isinstance(condition_data["conditions"], list):
            for sub_condition in condition_data["conditions"]:
                if isinstance(sub_condition, dict):
                    # 중첩 조건인 경우 재귀 호출
                    if "conditions" in sub_condition:
                        sub_nested_conditions = extract_nested_conditions(sub_condition)
                        if sub_nested_conditions:
                            nested_conditions.extend(sub_nested_conditions)
                    # 단순 조건인 경우
                    elif "field" in sub_condition and "operator" in sub_condition:
                        operator = map_operator(sub_condition.get("operator", "eq"))
                        nested_conditions.append(RuleCondition(
                            field=sub_condition["field"],
                            operator=operator,
                            value=sub_condition.get("value")
                        ))
        
        # 단일 조건으로 처리할 경우 (트리 구조 유지를 위해)
        if "field" in condition_data:
            result.append(RuleCondition(
                field=condition_data["field"],
                operator=group_operator,
                value=condition_data.get("value"),
                conditions=nested_conditions
            ))
        # 그룹 조건으로 처리할 경우
        else:
            result.append(RuleCondition(
                field="placeholder",
                operator=group_operator,
                value=None,
                conditions=nested_conditions
            ))
    # 단순 조건인 경우
    elif "field" in condition_data and "operator" in condition_data:
        operator = map_operator(condition_data.get("operator", "eq"))
        result.append(RuleCondition(
            field=condition_data["field"],
            operator=operator,
            value=condition_data.get("value")
        ))
    
    return result

def map_operator(operator: str) -> str:
    """연산자 약어를 완전한 형태로 변환"""
    operator_map = {
        "eq": "==",
        "neq": "!=",
        "gt": ">",
        "lt": "<",
        "gte": ">=",
        "lte": "<=",
        "and": "and",
        "or": "or",
        "contains": "contains",
        "not_contains": "not_contains",
        "in": "in",
        "not_in": "not_in",
        "starts_with": "starts_with",
        "ends_with": "ends_with",
        
        # 이미 완전한 형태로 제공된 경우
        "==": "==",
        "!=": "!=",
        ">": ">",
        "<": "<",
        ">=": ">=",
        "<=": "<=",
        "AND": "and",
        "OR": "or"
    }
    
    return operator_map.get(operator, operator.lower()) 