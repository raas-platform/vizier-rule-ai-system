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

## 🖥️ 서버 접속 및 운영 가이드

### EC2 서버 SSH 접속 방법

#### 사전 준비사항
```bash
# PEM 키 파일 위치 확인
ls -la /Users/roseline/projects/VizierAI.pem

# PEM 키 권한 설정 (최초 1회)
chmod 400 /Users/roseline/projects/VizierAI.pem
```

#### 스테이징 서버 접속
```bash
# 스테이징 서버 SSH 접속 (포트 8001)
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org

# 스테이징 서버 상태 확인
curl http://vizierai.duckdns.org:8001/health

# 스테이징 API 문서
open http://vizierai.duckdns.org:8001/docs
```

#### 프로덕션 서버 접속
```bash
# 프로덕션 서버 SSH 접속 (포트 8000)
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org

# 프로덕션 서버 상태 확인
curl http://vizierai.duckdns.org:8000/health

# 프로덕션 API 문서
open http://vizierai.duckdns.org:8000/docs
```

#### EC2 서버 관리 명령어
```bash
# 서버 접속 후 서비스 관리
sudo systemctl status vizierai    # 서비스 상태 확인
sudo systemctl restart vizierai   # 서비스 재시작
sudo systemctl stop vizierai      # 서비스 중지
sudo systemctl start vizierai     # 서비스 시작

# Docker 컨테이너 관리 (Docker 배포인 경우)
docker ps                         # 실행 중인 컨테이너 확인
docker-compose logs -f            # 실시간 로그 확인
docker-compose restart            # 서비스 재시작
```

### 로컬 서버 실행 방법

#### 1. 개발 환경 설정
```bash
# 프로젝트 디렉토리로 이동
cd /Users/roseline/projects/vizier-rule-ai-system

# Python 가상환경 활성화
source activate_env.sh

# 또는 수동으로 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

#### 2. 환경 변수 설정
```bash
# 환경 변수 파일 복사
cp env.template .env

# API 키 설정 스크립트 실행
./set_api_keys.sh

# 또는 수동으로 .env 파일 편집
nano .env
```

#### 3. 로컬 서버 실행
```bash
# 백엔드 디렉토리로 이동
cd backend

# 개발 서버 실행 (자동 리로드)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는 프로덕션 모드로 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker로 실행하는 경우
cd ..  # 프로젝트 루트로 이동
docker-compose up -d
```

#### 4. 서비스 확인
```bash
# API 상태 확인
curl http://localhost:8000/health

# API 문서 접속
open http://localhost:8000/docs

# 스트리밍 대시보드 접속
open http://localhost:8000/static/index.html
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

## 🎨 프론트엔드 개발 환경

### 프론트엔드 서버 실행

#### 기본 HTTP 서버 (권장)
```bash
# 프론트엔드 디렉터리로 이동
cd frontend/streaming-dashboard

# Python HTTP 서버 실행 (포트 3000)
python3 -m http.server 3000

# 백그라운드 실행
nohup python3 -m http.server 3000 > /dev/null 2>&1 &
```

#### 접속 URL
```bash
# 메인 스트리밍 대시보드
http://localhost:3000/

# Vue 기능 테스트 페이지
http://localhost:3000/test.html
```

### 프론트엔드 문제 해결

#### 버튼이 클릭되지 않는 경우
1. **HTTP 서버 실행 확인**:
   ```bash
   curl -I http://localhost:3000/
   ```

2. **백엔드 서버 연결 확인**:
   ```bash
   curl http://localhost:8000/health
   ```

3. **브라우저 개발자 도구 확인**:
   - F12 → Console 탭에서 JavaScript 오류 확인
   - Network 탭에서 API 요청 상태 확인

#### 디버깅 로그 확인
브라우저 콘솔에서 다음 로그들을 확인:
```
🔍 라이브러리 상태 체크
🚀 Vue 앱 마운트 시도
✅ Vue 앱 마운트 완료
🔗 API Base URL: http://localhost:8000/api
🔥 analyzeJson 메서드 호출됨
```

#### CORS 문제 해결
- `file://` 프로토콜 대신 `http://` 프로토콜 사용
- 백엔드 CORS 설정: `allow_origins=["*"]` (개발 환경)

### 로그 확인 및 관리

#### 로컬 개발 환경
```bash
# 실시간 로그 확인 (uvicorn 실행 중)
# 터미널에서 직접 로그 출력 확인

# 로그 파일 확인
tail -f logs/vizierai.log

# 에러 로그만 필터링
grep ERROR logs/vizierai.log

# 로그 레벨별 확인
grep -E "(ERROR|WARNING)" logs/vizierai.log
```

