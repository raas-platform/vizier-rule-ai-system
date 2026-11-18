"""Vizier 연산자(IN / NOT IN) 정렬, CORS 제한, 헤더 보안 테스트.

스펙: 프로젝트 파일 judge/operator-cors-requirements.md (2026-11-18)
"""

import asyncio
import itertools
import logging

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.models.rule import Rule
from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.utils.operators import normalize_operator, split_list_value

_n = itertools.count(1)


def C(key, op, val, typ="String"):
    return {
        "condUuid": f"op{next(_n):03d}",
        "keyName": key,
        "dispName": key,
        "operator": op,
        "value": val,
        "fieldDataType": typ,
    }


def N(key, op, val):
    return C(key, op, val, "Number")


def G(logic, *kids):
    return {"logicType": logic, "condition": list(kids)}


def analyze(tree):
    rule = Rule(ruleUuid="t", ruleName="t", ruleMsg="t", conditionTree=tree)
    return asyncio.run(RuleAnalyzerV2().analyze_rule(rule))


def issues_of(result, issue_type, severity=None):
    return [
        i
        for i in result.issues
        if i.issue_type == issue_type and (severity is None or i.severity == severity)
    ]


def errors(result):
    return [i for i in result.issues if i.severity == "error"]


# ---------------------------------------------------------------------------
# 1-1. 연산자 표기 정규화
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("IN", "in"),
        ("in", "in"),
        (" In ", "in"),
        ("NOT IN", "not_in"),
        ("not in", "not_in"),
        ("NOT   IN", "not_in"),
        ("  Not In ", "not_in"),
        ("not_in", "not_in"),
        ("NOT_IN", "not_in"),
        ("==", "=="),
        (" >= ", ">="),
    ],
)
def test_normalize_operator(raw, expected):
    assert normalize_operator(raw) == expected


@pytest.mark.parametrize("op", ["IN", "NOT IN", "in", "not_in", "not  in", " In "])
@pytest.mark.parametrize("typ,val", [("String", "GOLD,VIP"), ("Number", "1,2,3")])
def test_in_spellings_accepted(op, typ, val):
    result = analyze(G("AND", C("F", op, val, typ)))
    assert not issues_of(result, "invalid_operator")
    assert not issues_of(result, "type_mismatch")
    assert result.is_valid


# ---------------------------------------------------------------------------
# 1-2. 타입별 허용 연산자
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("op", ["==", "!=", "IN", "NOT IN"])
def test_string_allowed_operators(op):
    result = analyze(G("AND", C("GRADE", op, "VIP")))
    assert not issues_of(result, "invalid_operator")


@pytest.mark.parametrize(
    "op", [">", ">=", "<", "<=", "contains", "not_contains", "starts_with", "ends_with"]
)
def test_string_disallowed_operators(op):
    c = C("GRADE", op, "VIP")
    result = analyze(G("AND", c))
    hit = issues_of(result, "invalid_operator", "error")
    assert hit and hit[0].condUuid == c["condUuid"]
    assert not result.is_valid


@pytest.mark.parametrize("op", ["==", "!=", ">", ">=", "<", "<=", "IN", "NOT IN"])
def test_number_allowed_operators(op):
    result = analyze(G("AND", N("AGE", op, "3")))
    assert not issues_of(result, "invalid_operator")
    assert result.is_valid


@pytest.mark.parametrize("op", ["contains", "not_contains", "starts_with", "ends_with"])
def test_number_disallowed_operators(op):
    result = analyze(G("AND", N("AGE", op, "3")))
    assert issues_of(result, "invalid_operator", "error")


def test_boolean_handling_kept():
    # Boolean 처리 코드는 이번 범위 밖: 기존 동작 유지 (==는 정상, IN은 허용 안 함)
    assert analyze(G("AND", C("IS_VIP", "==", "true", "Boolean"))).is_valid
    assert issues_of(analyze(G("AND", C("IS_VIP", "IN", "true", "Boolean"))), "invalid_operator")


