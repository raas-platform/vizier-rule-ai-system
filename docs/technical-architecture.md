# 🧠 Rule AI System 기술 아키텍처 문서

## 📋 개요

이 문서는 Rule AI System의 전체 아키텍처, 데이터 흐름, 소스 코드 구조 및 주요 함수에 대한 상세 설명을 제공합니다.

**문서 작성일**: 2024-05-25  
**최종 업데이트**: 2024-06-12  
**작성자**: 기술 문서 작성팀

## 🏗️ 시스템 아키텍처

### 전체 구조

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │         │                 │
│    Frontend     │ ◄─────► │    Backend      │ ◄─────► │    OpenAI API   │
│    (Vue.js)     │   HTTP  │    (FastAPI)    │   HTTP  │    (GPT Model)  │
│                 │         │                 │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 백엔드 구조

```
├── app/
│   ├── api/                   # API 엔드포인트 정의
│   │   ├── __init__.py       # API 라우터 설정
│   │   ├── rule_validator.py # 룰 검증 API (레거시)
│   │   ├── rule_report.py    # 리포트 생성 API
│   │   └── v1/               # 버전화된 API
│   │       └── rule_validator.py # 룰 검증 API v1
│   │
│   ├── models/               # 데이터 모델 정의
│   │   ├── __init__.py
│   │   ├── rule.py           # 룰 관련 데이터 모델
│   │   ├── validation_result.py # 검증 결과 모델
│   │   ├── rule_json_validation_request.py # JSON 검증 요청 모델
│   │   └── report.py         # 리포트 관련 모델
│   │
│   ├── services/             # 비즈니스 로직 서비스
│   │   ├── __init__.py
│   │   ├── llm_service.py    # LLM API 통신 서비스
│   │   ├── rule_analyzer.py  # 룰 검증 서비스
│   │   ├── rule_parser.py    # 룰 파싱 서비스
│   │   ├── rule_report_service.py # 리포트 생성 서비스
│   │   ├── fixed_report_service.py # 고정 형식 리포트 서비스
│   │   └── test_report.py    # 리포트 테스트 유틸리티
│   │
│   ├── config.py             # 환경 설정
│   └── main.py               # 애플리케이션 진입점
```

### 프론트엔드 구조

```
├── src/
│   ├── assets/              # 정적 파일 (이미지, 스타일)
│   ├── services/            # API 서비스
│   │   └── apiService.ts    # 백엔드 API 통신
│   │
│   ├── types/               # 타입 정의
│   │   └── rule.ts          # 룰 관련 인터페이스
│   │
│   ├── views/               # 화면 컴포넌트
│   │   └── ValidationReport.vue # 룰 검증 화면
│   │
│   ├── App.vue              # 메인 앱 컴포넌트
│   └── main.ts              # 앱 진입점
```

## 🌊 데이터 흐름

### 1. 룰 검증 흐름 (Rule Validation Flow)

```
┌─────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 사용자 입력  │────►│ ValidationReport.vue │──►│ apiService.ts   │────►│ rule_validator.py│
│ (JSON 룰)   │     │ (프론트엔드)       │     │ (post 메서드)    │     │ (API 엔드포인트) │
└─────────────┘     └───────────────────┘     └─────────────────┘     └────────┬────────┘
                                                                               │
                                                                               ▼
┌─────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 화면에 표시  │◄────│ ValidationReport.vue │◄───│ apiService.ts   │◄────│ RuleAnalyzerSvc │
│ (검증 결과)  │     │ (프론트엔드)       │     │ (응답 처리)     │     │ (룰 검증 처리)  │
└─────────────┘     └───────────────────┘     └─────────────────┘     └─────────────────┘
```

프로세스 설명:
1. 사용자가 ValidationReport 화면에 JSON 룰 입력
2. 프론트엔드에서 JSON 파싱 및 요청 객체 생성
   - `rule_json` 필드가 있으면 원본 사용, 없으면 래핑
3. `apiService.post('/api/v1/rules/validate-json', requestData)` 호출
4. 백엔드 API가 요청을 받아 RuleAnalyzerService 호출
5. RuleAnalyzerService가 룰 분석 및 검증 수행:
   - 중복 조건 검출
   - 연산자 검증
   - 타입 일치 확인
   - 논리적 모순 확인
   - 구조 복잡도 평가
6. 결과 객체 생성:
   - 유효성 여부
   - 요약 정보
   - 이슈 목록
   - 이슈 유형별 개수
   - 구조 정보
7. 프론트엔드에서 응답 처리 및 결과 시각화

### 2. 리포트 생성 흐름 (Rule Report Flow)

