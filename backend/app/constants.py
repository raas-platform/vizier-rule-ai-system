"""
시스템 상수 정의
하드코딩된 값들을 중앙 집중식으로 관리
"""


class QualityThresholds:
    """품질 메트릭 임계값들"""

    # 복잡성 관련
    COMPLEXITY_WARNING_THRESHOLD = 20
    COMPLEXITY_ERROR_THRESHOLD = 30
    COMPLEXITY_MAX_SCORE = 100

    # 점수 계산 관련
    BASE_SCORE = 100
    ERROR_PENALTY_PER_ISSUE = 15
    WARNING_PENALTY_PER_ISSUE = 5
    DEPTH_PENALTY_PER_LEVEL = 10
    COMPLETENESS_ERROR_PENALTY = 20
    CONSISTENCY_ERROR_PENALTY = 10
    CONSISTENCY_WARNING_PENALTY = 3

    # 조건 수 관련
    MAX_READABLE_CONDITIONS = 20
    READABILITY_PENALTY_FOR_MANY_CONDITIONS = 10


class PerformanceThresholds:
    """성능 관련 임계값들"""

    # 시간 임계값 (밀리초)
    FAST_RESPONSE_MS = 1000
    MODERATE_RESPONSE_MS = 3000
    SLOW_RESPONSE_TIMEOUT_MS = 10000

    # 복잡성 등급별 시간 예상
    SIMPLE_MAX_COMPLEXITY = 5
    MODERATE_MAX_COMPLEXITY = 10
    COMPLEX_MAX_COMPLEXITY = 15

    # 조건 수 임계값
    MANY_CONDITIONS_THRESHOLD = 10
    MAX_SAFE_DEPTH = 4


class ComplexityRatings:
    """복잡성 등급 정의"""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"

    # 복잡성 점수 매핑
    RATING_THRESHOLDS = {
        SIMPLE: PerformanceThresholds.SIMPLE_MAX_COMPLEXITY,
        MODERATE: PerformanceThresholds.MODERATE_MAX_COMPLEXITY,
        COMPLEX: PerformanceThresholds.COMPLEX_MAX_COMPLEXITY,
    }

    # 예상 실행 시간 매핑
    ESTIMATED_TIMES = {
        SIMPLE: "< 1ms",
        MODERATE: "1-5ms",
        COMPLEX: "5-10ms",
        VERY_COMPLEX: "> 10ms",
    }


class NetworkConfig:
    """네트워크 설정 상수"""

    # 기본값들 (환경변수로 오버라이드 가능)
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8000
    DEFAULT_WORKERS = 4

    # API 제한
    DEFAULT_REQUEST_TIMEOUT = 30  # 초
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB


class DomainConfig:
    """도메인 및 CORS 설정"""

    # 기본 도메인들 (환경변수로 오버라이드)
    DEFAULT_PRODUCTION_DOMAINS = ["https://yourdomain.com"]
    DEFAULT_STAGING_DOMAINS = [
        "https://staging.yourdomain.com",
        "https://test.yourdomain.com",
    ]


class ApiKeyConfig:
    """API 키 관련 설정"""

    # API 키 접두사들
    OPENAI_KEY_PREFIX = "sk-"
    ANTHROPIC_KEY_PREFIX = "sk-ant-"

    # 캐시 설정
    VALIDATION_CACHE_TTL_MINUTES = 5
    FAILED_VALIDATION_CACHE_TTL_MINUTES = 1


class IssueDetectionConfig:
    """이슈 검출 관련 설정"""

    # 심각도 레벨
    SEVERITY_ERROR = "error"
    SEVERITY_WARNING = "warning"
    SEVERITY_INFO = "info"

    # 이슈 타입 우선순위 (낮을수록 높은 우선순위)
    ISSUE_TYPE_PRIORITIES = {
        "self_contradiction": 0,
        "invalid_operator": 1,
        "type_mismatch": 2,
        "ambiguous_branch": 3,
        "missing_condition": 4,
        "complexity_warning": 5,
        "duplicate_condition": 6,
    }

    # 기본 우선순위 (정의되지 않은 이슈 타입용)
    DEFAULT_ISSUE_PRIORITY = 999


class TestConfig:
    """테스트 관련 설정"""

    # HTTP 상태 코드
    STATUS_OK = 200
    STATUS_VALIDATION_ERROR = 422
    STATUS_INTERNAL_ERROR = 500
    STATUS_NOT_FOUND = 404
    STATUS_METHOD_NOT_ALLOWED = 405

    # 테스트 성능 임계값
    MAX_TEST_PROCESSING_TIME_SECONDS = 10.0
    LARGE_PAYLOAD_CONDITIONS_COUNT = 50


class MetricsConfig:
    """메트릭 관련 설정"""

    # 분석 관련
    MIN_FIELD_ANALYSIS_CONDITIONS = 1
    MAX_FIELD_EXAMPLES = 5
    MAX_NUMERIC_EXAMPLES = 3

    # 품질 메트릭 가중치
    QUALITY_WEIGHT_MAINTAINABILITY = 0.25
    QUALITY_WEIGHT_READABILITY = 0.25
    QUALITY_WEIGHT_COMPLETENESS = 0.25
    QUALITY_WEIGHT_CONSISTENCY = 0.25

    # 논리 연산자 불균형 임계값
    OR_TO_AND_RATIO_THRESHOLD = 2.0


class LoggingConfig:
    """로깅 관련 설정"""

    # 구분선 길이
    SEPARATOR_LENGTH = 60
    HALF_SEPARATOR_LENGTH = 50

    # 로그 레벨
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationConfig:
    """룰 검증 관련 설정"""

    # 검증 타입
    FIELD_TYPES = {
        "string": "String",
        "number": "Number",
        "boolean": "Boolean",
        "date": "Date",
        "array": "Array",
        "logical": "Logical",
    }

    # 연산자 검증
    VALID_OPERATORS = {
        "string": ["==", "!=", "contains", "starts_with", "ends_with", "in", "not_in"],
        "number": ["==", "!=", ">", ">=", "<", "<=", "in", "not_in"],
        "boolean": ["==", "!="],
        "date": ["==", "!=", ">", ">=", "<", "<="],
        "array": ["contains", "in", "not_in"],
        "logical": ["and", "or"],
    }

    # 엣지 케이스 값들
    EDGE_CASE_VALUES = [0, 1, -1]
    NULL_REPRESENTATIONS = [None, "", "null", "NULL"]
