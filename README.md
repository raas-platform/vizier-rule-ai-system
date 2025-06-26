# 🚀 VizierAI Rule Validation System

> **프로덕션 배포 준비 완료!** 
> AI 기반 하이브리드 룰 검증 및 분석 시스템

![Python](https://img.shields.io/badge/Python-3.11%2F3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![AI Models](https://img.shields.io/badge/AI%20Models-7-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 개요

VizierAI는 복잡한 비즈니스 룰을 AI로 분석하고 검증하는 혁신적인 시스템입니다. **GPT-4, Claude-3, Gemini** 등 7개 최신 LLM을 활용하여 룰의 논리적 오류, 성능 문제, 보안 취약점을 자동으로 탐지하고 개선 방안을 제시합니다.

### ✨ 핵심 기능

- 🧠 **AI 기반 룰 분석**: **8가지 오류 유형** 자동 탐지
- 🔄 **멀티 AI 모델**: OpenAI, Anthropic, Google AI **7개 모델** 통합
- 📊 **상세한 분석 리포트**: 심각도별 이슈 분류 및 해결방안 제시
- 🏗️ **모듈화된 아키텍처**: 5개 전문 분석기 컴포넌트
- 🚀 **프로덕션 Ready**: Docker, 헬스체크, 모니터링 지원
- 🔒 **엔터프라이즈 보안**: CORS, 보안 헤더, 환경별 설정

### 🔍 탐지 가능한 8가지 오류 유형

1. **duplicate_condition** - 중복 조건 검출
2. **type_mismatch** - 타입 불일치 검출  
3. **invalid_operator** - 잘못된 연산자 검출
4. **self_contradiction** - 자기모순 검출
5. **missing_condition** - 누락 조건 검출
6. **ambiguous_branch** - 분기 불명확성 검출
7. **complexity_warning** - 복잡성 경고
8. **performance_issue** - 성능 이슈 검출

## 🏗️ 시스템 아키텍처

```
VizierAI System (모듈화된 모놀리스)
├── 📡 FastAPI Gateway
│   ├── CORS & Security Headers
│   ├── Rate Limiting  
│   └── Request Routing
├── 🧠 AI Analysis Engine
│   ├── OpenAI (GPT-4, GPT-4 Turbo, GPT-3.5)
│   ├── Anthropic (Claude-3 Opus/Sonnet/Haiku)
│   └── Google (Gemini Pro)
├── 📊 Modular Analyzers
│   ├── ConditionAnalyzer (조건 분석)
│   ├── IssueDetector (이슈 검출)
│   ├── AIEnhancer (AI 개선)
│   ├── MetricsGenerator (메트릭 생성)
│   └── ReportGenerator (보고서 생성)
└── 📈 Monitoring & Logging
```

### 🛠️ 기술 스택

**백엔드**
- **Framework**: FastAPI 0.104.1
- **Language**: Python 3.11 / 3.12
- **Server**: Uvicorn (개발), Gunicorn (프로덕션)
- **Validation**: Pydantic 2.4.2

**AI/ML** 
- **OpenAI**: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- **Anthropic**: Claude-3 Opus, Sonnet, Haiku  
- **Google**: Gemini Pro
- **Total**: **7개 AI 모델** 지원

**데이터베이스**
- **Main**: SQLite (개발), SQLAlchemy 2.0.23
- **Cache**: Redis (선택사항)

**인프라**
- **Container**: Docker, Docker Compose
- **Proxy**: Nginx (선택사항)
- **Logging**: JSON Logger, Colorama

## 🚀 빠른 시작

### 1. 사전 요구사항

- **Docker** 24.x & **Docker Compose** v2.20+
- **Python** 3.11+ (로컬 개발시) – 3.12 권장
- **AI API 키** (OpenAI, Anthropic, Google 중 하나 이상)

### 2. 환경 설정

```bash
# 프로젝트 클론
git clone https://github.com/your-org/vizierAI.git
cd vizierAI

# 환경 변수 설정
cp env.template .env
# .env 파일을 편집하여 API 키 설정
```

### 3. 원클릭 프로덕션 배포

```bash
# 자동 배포 스크립트 실행
./deploy-production.sh

# 또는 수동 배포
docker-compose up -d
```

### 4. 서비스 확인

```bash
# API 상태 확인
curl http://localhost:8000/health

# API 문서 접속
open http://localhost:8000/docs
```

## 🔧 개발 환경

### 로컬 개발 실행

```bash
# 가상환경 활성화
source activate_env.sh  # 또는 venv 수동 생성

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # `app` alias 경로 지원됨
```

### 테스트 실행

```bash
# 전체 테스트 실행 (5개) – 모든 테스트가 통과해야 합니다.
pytest

# 커버리지 보고서 생성
pytest --cov=backend --cov-report=term-missing
```

## 📊 API 사용법

### 주요 API 엔드포인트

#### 룰 검증 API
- `POST /rules/validate-json` - 룰 검증 및 분석

#### LLM API
- `GET /llm/models` - 사용 가능한 LLM 모델 목록 조회
- `POST /llm/generate` - 텍스트 생성
- `POST /llm/generate/stream` - 스트리밍 텍스트 생성
- `GET /llm/models/{model_id}/status` - 특정 모델 상태 확인

#### 프롬프트 API
- `GET /prompts/` - 프롬프트 목록 조회
- `POST /prompts/` - 프롬프트 생성
- `GET /prompts/{prompt_id}` - 프롬프트 조회
- `PUT /prompts/{prompt_id}` - 프롬프트 수정
- `DELETE /prompts/{prompt_id}` - 프롬프트 삭제
- `POST /prompts/execute` - 프롬프트 실행

#### 헬스체크
- `GET /health` - 서비스 상태 확인
- `GET /admin/api-keys` - API 키 상태 확인 (관리자용)

### 룰 검증 API 사용 예시

```bash
POST /rules/validate-json
Content-Type: application/json

{
  "rules": [
    {
      "ruleUuid": "RULE_001",
      "ruleName": "신용 한도 체크",
      "ruleMsg": "신용 점수 기반 한도 승인",
      "conditionTree": {
        "logicType": "AND",
        "condition": [
          {
            "keyName": "credit_score",
            "operator": ">=",
            "value": 700,
            "fieldDataType": "Number"
          },
          {
            "keyName": "income",
            "operator": ">=", 
            "value": 50000,
            "fieldDataType": "Number"
          }
        ]
      }
    }
  ]
}
```

### 응답 예시

```json
{
  "status": "success",
  "analysis_summary": {
    "total_rules": 1,
    "errors_found": 0,
    "warnings_found": 1,
    "performance_score": 85
  },
  "detailed_analysis": [
    {
      "rule_id": "RULE_001",
      "rule_name": "신용 한도 체크",
      "is_valid": true,
      "severity": "info",
      "issues": [],
      "structure": {
        "depth": 1,
        "condition_node_count": 2,
        "field_condition_count": 2,
        "unique_fields": ["credit_score", "income"]
      },
      "field_analysis": [
        {
          "field_name": "credit_score",
          "field_type": "Number",
          "condition_count": 1,
          "operators_used": [">="],
          "complexity_score": 5
        }
      ],
      "performance_metrics": {
        "estimated_execution_time": "< 1ms",
        "complexity_rating": "simple",
        "optimization_opportunities": []
      },
      "quality_metrics": {
        "maintainability_score": 90,
        "readability_score": 95,
        "overall_score": 88
      },
      "ai_insights": {
        "strengths": ["명확한 조건 구조", "적절한 필드 선택"],
        "recommendations": ["엣지 케이스 추가 고려"]
      }
    }
  ]
}
```

## 🔒 보안 및 환경 설정

### 필수 환경 변수

```bash
# 기본 설정
ENVIRONMENT=production
DEBUG=false

# AI API 키 (최소 하나 이상 필요)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key  
GOOGLE_API_KEY=your-google-key

# 보안 설정
ALLOWED_ORIGINS=https://yourdomain.com
SECRET_KEY=your-super-secret-key-here

# 성능 설정
WORKERS=4
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=30
```

### 환경별 CORS 설정

```bash
# 프로덕션: 특정 도메인만 허용
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# 스테이징: 스테이징 도메인 허용  
ALLOWED_ORIGINS=https://staging.yourdomain.com

# 개발: 모든 도메인 허용
ALLOWED_ORIGINS=*
```

## 📈 모니터링 및 운영

### 헬스체크

```bash
# 서비스 상태 확인
curl http://localhost:8000/health

# API 키 상태 확인 (관리자용)
curl http://localhost:8000/admin/api-keys

# 응답 예시
{
  "status": "healthy", 
  "timestamp": "2024-12-19T10:00:00Z",
  "environment": "production"
}
```

### 로그 확인

```bash
# 실시간 로그 확인
docker-compose logs -f vizierai-api

# 에러 로그만 필터링
docker-compose logs vizierai-api | grep ERROR

# 로그 파일 직접 확인
tail -f logs/vizierai.log
```

### 운영 명령어

```bash
# 서비스 관리
docker-compose up -d        # 시작
docker-compose down         # 중지  
docker-compose restart      # 재시작
docker-compose pull         # 이미지 업데이트

# 리소스 확인
docker stats                # 리소스 사용량
docker-compose ps          # 서비스 상태

# 데이터베이스 백업
cp backend/test.db backup/db-$(date +%Y%m%d).db
```

## 🧪 테스트 케이스

프로젝트에는 다양한 오류 시나리오를 테스트하는 JSON 파일들이 포함되어 있습니다:

```bash
test_duplicate_condition.json    # 중복 조건 테스트
test_type_mismatch.json         # 타입 불일치 테스트  
test_invalid_operator.json      # 잘못된 연산자 테스트
test_self_contradiction.json    # 자기모순 테스트
test_missing_condition.json     # 누락 조건 테스트
test_ambiguous_branch.json      # 분기 불명확 테스트
test_complexity_warning.json    # 복잡성 경고 테스트
test_all_errors_combined.json   # 통합 오류 테스트
```

### 테스트 실행 예시

```bash
# 특정 오류 유형 테스트
python test_analyzer.py test_duplicate_condition.json

# 전체 테스트 실행
python backend/test_rule_analyzer.py
```

## 🚨 트러블슈팅

### 일반적인 문제

**API 키 오류**
```bash
# API 키 설정 확인
grep -E "(OPENAI|ANTHROPIC|GOOGLE)_API_KEY" .env

# API 키 상태 확인  
curl http://localhost:8000/admin/api-keys
```

**포트 충돌**
```bash
# 포트 사용 확인
lsof -i :8000

# 다른 포트로 실행
PORT=8080 docker-compose up -d
```

**메모리 부족**
```bash
# 컨테이너 리소스 확인
docker stats

# 워커 수 조정
WORKERS=2 docker-compose up -d
```

### 성능 최적화

**느린 AI 응답**
- AI 모델을 더 빠른 모델로 변경 (`gpt-3.5-turbo`, `claude-3-haiku`)
- 타임아웃 값 조정 (`AI_TIMEOUT=60`)
- 프롬프트 최적화

**높은 메모리 사용**
- 워커 수 감소 (`WORKERS=2`)
- 로그 레벨 조정 (`LOG_LEVEL=info`)
- Redis 캐싱 활용

## 🔧 프로젝트 구조

```
vizierAI/
├── backend/                    # 백엔드 애플리케이션
│   ├── app/
### 문제 신고
- 🐛 **버그 리포트**: [GitHub Issues](https://github.com/your-org/vizierAI/issues)
- 💡 **기능 요청**: [Feature Requests](https://github.com/your-org/vizierAI/discussions)

### 기여 방법
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

**🎯 다음 단계**: 
1. `.env` 파일에서 API 키 설정
2. `./deploy-production.sh` 실행
3. `http://localhost:8000/docs`에서 API 테스트
4. 운영 모니터링 설정

**Made with ❤️ by VizierAI Team** # test
# test2
# test3
# test4
# test5
# test6
# test7
# test8
# test9
# test10
# test11
# test12
# test13
# test14
# test15
# test16