```
┌─────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌────────────────┐
│ JSON 룰 &   │────►│ ValidationReport.vue │──►│ apiService.ts   │────►│ rule_report.py │
│ 검증 결과    │     │ (프론트엔드)       │     │ (generateReport)│     │ (API 엔드포인트)│
└─────────────┘     └───────────────────┘     └─────────────────┘     └────────┬───────┘
                                                                               │
                                                                               ▼
┌─────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌────────────────┐
│ 화면에 표시  │◄────│ ValidationReport.vue │◄───│ apiService.ts   │◄────│ RuleReportSvc  │
│ (마크다운 리포트)│  │ (프론트엔드)       │     │ (응답 처리)     │     │ (리포트 생성)  │
└─────────────┘     └───────────────────┘     └─────────────────┘     └────────┬───────┘
                                                                               │
                                                                               ▼
                                                                      ┌─────────────────┐
                                                                      │   LLMService    │
                                                                      │ (OpenAI API 호출)│
                                                                      └─────────────────┘
```

프로세스 설명:
1. 사용자가 ValidationReport 화면에서 검증 결과 확인 후 리포트 생성 요청
2. 프론트엔드는 `apiService.generateRuleReport()` 메서드로 API 호출
3. 백엔드의 rule_report.py가 요청을 받아 RuleReportService 호출
4. RuleReportService는 LLMService를 통해 OpenAI API 호출
5. 리포트용 프롬프트 생성 및 OpenAI API 호출
6. OpenAI가 생성한 마크다운 리포트를 응답으로 반환
7. 프론트엔드에서 마크다운을 HTML로 변환하여 표시

**중요**: 리포트 생성 API는 검증 API와 독립적으로 작동하며, 동일한 rule_json을 사용하지만 다른 분석을 수행합니다.

## 📁 주요 컴포넌트 상세 설명

### 백엔드 (Backend)

#### 1. LLMService (llm_service.py)
- **역할**: OpenAI API 통신 담당
- **주요 함수**:
  - `call_llm(prompt, system_message)`: LLM 모델에 요청 및 응답 처리
  - `generate_json(prompt, system_message)`: 구조화된 JSON 응답 생성
  - `get_text_generation(prompt, system_message)`: 텍스트 응답 생성
- **오류 처리**: API 키 인증, 응답 타임아웃, JSON 파싱 실패 처리

#### 2. RuleAnalyzerService (rule_analyzer.py)
- **역할**: 룰의 논리적 일관성과 구조적 문제 검증
- **주요 함수**:
  - `validate_rule(rule)`: 룰 객체 검증 및 결과 반환
  - `analyze_rule(rule_json)`: 룰 JSON 분석
  - `count_issues_by_type(issues)`: 이슈 유형별 개수 집계
  - `extract_unique_fields(conditions)`: 사용된 필드 목록 추출
  - `evaluate_structure_complexity(conditions)`: 구조 복잡도 평가
- **검증 항목**:
  - 중복 조건
  - 타입 불일치
  - 잘못된 연산자
  - 모순 조건
  - 구조 복잡도

#### 3. RuleParserService (rule_parser.py)
- **역할**: 다양한 형식의 룰 데이터 파싱 및 변환
- **주요 함수**:
  - `parse_rule_json(rule_json)`: JSON에서 규칙 객체로 변환
  - `normalize_rule_structure(rule_data)`: 규칙 구조 정규화
  - `extract_conditions(condition_data)`: 조건 정보 추출

#### 4. RuleReportService (rule_report_service.py)
- **역할**: 룰 분석 리포트 생성
- **주요 함수**:
  - `generate_report(rule_json, validation_result)`: 분석 리포트 생성
  - `create_report_prompt(rule_data, validation_result)`: 리포트 프롬프트 생성
  - `format_rule_for_report(rule_data)`: 리포트용 룰 포맷팅
- **생성 항목**:
  - 기본 룰 정보
  - 조건 구조 분석
  - 이슈 설명 및 제안
  - 참고 사항 및 개선 방안

### 프론트엔드 (Frontend)

#### 1. ValidationReport (ValidationReport.vue)
- **역할**: 룰 검증 및 리포트 생성 화면
- **주요 기능**:
  - JSON 입력 처리 (직접 입력, 파일 업로드)
  - 검증 요청 및 결과 표시
  - 리포트 생성 및 표시
  - 마크다운 렌더링
- **주요 컴포넌트**:
  - JSON 편집기
  - 검증 결과 패널
  - 이슈 목록 테이블
  - 마크다운 렌더러
  - 파일 업로드 컴포넌트

#### 2. ApiService (apiService.ts)
- **역할**: 백엔드 API 통신 담당
- **주요 함수**:
  - `validateRuleJson(ruleJson)`: 룰 검증 API 호출
  - `generateRuleReport(ruleJson, validationResult)`: 리포트 생성 API 호출
  - `post(endpoint, data)`: 일반 POST 요청 처리