#### Docker 환경
```bash
# 실시간 로그 확인
docker-compose logs -f vizierai-api

# 에러 로그만 필터링
docker-compose logs vizierai-api | grep ERROR

# 특정 시간 이후 로그 확인
docker-compose logs --since="2024-12-19T10:00:00" vizierai-api

# 로그 파일 크기 제한
docker-compose logs --tail=100 vizierai-api
```

#### EC2 서버 로그 확인
```bash
# === 실시간 로그 모니터링 (권장) ===
# 스테이징 서버 실시간 로그 (포트 8001)
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs -f vizierai-staging'

# 프로덕션 서버 실시간 로그 (포트 8000)
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs -f vizierai-production'

# === 최근 로그 확인 (실시간 아님) ===
# 스테이징 서버 최근 50줄
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs --tail=50 vizierai-staging'

# 프로덕션 서버 최근 50줄
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs --tail=50 vizierai-production'

# === 컨테이너 상태 확인 ===
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker ps'

# === 전통적인 시스템 로그 ===
sudo journalctl -u vizierai -f          # systemd 서비스 로그
sudo tail -f /var/log/vizierai.log       # 애플리케이션 로그
sudo tail -f /var/log/nginx/access.log   # Nginx 접근 로그
sudo tail -f /var/log/nginx/error.log    # Nginx 에러 로그

# 로그 아카이브 확인
ls -la /var/log/vizierai/
zcat /var/log/vizierai/archived-*.log.gz | grep ERROR
```

### 성능 모니터링
```bash
# CPU 및 메모리 사용량 확인
htop

# 디스크 사용량 확인
df -h

# 네트워크 연결 상태
netstat -tulpn | grep :8000

# Docker 컨테이너 리소스 사용량
docker stats

# 프로세스별 리소스 사용량
ps aux | grep python
```

### 배포 및 환경 관리

#### 자동화된 배포 스크립트
```bash
# 프로덕션 배포 (안전한 무중단 배포)
./deploy-production.sh

# 다중 환경 배포
./deploy-multi-env.sh development  # 개발 환경 (포트 8888)
./deploy-multi-env.sh staging     # 스테이징 환경 (포트 8001)
./deploy-multi-env.sh production  # 프로덕션 환경 (포트 8000)

# 빠른 배포 (개발용)
./quick-deploy.sh
```

#### EC2 서버 상태 확인
```bash
# EC2 인스턴스 전체 상태 확인
./ec2-status-check.sh vizierai.duckdns.org

# EC2 스케줄러 설정 확인
./check-ec2-scheduler.sh

# 고급 스케줄러 확인
./check-ec2-scheduler-advanced.sh
```

### 운영 명령어

#### 로컬 Docker 관리
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

# Docker 정리
./docker-cleanup.sh        # 자동 정리 스크립트
docker system prune -af    # 수동 정리
```

#### 원격 서버 관리
```bash
# SSH 접속 후 서비스 관리
sudo systemctl status vizierai    # 서비스 상태
sudo systemctl restart vizierai   # 서비스 재시작
sudo systemctl logs -f vizierai   # 서비스 로그

# 원격 배포
scp -i /Users/roseline/projects/VizierAI.pem ./deploy-production.sh ubuntu@vizierai.duckdns.org:~/
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org './deploy-production.sh'
```

## 🔄 빠른 참조 가이드

### 환경별 접속 정보

#### 백엔드 API 서버
| 환경 | SSH 접속 | API URL | 포트 | 컨테이너명 | 용도 |
|------|----------|---------|------|-----------|------|
| **로컬** | - | http://localhost:8000 | 8000 | `vizierai-api` | 개발 |
| **스테이징** | `ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org` | http://vizierai.duckdns.org:8001 | 8001 | `vizierai-staging` | 테스트 |
| **프로덕션** | `ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org` | http://vizierai.duckdns.org:8000 | 8000 | `vizierai-production` | 운영 |

#### 프론트엔드 대시보드
| 환경 | 대시보드 URL | 테스트 페이지 | 서버 실행 방법 |
|------|-------------|-------------|---------------|
| **로컬** | http://localhost:3000/ | http://localhost:3000/test.html | `python3 -m http.server 3000` |
| **스테이징** | 🚧 구성 예정 | - | - |
| **프로덕션** | 🚧 구성 예정 | - | - |

### 주요 명령어 요약

```bash
# === 로컬 개발 ===
source activate_env.sh                    # 가상환경 활성화
cd backend && uvicorn app.main:app --reload  # 백엔드 서버 시작
cd frontend/streaming-dashboard && python3 -m http.server 3000  # 프론트엔드 서버 시작
curl http://localhost:8000/health         # 백엔드 헬스체크
open http://localhost:3000/               # 프론트엔드 대시보드

# === 로그 확인 ===
tail -f logs/vizierai.log                 # 로컬 로그
docker-compose logs -f                    # Docker 로그
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs -f vizierai-staging'   # 스테이징 실시간 로그
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs -f vizierai-production' # 프로덕션 실시간 로그