# ---------------------------------------------------------------------------
# 1-3. invalid_operator 안내문은 Vizier 표기
# ---------------------------------------------------------------------------
def test_invalid_operator_suggestion_uses_vizier_spelling():
    result = analyze(G("AND", C("NAME", "contains", "김")))
    sug = issues_of(result, "invalid_operator")[0].suggestion
    assert "IN" in sug and "NOT IN" in sug
    assert "not_in" not in sug and "contains" not in sug
    assert "==" in sug and "!=" in sug and ">=" not in sug

    sug_num = issues_of(analyze(G("AND", N("AGE", "contains", "3"))), "invalid_operator")[0].suggestion
    for op in ["==", "!=", ">", ">=", "<", "<=", "IN", "NOT IN"]:
        assert op in sug_num


# ---------------------------------------------------------------------------
# 1-4. 응답에 담긴 연산자는 요청 원문 그대로
# ---------------------------------------------------------------------------
def test_response_keeps_original_operator_text():
    client = TestClient(main_module.app)
    body = [
        {
            "ruleUuid": "r1",
            "ruleName": "r1",
            "ruleMsg": "r1",
            "conditionTree": G("AND", N("AGE", "NOT IN", "1,2"), C("G", "IN", "A, B")),
        }
    ]
    res = client.post("/rules/validate-json", json=body)
    assert res.status_code == 200
    ops = set()
    for f in res.json()["field_analysis"]:
        ops |= set(f["operators_used"])
    assert ops == {"NOT IN", "IN"}
    assert res.json()["is_valid"] is True


# ---------------------------------------------------------------------------
# 2-1. 값 나누기
# ---------------------------------------------------------------------------
def test_split_list_value():
    assert split_list_value("1,2,3") == ["1", "2", "3"]
    assert split_list_value("GOLD, VIP") == ["GOLD", "VIP"]
    assert split_list_value(" A ,B ") == ["A", "B"]
    assert split_list_value(["1", 2, " 3 "]) == ["1", "2", "3"]
    assert split_list_value("1,,2") == ["1", "", "2"]
    assert split_list_value("") == [""]


def test_in_value_as_array_accepted():
    result = analyze(G("AND", N("AGE", "IN", ["1", "2", "3"])))
    assert result.is_valid and not result.issues


# ---------------------------------------------------------------------------
# 2-2. 빈 항목은 오류
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "val,where",
    [("1,,2", "2번째"), ("1,", "2번째"), (",1", "1번째"), ("", "값이 비어")],
)
@pytest.mark.parametrize("typ", ["String", "Number"])
def test_empty_item_is_error(val, where, typ):
    c = C("F", "IN", val, typ)
    result = analyze(G("AND", c))
    hit = [i for i in issues_of(result, "type_mismatch", "error") if "빈 항목" in i.explanation]
    assert hit, result.issues
    assert hit[0].condUuid == c["condUuid"]
    assert where in hit[0].explanation
    assert not result.is_valid


# ---------------------------------------------------------------------------
# 2-3. Number 필드는 항목마다 숫자 검사
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("val", ["1,2,3", "1, 2, 3", "-1,0.5,10", "7"])
@pytest.mark.parametrize("op", ["IN", "NOT IN"])
def test_number_in_all_numeric_no_type_mismatch(op, val):
    result = analyze(G("AND", N("AGE", op, val)))
    assert not issues_of(result, "type_mismatch")
    assert result.is_valid


def test_number_in_non_numeric_item_reported_with_value():
    c = N("AGE", "IN", "1,abc,3,x")
    result = analyze(G("AND", c))
    hit = issues_of(result, "type_mismatch", "error")
    assert len(hit) == 1 and hit[0].condUuid == c["condUuid"]
    assert "'abc'" in hit[0].explanation and "'x'" in hit[0].explanation
    assert "'1'" not in hit[0].explanation
    assert not result.is_valid


def test_string_in_numeric_looking_items_ok():
    assert analyze(G("AND", C("CODE", "IN", "001,002"))).is_valid


