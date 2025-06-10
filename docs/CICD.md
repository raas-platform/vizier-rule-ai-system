# 🚀 VizierAI CI/CD 가이드

## 📋 개요

VizierAI 프로젝트는 **GitHub Actions**를 활용한 완전 자동화된 CI/CD 파이프라인을 구축했습니다.

## 🏗️ CI/CD 아키텍처

```
📂 .github/workflows/
├── 🔍 ci.yml                 # 지속적 통합 (CI)
├── 🚀 cd.yml                 # 지속적 배포 (CD)  
└── 📦 dependency-update.yml  # 의존성 업데이트
```

## 🔍 CI (지속적 통합) 워크플로우

### 트리거 조건
- `main`, `develop` 브랜치에 push
- Pull Request 생성/업데이트

### 실행 단계

#### 1. **코드 품질 검사**
- **Black**: 코드 포맷팅 검사
- **isort**: Import 정렬 검사  
- **Flake8**: 린트 검사
- **MyPy**: 타입 검사

#### 2. **보안 검사**
- **Bandit**: Python 보안 취약점 검사
- **Safety**: 의존성 보안 검사

#### 3. **테스트 실행**
- **단위 테스트**: Python 3.9, 3.10, 3.11에서 병렬 실행
- **통합 테스트**: Redis 서비스와 함께 실행
- **커버리지**: Codecov로 커버리지 리포트 업로드

#### 4. **Docker 빌드 테스트**
- Docker 이미지 빌드 검증
- 컨테이너 실행 및 헬스체크

## 🚀 CD (지속적 배포) 워크플로우

### 트리거 조건
- `main` 브랜치에 push (스테이징 자동 배포)
- 버전 태그 push (프로덕션 배포)
- 수동 트리거 (workflow_dispatch)

### 배포 전략

#### **Blue-Green 배포**
1. 새 컨테이너를 다른 포트에서 시작
2. 헬스체크 완료 후 트래픽 전환
3. 기존 컨테이너 안전 종료

#### **환경별 배포**

##### 🧪 스테이징 환경
- **트리거**: develop 브랜치 push
- **URL**: https://staging.vizierai.com
- **특징**: 디버그 모드, 상세 로깅

##### 🏭 프로덕션 환경  
- **트리거**: 버전 태그 (v1.0.0)
- **URL**: https://api.vizierai.com
- **특징**: 최적화 모드, 에러 로깅만

## 📦 의존성 관리

### Dependabot 설정
- **Python 패키지**: 매주 월요일
- **Docker 이미지**: 매주 화요일  
- **GitHub Actions**: 매월

### 자동 업데이트 워크플로우
- 의존성 업데이트 감지
- 자동 테스트 실행
- PR 자동 생성

## 🔐 보안 설정

### GitHub Secrets 설정 필요

#### CI 관련
```bash
OPENAI_API_KEY_TEST=sk-test-...
ANTHROPIC_API_KEY_TEST=sk-ant-test-...
CODECOV_TOKEN=...
```

#### CD 관련
```bash
# 스테이징 환경
STAGING_HOST=staging.vizierai.com
STAGING_USER=deploy
STAGING_SSH_KEY=-----BEGIN RSA PRIVATE KEY-----

# 프로덕션 환경  
PRODUCTION_HOST=api.vizierai.com
PRODUCTION_USER=deploy
PRODUCTION_SSH_KEY=-----BEGIN RSA PRIVATE KEY-----

# 알림
SLACK_WEBHOOK=https://hooks.slack.com/...
```

#### GitHub Variables 설정
```bash
STAGING_URL=https://staging.vizierai.com
PRODUCTION_URL=https://api.vizierai.com
```

## 🛠️ 로컬 개발 도구

### Makefile 사용법

```bash
# 도움말 확인
make help

# 빠른 시작 (권장)
make quick-start

# 개발 서버 실행
make dev

# 모든 검사 실행 (CI와 동일)
make all-checks

# Docker로 실행
make up
```

### Pre-commit 훅 설정 (선택사항)

```bash
# pre-commit 설치
pip install pre-commit

# 훅 설치
pre-commit install

# 수동 실행
pre-commit run --all-files
```

## 📊 모니터링 및 알림

### 슬랙 알림
- **배포 성공/실패**: #deployments 채널
- **프로덕션 알림**: #production-alerts 채널
- **테스트 실패**: #alerts 채널

### 메트릭 수집
- 배포 성공률
- 테스트 커버리지
- 빌드 시간
- 보안 취약점 수

## 🔄 워크플로우 실행 방법

### 1. 자동 실행
```bash
# CI 트리거
git push origin feature/new-feature

# 스테이징 배포
git push origin develop

# 프로덕션 배포  
git tag v1.2.0
git push origin v1.2.0
```

### 2. 수동 실행
GitHub 웹사이트에서:
1. Actions 탭 이동
2. 원하는 워크플로우 선택
3. "Run workflow" 버튼 클릭
4. 환경 선택 후 실행

## 🐛 트러블슈팅

### 자주 발생하는 문제

#### CI 실패
```bash
# 로컬에서 CI 검사 실행
make all-checks

# 특정 오류 확인
make lint      # 린트 오류
make test      # 테스트 실패
make security  # 보안 취약점
```

#### 배포 실패
```bash
# 로컬에서 배포 스크립트 테스트
./deploy-production.sh staging

# Docker 빌드 테스트
make build
make up
```

#### 환경 변수 누락
1. GitHub Settings → Secrets and variables
2. Actions 탭에서 필요한 시크릿 추가
3. 워크플로우 재실행

## 📈 성능 최적화

### 빌드 시간 단축
- **캐싱**: pip, Docker layer 캐싱 활용
- **병렬 실행**: 매트릭스 전략으로 다중 Python 버전 테스트
- **조건부 실행**: 파일 변경 감지로 불필요한 단계 스킵

### 리소스 최적화
- **타임아웃**: 각 단계별 적절한 시간 제한
- **동시 실행**: 제한된 동시 실행으로 비용 최적화

## 🚀 향후 개선 계획

- [ ] **Kubernetes 배포**: Helm 차트 활용
- [ ] **E2E 테스트**: Playwright 추가
- [ ] **성능 테스트**: 자동화된 부하 테스트
- [ ] **배포 승인**: 프로덕션 배포 승인 프로세스
- [ ] **롤백 자동화**: 실패 시 자동 롤백 