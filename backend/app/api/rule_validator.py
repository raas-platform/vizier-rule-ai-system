from typing import Any, Dict, List
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from fastapi.responses import HTMLResponse

from ..models.rule import Rule, RuleAction, RuleCondition
from ..models.validation_result import (
    RuleJsonValidationRequest,
    RuleValidationResponse,
)
from ..services.rule_analyzer_v2 import RuleAnalyzerV2
from ..services.rule_parser import RuleParser
from ..utils.logger import get_logger
from ..services.llm_service import LLMService

router = APIRouter()
logger = get_logger(__name__)


@router.post("/validate-json", response_model=RuleValidationResponse)
async def validate_rule_json(request: RuleJsonValidationRequest):
    """
    Validate a rule using the new JSON format and check for logical issues

    - **request**: 룰 배열 데이터 (ruleUuid, ruleName, ruleMsg, conditionTree 포함)
    """
    try:
        # 사용자 제공 형식에서 룰 데이터 추출 (직접 배열)
        rules_data = request

        # 입력 데이터 검증 - 빈 데이터는 422 Validation Error
        if not rules_data:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Validation Error",
                    "message": "Rules data cannot be empty",
                    "type": "empty_request",
                },
            )

        if len(rules_data) == 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Validation Error",
                    "message": "Rules array cannot be empty",
                    "type": "empty_array",
                },
            )

        # 첫 번째 룰 처리 (배열의 첫 번째 룰)
        rule_data = rules_data[0]

        # Rule 객체로 변환 - 직접 Pydantic 모델 사용
        try:
            # 직접 Pydantic 모델로 변환하여 중첩 구조 보존
            rule = Rule(**rule_data)
        except Exception as e:
            # 실패 시 기존 파서 사용
            logger.warning(f"직접 Pydantic 변환 실패, 파서 사용: {str(e)}")
            rule = convert_json_to_rule(rule_data)

        rule_analyzer = RuleAnalyzerV2()
        result = await rule_analyzer.analyze_rule(rule)

        # 추가 정보 설정
        rule_name = getattr(rule, "name", getattr(rule, "ruleName", "Unknown Rule"))
        if result.is_valid:
            result.summary = f"룰 '{rule_name}'은(는) 유효합니다."
        else:
            issue_type_count = len(result.issue_counts)
            total_issue_count = len(result.issues)
            result.summary = (
                f"룰 '{rule_name}'에 {issue_type_count}가지 유형, "
                f"{total_issue_count}건의 오류가 발견되었습니다."
            )

        return RuleValidationResponse(
            is_valid=result.is_valid,
            summary=result.summary,
            issue_counts=result.issue_counts,
            issues=result.issues,
            structure=result.structure,
            ai_comment=result.ai_comment,
            field_analysis=result.field_analysis,
            logic_flow=result.logic_flow,
            performance_metrics=result.performance_metrics,
            quality_metrics=result.quality_metrics,
            report_metadata=result.report_metadata,
            ai_insights=result.ai_insights,
            improvement_recommendations=result.improvement_recommendations,
            risk_assessment=result.risk_assessment,
        )
    except HTTPException:
        # HTTPException은 그대로 전파
        raise
    except ValidationError as e:
        # Pydantic validation 에러는 422로 처리
        logger.warning(f"데이터 검증 실패: {str(e)}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": f"Invalid input data: {str(e)}",
                "type": "validation_error",
                "validation_details": (e.errors() if hasattr(e, "errors") else str(e)),
            },
        )
    except ValueError as e:
        # ValueError는 잘못된 입력 데이터로 간주하여 422로 처리
        logger.warning(f"잘못된 입력 데이터: {str(e)}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": str(e),
                "type": "invalid_input",
            },
        )
    except KeyError as e:
        # 필수 필드 누락은 422로 처리
        logger.warning(f"필수 필드 누락: {str(e)}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Validation Error",
                "message": f"Required field missing: {str(e)}",
                "type": "missing_field",
            },
        )
    except Exception as e:
        # 그 외 예상치 못한 에러는 500으로 처리
        error_msg = f"Internal server error during rule validation: {str(e)}"
        logger.error(f"API 내부 오류: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred during rule validation",
                "type": "internal_error",
            },
        )


