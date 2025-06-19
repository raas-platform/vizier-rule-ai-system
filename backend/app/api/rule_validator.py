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

        context = {
            **validation_result,
            "structure": structure,
            "report_metadata": report_metadata,
            "issues": issues,
            "rule_name": rule_name,
            "validation_model": validation_model,
            "report_model": report_model,
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


# ---------------------------------------------------------------------------
# AI 기반 리포트 (Claude 등) ----------------------------------------------------
# ---------------------------------------------------------------------------


@router.post("/generate-ai-html-report")
async def generate_ai_html_report(validation_result: Dict[str, Any]) -> Dict[str, Any]:
    """LLM(Claude/GPT 등) 를 사용해 동적 · 트렌디한 HTML 리포트를 생성합니다.

    전달 JSON(validation_result)에 "preferred_model" 키가 있으면 해당 모델을 우선 시도합니다.
    """

    # --- ai_summary_md 는 리포트에 불필요하므로 제거 ---------------------------
    validation_result = dict(validation_result)  # shallow copy
    validation_result.pop("ai_summary_md", None)

    # 1) 요청 본문에 preferred_model 지정 시 최우선 사용
    user_preferred: str | None = validation_result.pop("preferred_model", None)  # 유저 지정 모델은 검증 데이터와 분리

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

    # 1) 환경 설정의 report_default_model / fallback_model 우선 삽입
    if settings.report_default_model.startswith("claude") and settings.report_default_model not in preferred_models:
        preferred_models.append(settings.report_default_model)

    if settings.report_fallback_model.startswith("claude") and settings.report_fallback_model not in preferred_models:
        preferred_models.append(settings.report_fallback_model)

    # 2) 나머지 Claude 모델 최신순
    preferred_models.extend(m for m in sorted_claude if m not in preferred_models)

    candidate_models = [m for m in preferred_models if llm_service.is_model_available(m)]
    if not candidate_models:
        raise HTTPException(status_code=503, detail="Claude 모델이 현재 사용 불가합니다.")

    # Claude 중에서도 첫 사용 가능 모델만 사용 (추가 폴백 없음)

    # 프롬프트 구성 -----------------------------------------------------------

    # (1) System Prompt – 기술적 제약을 모두 제거하고 크리에이티브 톤으로 교체
    system_prompt = (
        "당신은 최고급 데이터 대시보드 디자이너입니다.\n"
        "제공된 JSON 데이터로 Claude 웹버전 수준의 고품질 HTML 대시보드를 생성하세요.\n"

        "핵심 원칙:\n"
        "• JSON의 수치 데이터는 반드시 Chart.js 차트로 시각화 (텍스트 나열 절대 금지)\n"
        "• 점수/메트릭 → 레이더·게이지 차트, 분포 → 도넛 차트, 비교 → 막대 차트\n"
        "• 상단에 핵심 지표들을 큰 숫자 카드로 강조 표시\n"
        "• 각 섹션은 의미 있는 아이콘과 함께 카드 형태로 구성\n"
        "• 이슈나 문제점은 심각도별 색상 코딩으로 시각화\n"
        "• 제목은 JSON 데이터의 실제 룰명이나 분석 대상을 기반으로 설정\n\n"

        "필수 시각화 요소:\n"
        "• Overall Score나 주요 점수는 진행률 바 또는 원형 게이지로 표시\n"
        "• 여러 메트릭이 있으면 반드시 레이더 차트로 비교 시각화\n"
        "• 추천사항이나 개선안은 우선순위별 타임라인 카드로 표시\n"
        "• 모든 차트에 적절한 색상 팔레트와 라벨 적용\n\n"

        "JSON 데이터 활용 필수 규칙:\n"
        "• 절대로 하드코딩된 가짜 데이터 사용 금지\n"
        "• quality_metrics 의 실제 점수들을 반드시 사용\n"
        "• overall_score, maintainability_score, readability_score, completeness_score, consistency_score 값을 그대로 활용\n"
        "• field_analysis 의 실제 complexity_score 값들을 차트에 반영\n"
        "• JSON 에 없는 데이터는 만들어내지 말고 생략\n"
        "• 모든 차트는 JSON 의 실제 숫자 데이터만 사용\n\n"

        "JSON 데이터를 먼저 분석하고 이해한 후 작업하세요:\n"
        "1. JSON 구조를 파악하고 어떤 데이터가 있는지 확인\n"
        "2. 각 필드의 실제 값들을 정확히 매핑\n"
        "3. 존재하지 않는 데이터는 절대 만들어내지 말 것\n"
        "4. 예시: quality_metrics.overall_score = 84, maintainability_score = 85 등\n\n"

        "언어 사용 규칙:\n"
        "- 제목과 주요 헤딩: 한글 기반 (예: '룰 검증 결과', '품질 지표')\n"
        "- 기술 용어나 메트릭: 영어 혼용 가능 (예: 'Quality Score', 'Performance')\n"
        "- 모든 설명 텍스트와 내용: 반드시 한글로 작성\n"
        "- 버튼이나 라벨: 한글 우선, 필요시 영어 병기\n"
        "- 차트 라벨: 한글로 작성하되 기술 용어는 영어 가능\n"
        "\n"
        "절대로 전체를 영어로만 작성하지 마세요. 한국어가 기본 언어입니다.\n"
        "Figma Community, Dribbble 2024 트렌드, Material Design 3.0 기준으로 현대적 카드 컴포넌트 디자인을 적용하세요.\n"

        "카드 디자인 필수 적용사항:\n"
        "- 이슈나 경고 항목은 반드시 Left Border Card 스타일 사용\n"
        "- border-left: 4px solid [색상]; 형태로 왼쪽에 색상 accent 추가\n"
        "- 심각도별 색상: Error(#ef4444), Warning(#f59e0b), Info(#3b82f6)\n"
        "- 2024-2025 모던 색상 팔레트 사용 (Tailwind CSS 색상 기준)\n"
        "- Bootstrap 기본 색상 사용 금지\n"
        "- 현대적 그라데이션과 중성 톤 활용\n"
        "\n"
        "레이아웃 규격:\n"
        "- 최상위 컨테이너는 다음 스타일을 준수합니다 → max-width: 890px; width: 100%; height: auto; gap: 0px; border-radius: 12px;\n"
        "- 모든 실제 콘텐츠는 반드시 하나의 \u003cdiv class='container'\u003e 래퍼 안에 들어가야 합니다. body 태그 바로 아래에 위치하며, 추가 상위 래퍼나 병렬 형제 요소를 생성하지 마세요.\n"
        "- 이 규격을 기반으로 내부 카드를 Grid/Flex 로 배치하되 반응형(≤ 890px)에서도 형태가 유지되도록 media query 적용\n"
        "- 전체 콘텐츠는 해당 컨테이너보다 작게 구성해 내부·외부 어느 곳에도 스크롤바가 생성되지 않도록 합니다.\n"
        "\n"
        "JSON 데이터의 수치는 반드시 Chart.js로 시각화하세요. 텍스트 나열 금지.\n"

        "AI 조언(Recommendations) 섹션은 대시보드에서 가장 눈에 띄도록 디자인하세요.\n"
        "- 별도 카드 또는 하이라이트 영역으로 배치\n"
        "- 아이콘·배경 그라데이션·살짝의 애니메이션 효과로 강조\n"
        "- 중요도 순 정렬 및 우선순위 배지 표시\n"

        "데이터 분석 → 차트 매핑 → HTML 생성 순서로 진행하세요.\n"

        "\n스크립트·데이터 삽입 규칙(필수):\n"
        "• 라이브러리 스크립트(Chart.js 등)는 &lt;script src=... defer&gt; 형태로 &lt;/body&gt; 바로 위에만 삽입\n"
        "• 모든 JSON 원본 데이터는 &lt;script type=\"application/json\" id=\"raw-data\"&gt;...&lt;/script&gt; 블록으로 래핑\n"
        "• 초기화 코드는 window.addEventListener('load', ()=>{{...}}) 블록 안에 작성하여 라이브러리 로드가 끝난 뒤 실행\n"
        "• 라이브러리 스크립트와 초기화 스크립트를 같은 태그에 섞지 마세요.\n"

        "디자인 · 개발 최신 트렌드 기준:\n"
        "• 2024-2025 프리미엄 대시보드 수준 (Glassmorphism, Neumorphism, Soft UI, 블러 그라데이션)\n"
        "• CSS 최신 기능 활용: Container Queries, Subgrid, :has() 의존 선택자, Motion Path, View Transitions API\n"
        "• JavaScript 최신 스펙(ES2023+) 및 모듈 패턴 사용 – async/await, optional chaining 등\n"
        "• Chart.js 4.x, Tailwind CSS 3.4+, Font Awesome 6.5 (JS Kit) 등 최신 버전 사용\n"
        "• 반응형 CSS Grid · Flex, Dark/Light mode 토글, micro-interaction 및 scroll animation 필수\n"
        "• 데이터에 맞는 적절한 컬러 팔레트 자동 적용 – Tailwind/Material 3 색상 시스템 기반\n"
        "• 한영 적절히 혼용하여 현대적 · 세련된 느낌 \n"
        "• 완전한 독립형 HTML (모든 CSS, JS 인라인 포함)\n"
        "• A4 출력 호환성 고려 (@media print 포함)\n\n"

        "Claude 웹버전처럼 완성도 높고 아름다운 결과물을 만드세요.\n"
        "절대적으로 HTML 코드만 응답하세요. 어떤 설명이나 메타 정보, 특징 설명도 포함하지 마세요.\n"
        "```html 로 시작하거나 ``` 로 끝나는 코드 블록도 사용하지 마세요.\n"
        "<!DOCTYPE html>로 시작하는 순수한 HTML 코드만 응답하세요."
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
        header = (
            "아래 JSON 데이터는 리포트 제작에 활용할 정보입니다. 이 데이터를 분석하여 창의적이고 현대적인 단일 HTML 파일을 작성해 주세요.\n"
            "\n* 반드시 HTML 하단(footer) 또는 눈에 띄지 않는 작은 글씨 영역에 다음 정보를 표기하세요.\n"
            f"  - 검증 모델(validation_model): {validation_model_name}\n"
            f"  - 리포트 모델(report_model): {model_name}\n"
        )

        user_prompt = header + "```json\n" + validation_json_str + "\n```"
        return system_prompt + "\n\n" + user_prompt

    gen_start = time.time()

    for model_id in candidate_models:
        try:
            full_prompt = build_prompt(model_id)

            if model_id.startswith("claude") and "anthropic" in llm_service.providers:
                # Anthropic 공식 클라이언트로 role 기반 메시지 전달
                anthropic_provider = llm_service.providers["anthropic"]
                anthropic_client = getattr(anthropic_provider, "client")  # type: ignore[attr-defined]
                response = await anthropic_client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    temperature=0.7,
                    system=system_prompt,
                    messages=[{"role": "user", "content": full_prompt}],
                )
                html = response.content[0].text
            else:
                # 기타 모델은 기존 방식 사용
                html = await llm_service.generate_text(full_prompt, model_id)

            # OpenAI 응답이 HTML이 아닐 경우 거부(refusal)로 간주하고 실패 처리
            if not _looks_like_html(html) or "i'm sorry" in html.lower():
                refusal_snippet = html.strip().replace("\n", " ")[:200]
                logger.warning(
                    f"OpenAI 응답이 HTML이 아님 또는 거부 응답 감지 (model={model_id}): '{refusal_snippet}...'",
                )
                raise ValueError(f"OpenAI 모델 거부/비HTML 응답: {refusal_snippet}")

            gen_ms = int((time.time() - gen_start) * 1000)

            # --- 후처리: 라이브러리 스크립트 선행, 초기화 스크립트 후행 -----------------
            try:
                # 스크립트 로딩 순서 보정 후, Chart.js 인라인 초기화 보강
                html = _reorder_scripts(html)
                html = _ensure_chartjs_and_init(html)
            except Exception as _rs_err:
                logger.warning("script reordering failed: %s", _rs_err)

            # 구조 복원은 스크립트 재배치 이후 수행 (스크립트 이동 후 깨진 태그 재수정)
            try:
                html = _sanitize_html(html)
            except Exception:
                # sanitize 실패 시에는 경고만 기록하고 진행
                logger.warning("sanitize_html post-processing skipped due to error", exc_info=True)

            return {
                "report": html,
                "model_used": model_id,
                "generation_time_ms": str(gen_ms),
                "report_generated_by": "llm",
            }
        except anthropic.BadRequestError as ae:  # granular logging for Anthropic
            err_payload = getattr(ae, "error", {})  # type: ignore[attr-defined]
            err_type = err_payload.get("type", "unknown") if isinstance(err_payload, dict) else "unknown"
            err_msg = err_payload.get("message", str(ae)) if isinstance(err_payload, dict) else str(ae)

            logger.error(
                f"Anthropic API 오류({model_id}) — type: {err_type}, message: {err_msg}",
                exc_info=True,
            )
            # 크레딧 부족 오류면 즉시 중단하고 402 반환
            if "credit balance is too low" in err_msg.lower():
                raise HTTPException(
                    status_code=402,
                    detail="Anthropic 크레딧이 부족합니다. 결제를 완료한 후 다시 시도해 주세요.",
                )
            # 기타 Anthropic 오류 → 다음 모델 시도
            continue
        except Exception as e:
            # 모델 단위 실패 → 다음 후보 시도
            logger.warning(
                f"모델 '{model_id}' 시도 실패 → {type(e).__name__}: {e}. 다음 후보를 시도합니다.",
                exc_info=True,
            )

    # 모든 Claude 후보 모델 시도 실패 – OpenAI 폴백 시도 ---------------------------------
    logger.error(
        "Claude 모델 전부 실패했습니다. OpenAI 모델 폴백을 시도합니다.",
    )

    # 1차 폴백: OpenAI 계열 모델 시도 --------------------------------------
    openai_priority = [
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    openai_candidates = [m for m in openai_priority if llm_service.is_model_available(m)]

    if openai_candidates:
        for model_id in openai_candidates:
            try:
                logger.info(f"OpenAI 모델 '{model_id}' 시도 (Claude 실패 폴백)")
                full_prompt_fb = build_prompt(model_id)
                html = await llm_service.generate_text(full_prompt_fb, model_id)
                # Claude 실패 → OpenAI 생성 결과에 대해서도 스크립트 순서 및 차트 초기화 보강
                try:
                    html = _reorder_scripts(html)
                    html = _ensure_chartjs_and_init(html)
                    html = _sanitize_html(html)
                except Exception as _rs_err:
                    logger.warning("script reordering failed (OpenAI fallback): %s", _rs_err)

                logger.info(f"OpenAI 모델 '{model_id}'로 리포트 생성 성공 – Claude 실패 폴백 완료")
                gen_ms = int((time.time() - gen_start) * 1000)
                return {
                    "report": html,
                    "model_used": model_id,
                    "generation_time_ms": str(gen_ms),
                    "report_generated_by": "llm",
                    "note": "claude_failed_openai_fallback",
                }
            except Exception as oe:
                logger.warning(
                    f"OpenAI 모델 '{model_id}' 시도 실패 → {type(oe).__name__}: {oe}. 다음 OpenAI 후보를 시도합니다.",
                    exc_info=True,
                )
    else:
        logger.warning("사용 가능한 OpenAI 모델이 없습니다. 템플릿 폴백으로 진행합니다.")

    # 2차 폴백: Jinja 템플릿 기반 HTML 리포트 -------------------------------
    try:
        template_report = await _generate_html_report(validation_result)
        gen_ms = int((time.time() - gen_start) * 1000)
        template_report["model_used"] = "template_fallback"
        template_report["note"] = "claude_and_openai_failed_template_fallback"
        template_report["generation_time_ms"] = str(gen_ms)
        template_report["report_generated_by"] = "template"
        logger.info("템플릿 HTML 폴백으로 리포트 생성 완료 (Claude & OpenAI 실패)")
        return template_report
    except Exception as template_err:
        logger.error(
            "템플릿 기반 폴백에도 실패했습니다. 간이 HTML 리포트를 반환합니다.",
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


# ---------------------------------------------------------------------------
# HTML 후처리 – 스크립트 로딩 순서 보정
# ---------------------------------------------------------------------------


_SCRIPT_RE = re.compile(r"(<script[\s\S]*?</script>)", flags=re.IGNORECASE)


def _reorder_scripts(html: str) -> str:
    """HTML 문자열에서 script 태그를 추출해
    1) src 속성이 있는 라이브러리 스크립트를 먼저
    2) 인라인 스크립트를 나중에
    순서대로 body 끝에 재배치한다.

    args:
        html: 원본 HTML
    returns:
        수정된 HTML (스크립트 순서 보정)
    """
    # <script> 태그 전체 추출
    scripts = _SCRIPT_RE.findall(html)
    if not scripts:
        return html  # Nothing to do

    src_scripts = [s for s in scripts if "src=" in s[:150].lower()]
    inline_scripts = [s for s in scripts if s not in src_scripts]

    # 본문에서 기존 스크립트 제거
    html_wo_scripts = _SCRIPT_RE.sub("", html)

    # body 태그 찾기
    idx = html_wo_scripts.lower().rfind("</body>")
    if idx == -1:
        # fallback: 그냥 끝에 붙이기
        return html_wo_scripts + "".join(src_scripts + inline_scripts)

    reordered = "".join(src_scripts + inline_scripts)
    return html_wo_scripts[:idx] + reordered + html_wo_scripts[idx:]


# ---------------------------------------------------------------------------
# 그래프 시각화 보강 – Chart.js 자동 삽입 및 초기화 스크립트 --------------------
# ---------------------------------------------------------------------------

_CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js"


def _ensure_chartjs_and_init(html: str) -> str:
    """HTML 내에 Chart.js CDN 및 기본 초기화 스크립트를 삽입한다.

    1) Chart.js <script src> 가 없으면 body 끝 전에 삽입
    2) 'overallScoreChart' 초기화 코드가 없으면 간단한 기본 초기화 스크립트를 삽입

    Returns:
        수정된 HTML 문자열
    """
    lower = html.lower()
    needs_chartjs = _CHARTJS_CDN.lower() not in lower
    needs_init = "overallscorechart" not in lower  # 초기화 스크립트 존재 여부 (대소문자 무시)

    if not needs_chartjs and not needs_init:
        return html  # Nothing to do

    # body 닫는 태그 위치
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

      // Overall Score Doughnut -----------------------------
      var ctxOverall = document.getElementById('overallScoreChart');
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

      // Quality Metrics Radar ------------------------------
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

    # 삽입
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