- **오류 처리**: API 연결 실패, 응답 타임아웃, 요청 형식 오류 처리

## 🔄 API 엔드포인트

### 1. 룰 검증 API
- **URL**: `/api/v1/rules/validate-json`
- **메서드**: POST
- **요청 형식**:
```json
{
  "rule_json": {
    "ruleId": "R123",
    "name": "3회선 이상 할인",
    "description": "무선 회선이 3개 이상인 고객에게 10% 할인 적용",
    "conditions": {...},
    "priority": 1,
    "message": [...]
  }
}
```
- **응답 형식**:
```json
{
  "is_valid": true,
  "summary": "이 룰은 유효합니다.",
  "issues": [...],
  "issue_counts": {"duplicate_condition": 1, ...},
  "structure": {
    "depth": 3,
    "condition_count": 5,
    "unique_fields": ["MBL_ACT_MEM_PCNT", "ENTR_STUS_CD"]
  }
}
```

### 2. 리포트 생성 API
- **URL**: `/api/v1/rules/report`
- **메서드**: POST
- **요청 형식**:
```json
{
  "rule_json": {
    "ruleId": "R123",
    "name": "3회선 이상 할인",
    "description": "무선 회선이 3개 이상인 고객에게 10% 할인 적용",
    "conditions": {...},
    "priority": 1,
    "message": [...]
  },
  "include_markdown": true
}
```
- **응답 형식**:
```json
{
  "report": "# 룰 분석 리포트\n\n## 개요\n\n이 룰은 ...",
  "rule_id": "R123",
  "rule_name": "3회선 이상 할인"
}
```

## 📊 데이터 모델

### Rule 모델 (rule.py)
```python
class RuleCondition(BaseModel):
    field: Optional[str] = None
    operator: str
    value: Any = None
    conditions: Optional[List['RuleCondition']] = None

class Rule(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    conditions: List[RuleCondition]
    actions: Optional[List[Dict[str, Any]]] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = True
```

### ValidationResult 모델 (validation_result.py)
```python
class ConditionIssue(BaseModel):
    field: Optional[str] = None
    issue_type: str
    severity: str
    location: str
    explanation: str
    suggestion: str

class StructureInfo(BaseModel):
    depth: int
    condition_count: int
    condition_node_count: int
    field_condition_count: int
    unique_fields: List[str]

class ValidationResult(BaseModel):
    is_valid: bool
    summary: str
    issues: List[ConditionIssue]
    issue_counts: Dict[str, int]
    structure: StructureInfo
    rule_summary: Optional[str] = None
    complexity_score: Optional[float] = None
    ai_comment: Optional[str] = None
```

### RuleJsonValidationRequest 모델 (rule_json_validation_request.py)
```python
class RuleJsonValidationRequest(BaseModel):
    rule_json: Dict[str, Any]
```

### Report 모델 (report.py)
```python
class RuleReportRequest(BaseModel):
    rule_json: Dict[str, Any]
    include_markdown: bool = True
    validation_result: Optional[Dict[str, Any]] = None

class RuleReport(BaseModel):
    report: str
    rule_id: str
    rule_name: str
```

## 🛠️ 개발 및 운영 가이드

### 개발 환경 설정
- **Python**: 3.9 이상 필요
- **Node.js**: 16.0 이상 필요
- **개발 서버 실행**:
  ```bash
  # 백엔드
  cd backend
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  
  # 프론트엔드
  cd frontend
  npm install
  npm run dev
  ```

### API 키 설정
1. 프로젝트 루트에 `.env` 파일 생성
2. 다음 내용 추가:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

### 빌드 및 배포
- **Docker 사용**:
  ```bash
  docker-compose up -d
  ```
- **수동 배포**:
  ```bash
  # 프론트엔드 빌드
  cd frontend
  npm run build
  
  # 백엔드 실행
  cd backend
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```

### 로깅 설정
- 로그 레벨: `/backend/app/config.py`에서 설정
- 로그 파일: `/var/log/rule-ai-system/app.log`에 기록
- 로그 포맷: JSON 포맷으로 구조화된 로깅 사용

## 🔍 성능 및 한계

### 성능 지표
- **응답 시간**:
  - 룰 검증: 평균 0.5초 (복잡도에 따라 변동)
  - 리포트 생성: 평균 5초 (OpenAI API 응답 시간에 의존)
- **동시 처리 능력**: 기본 설정으로 최대 50 동시 요청

### 한계
- **룰 크기**: 매우 큰 룰(1000개 이상의 조건)의 경우 성능 저하
- **API 의존성**: OpenAI API 장애 시 리포트 생성 기능 사용 불가
- **필드 인식**: 시스템에 등록되지 않은 필드는 타입 검증이 제한적
- **모순 검출**: 복잡한 논리 구조에서는 일부 모순 검출 제한적 