# ---------------------------------------------------------------------------
# 2-4. 중복 항목은 경고
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("typ,val,dup", [("Number", "1,2,2", "'2'"), ("String", "A, B, A", "'A'")])
def test_duplicate_item_is_warning(typ, val, dup):
    c = C("F", "IN", val, typ)
    result = analyze(G("AND", c))
    hit = issues_of(result, "duplicate_condition", "warning")
    assert hit and hit[0].condUuid == c["condUuid"] and dup in hit[0].explanation
    assert result.is_valid
    assert not errors(result)


# ---------------------------------------------------------------------------
# 2-5. 모순 판정 연결
# ---------------------------------------------------------------------------
CONTRADICTIONS = [
    ("IN과 == 겹치지 않음(숫자)", lambda: G("AND", N("A", "IN", "1,2"), N("A", "==", "3"))),
    ("IN과 == 겹치지 않음(문자)", lambda: G("AND", C("G", "IN", "GOLD,VIP"), C("G", "==", "BASIC"))),
    ("NOT IN에 == 포함(숫자)", lambda: G("AND", N("A", "NOT IN", "1,2"), N("A", "==", "2"))),
    ("NOT IN에 == 포함(문자)", lambda: G("AND", C("G", "==", "VIP"), C("G", "NOT IN", "GOLD, VIP"))),
    ("IN 전부 범위 밖(>)", lambda: G("AND", N("A", "IN", "1,2,3"), N("A", ">", "5"))),
    ("IN 전부 범위 밖(<=)", lambda: G("AND", N("A", "IN", "10,20"), N("A", "<=", "5"))),
    ("IN 전부 범위 밖(구간)", lambda: G("AND", N("A", "IN", "1,9"), N("A", ">=", "3"), N("A", "<", "7"))),
    ("IN 경계 미포함", lambda: G("AND", N("A", "IN", "5"), N("A", ">", "5"))),
    ("IN 둘 교집합 없음(문자)", lambda: G("AND", C("G", "IN", "A,B"), C("G", "IN", "C,D"))),
    ("IN 둘 교집합 없음(숫자)", lambda: G("AND", N("A", "IN", "1,2"), N("A", "IN", "3"))),
    ("중첩 AND 안의 IN", lambda: G("AND", N("A", "IN", "1,2"), G("AND", N("A", "==", "3")))),
    ("Vizier 표기 섞임", lambda: G("AND", N("A", "in", "1"), N("A", "NOT  IN", "1"), N("A", "==", "1"))),
]


@pytest.mark.parametrize("title,tree", CONTRADICTIONS, ids=[c[0] for c in CONTRADICTIONS])
def test_in_contradictions(title, tree):
    t = tree()
    result = analyze(t)
    hit = issues_of(result, "self_contradiction", "error")
    assert hit, f"{title}: {[(i.issue_type, i.explanation) for i in result.issues]}"
    assert not result.is_valid


def test_contradiction_points_to_first_condition_in_tree():
    a, b = N("A", "==", "3"), N("A", "IN", "1,2")
    hit = issues_of(analyze(G("AND", a, b)), "self_contradiction")
    assert hit[0].condUuid == a["condUuid"]


def test_or_branch_dead_makes_rule_invalid():
    # OR 가지 정책(기존 확정): 죽은 가지 하나라도 있으면 그 조건 오류 + 룰 무효
    dead = N("A", "IN", "1,2")
    tree = G("OR", G("AND", dead, N("A", "==", "3")), N("A", "==", "5"))
    result = analyze(tree)
    hit = issues_of(result, "self_contradiction", "error")
    assert hit and hit[0].condUuid == dead["condUuid"]
    assert not result.is_valid


