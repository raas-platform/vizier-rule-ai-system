"""
Vizier 화면 호환 오류 응답.

Vizier는 실패하면 응답 JSON의 `errorMsg`만 토스트로 보여 주고(없으면 빈 토스트),
401을 받으면 로그인 화면으로 보낸다. 그래서
- 모든 오류 JSON에 `errorMsg`(사용자에게 보여 줄 한국어 한 문장)를 넣고
- 401은 쓰지 않는다(인증·키 문제는 403).
errorMsg에는 내부 예외 메시지·스택·키 값을 넣지 않는다.
"""

from typing import Any, Optional

# 상태 코드별 기본 문구
ERROR_MESSAGES = {
    400: "요청 내용이 올바르지 않습니다. 입력값을 확인해 주세요.",
    403: "접근 권한이 없습니다. API 키를 확인해 주세요.",
    404: "요청한 주소를 찾을 수 없습니다.",
    405: "지원하지 않는 요청 방식입니다.",
    413: "요청 데이터가 너무 큽니다.",
    422: "룰 데이터 형식이 올바르지 않습니다. 입력값을 확인해 주세요.",
    429: "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    500: "검증 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    502: "서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    503: "서버를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    504: "검증 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
}

DEFAULT_CLIENT_ERROR = "요청을 처리할 수 없습니다. 입력값을 확인해 주세요."
DEFAULT_SERVER_ERROR = ERROR_MESSAGES[500]


def safe_status(status_code: int) -> int:
    """401은 403으로 바꾼다 (Vizier가 401을 받으면 로그인 화면으로 이동하므로)."""
    return 403 if status_code == 401 else status_code


def error_message(status_code: int, detail: Any = None) -> str:
    """오류 응답에 넣을 errorMsg.

    detail이 dict이고 직접 정한 `errorMsg`가 있으면 그것을 쓴다(코드에서 정한 문구만 들어감).
    그 밖에는 상태 코드별 기본 문구. detail 문자열(내부 예외가 섞일 수 있음)은 쓰지 않는다.
    """
    if isinstance(detail, dict):
        custom: Optional[str] = detail.get("errorMsg")
        if isinstance(custom, str) and custom.strip():
            return custom
    status_code = safe_status(status_code)
    if status_code in ERROR_MESSAGES:
        return ERROR_MESSAGES[status_code]
    return DEFAULT_SERVER_ERROR if status_code >= 500 else DEFAULT_CLIENT_ERROR
