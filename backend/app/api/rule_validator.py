from typing import Any, Dict, List
import json
from datetime import datetime
from pathlib import Path
import time

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup  # HTML structure repair

from ..models.rule import Rule, RuleAction, RuleCondition
from ..models.validation_result import (
    RuleJsonValidationRequest,
    RuleValidationResponse,
)
from ..services.rule_analyzer_v2 import RuleAnalyzerV2
from ..services.rule_parser import RuleParser
from ..utils.logger import get_logger
from ..services.llm_service import LLMService, llm_service
from ..config import settings, SUPPORTED_MODELS
from urllib.parse import quote
import anthropic  # for explicit exception type
import re

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
    # 🟢 전체 처리 시간 측정 시작
    total_start_time = time.time()
    
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
            ai_summary_md=result.ai_summary_md,
            complexity_score=result.complexity_score,
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


# 내부 전용 HTML 리포트 생성 헬퍼 --------------------------------------------
async def _generate_html_report(validation_result: Dict[str, Any]) -> Dict[str, str]:
    """(라우터에 노출되지 않음) 검증 결과를 바탕으로 HTML 리포트를 생성합니다."""
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
        validation_model = report_metadata.get("validation_model", "unknown")
        report_model = validation_result.get("model_used", "template")

        # 템플릿 렌더링 시간 측정 -----------------------------------
        render_start = time.time()

        # 호출 전에 report_generation_time_ms 를 None 으로 초기화해 템플릿에서 N/A 대신 0ms 로 보일 수도 있음
        report_metadata.setdefault("report_generation_time_ms", None)

        context_base = {
            **validation_result,
            "structure": structure,
            "issues": issues,
            "rule_name": rule_name,
            "validation_model": validation_model,
            "report_model": report_model,
            "now": datetime.now(),
            "json_dumps": lambda d, i: json.dumps(d, indent=i, ensure_ascii=False),
        }

        # 1차 렌더링 – 시간 측정을 위해 빈 값으로 먼저 렌더
        html_content = template.render(**{**context_base, "report_metadata": report_metadata})

        render_time_ms = int((time.time() - render_start) * 1000)

        # 메타데이터 및 템플릿 모두에 시간 주입 -----------------------------------
        report_metadata["report_generation_time_ms"] = render_time_ms
        report_metadata["report_generated_by"] = "template"
        report_metadata["report_model"] = "template"

        # 2차 렌더링 – 실제 시간을 포함해 재렌더
        html_content = template.render(**{**context_base, "report_metadata": report_metadata})

        return {"report": html_content}
    except Exception as e:
        logger.error(f"HTML 리포트 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"HTML 리포트 생성 실패: {e}"
        )


# ---------------------------------------------------------------------------
# AI 기반 리포트 (Claude 등) ----------------------------------------------------
# ---------------------------------------------------------------------------