def convert_json_to_rule(rule_json: Dict[str, Any]) -> Rule:
    """JSON 형식을 Rule 모델로 변환 - 새로운 형식 전용"""

    # 입력 데이터 검증
    if not isinstance(rule_json, dict):
        raise ValueError("Rule data must be a dictionary")

    if not rule_json:
        raise ValueError("Rule data cannot be empty")

    rule_parser = RuleParser()

    logger.debug(f"룰 데이터 키: {list(rule_json.keys())}")

    # 새로운 JSON 형식인지 확인 (ruleUuid, ruleName, ruleMsg, conditionTree 필드 존재)
    required_new_fields = ["ruleUuid", "ruleName", "ruleMsg", "conditionTree"]
    if all(key in rule_json for key in required_new_fields):
        # 새로운 형식 필수 필드 검증
        for field in required_new_fields:
            if rule_json.get(field) is None:
                raise ValueError(f"Required field '{field}' cannot be null or empty")

        logger.debug("새로운 JSON 형식으로 파싱")
        logger.debug(f"ruleName: {rule_json.get('ruleName')}")
        logger.debug(f"ruleUuid: {rule_json.get('ruleUuid')}")

        try:
            rule = rule_parser.parse_rule(rule_json)
            logger.debug(f"파싱된 Rule의 ruleName: {rule.ruleName}")
            logger.debug(f"파싱된 Rule의 name: {getattr(rule, 'name', 'None')}")
            return rule
        except ValidationError as e:
            raise ValueError(f"Rule validation failed: {str(e)}")

    # 기존 형식으로 처리 (하위 호환성 유지)
    logger.debug("기존 JSON 형식으로 파싱")
    return convert_legacy_json_to_rule(rule_json)


def convert_legacy_json_to_rule(rule_json: Dict[str, Any]) -> Rule:
    """기존 JSON 형식을 Rule 모델로 변환"""

    # 입력 데이터 검증
    if not isinstance(rule_json, dict):
        raise ValueError("Rule data must be a dictionary")

    # 기본값 설정 및 필수 필드 검증
    rule_id = rule_json.get("ruleId") or rule_json.get("id")
    rule_name = rule_json.get("name")

    # name 필드는 기존 형식에서 필수
    if not rule_name:
        rule_name = "Unnamed Rule"  # 기본값 제공하되 경고
        logger.warning("Rule name is missing, using default name")

    rule_description = rule_json.get("description", "")
    rule_priority = rule_json.get("priority", 1)
    rule_enabled = rule_json.get("enabled", True)

    # 조건 처리
    raw_conditions = rule_json.get("conditions", [])
    logger.debug(f"Raw conditions type: {type(raw_conditions)}")

    # 조건이 리스트인 경우 직접 처리
    conditions = []
    if isinstance(raw_conditions, list):
        # 리스트 내 각 조건을 RuleCondition 객체로 변환
        for i, condition in enumerate(raw_conditions):
            if (
                isinstance(condition, dict)
                and "field" in condition
                and "operator" in condition
            ):
                # 필수 필드 검증
                if not condition.get("field"):
                    raise ValueError(
                        f"Condition {i}: 'field' is required and cannot be empty"
                    )
                if not condition.get("operator"):
                    raise ValueError(
                        f"Condition {i}: 'operator' is required and cannot be empty"
                    )

                # 단순 조건 처리
                operator = map_operator(condition.get("operator", "eq"))
                conditions.append(
                    RuleCondition(
                        keyName=condition["field"],
                        dispName=condition["field"],
                        operator=operator,
                        value=str(condition.get("value", "")),
                        fieldDataType="String",
                        field=condition["field"],
                    )
                )
            elif isinstance(condition, dict) and "conditions" in condition:
                # 중첩 조건 처리
                nested = extract_nested_conditions(condition)
                if nested:
                    conditions.extend(nested)
            else:
                # 조건 형식이 잘못된 경우
                raise ValueError(
                    f"Condition {i}: Invalid condition format. "
                    f"Must have 'field' and 'operator' or 'conditions' field"
                )
    # 조건이 딕셔너리인 경우 (중첩 구조)
    elif isinstance(raw_conditions, dict):
        conditions = extract_conditions(raw_conditions)

    logger.debug(f"Final conditions count: {len(conditions)}")

    # 액션 변환
    actions = []
    if "message" in rule_json:
        message = rule_json["message"]
        if isinstance(message, list) and len(message) > 0:
            message = message[0]

        actions.append(
            RuleAction(action_type="display_message", parameters={"message": message})
        )

    # 명시적인 액션이 있으면 추가
    if "actions" in rule_json and isinstance(rule_json["actions"], list):
        for action in rule_json["actions"]:
            if isinstance(action, dict) and "action_type" in action:
                actions.append(
                    RuleAction(
                        action_type=action["action_type"],
                        parameters=action.get("parameters", {}),
                    )
                )

    # action 필드로 처리
    action = rule_json.get("action")

    # action이 없고 actions가 있으면 첫 번째 action 사용
    if not action and actions:
        first_action = actions[0]
        action = {
            "action_type": first_action.action_type,
            "parameters": first_action.parameters,
        }

    # 둘 다 없으면 기본 액션 설정
    if not action and not actions:
        action = {"action_type": "no_action", "parameters": {}}

    # Rule 객체 생성 및 반환 (기존 형식 지원을 위해)
    try:
        return Rule(
            id=rule_id,
            name=rule_name,
            description=rule_description,
            conditions=conditions,
            action=action,
            priority=rule_priority,
            enabled=rule_enabled,
        )
    except ValidationError as e:
        # Pydantic 검증 실패 시 명확한 에러 메시지 제공
        raise ValueError(f"Rule object creation failed: {str(e)}")


