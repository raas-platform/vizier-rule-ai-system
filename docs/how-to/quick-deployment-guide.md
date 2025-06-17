# 🚀 빠른 배포 트러블슈팅 가이드

## 📋 현재 상황
- **문제**: GitHub Actions 배포 실패
- **원인**: 환경 파일 누락 및 GitHub Secrets 미설정
- **해결책**: 워크플로우 수정 완료, Secrets 설정 필요

## ✅ 해결 완료된 사항
1. **환경 파일 문제**: `env.template` 기반 동적 생성으로 수정
2. **CSP 문제**: Swagger UI CDN 허용으로 수정  
3. **워크플로우 조건**: 브랜치 참조 수정

## 🔧 필요한 조치사항

### 1. GitHub Secrets 설정 (필수)
Repository → Settings → Secrets and variables → Actions

```bash
# 최소 필수 Secrets
STAGING_SSH_KEY=your-ssh-private-key
PRODUCTION_SSH_KEY=your-ssh-private-key

# API 키들 (선택사항, fallback 있음)
OPENAI_API_KEY_STAGING=sk-...
OPENAI_API_KEY_PROD=sk-...
ANTHROPIC_API_KEY_STAGING=sk-ant-...
ANTHROPIC_API_KEY_PROD=sk-ant-...
```

### 2. 수동 배포 방법 (임시)

#### 🔑 SSH 키 생성 및 설정
```bash
# 1. SSH 키 생성
ssh-keygen -t ed25519 -f ~/.ssh/vizierai_production -C "github-actions"

# 2. 공개키를 서버에 추가
ssh-copy-id -i ~/.ssh/vizierai_production.pub ubuntu@vizierai.duckdns.org

# 3. 개인키를 GitHub Secrets에 추가
cat ~/.ssh/vizierai_production  # 이 내용을 복사해서 PRODUCTION_SSH_KEY에 추가
```

#### 🚀 즉시 배포 명령
```bash
# 서버 직접 접속
ssh -i ~/.ssh/vizierai_production ubuntu@vizierai.duckdns.org

# 서버에서 실행
cd /opt/vizierai || mkdir -p /opt/vizierai && cd /opt/vizierai
git clone https://github.com/yeonjae-work/vizier-rule-ai-system.git . || git pull
docker build -t vizierai:latest .
docker stop vizierai-production || true
docker rm vizierai-production || true
docker run -d --name vizierai-production \
  -p 8000:8000 \
  --restart unless-stopped \
  -e ENVIRONMENT=production \
  -e DEBUG=false \
  vizierai:latest
```

## 🏥 배포 확인 방법

### 1. 서비스 상태 체크
```bash
curl http://vizierai.duckdns.org:8000/health
```

### 2. Swagger UI 접근 테스트
```bash
curl -I http://vizierai.duckdns.org:8000/docs
```

### 3. 컨테이너 로그 확인
```bash
ssh -i ~/.ssh/vizierai_production ubuntu@vizierai.duckdns.org
docker logs -f vizierai-production
```

## 📊 워크플로우 정리 계획

### 유지할 워크플로우
- ✅ `ci.yml` - 코드 품질 & 테스트
- ✅ `cd.yml` - 자동 배포 (수정 완료)  
- ✅ `ec2-scheduler.yml` - 비용 절약
- ✅ `get-instance-id.yml` - AWS 관리

### 정리할 워크플로우  
- 🔄 `dependency-update.yml` - 필요시 유지

## 🎯 다음 단계

1. **즉시**: SSH 키 설정하여 수동 배포
2. **단기**: GitHub Secrets 설정 완료
3. **장기**: 모니터링 & 알림 시스템 추가

## 🚨 응급 복구 명령

서비스가 완전히 다운된 경우:
```bash
# 기존 방식으로 복구
ssh ubuntu@vizierai.duckdns.org
cd /opt/vizierai
docker-compose down
docker-compose up -d
```

---

**💡 팁**: GitHub Actions 실패 시 로그를 확인하여 정확한 오류 원인을 파악하세요. 