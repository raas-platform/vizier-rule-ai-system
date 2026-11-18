from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConditionIssue(BaseModel):
    """룰 조건 이슈 모델"""

    condUuid: Optional[str] = Field(None, description="조건 고유 ID")
    keyName: Optional[str] = Field(None, description="조건 키 이름")
    issue_type: str
    severity: str
    location: str = ""
    explanation: str = ""
    suggestion: str = ""
    # AI 확장 정보
    ai_explanation: Optional[str] = None
    ai_suggestion: Optional[str] = None
    impact_level: Optional[str] = None  # "low", "medium", "high"
    affected_scenarios: Optional[List[str]] = None



class FieldAnalysis(BaseModel):
    """필드별 분석 정보"""

    keyName: str = Field(..., description="조건 키 이름")
    field_type: str
    condition_count: int
    operators_used: List[str]
    values_range: Optional[Dict[str, Any]] = None  # min, max, examples
    issues_count: int
    complexity_score: int
    # 필드와 관련된 조건들의 UUID 목록
    condition_uuids: List[str] = Field(default_factory=list, description="해당 필드와 관련된 조건 UUID 목록")


class LogicFlow(BaseModel):
    """논리 흐름 분석"""

    logical_operators: Dict[str, int]  # AND, OR 사용 횟수
    nesting_levels: List[int]  # 각 레벨별 조건 수
    branch_coverage: Dict[str, Any]  # 분기 커버리지 정보
    potential_dead_code: List[str]  # 도달 불가능한 조건들


class PerformanceMetrics(BaseModel):
    """성능 메트릭"""

    estimated_execution_time: Optional[str] = None
    complexity_rating: str  # "simple", "moderate", "complex", "very_complex"
    optimization_opportunities: List[str] = []
    bottleneck_conditions: List[str] = []


class QualityMetrics(BaseModel):
    """품질 메트릭"""

    maintainability_score: int = Field(ge=0, le=100)
    readability_score: int = Field(ge=0, le=100)
    completeness_score: int = Field(ge=0, le=100)
    consistency_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)


class ReportMetadata(BaseModel):
    """리포트 메타데이터"""

    analysis_timestamp: str
    ruleUuid: Optional[str] = Field(None, description="룰 고유 ID")
    ruleName: Optional[str] = Field(None, description="룰 이름")
    analysis_version: str = "1.0"
    total_analysis_time_ms: Optional[int] = None


class ConditionDetail(BaseModel):
    """조건 상세 정보"""
    
    condUuid: str = Field(..., description="조건 고유 ID")
    keyName: Optional[str] = Field(None, description="조건 키 이름")
    dispName: Optional[str] = Field(None, description="조건 표시 이름")
    operator: Optional[str] = Field(None, description="연산자")
    value: Optional[Any] = Field(None, description="조건 값")
    fieldDataType: Optional[str] = Field(None, description="필드 데이터 타입")
    depth_level: int = Field(0, description="중첩 깊이 레벨")
    parent_logic: Optional[str] = Field(None, description="부모 논리 연산자")


class StructureInfo(BaseModel):
    """룰 구조 정보 모델"""

    depth: int
    condition_count: int = 0  # 이전 버전 호환성을 위해 유지
    condition_node_count: int = Field(
        0, description="전체 조건 노드 수 (논리 연산자 포함)"
    )
    field_condition_count: int = Field(0, description="실제 필드가 있는 비교 조건 수")
    unique_fields: List[str]


class RuleDescription(BaseModel):
    """AI가 룰의 조건을 읽고 정리한 설명 (검증 이슈와는 무관)"""

    what: str = Field(..., description="조건이 말하는 그대로 풀어 쓴 1~2문장")
    purpose: Optional[str] = Field(
        None, description="룰 이름·메시지·조건 표시명으로 추정한 목적 (근거가 약하면 null)"
    )


class ValidationResult(BaseModel):
    """룰 검증 결과 모델 - GUI 리포트 생성용 확장"""

    # 기본 검증 정보
    is_valid: bool
    summary: str
    issue_counts: Dict[str, int] = Field(default_factory=dict)
    issues: List[ConditionIssue]
    structure: StructureInfo
    rule_summary: str = ""
    complexity_score: int = 0
    ai_comment: Optional[str] = None

    # 확장된 분석 정보 (GUI 리포트용)
    field_analysis: List[FieldAnalysis] = Field(default_factory=list)
    logic_flow: Optional[LogicFlow] = None
    performance_metrics: Optional[PerformanceMetrics] = None
    quality_metrics: Optional[QualityMetrics] = None
    report_metadata: Optional[ReportMetadata] = None

    # AI 생성 콘텐츠
    ai_insights: Optional[Dict[str, Any]] = None  # AI가 생성한 추가 통찰
    improvement_recommendations: Optional[List[Dict[str, str]]] = None  # AI 개선 제안
    risk_assessment: Optional[Dict[str, Any]] = None  # AI 위험도 평가

    # AI 설명 상태: "ok" | "skipped"(키 없음 등으로 건너뜀) | "failed"(호출 실패)
    # AI가 실패해도 규칙 판정 결과는 그대로 반환된다. ai_error에 한국어 사유.
    ai_status: Optional[str] = None
    ai_error: Optional[str] = None
    rule_description: Optional[RuleDescription] = None  # AI 룰 설명 (실패 시 null)


# 사용자 제공 형식에 맞는 새로운 요청 모델 - 직접 배열 형태
RuleJsonValidationRequest = List[Dict[str, Any]]


class RuleValidationResponse(BaseModel):
    """Rule validation response model"""

    is_valid: bool
    summary: str
    issue_counts: Dict[str, int]
    issues: List[ConditionIssue]
    structure: StructureInfo
    ai_comment: Optional[str] = None

    # 확장된 분석 정보 (GUI 리포트용)
    field_analysis: List[FieldAnalysis] = Field(default_factory=list)
    logic_flow: Optional[LogicFlow] = None
    performance_metrics: Optional[PerformanceMetrics] = None
    quality_metrics: Optional[QualityMetrics] = None
    report_metadata: Optional[ReportMetadata] = None

    # AI 생성 콘텐츠
    ai_insights: Optional[Dict[str, Any]] = None
    improvement_recommendations: Optional[List[Dict[str, str]]] = None
    risk_assessment: Optional[Dict[str, Any]] = None

    # AI 설명 상태 (ok / skipped / failed)와 한국어 사유. 실패해도 검증 결과는 반환됨
    ai_status: Optional[str] = None
    ai_error: Optional[str] = None
    rule_description: Optional[RuleDescription] = None