def extract_conditions(conditions_data: Any) -> List[RuleCondition]:
    """중첩된 조건 구조에서 조건 목록 추출"""
    result = []

    logger.debug(f"extract_conditions - Input type: {type(conditions_data)}")
    logger.debug(f"extract_conditions - Input: {conditions_data}")

    # 리스트 형태의 조건인 경우
    if isinstance(conditions_data, list):
        logger.debug(f"Condition is a list with {len(conditions_data)} items")
        for i, condition in enumerate(conditions_data):
            logger.debug(f"Processing list condition {i}: {condition}")

            if isinstance(condition, dict) and "field" in condition:
                # 단순 조건 처리
                operator = map_operator(condition.get("operator", "eq"))
                result.append(
                    RuleCondition(
                        keyName=condition["field"],
                        dispName=condition["field"],
                        operator=operator,
                        value=str(condition.get("value", "")),
                        fieldDataType="String",
                        field=condition["field"],
                    )
                )
                logger.debug(
                    f"Added simple condition from list for field: {condition['field']}"
                )
            elif isinstance(condition, dict) and "conditions" in condition:
                # 중첩 조건 처리
                nested_conditions = extract_nested_conditions(condition)
                result.extend(nested_conditions)
                logger.debug(
                    f"Added {len(nested_conditions)} nested conditions from list"
                )
        logger.debug(f"Returning {len(result)} conditions from list processing")
        return result

    # 딕셔너리 형태의 조건인 경우
    elif isinstance(conditions_data, dict):
        if "field" in conditions_data:
            # 단순 조건
            operator = map_operator(conditions_data.get("operator", "eq"))
            result.append(
                RuleCondition(
                    keyName=conditions_data["field"],
                    dispName=conditions_data["field"],
                    operator=operator,
                    value=str(conditions_data.get("value", "")),
                    fieldDataType="String",
                    field=conditions_data["field"],
                )
            )
        elif "conditions" in conditions_data:
            # 중첩 조건
            return extract_conditions(conditions_data["conditions"])
        elif "and" in conditions_data or "or" in conditions_data:
            # 논리 연산자 조건
            logical_op = "and" if "and" in conditions_data else "or"
            nested_conditions = conditions_data[logical_op]

            for nested_condition in nested_conditions:
                nested_result = extract_conditions(nested_condition)
                result.extend(nested_result)

    return result