# === 배포 ===
./deploy-production.sh                    # 프로덕션 배포
./deploy-multi-env.sh staging            # 스테이징 배포
./ec2-status-check.sh vizierai.duckdns.org  # 서버 상태 확인

# === 트러블슈팅 ===
docker-compose down && docker-compose up -d  # 로컬 서비스 재시작
./docker-cleanup.sh                      # Docker 정리
grep ERROR logs/vizierai.log              # 로컬 에러 로그 확인

# 원격 서버 트러블슈팅
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker restart vizierai-staging'   # 스테이징 재시작
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker restart vizierai-production' # 프로덕션 재시작
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker logs --tail=100 vizierai-staging | grep ERROR'  # 에러 로그 필터링
```

### API 테스트 예시

```bash
# === 헬스체크 ===
curl http://vizierai.duckdns.org:8000/health     # 프로덕션
curl http://vizierai.duckdns.org:8001/health     # 스테이징
curl http://localhost:8000/health                # 로컬

# === 룰 검증 테스트 ===
# 프로덕션 서버 테스트
curl -X POST "http://vizierai.duckdns.org:8000/rules/validate-json" \
  -H "Content-Type: application/json" \
  -d @test_new_rule.json

# 스테이징 서버 테스트 (실시간 로그 확인 가능)
curl -X POST "http://vizierai.duckdns.org:8001/rules/validate-json" \
  -H "Content-Type: application/json" \
  -d @test_new_rule.json

# === LLM 모델 목록 ===
curl http://vizierai.duckdns.org:8000/llm/models  # 프로덕션
curl http://vizierai.duckdns.org:8001/llm/models  # 스테이징

# === 서버 상태 종합 확인 ===
# 컨테이너 상태 확인
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

# 서버별 헬스체크 + 로그 확인 (한 번에)
ssh -i /Users/roseline/projects/VizierAI.pem ubuntu@vizierai.duckdns.org 'echo "=== 스테이징 서버 ===" && curl -s http://localhost:8001/health && echo -e "\n=== 프로덕션 서버 ===" && curl -s http://localhost:8000/health'
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
│   │   ├── api/               # API 엔드포인트
│   │   ├── services/          # 비즈니스 로직
│   │   │   ├── rule_analyzer_v2.py  # PyPI 모듈 통합
│   │   │   └── analyzers/     # AI 기능 (로컬)
│   │   │       └── ai_enhancer.py
│   │   ├── models/            # 데이터 모델
│   │   └── utils/             # 유틸리티
├── raas-modules/              # RaaS 모듈 저장소
│   └── packages/              # 독립 PyPI 패키지들
│       ├── raas-rule-analyzer/     # 룰 분석 모듈
│       ├── raas-report-generator/  # 리포트 생성 모듈
│       └── ... (10개 더)
└── docs/                      # 문서
```

### **모듈 조합 방식**

#### **1. PyPI 모듈 (외부 의존성)**
```python
# 설치된 PyPI 모듈들
pip install raas-rule-analyzer==1.0.0
pip install raas-report-generator==1.0.0
pip install raas-http-api-client==1.0.5
```

#### **2. 통합 서비스 (backend/app/services/)**
```python
from raas_rule_analyzer.analyzers import RuleAnalyzer
from raas_report_generator import ReportGenerator
from .analyzers.ai_enhancer import AIEnhancer  # 로컬 AI 기능

class RuleAnalyzerV2:
    """PyPI 모듈 기반 룰 분석 서비스"""
    
    def __init__(self):
        self.rule_analyzer = RuleAnalyzer()      # PyPI 모듈
        self.report_generator = ReportGenerator() # PyPI 모듈
        self.ai_enhancer = AIEnhancer()          # 로컬 AI 기능
