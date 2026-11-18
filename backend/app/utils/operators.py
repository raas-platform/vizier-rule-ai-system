"""
비교 연산자 정규화와 IN / NOT IN 값 처리.

Vizier가 보내는 연산자 표기(`IN`, `NOT IN` - 대문자, 공백 한 칸)와
기존 표기(`in`, `not_in`)를 모두 받아들이기 위해, 비교·검사할 때는
항상 `normalize_operator()`로 바꾼 '표준 표기'를 쓴다.
응답에 담기는 연산자 문자열 자체는 요청 원문을 그대로 둔다.
"""

from typing import Any, List, Optional

# 표준 표기 -> 사용자에게 보여줄 표기 (Vizier 표기)
_DISPLAY = {
    "in": "IN",
    "not_in": "NOT IN",
}

# 목록 값을 받는 연산자 (표준 표기)
LIST_OPERATORS = frozenset({"in", "not_in"})


def normalize_operator(operator: Any) -> Optional[str]:
    """연산자를 비교용 표준 표기로 바꾼다.

    - 앞뒤 공백 제거, 중간 공백 여러 칸은 한 칸으로
    - 대소문자 무시 (소문자로)
    - `not in` / `not_in` -> `not_in`, `in` -> `in`
    - 그 밖의 연산자(==, >= 등)는 공백만 정리해 그대로 둔다.
    """
    if operator is None:
        return None
    text = " ".join(str(operator).split()).lower()
    if not text:
        return text
    if text in ("not in", "not_in"):
        return "not_in"
    return text


def display_operator(operator: Any) -> str:
    """연산자를 안내문에 쓸 Vizier 표기로 바꾼다 (in -> IN, not_in -> NOT IN)."""
    canonical = normalize_operator(operator)
    if canonical is None:
        return ""
    return _DISPLAY.get(canonical, canonical)


def is_list_operator(operator: Any) -> bool:
    return normalize_operator(operator) in LIST_OPERATORS


def split_list_value(value: Any) -> List[str]:
    """IN / NOT IN 값을 항목 목록으로 나눈다.

    콤마로 이어진 문자열("1,2,3", "GOLD, VIP")은 콤마로 나누고 각 항목 앞뒤 공백을
    지운다. 배열로 와도 받아들인다. 빈 항목도 그대로 남겨 두므로(""),
    호출하는 쪽에서 빈 항목을 오류로 처리할 수 있다.
    """
    if value is None:
        return [""]
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = str(value).split(",")
    out: List[str] = []
    for item in items:
        if isinstance(item, bool):
            out.append("true" if item else "false")
        elif item is None:
            out.append("")
        else:
            out.append(str(item).strip())
    return out


def to_number(text: Any) -> Optional[float]:
    """숫자로 읽을 수 있으면 float, 아니면 None."""
    if isinstance(text, bool) or text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip()
    if not s:
        return None
    try:
        num = float(s)
    except (ValueError, TypeError):
        return None
    if num != num or num in (float("inf"), float("-inf")):  # nan / inf 제외
        return None
    return num