def extract_nested_conditions(
    condition_data: Dict[str, Any],
) -> List[RuleCondition]:
    """중첩된 조건을 재귀적으로 처리"""
    result = []

    if "operator" in condition_data:
        group_operator = map_operator(condition_data.get("operator", "and"))
        nested_conditions = []

        # 내부 조건 처리
        if "conditions" in condition_data and isinstance(
            condition_data["conditions"], list
        ):
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
                        nested_conditions.append(
                            RuleCondition(
                                field=sub_condition["field"],
                                operator=operator,
                                value=sub_condition.get("value"),
                            )
                        )

        # 단일 조건으로 처리할 경우 (트리 구조 유지를 위해)
        if "field" in condition_data:
            result.append(
                RuleCondition(
                    field=condition_data["field"],
                    operator=group_operator,
                    value=condition_data.get("value"),
                    conditions=nested_conditions,
                )
            )
        # 그룹 조건으로 처리할 경우
        else:
            result.append(
                RuleCondition(
                    field="placeholder",
                    operator=group_operator,
                    value=None,
                    conditions=nested_conditions,
                )
            )
    # 단순 조건인 경우
    elif "field" in condition_data and "operator" in condition_data:
        operator = map_operator(condition_data.get("operator", "eq"))
        result.append(
            RuleCondition(
                field=condition_data["field"],
                operator=operator,
                value=condition_data.get("value"),
            )
        )

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
        "OR": "or",
    }

    return operator_map.get(operator, operator.lower())


@router.post("/generate-html-report")
async def generate_html_report(
    validation_result: Dict[str, Any]
) -> Dict[str, str]:
    """
    룰 검증 결과를 HTML 리포트로 변환
    
    Args:
        validation_result: 룰 검증 API의 JSON 응답
        
    Returns:
        Dict[str, str]: HTML 리포트와 메타데이터
    """
    try:
        llm_service = LLMService()
        
        # JSON을 문자열로 변환
        json_str = json.dumps(validation_result, ensure_ascii=False, indent=2)
        
        # HTML 리포트 생성 프롬프트 (사용자 템플릿 기반)
        html_prompt = f"""
다음 프리미엄 HTML 템플릿을 기반으로 룰 검증 결과 리포트를 생성해주세요.
실제 CSS 스타일과 JavaScript 코드를 모두 포함해서 완전한 HTML 문서를 만들어주세요.

JSON 데이터:
```json
{json_str}
```

다음과 같은 완전한 HTML 구조로 작성해주세요:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>룰 검증 결과 리포트</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            position: relative;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .rule-id {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .timestamp {{
            position: absolute;
            top: 30px;
            right: 30px;
            font-size: 0.9em;
            opacity: 0.8;
        }}
        
        .dashboard {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            border-left: 5px solid #667eea;
        }}
        
        .health-card {{
            text-align: center;
            border-left-color: #4CAF50;
        }}
        
        .health-score {{
            font-size: 3em;
            font-weight: bold;
            color: #4CAF50;
            margin: 15px 0;
        }}
        
        .issues-card {{
            border-left-color: #FF5722;
        }}
        
        .structure-card {{
            border-left-color: #2196F3;
        }}
        
        .issue-item {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 10px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid #f39c12;
        }}
        
        .issue-critical {{
            background: #f8d7da;
            border-color: #f5c6cb;
            border-left-color: #dc3545;
        }}
        
        .issue-warning {{
            background: #fff3cd;
            border-color: #ffeaa7;
            border-left-color: #ffc107;
        }}
        
        .issue-info {{
            background: #d1ecf1;
            border-color: #bee5eb;
            border-left-color: #17a2b8;
        }}
        
        .content-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin: 30px 0;
        }}
        
        .ai-analysis {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            margin: 30px 0;
        }}
        
        .action-items {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            margin: 30px 0;
        }}
        
        .action-item {{
            background: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }}
        
        .quality-metrics {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}
        
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }}
        
        .metric-score {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #eee;
            border-radius: 4px;
            margin: 10px 0;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #4CAF50);
            border-radius: 4px;
            transition: width 1s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 실제 데이터로 채워진 컨텐츠 -->
    </div>
    
    <script>
        // Chart.js 실제 코드
    </script>
</body>
</html>
"""

        if llm_service.is_model_available("gpt-3.5-turbo"):
            html_content = await llm_service.generate_text(
                html_prompt, "gpt-3.5-turbo"
            )
            
            return {
                "html_content": html_content,
                "content_type": "text/html",
                "status": "success",
                "rule_name": validation_result.get("report_metadata", {}).get("rule_name", "Unknown"),
                "generated_at": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=503, 
                detail="LLM 서비스를 사용할 수 없습니다"
            )
            
    except Exception as e:
        logger.error(f"HTML 리포트 생성 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"HTML 리포트 생성 실패: {str(e)}"
        )


