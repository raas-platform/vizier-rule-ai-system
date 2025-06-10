# 🚀 Vizier AI 시스템 배포 가이드

## 📋 배포 시스템 개요

Vizier AI 시스템은 **GitHub Actions**를 활용한 현대적인 CI/CD 파이프라인으로 관리됩니다.

### 🏗️ 아키텍처
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Development   │    │     Staging     │    │   Production    │
│   localhost     │    │ vizierai:8001   │    │ vizierai:8000   │
│     :8888       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ GitHub Actions  │
                    │   CI/CD         │
                    └─────────────────┘
```

## 🔄 배포 플로우

### 1. **자동 배포 트리거**
- `feature/*` 브랜치 푸시 → **개발 환경** 배포
- `develop` 브랜치 푸시 → **스테이징 환경** 배포  
- `v*` 태그 생성 → **프로덕션 환경** 배포

### 2. **수동 배포**
GitHub Actions에서 **workflow_dispatch**로 원하는 환경 선택 배포

## 🐳 Docker 기반 배포

### Container Registry
- **Registry**: `ghcr.io` (GitHub Container Registry)
- **이미지**: `ghcr.io/yeonjae-work/vizier-rule-ai-system`
- **태그 전략**: 브랜치명, 태그명, latest

### 환경별 설정

#### 💻 개발 환경 (Development)
```yaml
포트: 8888
환경: development
디버그: true
로그레벨: debug
자동재시작: false
```

#### 🧪 스테이징 환경 (Staging)  
```yaml
포트: 8001
환경: staging
디버그: true  
로그레벨: debug
자동재시작: true
도메인: vizierai.duckdns.org:8001
```

#### 🏭 프로덕션 환경 (Production)
```yaml
포트: 8000
환경: production
디버그: false
로그레벨: info
자동재시작: true
도메인: vizierai.duckdns.org:8000
```

## 🔐 보안 및 인증

### GitHub Secrets 관리
- 환경별 API 키 분리 (OpenAI, Anthropic, Google)
- SSH 키 기반 서버 접속
- SECRET_KEY 환경별 관리

### 배포 보안
- Blue-Green 배포로 무중단 서비스
- 헬스체크 기반 자동 롤백
- Container Registry 인증

## 📁 파일 구조

```
deployment/
├── README.md                    # 이 파일
├── github-secrets-setup.md      # GitHub Secrets 설정 가이드
├── deploy-multi-env.sh          # 로컬 멀티환경 배포 스크립트 (백업용)
├── .env.development             # 개발 환경 설정
├── .env.staging                 # 스테이징 환경 설정
└── .env.production              # 프로덕션 환경 설정

.github/workflows/
├── ci.yml                       # CI: 코드 품질, 테스트, 보안
└── cd.yml                       # CD: 환경별 자동 배포
```

## 🚀 빠른 시작

### 1. GitHub Secrets 설정
[github-secrets-setup.md](./github-secrets-setup.md) 가이드를 따라 필수 시크릿들을 설정하세요.

### 2. 환경별 배포 테스트

#### 개발 환경
```bash
# feature 브랜치 생성 및 푸시
git checkout -b feature/new-feature
git push origin feature/new-feature
# → 자동으로 개발 환경 배포
```

#### 스테이징 환경  
```bash
# develop 브랜치에 머지 및 푸시
git checkout develop
git merge feature/new-feature
git push origin develop
# → 자동으로 스테이징 환경 배포
```

#### 프로덕션 환경
```bash
# 버전 태그 생성 및 푸시
git tag v1.0.0
git push origin v1.0.0
# → 자동으로 프로덕션 환경 배포
```

## 🏥 헬스체크 및 모니터링

### 엔드포인트
- **헬스체크**: `/health`
- **API 문서**: `/docs`  
- **메트릭**: `/metrics` (향후 추가)

### 배포 확인
```bash
# 스테이징 확인
curl http://vizierai.duckdns.org:8001/health

# 프로덕션 확인  
curl http://vizierai.duckdns.org:8000/health
```

## 🔧 문제 해결

### 일반적인 문제

#### 1. 배포 실패
```bash
# GitHub Actions 로그 확인
# Settings → Actions → 해당 워크플로우 클릭

# 서버에서 직접 확인
ssh ubuntu@vizierai.duckdns.org
sudo docker ps -a
sudo docker logs vizierai-[환경명]
```

#### 2. SSH 연결 실패
```bash
# SSH 키 권한 확인
chmod 600 ~/.ssh/vizierai_*

# 연결 테스트
ssh -i ~/.ssh/vizierai_staging ubuntu@vizierai.duckdns.org
```

#### 3. 컨테이너 문제
```bash
# 컨테이너 재시작
sudo docker restart vizierai-[환경명]

# 로그 확인
sudo docker logs -f vizierai-[환경명]

# 수동 재배포
sudo docker stop vizierai-[환경명]
sudo docker rm vizierai-[환경명]
# GitHub Actions에서 재배포 실행
```

## 📊 배포 전략

### Blue-Green 배포
- 새 컨테이너 실행 → 헬스체크 → 성공시 기존 컨테이너 제거
- 실패시 자동 롤백

### 버전 관리
- **Semantic Versioning**: `v1.0.0`, `v1.1.0`, `v2.0.0`
- **브랜치 전략**: GitFlow (main, develop, feature/*)

### 환경 격리
- 각 환경별 독립된 설정 파일
- 환경별 별도 API 키 및 시크릿

## 🔮 향후 개선 계획

### 모니터링
- [ ] Prometheus + Grafana 대시보드
- [ ] 로그 집계 (ELK Stack)
- [ ] 알림 시스템 (Slack, Discord)

### 보안
- [ ] HTTPS 인증서 자동 갱신
- [ ] 취약점 스캔 자동화
- [ ] 정기적 의존성 업데이트

### 성능
- [ ] 컨테이너 이미지 최적화
- [ ] CDN 적용
- [ ] 로드 밸런싱

## 📞 지원

배포 관련 문제가 있으시면:
1. GitHub Issues에 문제 등록
2. GitHub Actions 로그 첨부
3. 서버 로그 첨부 (민감정보 제외)

---

**✨ 깔끔하고 안전한 배포 시스템으로 더 나은 개발 경험을 제공합니다! ✨** 