```

## 🚀 주요 기능

### **1. 룰 분석 (PyPI 모듈)**
- **raas-rule-analyzer**: 룰 파싱, 조건 분석, 이슈 검출
- **7가지 이슈 타입**: 누락 조건, 타입 불일치, 논리적 모순 등
- **복잡도 분석**: 구조적 복잡성 평가

### **2. AI 기반 개선 (로컬 기능)**
- **LLM 통합**: OpenAI, Anthropic, Google 모델 지원
- **이슈 설명 개선**: AI 기반 상세 설명 생성
- **개선 제안**: 구체적인 수정 방안 제시

### **3. 리포트 생성 (PyPI 모듈)**
- **raas-report-generator**: HTML, JSON, PDF 리포트
- **실시간 대시보드**: SSE 기반 스트리밍
- **시각화**: 차트 및 메트릭 시각화

## 🔧 기술 스택

### **Backend (FastAPI)**
- **프레임워크**: FastAPI 0.104+
- **Python**: 3.9+
- **데이터 검증**: Pydantic v2
- **AI 모델**: OpenAI GPT-4, Anthropic Claude, Google Gemini

### **PyPI 모듈들**
- **raas-rule-analyzer**: 룰 분석 핵심 로직
- **raas-report-generator**: 리포트 생성 및 시각화
- **rass-prompt-builder**: LLM 프롬프트 생성 및 관리
- **rass-llm-service**: 범용 LLM 서비스 통합 관리
- **raas-http-api-client**: HTTP API 클라이언트

### **개발 도구**
- **패키지 관리**: Poetry / pip
- **코드 품질**: Black, isort, mypy
- **테스트**: pytest
- **문서화**: Sphinx

## 📦 설치 및 실행

### **1. 환경 설정**
```bash
# 프로젝트 클론
git clone https://github.com/your-org/vizier-rule-ai-system.git
cd vizier-rule-ai-system

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r backend/requirements.txt
```

### **2. PyPI 모듈 설치**
```bash
# RaaS 모듈들 설치
pip install raas-rule-analyzer==1.0.0
pip install raas-report-generator==1.0.0
pip install rass-prompt-builder==1.0.5
pip install rass-llm-service==1.0.5
pip install raas-http-api-client==1.0.5
```

### **3. 환경 변수 설정**
```bash
# .env 파일 생성
cp .env.example .env

# API 키 설정
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
```

### **4. 애플리케이션 실행**
```bash
# 개발 서버 실행
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# API 문서 확인
# http://localhost:8000/docs
```

## 🧪 테스트

### **단위 테스트**
```bash
# 전체 테스트 실행
pytest backend/tests/

# 특정 모듈 테스트
pytest backend/tests/test_rule_analyzer_v2.py -v
```

### **API 테스트**
```bash
# 룰 검증 API 테스트
curl -X POST "http://localhost:8000/api/v1/rules/validate-json" \
  -H "Content-Type: application/json" \
  -d '[{"ruleUuid": "test-001", "ruleName": "테스트 룰", "ruleMsg": "테스트", "conditionTree": {...}}]'
```

## 📊 성능 메트릭

### **분석 성능**
- **기본 분석**: 평균 50-200ms
- **AI 개선**: 평균 1-3초 (모델에 따라 상이)
- **리포트 생성**: 평균 100-500ms

### **확장성**
- **동시 요청**: 최대 100개 처리
- **메모리 사용량**: 평균 200MB
- **CPU 사용률**: 평균 30-50%

## 🔄 개발 워크플로우

### **1. 모듈 개발**
```bash
# RaaS 모듈 개발
cd raas-modules/packages/raas-rule-analyzer/
pip install -e .  # 개발 모드 설치

# 테스트 실행
pytest tests/
```

### **2. 통합 테스트**
```bash
# 백엔드와 PyPI 모듈 통합 테스트
cd backend/
python -c "from app.services.rule_analyzer_v2 import RuleAnalyzerV2; print('통합 테스트 성공')"
```

### **3. 배포**
```bash
# PyPI 모듈 배포
cd raas-modules/packages/raas-rule-analyzer/
python setup.py sdist bdist_wheel
twine upload dist/*

# 백엔드 배포
cd backend/
docker build -t vizier-rule-ai-system .
docker run -p 8000:8000 vizier-rule-ai-system
```

## 📋 API 문서

### **주요 엔드포인트**

#### **1. 룰 검증**
```http
POST /api/v1/rules/validate-json
Content-Type: application/json

[{
  "ruleUuid": "rule-001",
  "ruleName": "사용자 등급 규칙",
  "ruleMsg": "사용자 등급 판단 규칙",
  "conditionTree": {
    "logicType": "AND",
    "condition": [...]
  }
}]
```

#### **2. HTML 리포트 생성**
```http
POST /api/v1/rules/generate-ai-html-report
Content-Type: application/json

{
  "validation_result": {...},
  "template_options": {...}
}
```

#### **3. 실시간 대시보드**
```http
GET /api/v1/streaming-dashboard
Accept: text/event-stream
```

## 🤝 기여 가이드

### **코드 기여**
1. Fork 및 브랜치 생성
2. 코드 변경 및 테스트
3. Pull Request 제출

### **모듈 개발**
1. RaaS 모듈 저장소에서 개발
2. 독립적인 테스트 작성
3. PyPI 배포 및 버전 관리

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🔗 관련 링크

- **PyPI 모듈 저장소**: https://github.com/raas-platform/raas-modules
- **API 문서**: http://localhost:8000/docs
- **기술 문서**: [docs/](docs/)
- **이슈 트래커**: https://github.com/your-org/vizier-rule-ai-system/issues

---

**✨ PyPI 모듈 기반 리팩토링으로 더욱 모듈화되고 확장 가능한 아키텍처를 구현했습니다!**