# ---------------------------------------------------------------------------
# 2-6. 오탐 금지
# ---------------------------------------------------------------------------
NO_FALSE_POSITIVES = [
    ("IN과 == 겹침", lambda: G("AND", N("A", "IN", "1,2"), N("A", "==", "2"))),
    ("IN과 == 겹침(문자)", lambda: G("AND", C("G", "IN", "GOLD, VIP"), C("G", "==", "VIP"))),
    ("NOT IN에 == 없음", lambda: G("AND", N("A", "NOT IN", "1,2"), N("A", "==", "3"))),
    ("IN 일부만 범위 밖", lambda: G("AND", N("A", "IN", "1,7"), N("A", ">", "5"))),
    ("IN 경계 포함", lambda: G("AND", N("A", "IN", "5"), N("A", ">=", "5"))),
    ("IN 둘 교집합 있음", lambda: G("AND", C("G", "IN", "A,B"), C("G", "IN", "B,C"))),
    ("IN과 NOT IN 겹침 일부", lambda: G("AND", N("A", "IN", "1,2"), N("A", "NOT IN", "2,3"))),
    ("NOT IN 둘", lambda: G("AND", N("A", "NOT IN", "1"), N("A", "NOT IN", "2"))),
    ("IN과 !=", lambda: G("AND", N("A", "IN", "1,2"), N("A", "!=", "1"))),
    ("OR 가지 사이 IN", lambda: G("OR", N("A", "IN", "1,2"), N("A", "==", "3"))),
    ("OR 가지 사이 IN(문자)", lambda: G("OR", C("G", "IN", "A"), C("G", "IN", "B"))),
    ("다른 필드", lambda: G("AND", N("A", "IN", "1,2"), N("B", "==", "3"))),
    ("숫자 1과 1.0", lambda: G("AND", N("A", "IN", "1,2"), N("A", "==", "1.0"))),
    ("IN 한 개만", lambda: G("AND", N("A", "IN", "1,2,3"))),
    ("NOT IN 한 개만", lambda: G("AND", C("G", "NOT IN", "STOP,BLOCK"))),
]


@pytest.mark.parametrize("title,tree", NO_FALSE_POSITIVES, ids=[c[0] for c in NO_FALSE_POSITIVES])
def test_in_no_false_positive(title, tree):
    result = analyze(tree())
    errs = errors(result)
    assert not errs, f"{title}: {[(i.issue_type, i.explanation) for i in errs]}"
    assert result.is_valid


def test_bad_in_value_not_used_for_contradiction():
    # 숫자 아닌 항목이 있는 IN은 type_mismatch만 내고 모순 판정에는 쓰지 않는다
    result = analyze(G("AND", N("A", "IN", "1,x"), N("A", "==", "5")))
    assert issues_of(result, "type_mismatch")
    assert not issues_of(result, "self_contradiction")


# ---------------------------------------------------------------------------
# 3. CORS
# ---------------------------------------------------------------------------
def _client(monkeypatch, environment="production", origins=None):
    monkeypatch.setattr(main_module.settings, "environment", environment)
    monkeypatch.setattr(main_module.settings, "cors_allowed_origins", origins)
    return TestClient(main_module.create_app())


def _preflight(client, origin, headers="Content-Type, X-User-Id, A-TOKEN"):
    return client.options(
        "/rules/validate-json",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": headers,
        },
    )


