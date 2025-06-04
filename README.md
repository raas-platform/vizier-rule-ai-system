# Rule AI System 기술 문서

## 1. 프로젝트 개요

Rule AI System은 비즈니스 룰을 생성, 검증 및 분석하는 AI 기반 도구입니다. 자연어 처리 기술을 활용하여 텍스트 설명을 구조화된 룰로 변환하고, 기존 룰의 논리적 일관성을 검증하며, 상세한 분석 리포트를 생성합니다.

**주요 기능:**
- 자연어 설명에서 구조화된 룰 생성
- 기존 룰의 논리적 오류 및 문제점 검증
- 룰에 대한 상세 분석 리포트 생성
- 이해하기 쉬운 시각적 표현

## 2. 기술 스택

### 백엔드
- **언어**: Python 3.9+
- **프레임워크**: FastAPI
- **AI/ML**: OpenAI API (GPT 모델)
- **비동기 처리**: asyncio, uvicorn
- **데이터 검증**: Pydantic

### 프론트엔드
- **언어**: TypeScript
- **프레임워크**: Vue.js 3
- **상태 관리**: Vue Composition API
- **HTTP 클라이언트**: Axios
- **마크다운 렌더링**: marked
- **스타일링**: CSS (스코프 스타일)

### 개발 도구
- **패키지 관리**: npm (프론트엔드), pip (백엔드)
- **가상 환경**: venv
- **API 문서**: FastAPI 자동 생성 Swagger UI

## 3. 시스템 아키텍처

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │         │                 │
│    Frontend     │ ◄─────► │    Backend      │ ◄─────► │    OpenAI API   │
│    (Vue.js)     │   HTTP  │    (FastAPI)    │   HTTP  │    (GPT Model)  │
│                 │         │                 │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

- **프론트엔드**: 사용자 인터페이스 제공, 입력 관리, 결과 시각화
- **백엔드**: API 엔드포인트 제공, 룰 검증, 요청 처리, OpenAI API 통합
- **OpenAI API**: 자연어 처리, 룰 생성, 요약 생성

## 4. API 엔드포인트

### 기본 접두사
- `/api/v1/rules`

### 룰 생성 API
- **엔드포인트**: `/api/v1/rules/generate`
- **메서드**: POST
- **기능**: 자연어 설명을 구조화된 룰로 변환
- **요청 형식**:
  ```json
  {
    "description": "무선 회선이 3개 이상인 고객에게 10% 할인 적용",
    "additional_context": "통신사 프로모션을 위한 룰입니다"
  }
  ```
- **응답 형식**:
  ```json
  {
    "rule": {
      "id": "R123",
      "name": "3회선 이상 할인",
      "description": "무선 회선이 3개 이상인 고객에게 10% 할인 적용",
      "conditions": [...],
      "actions": [...],
      "priority": 1,
      "enabled": true
    },
    "explanation": "이 룰은 무선 회선 수를 확인하여 3개 이상인 경우 10% 할인을 적용합니다..."
  }
  ```

### 룰 검증 API
- **엔드포인트**: `/api/v1/rules/validate` & `/api/v1/rules/validate-json`
- **메서드**: POST
- **기능**: 룰의 논리적 일관성 검증
- **요청 형식 (validate)**:
  ```json
  {
    "rule": {
      "name": "3회선 이상 할인",
      "description": "무선 회선이 3개 이상인 고객에게 10% 할인 적용",
      "conditions": [...],
      "actions": [...],
      "priority": 1,
      "enabled": true
    }
  }
  ```
