# 룰 검사 로직 회귀 테스트용 58개 케이스 (출처: 로컬 로직 테스트 vizier-logic-test/cases.py)
# 50+ 로직 테스트 케이스. 기대값은 "올바른 룰 검사기라면 이래야 한다"는 기준으로 먼저 정함(현재 서버 출력 보고 맞춘 것 아님).
import itertools
_n = itertools.count(1)
def C(key, op, val, typ="String", disp=None, uid=None):
    return {"condUuid": uid or f"c{next(_n):03d}", "keyName": key, "dispName": disp or key,
            "operator": op, "value": val, "fieldDataType": typ}
def G(logic, *kids): return {"logicType": logic, "condition": list(kids)}

CASES = []
def case(cid, cat, title, tree, valid, must=(), must_not=()):
    # must: [(issue_type, condUuid or None)]  condUuid None이면 유형만 확인
    CASES.append(dict(id=cid, cat=cat, title=title, tree=tree, valid=valid, must=list(must), must_not=list(must_not)))

def U(c): return c["condUuid"]

# ---------- 간단·정상 (오류 없어야 함) ----------
case("S01","간단·정상","문자열 == 한 개", G("AND", C("GRADE","==","VIP")), True, must_not=["self_contradiction","type_mismatch","invalid_operator"])
case("S02","간단·정상","숫자 >= 0", G("AND", C("AGE",">=","0","Number")), True, must_not=["type_mismatch","invalid_operator"])
case("S03","간단·정상","불리언 == true", G("AND", C("IS_VIP","==","true","Boolean")), True, must_not=["type_mismatch","invalid_operator"])
case("S04","간단·정상","나이 18 이상 65 미만 (AND 범위)", G("AND", C("AGE",">=","18","Number"), C("AGE","<","65","Number")), True, must_not=["self_contradiction"])
case("S05","간단·정상","문자열 != 한 개", G("AND", C("STATUS","!=","STOP")), True, must_not=["self_contradiction","invalid_operator"])
case("S06","간단·정상","10 이상 20 이하 (AND 범위)", G("AND", C("CNT",">=","10","Number"), C("CNT","<=","20","Number")), True, must_not=["self_contradiction"])
case("S07","간단·정상","같은 필드 OR 두 값 (A 또는 B)", G("OR", C("REGION","==","SEOUL"), C("REGION","==","BUSAN")), True, must_not=["self_contradiction"])
case("S08","간단·정상","숫자 == 0", G("AND", C("LINES","==","0","Number")), True, must_not=["type_mismatch"])
case("S09","간단·정상","문자열 contains", G("AND", C("NAME","contains","김")), True, must_not=["invalid_operator"])
case("S10","간단·정상","불리언 != false", G("AND", C("AGREE","!=","false","Boolean")), True, must_not=["type_mismatch","invalid_operator"])
case("S11","간단·정상","숫자 소수값 12.5", G("AND", C("RATE",">=","12.5","Number")), True, must_not=["type_mismatch"])
case("S12","간단·정상","숫자 음수 -3", G("AND", C("DELTA",">","-3","Number")), True, must_not=["type_mismatch"])

