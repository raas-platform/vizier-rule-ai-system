# Rule Validation & LLM Interaction Flow

이 문서는 `/rules/validate-json` 엔드포인트부터 HTML 리포트 생성까지, 코드베이스에 구현된 전체 데이터 흐름을 단계별로 요약합니다.

---

## 1. GUI → 백엔드: 룰 JSON 전송

```
POST /rules/validate-json
Body: [ { ruleUuid, ruleName, ruleMsg, conditionTree, ... } ]
```

* GUI(웹·데스크톱)가 검사 대상 룰 배열을 전송합니다.
* FastAPI 라우터: `backend/app/api/rule_validator.py` → `validate_rule_json()`

---

## 2. Rule 객체 변환 & 기본 검증

1. 첫 번째 룰만 선택 (`rule_data = rules_data[0]`).
2. `Rule(**rule_data)` 로 Pydantic 변환 시도 → 실패 시 `convert_json_to_rule()` 파서 사용.
3. `RuleAnalyzerV2.analyze_rule(rule)` 호출로 본격 검증 시작.

> 관련 코드
> * 37-50라인 `rule_validator.py`
> * `backend/app/services/rule_analyzer_v2.py`

---

## 3. RuleAnalyzerV2 – 내부 단계

| 순서 | 서브컴포넌트 | 기능 |
|------|-------------|------|
| 1 | **ConditionAnalyzer** | 조건 파싱·필드 타입 추론 |
| 2 | **IssueDetector** | 7가지 이슈 탐지 (missing, duplicate, type_mismatch …) |
| 3 | **AIEnhancer** | LLM 호출로 이슈 설명·개선·통찰 보강 |
| 4 | **MetricsGenerator** | 복잡도·품질·성능 메트릭 생성 |
| 5 | **ReportGenerator** | 요약, 카운트, 텍스트 보고서 제작 |

### 3-A. AIEnhancer – LLM 상호작용

1. **프롬프트 구성**
   * 검출된 `ConditionIssue` 목록, 오류 개수, 구조 정보 등 **일부 데이터**를 Python dict로 준비.
   * `json.dumps()` 로 JSON-모양 문자열 생성.
   * 안내 문구와 합쳐 하나의 프롬프트 문자열(`ai_prompt`)로 만들기.
2. **LLM 호출**
   * `llm_service.generate_text(ai_prompt, model_id)`
   * 네트워크 전송 데이터 → `messages=[{"role":"user","content": ai_prompt}]` (텍스트)
3. **응답 처리**
   * LLM은 지시대로 JSON-형식 문자열 반환.
   * `json.loads()` 성공 시 dict → 각 이슈에 `ai_explanation`, `ai_suggestion` 등 병합.

> 관련 코드: `backend/app/services/analyzers/ai_enhancer.py` 120-160라인 등

### 3-B. ValidationResult 생성

* `ValidationResult`(Pydantic) 객체에
  * 기본 이슈 정보 + AI 보강 내용 + 메트릭 + 구조 정보 포함.

---

## 4. FastAPI 응답: RuleValidationResponse

* 엔드포인트가 `ValidationResult` 를 `RuleValidationResponse` 로 래핑 후 반환.
* FastAPI 가 `.dict()` 호출 → **JSON** 으로 직렬화되어 GUI로 전송.

```
HTTP/200 OK
Body: {
  "is_valid": false,
  "issues": [ ... ],
  "ai_comment": "...",
  ...
}
```

---

## 5. GUI → 백엔드: HTML 리포트 생성 (후속 단계)

```
POST /rules/generate-ai-html-report
Body: <위 4단계 전체 JSON>
```

1. 백엔드가 `json.dumps(validation_result)` 로 **전체**를 프롬프트 문자열에 포함.
2. Claude 계열 LLM 호출 → HTML 문자열 반환.
3. GUI에 HTML 리포트 제공.

---

## 요약 다이어그램

```
GUI ──(Rule JSON)──▶ validate-json
          │
          ▼
   RuleAnalyzerV2
      ├─ ConditionAnalyzer
      ├─ IssueDetector
      ├─ AIEnhancer ──▶ LLM (text ↔ text)
      └─ Metrics/ReportGen
          │
          ▼
 HTTP 200 JSON ◀─── RuleValidationResponse
          │
          ▼
GUI ──(Validation JSON)──▶ generate-ai-html-report ──▶ LLM (text ↔ text)
          │
          ▼
        HTML 리포트
```

---

### 참고
* 모든 LLM 통신은 "텍스트 프롬프트 ↔ 텍스트 응답"이며, JSON 구조는 문자열 내부 포맷에 불과합니다.
* 코드 위치
  * LLM 서비스: `backend/app/services/llm_service.py`
  * 검증/AI 보강: `backend/app/services/rule_analyzer_v2.py`, `analyzers/ai_enhancer.py`
  * API 라우터: `backend/app/api/rule_validator.py` 