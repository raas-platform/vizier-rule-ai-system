# 🔍 AWS 서버 상태 확인 및 운영 배포 가이드

## 1. AWS 콘솔에서 EC2 인스턴스 확인

### A. 인스턴스 상태 확인
1. **AWS 콘솔 로그인** → EC2 → Instances
2. 인스턴스 검색 (IP: 54.180.109.51)
3. 상태 확인:
   - **Instance State**: running/stopped/terminated
   - **Status Checks**: 2/2 checks passed
   - **Public IPv4**: 현재 IP 주소 확인

### B. 보안 그룹 확인
1. 인스턴스 선택 → Security 탭
2. **Inbound rules** 확인:
   - SSH (22): Your IP 또는 0.0.0.0/0
   - HTTP (8000): 0.0.0.0/0 
   - HTTP (8001): 0.0.0.0/0

## 2. 서버 접속 방법

### A. EC2 Instance Connect 사용
```bash
# AWS 콘솔에서
1. 인스턴스 선택 → Connect 
2. "EC2 Instance Connect" 탭
3. Username: ubuntu (또는 ec2-user)
4. Connect 클릭
```

### B. SSH 직접 접속 (키 있는 경우)
```bash
ssh -i "your-key.pem" ubuntu@54.180.109.51
```

## 3. 서버에서 배포 실행

### A. 현재 상태 확인
```bash
# 서버 접속 후
cd /opt/vizierai
pwd
ls -la
git status
docker ps -a
```

### B. 수동 배포 실행
```bash
# 1. 최신 코드 업데이트
git pull origin main  # 또는 develop

# 2. 환경 설정
cp env.template .env
# API 키 설정 (vim .env)

# 3. 프로덕션 배포
chmod +x deploy-production.sh
./deploy-production.sh production

# 4. 서비스 확인
docker ps
curl http://localhost:8000/health
```

## 4. 대안 배포 방법

### A. Docker Compose 직접 실행
```bash
# 기존 컨테이너 정리
docker-compose down

# 환경 설정
echo "ENVIRONMENT=production" >> .env
echo "DEBUG=false" >> .env
echo "LOG_LEVEL=info" >> .env
echo "PORT=8000" >> .env

# 서비스 시작
docker-compose up -d --build

# 확인
docker-compose logs -f
```

### B. 수동 Docker 실행
```bash
# 이미지 빌드
cd backend
docker build -t vizierai-api .

# 컨테이너 실행
docker run -d \
  --name vizierai-api \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DEBUG=false \
  -e LOG_LEVEL=info \
  vizierai-api

# 확인
docker logs vizierai-api
curl http://localhost:8000/health
```

## 5. 트러블슈팅

### A. 서버 중지된 경우
```bash
# AWS 콘솔에서 인스턴스 시작
Instance 선택 → Instance state → Start instance
```

### B. IP 주소 변경된 경우
```bash
# 1. AWS 콘솔에서 새 IP 확인
# 2. GitHub Secrets 업데이트 필요:
#    - PRODUCTION_HOST
#    - STAGING_HOST
# 3. DNS/도메인 설정 업데이트
```

### C. 보안 그룹 문제
```bash
# AWS 콘솔에서 Security Groups
# 필요한 포트 추가:
# - SSH (22): My IP
# - HTTP (8000): 0.0.0.0/0
# - HTTP (8001): 0.0.0.0/0
```

## 6. 배포 확인 체크리스트

### ✅ 사전 확인
- [ ] EC2 인스턴스 실행 중
- [ ] 보안 그룹 포트 열림
- [ ] SSH 접속 가능
- [ ] Git 리포지토리 접근 가능

### ✅ 배포 후 확인
- [ ] 컨테이너 실행 중: `docker ps`
- [ ] 헬스체크 성공: `curl http://localhost:8000/health`
- [ ] API 문서 접근: `curl http://localhost:8000/docs`
- [ ] 로그 정상: `docker-compose logs`

## 7. 긴급 복구 명령어

```bash
# 전체 서비스 재시작
cd /opt/vizierai
docker-compose down
docker system prune -f
git pull
docker-compose up -d --build

# 방화벽 임시 해제 (Ubuntu)
sudo ufw disable

# Docker 서비스 재시작
sudo systemctl restart docker

# 디스크 공간 확인
df -h
docker system df
```

## 8. 모니터링 명령어

```bash
# 실시간 로그
docker-compose logs -f

# 리소스 사용량
docker stats

# 시스템 상태
htop
free -h
df -h

# 네트워크 연결
ss -tlnp | grep :8000
``` 