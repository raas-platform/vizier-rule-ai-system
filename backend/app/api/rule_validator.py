from typing import Any, Dict, List
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from ..models.rule import Rule, RuleAction, RuleCondition
from ..models.validation_result import (
    RuleJsonValidationRequest,
    RuleValidationResponse,
)
from ..services.rule_analyzer_v2 import RuleAnalyzerV2
from ..services.rule_parser import RuleParser
from ..utils.logger import get_logger
from ..services.llm_service import LLMService
from urllib.parse import quote

router = APIRouter()
logger = get_logger(__name__)

# 템플릿 경로: 현재 파일 위치 기준 ../../templates
_template_dir = Path(__file__).resolve().parent.parent / "templates"
template_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)


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
    검증 결과를 바탕으로 HTML 리포트를 생성합니다 (Jinja2 사용).
    """
    try:
        template = template_env.get_template("report_template.html")
        # 템플릿에서 사용되는 주요 값 추출 (누락 시 기본값 제공)
        structure = validation_result.get("structure", {}) or {}
        report_metadata = validation_result.get("report_metadata", {}) or {}
        issues = validation_result.get("issues", []) or []

        # 룰 이름이 없으면 메타데이터 또는 다른 필드에서 시도, 결국 Unknown Rule
        rule_name = (
            report_metadata.get("rule_name")
            or validation_result.get("rule_name")
            or validation_result.get("ruleName")
            or "Unknown Rule"
        )

        # 템플릿에 전달할 컨텍스트 구성
        context = {
            **validation_result,
            "structure": structure,
            "report_metadata": report_metadata,
            "issues": issues,
            "rule_name": rule_name,
            "now": datetime.now(),
            "json_dumps": lambda d, i: json.dumps(d, indent=i, ensure_ascii=False),
        }
        html_content = template.render(**context)
        return {"report": html_content}
    except Exception as e:
        logger.error(f"HTML 리포트 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"HTML 리포트 생성 실패: {e}"
        )


@router.post("/download-html-report", response_class=HTMLResponse)
async def download_html_report(
    validation_result: Dict[str, Any]
) -> HTMLResponse:
    """
    검증 결과를 받아 HTML 리포트를 다운로드합니다.
    """
    try:
        # generate-html-report 함수를 호출하여 HTML 컨텐츠를 가져옵니다.
        report_data = await generate_html_report(validation_result)
        html_content = report_data.get("report", "")

        # 파일명 생성
        rule_name = validation_result.get("report_metadata", {}).get(
            "rule_name", "룰리포트"
        )
        # Content-Disposition 헤더는 ISO-8859-1(latin-1) 범위를 벗어나는 문자를 허용하지 않음.
        # RFC 6266 규격에 따라 filename* 로 UTF-8 값을 함께 제공한다.
        raw_filename = f"{rule_name.replace(' ', '_').replace('/', '_')}_report.html"
        # latin-1 로 인코딩 불가능한 경우 대비해 ASCII fallback 제공
        ascii_fallback = (
            raw_filename.encode("latin-1", "ignore").decode("latin-1") or "report.html"
        )
        encoded_utf8 = quote(raw_filename)

        # HTMLResponse로 컨텐츠와 헤더를 함께 반환합니다.
        # Content-Type 헤더에 charset=utf-8을 명시하여 인코딩 문제를 해결합니다.
        return HTMLResponse(
            content=html_content,
            headers={
                # 표준 및 브라우저 호환을 동시에 만족
                "Content-Disposition": (
                    f"attachment; filename=\"{ascii_fallback}\"; "
                    f"filename*=UTF-8''{encoded_utf8}"
                ),
                "Content-Type": "text/html; charset=utf-8",
            },
        )
    except Exception as e:
        logger.error(f"HTML 리포트 다운로드 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"HTML 리포트 다운로드 실패: {e}"
        )
