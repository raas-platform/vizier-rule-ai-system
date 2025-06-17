# 🔐 GitHub Secrets 설정 가이드

GitHub Actions에서 안전한 배포를 위해 필요한 시크릿들을 설정하는 가이드입니다.

## 📍 Secrets 설정 방법

1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭하여 각 시크릿 추가

## 🔑 필수 Secrets 목록

### 🌐 API 키 (환경별)

#### 개발 환경
```
OPENAI_API_KEY_DEV=sk-dev-***
ANTHROPIC_API_KEY_DEV=sk-ant-dev-***
GOOGLE_API_KEY_DEV=AIza-dev-***
```

#### 스테이징 환경
```
OPENAI_API_KEY_STAGING=sk-staging-***
ANTHROPIC_API_KEY_STAGING=sk-ant-staging-***
GOOGLE_API_KEY_STAGING=AIza-staging-***
SECRET_KEY_STAGING=your-super-secret-staging-key-32-chars-min
```

#### 프로덕션 환경
```
OPENAI_API_KEY_PROD=sk-prod-***
ANTHROPIC_API_KEY_PROD=sk-ant-prod-***
GOOGLE_API_KEY_PROD=AIza-prod-***
SECRET_KEY_PROD=your-super-secret-production-key-32-chars-min
```

### 🔐 SSH 키 (서버 접속용)

#### 스테이징 서버 SSH 키
```
STAGING_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
[전체 SSH 개인키 내용]
-----END OPENSSH PRIVATE KEY-----
```

#### 프로덕션 서버 SSH 키
```
PRODUCTION_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
[전체 SSH 개인키 내용]
-----END OPENSSH PRIVATE KEY-----
```

## 🛠️ SSH 키 생성 및 설정

### 1. SSH 키 생성
```bash
# 스테이징용 SSH 키 생성
ssh-keygen -t ed25519 -f ~/.ssh/vizierai_staging -C "github-actions-staging"

# 프로덕션용 SSH 키 생성  
ssh-keygen -t ed25519 -f ~/.ssh/vizierai_production -C "github-actions-production"
```

### 2. 공개키를 서버에 추가
```bash
# 스테이징 서버에 공개키 추가
ssh-copy-id -i ~/.ssh/vizierai_staging.pub ubuntu@vizierai.duckdns.org

# 프로덕션 서버에 공개키 추가
ssh-copy-id -i ~/.ssh/vizierai_production.pub ubuntu@vizierai.duckdns.org
```

### 3. 개인키를 GitHub Secrets에 추가
```bash
# 개인키 내용 복사 (GitHub Secrets에 붙여넣기)
cat ~/.ssh/vizierai_staging
cat ~/.ssh/vizierai_production
```

## 🔒 보안 모범 사례

### 1. API 키 관리
- 환경별로 다른 API 키 사용
- 개발/테스트용 API 키는 사용량 제한 설정
- 정기적으로 API 키 로테이션

### 2. SSH 키 관리
- 각 환경별로 별도 SSH 키 사용
- SSH 키에 passphrase 설정 (선택사항)
- 주기적으로 SSH 키 교체

### 3. Secret 키 생성
```bash
# 안전한 SECRET_KEY 생성
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 📋 환경별 배포 트리거

### 자동 배포
- **개발**: `feature/*` 브랜치 푸시 → `development` 환경 배포
- **스테이징**: `develop` 브랜치 푸시 → `staging` 환경 배포
- **프로덕션**: `v*` 태그 생성 → `production` 환경 배포

### 수동 배포
1. GitHub Actions → **CD - 자동 배포** → **Run workflow**
2. 배포할 환경 선택 (`development`, `staging`, `production`)

## 🔍 배포 확인

### 배포 후 확인사항
- 🏥 헬스체크: `/health` 엔드포인트 응답
- 📚 API 문서: `/docs` 페이지 접근
- 🔗 실제 API 호출 테스트

### 환경별 URL
- **개발**: `http://localhost:8888`
- **스테이징**: `http://vizierai.duckdns.org:8001`  
- **프로덕션**: `http://vizierai.duckdns.org:8000`

## 🚨 문제 해결

### 배포 실패 시
1. GitHub Actions 로그 확인
2. 서버 Docker 컨테이너 상태 확인: `sudo docker ps -a`
3. 컨테이너 로그 확인: `sudo docker logs vizierai-[환경명]`

### SSH 연결 실패 시
```bash
# SSH 키 권한 확인
chmod 600 ~/.ssh/vizierai_*

# 연결 테스트
ssh -i ~/.ssh/vizierai_staging ubuntu@vizierai.duckdns.org
```

### Docker 이미지 풀 실패 시
```bash
# Container Registry 로그인 확인
echo "$GITHUB_TOKEN" | sudo docker login ghcr.io -u [username] --password-stdin
```

## 📱 알림 설정 (선택사항)

추가 시크릿으로 배포 결과 알림을 설정할 수 있습니다:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/***
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/***
```

## ✅ 설정 완료 체크리스트

- [ ] 모든 API 키 Secrets 추가
- [ ] SSH 키 생성 및 서버 등록
- [ ] SSH 개인키 Secrets 추가
- [ ] SECRET_KEY 생성 및 추가
- [ ] 환경별 배포 테스트
- [ ] 헬스체크 및 API 문서 접근 확인 