- **요청 형식 (validate-json)**:
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
    "issues": [
      {
        "severity": "warning",
        "field": "MBL_ACT_MEM_PCNT",
        "issue_type": "duplicate_condition",
        "location": "조건 1의 중첩 조건",
        "explanation": "'MBL_ACT_MEM_PCNT' 필드에 대한 중복된 조건이 있습니다.",
        "suggestion": "'MBL_ACT_MEM_PCNT' 필드에 중복된 조건이 있습니다. 하나의 조건으로 통합하세요."
      }
    ],
    "issue_counts": {
      "duplicate_condition": 1
    },
    "structure": {
      "depth": 3,
      "condition_count": 5,
      "unique_fields": ["MBL_ACT_MEM_PCNT", "ENTR_STUS_CD"]
    }
  }
  ```

### 룰 리포트 API
- **엔드포인트**: `/api/v1/rules/report`
- **메서드**: POST
- **기능**: 룰에 대한 상세 분석 리포트 생성
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

## 5. 데이터 모델

### Rule 모델
```typescript
interface Rule {
  id?: string;
  name: string;
  description: string;
  conditions: RuleCondition[];
  actions: RuleAction[];
  priority: number;
  enabled: boolean;
}
```

### RuleCondition 모델
```typescript
interface RuleCondition {
  field: string;
  operator: string;  // eq, neq, gt, lt, gte, lte, in, not_in, contains
  value: any;
}
```

### RuleAction 모델
```typescript
interface RuleAction {
  action_type: string;
  parameters: Record<string, any>;
}
```

### ValidationIssue 모델
```typescript
interface ValidationIssue {
  severity: 'error' | 'warning' | 'info';
  message?: string;
  field?: string;
  issue_type?: string;
  location?: string;
  explanation?: string;
  suggestion?: string;
}
```

### ValidationResult 모델
```typescript
interface ValidationResult {
  is_valid: boolean;
  summary: string;
  issues: ValidationIssue[];
  issue_counts?: Record<string, number>;
  structure?: {
    depth: number;
    condition_count: number;
    unique_fields: string[];
  };
}
```

## 6. 프론트엔드 구성요소

### 주요 화면

#### ValidationReport 화면
- **기능**: 룰 검증 및 상세 리포트 생성
- **컴포넌트**: 
  - JSON 입력 폼
  - 검증 결과 표시
  - 이슈 목록 표시
  - 마크다운 렌더링된 상세 리포트

#### RuleGenerator 화면 (추정)
- **기능**: 자연어 설명에서 룰 생성
- **컴포넌트**:
  - 자연어 입력 폼
  - 생성된 룰 표시
  - 설명 표시

### 서비스

#### apiService
- **역할**: 백엔드 API와의 통신 처리
- **주요 함수**:
  - `generateRule()`: 룰 생성 API 호출
  - `validateRule()`: 룰 검증 API 호출
  - `generateRuleReport()`: 룰 리포트 API 호출

## 7. 백엔드 서비스

### LLMService
- **역할**: OpenAI API와의 통신 처리
- **주요 함수**:
  - `call_llm()`: LLM 모델 호출
  - `generate_json_response()`: JSON 형식 응답 생성

### RuleAnalyzerService
- **역할**: 룰 검증 및 분석
- **주요 함수**:
  - `validate_rule()`: 룰 검증
  - `_generate_issues_summary()`: 이슈 요약 생성
  - `_generate_rule_summary()`: 룰 요약 생성

### LogicalValidator
- **역할**: 룰의 논리적 일관성 검증
- **주요 함수**:
  - `validate()`: 룰 검증
  - 중복 조건, 모순, 연산자 오류 등 검사

## 8. 설치 및 실행 방법

### 사전 요구사항
- Python 3.9+
- Node.js 16+
- npm 8+

### 백엔드 설치
```bash
# 가상 환경 생성 및 활성화
cd vizierAI/rule-ai-system/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
cp etc/sample.env etc/.env
# .env 파일에 OPENAI_API_KEY 설정

# 서버 실행
python -m uvicorn app.main:app --reload
```

### 프론트엔드 설치
```bash
# 패키지 설치
cd vizierAI/rule-ai-system/frontend
npm install

# 개발 서버 실행
npm run dev
```

## 9. 개발 가이드라인

### 백엔드 개발
- FastAPI 라우터를 사용하여 API 엔드포인트 생성
- Pydantic 모델을 사용하여 데이터 검증
- 비동기 함수 사용으로 성능 최적화
- OpenAI API 호출을 캐싱하거나 모의 응답으로 대체하여 개발 비용 절감

### 프론트엔드 개발
- Vue Composition API 사용
- 타입스크립트 인터페이스로 데이터 모델 정의
- 컴포넌트 재사용성 고려
- API 호출 시 오류 처리 로직 구현

## 10. 최근 업데이트

### 프론트엔드 개선사항 (2023-04-30)
- ValidationReport 컴포넌트의 JSON 중첩 문제 해결
  - 사용자 입력 JSON이 이미 `rule_json` 객체를 포함하는 경우 중첩 제거
  - 파싱된 데이터 구조 분석 후 올바른 형태로 API 요청
- 백엔드 API 응답 필드명 동기화
  - 백엔드 응답의 `is_valid` 필드와 프론트엔드 타입 일치
  - ValidationResult 인터페이스의 `valid` 속성을 `is_valid`로 변경
- 전체 UI 한국어 지원 강화
  - 영문 에러 메시지 및 상태 텍스트 한국어로 번역
  - severity 값(error, warning, info)을 한국어('오류', '경고', '정보')로 변환
  - 'Unnamed Rule'을 '이름 없는 룰'로 표시
  - 검증 결과 메시지 한국어 변환 기능 추가

### 데이터 모델 수정사항
- ValidationResult 모델의 `valid` 필드를 `is_valid`로 변경하여 백엔드와 일관성 유지
- 한국어 인터페이스를 위한 텍스트 처리 로직 추가

## 11. 문제 해결 가이드

### 일반적인 오류
- **API 키 오류**: OpenAI API 키가 올바르게 설정되었는지 확인
- **API 엔드포인트 404**: 서버가 실행 중인지, URL이 올바른지 확인
- **검증 오류 422**: JSON 형식이 API 스펙과 일치하는지 확인
- **마크다운 렌더링 오류**: 프론트엔드 패키지가 올바르게 설치되었는지 확인
- **JSON 중첩 오류**: 요청 구조에 `rule_json` 키가 중복되지 않았는지 확인

### 디버깅 팁
- 백엔드 로그 확인 (`--log-level=debug` 옵션 사용)
- 브라우저 개발자 도구의 네트워크 탭 확인
- Vue Devtools로 컴포넌트 상태 디버깅
- OpenAI API 호출 로그 분석

---

이 문서는 Rule AI System의 기술적 측면을 개략적으로 설명합니다. 보다 자세한 정보는 코드 주석과 각 컴포넌트의 문서를 참조하세요. 