@pytest.mark.parametrize(
    "origin",
    [
        "https://dev.vizier-service.com",
        "https://demo.vizier-service.com",
        "https://prod.vizier-service.com",
    ],
)
def test_cors_default_origins_allowed(monkeypatch, origin):
    client = _client(monkeypatch)
    res = _preflight(client, origin)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == origin
    allowed = res.headers["access-control-allow-headers"].lower()
    for h in ["content-type", "x-user-id", "a-token", "x-api-key"]:
        assert h in allowed
    methods = res.headers["access-control-allow-methods"]
    assert set(m.strip() for m in methods.split(",")) == {"GET", "POST", "OPTIONS"}


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example.com",
        "http://dev.vizier-service.com",  # 스킴 다름
        "https://dev.vizier-service.com.evil.com",
        "http://localhost:5500",  # production에서는 로컬 거부
        "http://127.0.0.1:8080",
        "null",
    ],
)
def test_cors_other_origins_rejected_in_production(monkeypatch, origin):
    client = _client(monkeypatch)
    res = _preflight(client, origin)
    assert res.status_code == 400
    assert "access-control-allow-origin" not in res.headers
    # 일반 요청에도 허용 헤더가 붙지 않음
    res = client.get("/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in res.headers


def test_cors_no_wildcard(monkeypatch):
    client = _client(monkeypatch, origins="*,https://a.example.com")
    res = client.get("/health", headers={"Origin": "https://random.example.com"})
    assert res.headers.get("access-control-allow-origin") is None
    res = client.get("/health", headers={"Origin": "https://a.example.com"})
    assert res.headers["access-control-allow-origin"] == "https://a.example.com"
    assert res.headers["access-control-allow-origin"] != "*"


def test_cors_disallowed_header_rejected(monkeypatch):
    client = _client(monkeypatch)
    res = _preflight(client, "https://dev.vizier-service.com", headers="X-Evil")
    assert res.status_code == 400


def test_cors_env_override(monkeypatch):
    client = _client(monkeypatch, origins=" https://a.example.com/ , https://b.example.com")
    assert _preflight(client, "https://a.example.com").status_code == 200
    assert _preflight(client, "https://b.example.com").status_code == 200
    assert _preflight(client, "https://dev.vizier-service.com").status_code == 400


@pytest.mark.parametrize("environment", ["development", "staging"])
@pytest.mark.parametrize("origin", ["http://localhost:5500", "http://127.0.0.1:8080", "http://localhost"])
def test_cors_localhost_allowed_outside_production(monkeypatch, environment, origin):
    client = _client(monkeypatch, environment=environment)
    res = _preflight(client, origin)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", ["http://localhost.evil.com", "https://evil.com", "http://localhost:80@evil.com"])
def test_cors_dev_regex_is_strict(monkeypatch, origin):
    client = _client(monkeypatch, environment="development")
    assert _preflight(client, origin).status_code == 400


# ---------------------------------------------------------------------------
# 4-1. X-User-Id / A-TOKEN 값은 로그·응답 어디에도 남기지 않는다
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())
        if record.exc_info:
            self.lines.append(logging.Formatter().formatException(record.exc_info))


def test_sensitive_header_values_not_logged_or_returned(monkeypatch):
    user_id = "uid-SECRET-7f3a9"
    token = "tok-SECRET-b81c2"
    client = _client(monkeypatch, environment="development")
    body = [
        {
            "ruleUuid": "r1",
            "ruleName": "r1",
            "ruleMsg": "r1",
            "conditionTree": G("AND", N("AGE", "IN", "1,x"), C("NAME", "contains", "a")),
        }
    ]
    headers = {
        "Origin": "https://dev.vizier-service.com",
        "X-User-Id": user_id,
        "A-TOKEN": token,
    }
    # 앱 로거는 propagate=False라서, 존재하는 모든 로거에 직접 수집 핸들러를 붙인다
    cap = _Capture()
    loggers = [logging.getLogger()] + [
        lg for lg in logging.root.manager.loggerDict.values() if isinstance(lg, logging.Logger)
    ]
    saved = [(lg, lg.level) for lg in loggers]
    for lg in loggers:
        lg.addHandler(cap)
        lg.setLevel(logging.DEBUG)
    try:
        responses = [
            client.post("/rules/validate-json", json=body, headers=headers),
            client.post("/rules/validate-json", json={"bad": 1}, headers=headers),  # 422
            client.post("/rules/validate-json", content=b"{not json", headers=headers),
            client.get("/health", headers=headers),
        ]
    finally:
        for lg, level in saved:
            lg.removeHandler(cap)
            lg.setLevel(level)
    assert cap.lines  # 실제로 로그가 수집됐는지 확인
    logged = "\n".join(cap.lines)
    for value in (user_id, token):
        assert value not in logged
        for r in responses:
            assert value not in r.text
            assert value not in " ".join(r.headers.values())


# ---------------------------------------------------------------------------
# CloudFront 뒤 실제 클라이언트 IP (cloudfront-requirements.md 9번)
# ---------------------------------------------------------------------------
from starlette.requests import Request as _StarletteRequest  # noqa: E402

from app.middleware.rate_limiter import RateLimiter  # noqa: E402
from app.utils.client_ip import get_client_ip  # noqa: E402

SECRET = "s3cr3t-origin-value"