# ---------- 단일 오류 ----------
c=C("AGE",">=","abc","Number"); case("E01","단일 오류","숫자 필드에 abc", G("AND", c), False, must=[("type_mismatch",U(c))])
c=C("IS_VIP","==","maybe","Boolean"); case("E02","단일 오류","불리언 필드에 maybe", G("AND", c), False, must=[("type_mismatch",U(c))])
c=C("NAME",">","홍길동"); case("E03","단일 오류","문자열에 > 연산자", G("AND", c), False, must=[("invalid_operator",U(c))])
c=C("IS_VIP",">=","true","Boolean"); case("E04","단일 오류","불리언에 >= 연산자", G("AND", c), False, must=[("invalid_operator",U(c))])
c=C("AGE","contains","3","Number"); case("E05","단일 오류","숫자에 contains 연산자", G("AND", c), False, must=[("invalid_operator",U(c))])
a,b=C("AGE","==","30","Number"),C("AGE","==","25","Number"); case("E06","단일 오류","AND 나이==30 그리고 ==25", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("AGE",">","10","Number"),C("AGE","<","5","Number"); case("E07","단일 오류","AND 나이>10 그리고 <5", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("AGE",">=","30","Number"),C("AGE","<","25","Number"); case("E08","단일 오류","AND 나이>=30 그리고 <25", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("ST","==","ACTIVE"),C("ST","!=","ACTIVE"); case("E09","단일 오류","AND 상태==ACTIVE 그리고 !=ACTIVE", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("CNT","<=","5","Number"),C("CNT",">","5","Number"); case("E10","단일 오류","AND <=5 그리고 >5", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("IS_VIP","==","true","Boolean"),C("IS_VIP","==","false","Boolean"); case("E11","단일 오류","AND 불리언 true 그리고 false", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("AGE","<","18","Number"),C("AGE",">","65","Number"); case("E12","단일 오류","AND 나이<18 그리고 >65", G("AND",a,b), False, must=[("self_contradiction",None)])
a,b=C("G","==","VIP"),C("G","==","VIP"); case("E13","단일 오류","완전 중복 조건 (경고)", G("AND",a,b), True, must=[("duplicate_condition",None)])
case("E14","단일 오류","조건이 하나도 없음", G("AND"), False, must=[("missing_condition",None)])
c=C("AGE",">=","","Number"); case("E15","단일 오류","숫자 필드 값이 빈칸", G("AND", c), False, must=[("type_mismatch",U(c))])
c=C("","==","X"); case("E16","단일 오류","필드 키가 빈칸", G("AND", c), False)
c=C("AGE",">=","30","Number"); d=C("AGE",">=","30","Number"); case("E17","단일 오류","중복: 숫자 >=30 두 번 (경고)", G("AND",c,d), True, must=[("duplicate_condition",None)])

# ---------- 오탐 함정 (잡으면 안 됨) ----------
case("F01","오탐 함정","OR 나이==30 또는 ==25", G("OR", C("AGE","==","30","Number"), C("AGE","==","25","Number")), True, must_not=["self_contradiction"])
case("F02","오탐 함정","OR 나이>=30 또는 <25", G("OR", C("AGE",">=","30","Number"), C("AGE","<","25","Number")), True, must_not=["self_contradiction"])
case("F03","오탐 함정","AND 5 초과 10 미만", G("AND", C("CNT",">","5","Number"), C("CNT","<","10","Number")), True, must_not=["self_contradiction"])
case("F04","오탐 함정","서로 다른 필드 ==1, ==2", G("AND", C("A_CNT","==","1","Number"), C("B_CNT","==","2","Number")), True, must_not=["self_contradiction"])
case("F05","오탐 함정","AND 상태!=A 그리고 !=B", G("AND", C("ST","!=","A"), C("ST","!=","B")), True, must_not=["self_contradiction"])
case("F06","오탐 함정","OR 안 각각의 AND 가지에 나이>=30 / 나이<25", G("OR", G("AND", C("AGE",">=","30","Number"), C("G","==","VIP")), G("AND", C("AGE","<","25","Number"), C("G","==","GOLD"))), True, must_not=["self_contradiction"])
case("F07","오탐 함정","OR 상태==ACTIVE 또는 !=ACTIVE", G("OR", C("ST","==","ACTIVE"), C("ST","!=","ACTIVE")), True, must_not=["self_contradiction"])
case("F08","오탐 함정","OR 불리언 true 또는 false", G("OR", C("IS_VIP","==","true","Boolean"), C("IS_VIP","==","false","Boolean")), True, must_not=["self_contradiction"])
case("F09","오탐 함정","OR 가지별로 다른 지역", G("OR", G("AND", C("REGION","==","SEOUL"), C("AGE",">=","20","Number")), G("AND", C("REGION","==","BUSAN"), C("AGE",">=","30","Number"))), True, must_not=["self_contradiction"])

# ---------- 복잡·혼합 ----------
case("M01","복잡·정상","3단계 중첩, 서로 다른 필드 8개 (정상)",
  G("AND", C("SVC","==","LZP01"), C("MKT","==","LGT"),
    G("OR", C("MBL_CNT",">=","2","Number"),
      G("AND", C("MBL_CNT",">=","1","Number"), G("OR", C("IOT_CNT",">=","1","Number"), C("MVNO_CNT",">=","1","Number")))),
    C("IS_ACT","==","true","Boolean"), C("JOIN_YRS",">=","0","Number")), True, must_not=["self_contradiction","type_mismatch","invalid_operator"])
big = [C(f"F{i:02d}","==",f"V{i}") for i in range(1,21)]
case("M02","복잡","조건 20개 + 3단계 중첩 (복잡성 경고 기대)", G("AND", *big[:6], G("OR", *big[6:12], G("AND", *big[12:16], G("OR", *big[16:])))), True, must=[("complexity_warning",None)])
a=C("AGE",">=","abc","Number"); b=C("NAME",">","홍"); case("M03","혼합 오류","타입 오류 + 연산자 오류", G("AND",a,b,C("G","==","VIP")), False, must=[("type_mismatch",U(a)),("invalid_operator",U(b))])
a,b=C("CNT","==","1","Number"),C("CNT","==","2","Number"); case("M04","혼합 오류","OR 아래 AND 가지 안에서 ==1 그리고 ==2", G("OR", C("G","==","VIP"), G("AND",a,b)), False, must=[("self_contradiction",None)])
d=C("SCORE",">","xyz","Number"); case("M05","혼합 오류","4단계 깊이의 타입 오류", G("AND", C("A","==","1"), G("OR", C("B","==","2"), G("AND", C("C","==","3"), G("OR", d, C("E","==","5"))))), False, must=[("type_mismatch",U(d))])
a=C("IS_VIP",">","true","Boolean"); case("M06","혼합 오류","연산자 오류 + 중복", G("AND", a, C("G","==","VIP"), C("G","==","VIP")), False, must=[("invalid_operator",U(a)),("duplicate_condition",None)])
t=C("AGE",">=","abc","Number"); o=C("NAME","<=","가"); x1,x2=C("ST","==","A"),C("ST","!=","A")
case("M07","혼합 오류","타입 + 연산자 + 모순 3종", G("AND", t, o, x1, x2), False, must=[("type_mismatch",U(t)),("invalid_operator",U(o)),("self_contradiction",None)])
case("M08","혼합 오류","서로 다른 두 필드에 각각 모순", G("AND", C("AGE","==","30","Number"), C("AGE","==","25","Number"), C("ST","==","A"), C("ST","==","B")), False,
  must=[("self_contradiction",None)])
a=C("AGE",">=","abc","Number"); b=C("SCORE","<","xyz","Number"); case("M09","혼합 오류","서로 다른 필드 타입 오류 2건 (둘 다 표시)", G("AND",a,b), False, must=[("type_mismatch",U(a)),("type_mismatch",U(b))])
a=C("AGE",">=","abc","Number"); b=C("AGE","<","xyz","Number"); case("M10","혼합 오류","같은 필드 타입 오류 2건 (둘 다 표시)", G("AND",a,b), False, must=[("type_mismatch",U(a)),("type_mismatch",U(b))])
a=C("NAME",">","가"); b=C("NAME","<","하"); case("M11","혼합 오류","같은 필드 연산자 오류 2건 (둘 다 표시)", G("AND",a,b), False, must=[("invalid_operator",U(a)),("invalid_operator",U(b))])
case("M12","복잡·정상","실무형: 가족결합 할인 (정상 버전)",
  G("AND", C("DCNT_TRGT_SVC","==","LZP0000001",uid="u-svc"), C("MRKT_CD","==","LGT",uid="u-mkt"),
    G("OR", C("MBL_ACT_MEM_PCNT",">=","2","Number",uid="u-m2"), G("AND", C("MBL_ACT_MEM_PCNT","==","1","Number",uid="u-m1"), C("IOT_MEM_PCNT",">=","1","Number",uid="u-iot"))),
    C("ENTR_STUS_CD","==","정상",uid="u-st")), True, must_not=["self_contradiction","type_mismatch","invalid_operator"])
bad=C("IOT_MEM_PCNT",">=","하나","Number",uid="9f17d156-4459-4d56-bc8b-123044e13bc8")
case("M13","혼합 오류","실무형 + 깊은 곳 UUID 조건에 타입 오류",
  G("AND", C("DCNT_TRGT_SVC","==","LZP0000001"), G("OR", C("MBL_ACT_MEM_PCNT",">=","2","Number"), G("AND", C("MBL_ACT_MEM_PCNT",">=","1","Number"), G("OR", bad, C("MVNO_ACT_MEM_PCNT",">","0","Number"))))), False,
  must=[("type_mismatch",U(bad))])
a=C("IS_VIP","==","maybe","Boolean"); b=C("NAME",">","가"); cc=C("AGE","==","abc","Number")
case("M14","혼합 오류","maybe + 문자열> + 숫자abc", G("AND",a,b,cc), False, must=[("type_mismatch",U(a)),("invalid_operator",U(b)),("type_mismatch",U(cc))])
a,b=C("AGE","==","30","Number"),C("AGE","!=","30.0","Number"); case("M15","혼합 오류","숫자 ==30 그리고 !=30.0 (같은 값 다른 표기)", G("AND",a,b), False, must=[("self_contradiction",None)])
case("M16","혼합 오류","OR 안에 비어 있는 AND 그룹", G("OR", C("G","==","VIP"), G("AND")), False, must=[("missing_condition",None)])
a,b=C("AGE",">=","30","Number"),C("AGE","<","25","Number"); t=C("SCORE","==","abc","Number"); o=C("NAME",">","가"); d1,d2=C("R","==","S"),C("R","==","S")
case("M17","혼합 오류","모순+타입+연산자+중복 + 2단계 중첩", G("AND", a, b, G("OR", t, G("AND", o, d1, d2))), False,
  must=[("self_contradiction",None),("type_mismatch",U(t)),("invalid_operator",U(o)),("duplicate_condition",None)])
a,b=C("AGE",">","10","Number"),C("AGE","<","5","Number"); o=C("IS_VIP","contains","t","Boolean")
case("M18","혼합 오류","모순(>10,<5) + 불리언 contains", G("AND",a,b,o), False, must=[("self_contradiction",None),("invalid_operator",U(o))])
a,b,cc=C("CNT",">=","10","Number"),C("CNT","<=","20","Number"),C("CNT","==","50","Number")
case("M19","혼합 오류","10~20 범위인데 ==50 (AND)", G("AND",a,b,cc), False, must=[("self_contradiction",None)])
case("M20","복잡·정상","OR 루트, 가지 4개, 각 가지 2~3조건 (정상)",
  G("OR", G("AND", C("G","==","VIP"), C("AGE",">=","20","Number")), G("AND", C("G","==","GOLD"), C("AGE",">=","30","Number"), C("IS_APP","==","true","Boolean")),
        G("AND", C("G","==","SILVER"), C("PT",">=","1000","Number")), C("EMP","==","Y")), True, must_not=["self_contradiction","type_mismatch","invalid_operator"])

def to_req(cs):
    return [{"ruleUuid": f"lt-{cs['id']}", "ruleName": f"{cs['id']}_{cs['title']}", "ruleMsg": cs["title"], "conditionTree": cs["tree"]}]