@router.post("/download-html-report", response_class=HTMLResponse)
async def download_html_report(
    validation_result: Dict[str, Any]
) -> HTMLResponse:
    """
    룰 검증 결과를 HTML 리포트로 변환하고 바로 다운로드
    
    Args:
        validation_result: 룰 검증 API의 JSON 응답
        
    Returns:
        HTMLResponse: 다운로드 가능한 HTML 파일
    """
    try:
        llm_service = LLMService()
        
        # JSON을 문자열로 변환
        json_str = json.dumps(validation_result, ensure_ascii=False, indent=2)
        
        # HTML 리포트 생성 프롬프트 (사용자 템플릿 기반)
        html_prompt = f"""
다음 프리미엄 HTML 템플릿을 기반으로 룰 검증 결과 리포트를 생성해주세요.
실제 CSS 스타일과 JavaScript 코드를 모두 포함해서 완전한 HTML 문서를 만들어주세요.

JSON 데이터:
```json
{json_str}
```

다음과 같은 완전한 HTML 구조로 작성해주세요:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>룰 검증 결과 리포트</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            position: relative;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .rule-id {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .timestamp {{
            position: absolute;
            top: 30px;
            right: 30px;
            font-size: 0.9em;
            opacity: 0.8;
        }}
        
        .dashboard {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            border-left: 5px solid #667eea;
        }}
        
        .health-card {{
            text-align: center;
            border-left-color: #4CAF50;
        }}
        
        .health-score {{
            font-size: 3em;
            font-weight: bold;
            color: #4CAF50;
            margin: 15px 0;
        }}
        
        .issues-card {{
            border-left-color: #FF5722;
        }}
        
        .structure-card {{
            border-left-color: #2196F3;
        }}
        
        .issue-item {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 10px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid #f39c12;
        }}
        
        .issue-critical {{
            background: #f8d7da;
            border-color: #f5c6cb;
            border-left-color: #dc3545;
        }}
        
        .issue-warning {{
            background: #fff3cd;
            border-color: #ffeaa7;
            border-left-color: #ffc107;
        }}
        
        .issue-info {{
            background: #d1ecf1;
            border-color: #bee5eb;
            border-left-color: #17a2b8;
        }}
        
        .content-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin: 30px 0;
        }}
        
        .ai-analysis {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            margin: 30px 0;
        }}
        
        .action-items {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            margin: 30px 0;
        }}
        
        .action-item {{
            background: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }}
        
        .quality-metrics {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}
        
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }}
        
        .metric-score {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #eee;
            border-radius: 4px;
            margin: 10px 0;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #4CAF50);
            border-radius: 4px;
            transition: width 1s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 실제 데이터로 채워진 컨텐츠 -->
    </div>
    
    <script>
        // Chart.js 실제 코드
    </script>
</body>
</html>
"""

        if llm_service.is_model_available("gpt-3.5-turbo"):
            html_content = await llm_service.generate_text(
                html_prompt, "gpt-3.5-turbo"
            )
            
            # 파일명 생성
            rule_name = validation_result.get("report_metadata", {}).get("rule_name", "룰리포트")
            safe_filename = f"{rule_name.replace(' ', '_').replace('/', '_')}_report.html"
            
            return HTMLResponse(
                content=html_content,
                headers={
                    "Content-Disposition": f"attachment; filename={safe_filename}",
                    "Content-Type": "text/html; charset=utf-8"
                }
            )
        else:
            raise HTTPException(
                status_code=503, 
                detail="LLM 서비스를 사용할 수 없습니다"
            )
            
    except Exception as e:
        logger.error(f"HTML 리포트 다운로드 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"HTML 리포트 생성 실패: {str(e)}"
        )