def _req(headers=None, peer="203.0.113.10"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return _StarletteRequest(
        {"type": "http", "method": "GET", "path": "/", "headers": raw, "client": (peer, 1234)}
    )


def _cf(monkeypatch, trust=True, secret=None):
    from app.config import settings

    monkeypatch.setattr(settings, "trust_cloudfront", trust)
    monkeypatch.setattr(settings, "cloudfront_origin_secret", secret)


def test_client_ip_default_ignores_forwarded_for(monkeypatch):
    _cf(monkeypatch, trust=False)
    req = _req({"X-Forwarded-For": "1.2.3.4", "X-Amz-Cf-Id": "abc"})
    assert get_client_ip(req) == "203.0.113.10"


def test_client_ip_direct_request_forwarded_for_ignored_when_trust_on(monkeypatch):
    _cf(monkeypatch, trust=True)
    # CloudFront 표시(X-Amz-Cf-Id)가 없는 직접 접속: 위조된 XFF 무시
    assert get_client_ip(_req({"X-Forwarded-For": "1.2.3.4"})) == "203.0.113.10"


def test_client_ip_cloudfront_uses_last_forwarded_for(monkeypatch):
    _cf(monkeypatch, trust=True)
    # AWS 문서 예: 뷰어가 192.0.2.4,192.0.2.3을 보내면 CloudFront가 뷰어 IP 192.0.2.2를 끝에 붙인다
    req = _req({"X-Forwarded-For": "192.0.2.4, 192.0.2.3, 192.0.2.2", "X-Amz-Cf-Id": "abc"}, peer="130.176.0.1")
    assert get_client_ip(req) == "192.0.2.2"
    req = _req({"X-Forwarded-For": "2001:db8::1", "X-Amz-Cf-Id": "abc"}, peer="130.176.0.1")
    assert get_client_ip(req) == "2001:db8::1"


def test_client_ip_cloudfront_bad_forwarded_for_falls_back(monkeypatch):
    _cf(monkeypatch, trust=True)
    for xff in ["", "not-an-ip", "1.2.3.4, garbage"]:
        req = _req({"X-Forwarded-For": xff, "X-Amz-Cf-Id": "abc"}, peer="130.176.0.1")
        assert get_client_ip(req) == "130.176.0.1"


def test_client_ip_secret_header_required_when_configured(monkeypatch):
    _cf(monkeypatch, trust=True, secret=SECRET)
    xff = {"X-Forwarded-For": "192.0.2.2", "X-Amz-Cf-Id": "abc"}
    assert get_client_ip(_req(xff)) == "203.0.113.10"  # 비밀 헤더 없음
    assert get_client_ip(_req({**xff, "X-Origin-Verify": "wrong"})) == "203.0.113.10"
    assert get_client_ip(_req({**xff, "X-Origin-Verify": SECRET})) == "192.0.2.2"


def test_rate_limit_separates_viewers_behind_one_edge(monkeypatch):
    _cf(monkeypatch, trust=True, secret=SECRET)
    limiter = RateLimiter()
    limiter.rate_limit_per_minute = 2
    edge = "130.176.0.1"

    def call(viewer):
        return limiter.is_allowed(
            _req({"X-Forwarded-For": viewer, "X-Origin-Verify": SECRET}, peer=edge)
        )[0]

    assert call("192.0.2.1") and call("192.0.2.1")
    assert not call("192.0.2.1")  # 같은 뷰어는 한도 초과
    assert call("192.0.2.9")  # 같은 엣지 뒤 다른 뷰어는 따로 계산


def test_rate_limit_spoofed_forwarded_for_does_not_bypass(monkeypatch):
    _cf(monkeypatch, trust=True, secret=SECRET)
    limiter = RateLimiter()
    limiter.rate_limit_per_minute = 2
    peer = "203.0.113.50"
    results = [
        limiter.is_allowed(_req({"X-Forwarded-For": f"10.0.0.{i}", "X-Amz-Cf-Id": "x"}, peer=peer))[0]
        for i in range(3)
    ]
    assert results == [True, True, False]