@router.post("/generate-ai-html-report")
async def generate_ai_html_report(validation_result: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("🚀 generate_ai_html_report 함수 시작")
    """LLM(Claude/GPT 등) 를 사용해 동적 · 트렌디한 HTML 리포트를 생성합니다.

    전달 JSON(validation_result)에 "preferred_model" 키가 있으면 해당 모델을 우선 시도합니다.
    """

    # --- ai_summary_md 는 리포트에 불필요하므로 제거 ---------------------------
    validation_result = dict(validation_result)  # shallow copy
    validation_result.pop("ai_summary_md", None)

    # 1) 요청 본문에 preferred_model 지정 시 최우선 사용
    user_preferred: str | None = validation_result.pop("preferred_model", None)  # 유저 지정 모델은 검증 데이터와 분리
    logger.info(f"📝 사용자 선호 모델: {user_preferred}")

    # 2) Claude 계열 중 "가장 최신" 모델을 자동 탐색
    #    SUPPORTED_MODELS 목록에서 claude-* 패턴을 찾아 버전·릴리스 날짜 기준 내림차순 정렬
    def _claude_sort_key(model_name: str) -> tuple[int, int]:
        """정렬용 키: (메이저버전, 릴리스날짜) – 높은 값이 최신"""
        # 패턴 1) claude-4-sonnet-20241022
        m = re.search(r"claude-(\d+)-.*-(\d{8})$", model_name)
        if m:
            return int(m.group(1)), int(m.group(2))

        # 패턴 2) claude-sonnet-4-20250514 (역순)
        m2 = re.search(r"claude-.*-(\d+)-(\d{8})$", model_name)
        if m2:
            return int(m2.group(1)), int(m2.group(2))

        # 날짜·버전이 없으면 가장 오래된 것으로 간주
        return (0, 0)

    claude_models = [m for m in SUPPORTED_MODELS.keys() if m.startswith("claude")]
    # 최신 버전/날짜가 먼저 오도록 정렬
    sorted_claude = sorted(claude_models, key=_claude_sort_key, reverse=True)

    # 유저 지정 모델(Claude 한정)을 최우선으로, 나머지는 최신순으로
    preferred_models: list[str] = []

    # 0) 유저 지정 Claude 모델 최우선
    if user_preferred and user_preferred.startswith("claude"):
        preferred_models.append(user_preferred)

    # 1) Claude 3.7 우선 (속도 테스트용)
    if "claude-3-7-sonnet-20250219" not in preferred_models:
        preferred_models.append("claude-3-7-sonnet-20250219")
    
    # 2) Claude 4 폴백
    if "claude-sonnet-4-20250514" not in preferred_models:
        preferred_models.append("claude-sonnet-4-20250514")

    # 3) 환경 설정의 report_default_model / fallback_model 추가
    if settings.report_default_model.startswith("claude") and settings.report_default_model not in preferred_models:
        preferred_models.append(settings.report_default_model)

    if settings.report_fallback_model.startswith("claude") and settings.report_fallback_model not in preferred_models:
        preferred_models.append(settings.report_fallback_model)

    # 2) 나머지 Claude 모델 최신순
    preferred_models.extend(m for m in sorted_claude if m not in preferred_models)

    # Claude 4와 3.7을 우선 시도하고, 실패하면 가용한 다른 모델 사용
    candidate_models = []
    
    logger.info(f"=== 모델 선택 시작 ===")
    logger.info(f"선호 모델 목록: {preferred_models}")
    
    # 🟢 1순위: Claude 3.7 (HTML 리포트 생성 최적화)
    if "claude-3-7-sonnet-20250219" in preferred_models:
        candidate_models.append("claude-3-7-sonnet-20250219")
        logger.info("✅ Claude 3.7 (claude-3-7-sonnet-20250219) 1순위로 추가 - HTML 리포트 생성 최적화")
    
    # 🟢 2순위: Claude 4 (품질 폴백)
    if "claude-sonnet-4-20250514" in preferred_models:
        candidate_models.append("claude-sonnet-4-20250514")
        logger.info("✅ Claude 4 (claude-sonnet-4-20250514) 2순위로 추가 - 품질 폴백")
    
    # 3순위: 나머지 모델들 (가용성 체크 적용)
    for model in preferred_models:
        if model not in candidate_models:
            # Claude 4와 3.7은 가용성 체크 완전 우회
            if model in ["claude-sonnet-4-20250514", "claude-3-7-sonnet-20250219"]:
                candidate_models.append(model)
                logger.info(f"✅ {model} 추가 (가용성 체크 우회 - 우선 모델)")
            else:
                is_available = llm_service.is_model_available(model)
                if is_available:
                    candidate_models.append(model)
                    logger.info(f"✅ {model} 추가 (가용성 체크 통과)")
                else:
                    logger.warning(f"❌ {model} 제외 (가용성 체크 실패)")
    
    logger.info(f"최종 후보 모델 목록: {candidate_models}")
    
    if not candidate_models:
        logger.error("❌ 사용 가능한 Claude 모델이 없습니다!")
        raise HTTPException(status_code=503, detail="Claude 모델이 현재 사용 불가합니다.")

    # Claude 중에서도 첫 사용 가능 모델만 사용 (추가 폴백 없음)

    # 프롬프트 구성 -----------------------------------------------------------

    # (1) System Prompt – 기술적 제약을 모두 제거하고 크리에이티브 톤으로 교체
    system_prompt = (
        """당신은 완벽한 HTML 문서 구조를 작성하는 전문가입니다.

        ## 📱 **Vue 컨테이너 최적화 (최우선 요구사항)**

        **반드시 Vue 컨테이너(max-width: 890px)에 최적화하세요:**

        1. **컨테이너 설정**
           - 최대 너비: 890px (Vue 컨테이너와 동일)
           - 반응형 디자인: width: 100% (모바일 대응)
           - 적절한 패딩: 24-32px (여백 확보)

        2. **가독성 최우선**
           - **본문**: 12-14px (읽기 편한 크기)
           - **제목**: H1 18px, H2 16px (최대 18px 이하)
           - **줄 간격**: 1.5-1.6 (편안한 읽기)
           - **여백**: 충분한 공간으로 시각적 편안함 제공

        3. **섹션별 공간 배분**
           - **헤더**: 룰명, 상태, 점수 - 시각적으로 강조
           - **AI 통찰**: 가장 중요한 섹션 - 충분한 공간 할당
           - **핵심 메트릭**: 카드 형태로 명확히 구분
           - **중요 이슈**: 테이블 또는 리스트로 깔끔하게 정리

        4. **레이아웃 전략**
           - 단일 컬럼 또는 2컬럼 그리드 (890px 너비 활용)
           - 카드 기반 디자인으로 정보 구분
           - 적절한 그림자와 테두리로 시각적 구분
           - 색상 대비로 중요도 표현

        ## 🔍 1단계: JSON 데이터 분석 (필수)

        **먼저 제공된 JSON을 완전히 분석하세요:**

        1. **구조 파악**
           - 최상위 키들 식별 (quality_metrics, issues, field_analysis 등)
           - 각 섹션의 데이터 타입과 개수 확인
           - 중첩된 객체와 배열 구조 파악

        2. **중요도 평가 및 선별**
           - 사용자에게 가장 유용한 정보가 무엇인지 판단
           - 핵심 메트릭과 부차적 정보 구분
           - **Vue 컨테이너에서 스크롤 없이 편안하게 볼 수 있는 양 선택**

        3. **필수 정보 추출**
           - 룰명, 상태, 점수 등 핵심 정보
           - 심각한 이슈들 (error/warning 우선, 주요 이슈 모두 표시)
           - 모든 품질 지표 (공간이 충분하므로 전체 표시 가능)

        ## 🏗️ 2단계: HTML 구조 설계

        **Vue 컨테이너에 최적화된 읽기 쉬운 HTML 구조 설계:**

        1. **필수 섹션 구조**
           html
           <div class="vue-container">
             <header class="report-header"><!-- 룰 정보 (필수) - 크고 명확하게 --></header>
             <section class="ai-insights-section"><!-- 🤖 AI 통찰 & 의견 (필수 - 최우선 부각!) --></section>
             <section class="metrics-grid"><!-- 품질 지표들 (카드 형태) --></section>
             <section class="issues-section"><!-- 이슈들 (테이블 또는 카드) --></section>
             <footer class="model-info"><!-- 모델 정보 --></footer>
           </div>
           

        2. **가독성 우선 원칙**
           - 충분한 여백과 간격으로 편안한 읽기 환경 제공
           - 중요한 정보는 크게, 부가 정보는 적당히
           - 색상과 타이포그래피로 정보 계층 구분

        ## 🎨 3단계: 완전한 HTML 구현

        **Vue 컨테이너 최적화 CSS 필수 포함:**
        ```css
        .vue-container {
          max-width: 890px;
          width: 100%;
          margin: 0 auto;
          padding: 24px;
          font-family: 'Arial', sans-serif;
          font-size: 14px;
          line-height: 1.5;
          color: #333;
        }
        
        h1 {
          font-size: 18px;
          margin-bottom: 24px;
          color: #1a1a1a;
        }
        
        h2 {
          font-size: 16px;
          margin: 24px 0 16px 0;
          color: #2a2a2a;
        }
        
        .card {
          background: white;
          border-radius: 8px;
          padding: 20px;
          margin-bottom: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        ```

        ## 📋 필수 구현 항목 (Vue 컨테이너 최적화)

        **반드시 포함해야 할 핵심 정보:**

        ✅ **헤더 섹션 (필수 - 크고 명확하게)**
          * 룰명 (rule_name 또는 ruleName) - 18px 크기
          * 검증 상태 (is_valid 기반) - 시각적 아이콘 포함
          * 전체 요약 점수 - 큰 숫자로 강조
          * **충분한 여백으로 시각적 임팩트 제공**

        ✅ **AI 통찰 & 의견 (필수 - 가장 중요!)**
          * ai_comment: AI의 핵심 조언을 큰 글씨로 강조 표시
          * ai_insights: AI가 발견한 패턴이나 위험 신호를 카드로 부각
          * improvement_recommendations: AI 권장사항 (모든 항목 표시)
          * risk_assessment: AI의 위험도 평가를 시각적으로 강조
          * **14-18px 범위의 폰트로 읽기 쉽게 표현**

        ✅ **품질 메트릭 (필수 - 카드 그리드)**
          * quality_metrics의 모든 지표 표시 (공간 충분)
          * 각 메트릭을 큰 카드 형태로 명확하게 표시
          * 3×2 또는 2×3 그리드로 여유있지만 균형있는 배치
          * **프로그레스 바나 게이지로 시각화**

        ✅ **이슈 목록 (필수 - 읽기 쉬운 리스트)**
          * issues 배열의 모든 중요 이슈 표시
          * error/warning 심각도별 색상 구분
          * 카드 또는 테이블 형태로 여유있게 표시
          * **12-16px 폰트로 읽기 편하게**

        ## 🧠 추가 구현 항목 (공간이 충분할 때)

        **Vue 컨테이너는 공간이 충분하므로 더 많은 정보 포함 가능:**

        📊 **상세 분석 데이터**
          * field_analysis의 모든 중요 정보
          * performance_metrics 상세 표시
          * logic_flow 정보 (있는 경우)
          * **스크롤을 통해 모든 정보 제공 가능**

        ## 🚀 구현 원칙

        **가독성 최우선:**
        - 12-16px 폰트로 편안한 읽기 환경 제공
        - 충분한 여백과 간격으로 시각적 편안함
        - 스크롤이 있어도 괜찮으니 정보를 크고 명확하게 표시

        **AI 중심 설계:**
        - AI의 통찰과 의견을 가장 눈에 띄는 위치에 배치
        - AI 코멘트는 큰 글씨와 특별한 스타일로 강조
        - AI 권장사항은 실행 가능한 형태로 명확하게 표현

        **Vue 컨테이너 활용:**
        - 890px 너비를 최대한 활용한 레이아웃
        - 카드 기반 디자인으로 정보 구분
        - 2컬럼 그리드로 공간 효율성과 가독성 균형

        **품질 기준:**
        - 일반 브라우저에서 완벽 작동
        - Vue 컨테이너 안에서 자연스럽게 렌더링
        - 모든 중요 정보 포함 (공간 제약 없음)

        **디자인 자유도:**
        - 색상, 레이아웃, 스타일 완전 자유
        - **Chart.js 사용 금지**: 렌더링 오류 방지
        - CSS 기반 시각화만 사용 (프로그레스 바, 게이지 등)
        - 2025년 트렌드 적용 (카드 디자인, 넉넉한 여백)

        ## 🎯 최종 요구사항

        **출력 규칙:**
        - HTML 코드만 출력 (설명 없음)
        - <!DOCTYPE html>로 시작
        - Vue 컨테이너 최적화 CSS 반드시 포함
        - **Chart.js나 외부 차트 라이브러리 사용 금지**
        - 완전히 닫힌 모든 태그

        **판단 기준:**
        - HTML 문법이 완벽한가?
        - Vue 컨테이너(890px)에 적합한가?
        - 12px 이상 폰트로 읽기 쉬운가?
        - 차트 없이도 정보 전달이 명확한가?
        - 핵심 메시지를 효과적으로 전달하는가?

        **Vue 컨테이너에 최적화된** 완전하고 아름다우면서도 **읽기 쉬운** 대시보드를 창조하세요!
        공간 제약 없이 모든 중요 정보를 크고 명확하게 표시하세요! 📱✨"""
    )

    # JSON 을 그대로 전달하되 너무 길어지는 것을 방지하기 위해 최대 3000자 제한
    validation_json_str = json.dumps(validation_result, ensure_ascii=False, indent=2)
    # Claude-3 Opus 는 200k tokens 를 지원하므로 최대 20,000자(약 5k tokens) 까지는 그대로 전달
    max_json_chars = 20000  # 20k chars ≈ 5k tokens – 메트릭 손실 방지 목적
    if len(validation_json_str) > max_json_chars:
        logger.info(
            "validation_result JSON 길이 %d자 → %d자까지 전달, 나머지 Trim",
            len(validation_json_str),
            max_json_chars,
        )
        validation_json_str = validation_json_str[:max_json_chars] + "\n/* ... trimmed ... */"

    # (2) User Prompt – 예시 HTML 스니펫 제거, JSON 데이터만 포함
    validation_model_name = (
        validation_result.get("report_metadata", {})
        .get("validation_model", "unknown")
    )

    # place holder uses Python format key {report_model}
    def build_prompt(model_name: str) -> str:
        """모델명 주입하여 최종 프롬프트 구성 (format 치환 오류 방지)"""
        # 추가 시간 정보 추출
        meta = validation_result.get("report_metadata", {})
        analysis_ms = meta.get("total_analysis_time_ms", "unknown")
        report_ms = meta.get("report_generation_time_ms", "unknown")

        header = (
            "아래 JSON 데이터는 리포트 제작에 활용할 정보입니다. 이 데이터를 분석하여 창의적이고 현대적인 단일 HTML 파일을 작성해 주세요.\n"
            "\n* 반드시 HTML 하단(footer) 또는 눈에 띄지 않는 작은 글씨 영역에 다음 정보를 표기하세요.\n"
            f"  - 검증 모델(validation_model): {validation_model_name}\n"
            f"  - 리포트 모델(report_model): {model_name}\n"
            f"  - 분석 총 시간(total_analysis_time_ms): {analysis_ms}ms\n"
            f"  - 리포트 생성 시간(report_generation_time_ms): {report_ms}ms\n"
        )

        user_prompt = header + "```json\n" + validation_json_str + "\n```"
        return system_prompt + "\n\n" + user_prompt

    gen_start = time.time()

    # QC 실패 시에도 마지막 AI 결과를 보존해 최종 폴백으로 사용
    last_ai_html: str | None = None
    last_ai_model: str | None = None

    # 디버그 코드 제거 - 정상적인 모델 선택 로직 사용
    logger.info(f"🔄 정상 모델 선택 로직 사용 - candidate_models: {candidate_models}")
    
    for i, model_id in enumerate(candidate_models):
        try:
            logger.info(f"🔄 모델 시도 {i+1}/{len(candidate_models)}: {model_id}")
            
            full_prompt = build_prompt(model_id)

            # 모든 모델은 통일된 LLM 서비스를 통해 처리
            logger.info(f"🤖 LLM 서비스 호출 시작 - 모델: {model_id}")
            html = await llm_service.generate_text(full_prompt, model_id)
            logger.info(f"✅ {model_id} LLM 서비스 응답 수신 성공")

            # OpenAI 응답이 HTML이 아닐 경우 거부(refusal)로 간주하고 실패 처리
            if not _looks_like_html(html) or "i'm sorry" in html.lower():
                refusal_snippet = html.strip().replace("\n", " ")[:200]
                logger.warning(
                    f"❌ {model_id} HTML이 아닌 응답 또는 거부 응답: '{refusal_snippet}...'",
                )
                raise ValueError(f"OpenAI 모델 거부/비HTML 응답: {refusal_snippet}")

            # 마크다운 코드 블록 제거 (```html ... ``` 형태)
            html = _remove_markdown_codeblock(html)
            
            gen_ms = int((time.time() - gen_start) * 1000)
            logger.info(f"✅ {model_id} 리포트 생성 성공 ({gen_ms}ms)")

            # --- 후처리: 라이브러리 스크립트 선행, 초기화 스크립트 후행 -----------------
            try:
                # 1) 구조 복원 – 잘못 닫힌 태그/속성 자동 보정
                html = _sanitize_html(html)
                html = _ensure_raw_json_script(html, validation_result)
                # 2) 스크립트 로딩 순서 보정
                html = _reorder_scripts(html)
                # 3) Chart.js 관련 코드 제거 (렌더링 오류 방지)
                html = _remove_chartjs_code(html)
                # 4) 리포트 생성 시간 토큰 치환
                html = html.replace("__REPORT_GEN_MS__", str(gen_ms))
                logger.info(f"✅ {model_id} HTML 후처리 완료")
            except Exception as _rs_err:
                logger.warning(f"⚠️ {model_id} HTML 후처리 실패: {_rs_err}")

            # QC 결과 보존
            last_ai_html = html
            last_ai_model = model_id

            # 🟢 validation_result에 리포트 생성시간 저장 (프롬프트 및 HTML 표시용)
            if "report_metadata" not in validation_result:
                validation_result["report_metadata"] = {}
            validation_result["report_metadata"]["report_generation_time_ms"] = gen_ms
            validation_result["report_metadata"]["report_model"] = model_id
            validation_result["report_metadata"]["report_generated_by"] = "llm"

            # Claude 4와 3.7은 QC 우회하여 즉시 반환 (사용자 요청)
            if model_id in ["claude-sonnet-4-20250514", "claude-3-7-sonnet-20250219"]:
                logger.info(f"🚀 {model_id} QC 우회하여 즉시 반환 (선호 모델)")
                return {
                    "report": html,
                    "model_used": model_id,
                    "generation_time_ms": str(gen_ms),
                    "report_generated_by": "llm",
                    "note": "qc_bypassed_preferred_model",
                }
            
            # 다른 모델들은 QC 통과 시 즉시 반환, 실패하면 다음 모델 시도
            logger.info(f"🔍 {model_id} QC 검사 수행 중...")
            if _passes_qc(html, validation_result):
                logger.info(f"✅ {model_id} QC 통과 - 최종 반환")
                return {
                    "report": html,
                    "model_used": model_id,
                    "generation_time_ms": str(gen_ms),
                    "report_generated_by": "llm",
                }
            else:
                logger.warning(f"❌ {model_id} QC 실패 - 다음 모델로 이동")
                if i < len(candidate_models) - 1:
                    logger.info(f"⏭️ 다음 모델로 이동: {candidate_models[i+1]}")
                continue
        except anthropic.BadRequestError as ae:  # granular logging for Anthropic
            err_payload = getattr(ae, "error", {})  # type: ignore[attr-defined]
            err_type = err_payload.get("type", "unknown") if isinstance(err_payload, dict) else "unknown"
            err_msg = err_payload.get("message", str(ae)) if isinstance(err_payload, dict) else str(ae)

            logger.error(
                f"💥 Anthropic API 오류({model_id}) — type: {err_type}, message: {err_msg}",
                exc_info=True,
            )
            # 크레딧 부족 오류면 즉시 중단하고 402 반환
            if "credit balance is too low" in err_msg.lower():
                logger.error(f"💳 {model_id} 크레딧 부족으로 실패")
                raise HTTPException(
                    status_code=402,
                    detail="Anthropic 크레딧이 부족합니다. 결제를 완료한 후 다시 시도해 주세요.",
                )
            # 기타 Anthropic 오류 → 다음 모델 시도
            if i < len(candidate_models) - 1:
                logger.info(f"⏭️ Anthropic 오류로 다음 모델로 이동: {candidate_models[i+1]}")
            continue
        except Exception as e:
            # 모델 단위 실패 → 다음 후보 시도
            logger.warning(
                f"❌ 모델 {model_id} 시도 실패: {str(e)}")
            if "크레딧" in str(e) or "credit" in str(e).lower():
                logger.error(f"💳 {model_id} 크레딧 부족으로 실패")
            elif "rate limit" in str(e).lower():
                logger.error(f"⏱️ {model_id} 요청 한도 초과로 실패")
            elif "timeout" in str(e).lower():
                logger.error(f"⏰ {model_id} 타임아웃으로 실패")
            else:
                logger.error(f"⚠️ {model_id} 알 수 없는 오류: {str(e)}")
                
            if i < len(candidate_models) - 1:
                logger.info(f"⏭️ 오류로 다음 모델로 이동: {candidate_models[i+1]}")
            else:
                logger.error("💥 모든 후보 모델 시도 완료 - 실패")

    # 모든 Claude 후보 모델 시도 실패 – OpenAI 폴백 시도 ---------------------------------
    logger.error(
        "💥 Claude 모델 전부 실패했습니다. OpenAI 모델 폴백을 시도합니다.",
    )

    # 1차 폴백: OpenAI 계열 모델 시도 --------------------------------------
    openai_priority = [
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    openai_candidates = [m for m in openai_priority if llm_service.is_model_available(m)]
    logger.info(f"🔄 OpenAI 폴백 후보 모델: {openai_candidates}")

    if openai_candidates:
        for j, model_id in enumerate(openai_candidates):
            try:
                logger.info(f"🔄 OpenAI 폴백 시도 {j+1}/{len(openai_candidates)}: {model_id}")
                full_prompt_fb = build_prompt(model_id)
                html = await llm_service.generate_text(full_prompt_fb, model_id)
                logger.info(f"✅ {model_id} OpenAI 응답 수신 성공")
                
                # Claude 실패 → OpenAI 생성 결과에 대해서도 스크립트 순서 및 차트 초기화 보강
                try:
                    html = _sanitize_html(html)
                    html = _ensure_raw_json_script(html, validation_result)
                    html = _reorder_scripts(html)
                    html = _remove_chartjs_code(html)
                    logger.info(f"✅ {model_id} OpenAI HTML 후처리 완료")
                except Exception as _rs_err:
                    logger.warning(f"⚠️ {model_id} OpenAI HTML 후처리 실패: {_rs_err}")

                # QC 결과 보존
                last_ai_html = html
                last_ai_model = model_id

                # 🟢 validation_result에 리포트 생성시간 저장 (OpenAI 폴백)
                if "report_metadata" not in validation_result:
                    validation_result["report_metadata"] = {}
                validation_result["report_metadata"]["report_generation_time_ms"] = int((time.time() - gen_start) * 1000)
                validation_result["report_metadata"]["report_model"] = model_id
                validation_result["report_metadata"]["report_generated_by"] = "llm"

                logger.info(f"🔍 {model_id} OpenAI QC 검사 수행 중...")
                if not _passes_qc(html, validation_result):
                    logger.warning(f"❌ {model_id} OpenAI QC 실패 - 다음 폴백으로 이동")
                    if j < len(openai_candidates) - 1:
                        logger.info(f"⏭️ 다음 OpenAI 모델로 이동: {openai_candidates[j+1]}")
                    raise ValueError("qc_failed")

                logger.info(f"✅ {model_id} OpenAI 모델로 리포트 생성 성공 – Claude 실패 폴백 완료")
                gen_ms = int((time.time() - gen_start) * 1000)
                return {
                    "report": html,
                    "model_used": model_id,
                    "generation_time_ms": str(gen_ms),
                    "report_generated_by": "llm",
                    "note": "claude_failed_openai_fallback",
                }
            except Exception as oe:
                logger.warning(f"❌ OpenAI 모델 {model_id} 시도 실패: {str(oe)}")
                if "크레딧" in str(oe) or "credit" in str(oe).lower():
                    logger.error(f"💳 {model_id} OpenAI 크레딧 부족으로 실패")
                elif "rate limit" in str(oe).lower():
                    logger.error(f"⏱️ {model_id} OpenAI 요청 한도 초과로 실패")
                elif "timeout" in str(oe).lower():
                    logger.error(f"⏰ {model_id} OpenAI 타임아웃으로 실패")
                else:
                    logger.error(f"⚠️ {model_id} OpenAI 알 수 없는 오류: {str(oe)}")
                    
                if j < len(openai_candidates) - 1:
                    logger.info(f"⏭️ OpenAI 오류로 다음 모델로 이동: {openai_candidates[j+1]}")
                else:
                    logger.error("💥 모든 OpenAI 후보 모델 시도 완료 - 실패")
    else:
        logger.warning("❌ 사용 가능한 OpenAI 모델이 없습니다. 템플릿 폴백으로 진행합니다.")

    # 2a) 모든 AI 후보가 QC 불합격 – QC 미통과 결과라도 반환 ------------------
    if last_ai_html is not None:
        gen_ms = int((time.time() - gen_start) * 1000)
        
        # 🟢 validation_result에 리포트 생성시간 저장 (마지막 AI 결과)
        if "report_metadata" not in validation_result:
            validation_result["report_metadata"] = {}
        validation_result["report_metadata"]["report_generation_time_ms"] = gen_ms
        validation_result["report_metadata"]["report_model"] = last_ai_model or "unknown"
        validation_result["report_metadata"]["report_generated_by"] = "llm"
        
        logger.warning(f"⚠️ 모든 AI 모델이 QC 실패 - 마지막 AI 결과 반환 ({last_ai_model})")
        return {
            "report": last_ai_html,
            "model_used": last_ai_model or "unknown",
            "generation_time_ms": str(gen_ms),
            "report_generated_by": "llm",
            "note": "all_ai_failed_qc_returning_last_html",
        }

    # 2b) AI 결과 자체를 받지 못한 경우 – Jinja 템플릿 기반 폴백 ----------
    try:
        logger.info("🔄 템플릿 기반 폴백 시도 중...")
        template_report = await _generate_html_report(validation_result)
        gen_ms = int((time.time() - gen_start) * 1000)
        template_report["model_used"] = "template_fallback"
        template_report["note"] = "claude_and_openai_failed_template_fallback"
        template_report["generation_time_ms"] = str(gen_ms)
        template_report["report_generated_by"] = "template"
        logger.info("✅ 템플릿 HTML 폴백으로 리포트 생성 완료 (Claude & OpenAI 실패)")
        return template_report
    except Exception as template_err:
        logger.error(
            "💥 템플릿 기반 폴백에도 실패했습니다. 간이 HTML 리포트를 반환합니다.",
            exc_info=template_err,
        )

        # 3차 폴백: 최소한의 Raw JSON 표시 HTML -----------------------------
        safe_json = json.dumps(validation_result, ensure_ascii=False, indent=2)
        minimal_html = (
            "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
            "<title>AI 리포트 생성 실패</title>"
            "<style>body{font-family:monospace;white-space:pre-wrap}</style></head><body>"
            "<h1>AI 리포트 생성 실패 – Raw 데이터</h1><pre>" + safe_json + "</pre></body></html>"
        )
        gen_ms = int((time.time() - gen_start) * 1000)
        
        # 🟢 validation_result에 리포트 생성시간 저장 (Static 폴백)
        if "report_metadata" not in validation_result:
            validation_result["report_metadata"] = {}
        validation_result["report_metadata"]["report_generation_time_ms"] = gen_ms
        validation_result["report_metadata"]["report_model"] = "static_fallback"
        validation_result["report_metadata"]["report_generated_by"] = "static"
        
        return {
            "report": minimal_html,
            "model_used": "static_fallback",
            "note": "all_ai_and_template_failed_static_html",
            "generation_time_ms": str(gen_ms),
            "report_generated_by": "static",
        }


@router.post("/download-ai-html-report", response_class=HTMLResponse)
async def download_ai_html_report(validation_result: Dict[str, Any]) -> HTMLResponse:
    """AI 기반 HTML 리포트를 즉시 파일 다운로드 형태로 제공합니다."""
    try:
        # AI 리포트 생성
        report_data = await generate_ai_html_report(validation_result)
        html_content = report_data.get("report", "")

        # 파일명 생성 – 룰 이름이 없으면 기본값 사용
        rule_name = validation_result.get("report_metadata", {}).get("rule_name", "AI_Report")
        raw_filename = f"{rule_name.replace(' ', '_').replace('/', '_')}_AI_report.html"

        # Content-Disposition용 ASCII‧UTF-8 파일명 준비
        ascii_fallback = raw_filename.encode("latin-1", "ignore").decode("latin-1") or "ai_report.html"
        encoded_utf8 = quote(raw_filename)

        # HTMLResponse 반환 (다운로드)
        return HTMLResponse(
            content=html_content,
            headers={
                "Content-Disposition": (
                    f"attachment; filename=\"{ascii_fallback}\"; "
                    f"filename*=UTF-8''{encoded_utf8}"
                ),
                "Content-Type": "text/html; charset=utf-8",
                # 사용된 모델 정보를 헤더로 추가 (선택)
                "X-Model-Used": report_data.get("model_used", "unknown"),
            },
        )
    except Exception as e:
        logger.error(f"AI HTML 리포트 다운로드 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI HTML 리포트 다운로드 실패: {e}")


def _looks_like_html(text: str) -> bool:
    """간단한 휴리스틱으로 HTML 코드 여부 판단"""
    if not text or len(text) < 30:
        return False

    # 앞뒤에 ```html 코드블록이 감싸진 경우 제거 후 확인
    trimmed = text.strip()
    if trimmed.startswith("```html"):
        trimmed = trimmed[7:]
    if trimmed.startswith("```"):
        trimmed = trimmed[3:]
    if trimmed.endswith("```"):
        trimmed = trimmed[:-3]

    lower = trimmed.lower()
    return "<!doctype html" in lower or "<html" in lower


def _remove_markdown_codeblock(text: str) -> str:
    """AI 응답에서 마크다운 코드 블록을 제거하여 순수한 HTML만 반환"""
    if not text:
        return text
        
    trimmed = text.strip()
    
    # ```html로 시작하는 경우
    if trimmed.startswith("```html"):
        trimmed = trimmed[7:].strip()
    # ```로 시작하는 경우  
    elif trimmed.startswith("```"):
        trimmed = trimmed[3:].strip()
    
    # 끝의 ``` 제거
    if trimmed.endswith("```"):
        trimmed = trimmed[:-3].strip()
    
    return trimmed


# ---------------------------------------------------------------------------
# 스크립트 재배치 – DOM 파서 기반 (중간 삽입 방지) ------------------------------
# ---------------------------------------------------------------------------


def _reorder_scripts(html: str) -> str:
    """모든 <script> 태그를 추출해 body 끝으로 이동한다.

    1) src 속성이 있는 라이브러리 스크립트를 우선 배치
    2) 인라인 스크립트를 그 뒤에 배치

    BeautifulSoup(html5lib) 파서를 사용해 잘못 닫힌 태그도 복원하며
    중간에 끼어든 스크립트를 제거한다.
    """
    try:
        soup = BeautifulSoup(html, "html5lib")  # type: ignore[arg-type]

        libs, inlines = [], []
        for s in soup.find_all("script"):
            src_attr = s.get("src")  # type: ignore[attr-defined]
            (libs if src_attr else inlines).append(s.extract())

        body = soup.body or soup.new_tag("body")
        if not soup.body:
            soup.append(body)

        for s in libs + inlines:
            body.append(s)

        return str(soup)
    except Exception as err:
        logger.warning("DOM script reordering failed, fallback to original: %s", err)
        return html


# ---------------------------------------------------------------------------
# QC – 필수 요소 검사 ---------------------------------------------------------
# ---------------------------------------------------------------------------


def _passes_qc(html: str, validation_data: dict) -> bool:
    """간단한 품질 검증: 필수 요소 존재 확인 (Claude 4 호환성 강화)"""
    try:
        soup = BeautifulSoup(html, "html5lib")  # type: ignore[arg-type]

        # 기본 HTML 구조 확인
        if not soup.find("html") or not soup.find("body"):
            logger.warning("QC fail: missing basic HTML structure")
            return False

        # 컨테이너 존재 확인 (더 관대한 검사)
        has_container = (
            soup.find(class_="vue-container") or
            soup.find(class_="a4-container") or
            soup.find("main") or
            soup.find("section") or
            soup.find(class_="report-container") or
            soup.find(class_="content") or
            soup.find("div")  # 최소한 div라도 있으면 통과
        )
        
        if not has_container:
            logger.warning("QC fail: missing any container element")
            return False

        # HTML 길이 최소 체크 (너무 짧으면 실패한 것으로 간주)
        if len(html.strip()) < 500:
            logger.warning(f"QC fail: HTML too short ({len(html)} chars)")
            return False

        logger.info("✅ QC 통과 - 모든 검사 성공")
        return True
    except Exception as qc_err:
        logger.warning("QC parse error: %s", qc_err)
        return False


# ---------------------------------------------------------------------------
# 그래프 시각화 보강 – Chart.js 자동 삽입 및 초기화 스크립트 --------------------
# ---------------------------------------------------------------------------

_CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js"


def _ensure_chartjs_and_init(html: str) -> str:
    """HTML 내에 Chart.js CDN, 필수 차트 캔버스, 기본 초기화 스크립트를 삽입한다.

    1) <canvas id="qualityChart"> 가 없으면 body 최상단에 삽입
    2) Chart.js <script src> 가 없으면 body 끝 전에 삽입
    3) 'overallScoreChart' 초기화 코드가 없으면 기본 초기화 스크립트를 삽입

    Returns:
        수정된 HTML 문자열
    """
    # ------------------------------------------------------------------
    # 1) 우선 BeautifulSoup 로 DOM 파싱해 필수 캔버스가 없으면 삽입
    # ------------------------------------------------------------------

    try:
        soup = BeautifulSoup(html, "html5lib")  # type: ignore[arg-type]

        body = soup.body or soup.new_tag("body")
        if not soup.body:
            soup.append(body)

        # (1) qualityChart 캔버스 보강 ----------------------------------
        if not soup.find("canvas", {"id": "qualityChart"}):
            canvas_tag = soup.new_tag("canvas", id="qualityChart")
            canvas_tag["class"] = "mx-auto my-4 w-full max-w-md h-64"
            # body 최상단에 삽입하여 레이아웃 붕괴 최소화
            body.insert(0, canvas_tag)

        # DOM 수정 결과를 문자열로 반영
        html = str(soup)
    except Exception as dom_err:
        # 파서 오류 시 경고만 남기고 원본 HTML 사용 (후단 스크립트 삽입은 계속 수행)
        logger.warning("ensure_chartjs_and_init DOM 보강 실패: %s", dom_err)

    # ------------------------------------------------------------------
    # 2) Chart.js CDN 및 초기화 스크립트 삽입 (문자열 기반) ---------------
    # ------------------------------------------------------------------

    lower = html.lower()
    needs_chartjs = _CHARTJS_CDN.lower() not in lower
    needs_init = "overallscorechart" not in lower  # 대소문자 무시

    if not needs_chartjs and not needs_init:
        return html  # 추가 작업 불필요

    # body 닫는 태그 위치 계산
    insert_idx = lower.rfind("</body>")
    if insert_idx == -1:
        insert_idx = len(html)

    parts: list[str] = []
    if needs_chartjs:
        parts.append(f"<script src=\"{_CHARTJS_CDN}\"></script>")

    if needs_init:
        init_js = """
<script>
(function(){
  if (window.__vizierChartInit__) return; // 중복 방지
  window.__vizierChartInit__ = true;
  function ready(fn){ if(document.readyState!=='loading'){fn();} else{document.addEventListener('DOMContentLoaded', fn);} }
  ready(function(){
    try {
      var rawEl = document.getElementById('raw-data');
      if(!rawEl) return;
      var jsonText = rawEl.textContent || rawEl.innerText || '{}';
      var data = JSON.parse(jsonText);
      if(typeof Chart==='undefined'){console.warn('Chart.js not loaded'); return;}

      // Overall Score Doughnut (qualityChart 를 기본 캔버스로 사용) ---------
      var ctxOverall = document.getElementById('overallScoreChart') || document.getElementById('qualityChart');
      if(ctxOverall){
        var overall = (data.quality_metrics && data.quality_metrics.overall_score) || data.overall_score || 0;
        overall = Math.max(0, Math.min(100, overall));
        new Chart(ctxOverall, {
          type: 'doughnut',
          data: {
            labels: ['Score', 'Remaining'],
            datasets: [{
              data: [overall, 100 - overall],
              backgroundColor: ['#3b82f6', '#e5e7eb'],
              borderWidth: 0
            }]
          },
          options: {cutout: '60%', plugins:{legend:{display:false}}}
        });
      }

      // Quality Metrics Radar --------------------------------------------
      var ctxQuality = document.getElementById('qualityMetricsChart');
      if(ctxQuality && data.quality_metrics){
        var labels = Object.keys(data.quality_metrics);
        var values = labels.map(function(k){ return data.quality_metrics[k]; });
        new Chart(ctxQuality, {
          type: 'radar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Quality Metrics',
              data: values,
              fill: true,
              backgroundColor: 'rgba(59,130,246,0.2)',
              borderColor: '#3b82f6',
              pointBackgroundColor: '#3b82f6'
            }]
          },
          options:{ scales:{ r:{ beginAtZero:true, max:100 } } }
        });
      }
    } catch(e){ console.error('Chart init error', e); }
  });
})();
</script>
"""
        parts.append(init_js)

    # body 태그 앞에 삽입
    return html[:insert_idx] + "\n".join(parts) + html[insert_idx:]


# ---------------------------------------------------------------------------
# HTML 구조 복원 – 태그/속성 미닫힘 보정 --------------------------------------
# ---------------------------------------------------------------------------


def _sanitize_html(html: str) -> str:
    """BeautifulSoup(html5lib) 를 이용해 잘못 닫힌 태그·속성을 자동 복원합니다.

    LLM 이 생성한 HTML 은 종종 `<p<script ...>` 같이 태그 경계가 깨진 상태로
    전달됩니다. html5lib 파서는 이러한 오류를 최대한 복구해 주므로, 파싱 후
    다시 문자열로 직렬화하면 브라우저 파싱 실패를 방지할 수 있습니다.

    Args:
        html: 원본 HTML 문자열

    Returns:
        파싱-복원된 HTML 문자열 (Pretty-print 없이 그대로 직렬화)
    """

    try:
        # html5lib 파서는 Document 를 자동 생성하므로 태그 누락도 복원 가능
        soup = BeautifulSoup(html, "html5lib")  # type: ignore[arg-type]
        return str(soup)
    except Exception as _sanitize_err:
        # 파싱 실패 시 원본 그대로 반환 (후단 로깅만)
        logger.warning("sanitize_html failed: %s", _sanitize_err)
        return html


# ---------------------------------------------------------------------------
# JSON 원본 데이터 삽입 – <script id="raw-data"> ------------------------------
# ---------------------------------------------------------------------------


def _ensure_raw_json_script(html: str, validation_data: dict) -> str:
    """HTML 에 원본 validation_data JSON 을 <script id="raw-data"> 로 삽입한다.

    • 이미 id="raw-data" 스크립트가 존재하면 유지(덮어쓰기 X)
    • 없을 경우, body 끝 직전에 삽입하여 차트 초기화 스크립트에서 읽을 수 있도록 함
    """
    try:
        soup = BeautifulSoup(html, "html5lib")  # type: ignore[arg-type]

        # id="raw-data" 중복 여부 검사
        if soup.find("script", {"id": "raw-data"}):
            return str(soup)

        body = soup.body or soup.new_tag("body")
        if not soup.body:
            soup.append(body)

        # JSON 직렬화 (ASCII 보존)
        json_str = json.dumps(validation_data, ensure_ascii=False)
        script_tag = soup.new_tag("script", id="raw-data", type="application/json")
        script_tag.string = json_str
        # body 끝에 삽입하여 다른 스크립트보다 먼저 로드되도록 함
        body.append(script_tag)

        return str(soup)
    except Exception as rd_err:
        logger.warning("ensure_raw_json_script failed: %s", rd_err)
        return html


def _remove_chartjs_code(html: str) -> str:
    """Chart.js 관련 코드를 모두 제거하여 렌더링 오류를 방지합니다."""
    try:
        soup = BeautifulSoup(html, "html5lib")
        
        # Canvas 태그 제거
        for canvas in soup.find_all("canvas"):
            canvas.decompose()
        
        # Chart.js CDN 스크립트 제거
        for script in soup.find_all("script", src=True):
            if hasattr(script, 'get'):
                src_attr = script.get("src")  # type: ignore
                if src_attr and isinstance(src_attr, str) and "chart.js" in src_attr.lower():
                    script.decompose()
        
        # Chart 초기화 스크립트 제거
        for script in soup.find_all("script", src=False):
            script_content = script.get_text()
            if script_content and ("Chart" in script_content or "chart" in script_content.lower()):
                script.decompose()
        
        return str(soup)
    except Exception as e:
        logger.warning(f"Chart.js 제거 실패: {e}")
        return html
