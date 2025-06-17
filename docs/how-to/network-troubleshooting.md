# 🔧 네트워크 접속 문제 해결 가이드

## 현재 상황
- ✅ EC2 인스턴스: 실행 중
- ✅ IP 주소: 54.180.109.51 (변경 없음)
- ❌ ping: 응답 없음
- ❌ HTTP 접속: 불가능

## 🚨 **가장 가능성 높은 원인들**

### 1. 보안 그룹(Security Group) 설정 문제

#### 확인 방법:
```
AWS 콘솔 → EC2 → Instances 
→ 인스턴스 선택 → Security 탭 → Inbound rules 확인
```

#### 필요한 포트:
```
Type        Protocol  Port    Source
SSH         TCP       22      0.0.0.0/0 (또는 My IP)
HTTP        TCP       8000    0.0.0.0/0
HTTP        TCP       8001    0.0.0.0/0
All ICMP    ICMP      All     0.0.0.0/0 (ping용)
```

#### 🔧 수정 방법:
```
1. Security groups 클릭
2. 해당 보안그룹 선택
3. "Edit inbound rules"
4. "Add rule" 클릭하여 누락된 포트 추가
```

### 2. Network ACL 문제

#### 확인 방법:
```
AWS 콘솔 → VPC → Network ACLs
→ 서브넷과 연결된 ACL 확인
```

#### 해결 방법:
```
Inbound Rules에 다음 추가:
- Rule #100: HTTP (80) - Allow
- Rule #200: HTTPS (443) - Allow  
- Rule #300: SSH (22) - Allow
- Rule #400: Custom TCP (8000-8001) - Allow
- Rule #500: All ICMP - Allow

Outbound Rules:
- Rule #100: All Traffic - Allow
```

### 3. 서버 내부 방화벽 문제

#### EC2 Instance Connect로 접속하여 확인:
```bash
# Ubuntu 방화벽 상태 확인
sudo ufw status

# 방화벽이 활성화되어 있다면 포트 열기
sudo ufw allow 22
sudo ufw allow 8000  
sudo ufw allow 8001
sudo ufw reload

# 또는 임시로 방화벽 비활성화
sudo ufw disable
```

### 4. Docker 서비스 상태 확인

```bash
# EC2 Instance Connect로 접속 후:
docker ps -a
docker-compose ps
sudo systemctl status docker

# 서비스가 중지되어 있다면
cd /opt/vizierai
docker-compose up -d
```

### 5. 네트워크 인터페이스 문제

```bash
# EC2 Instance Connect로 접속 후:
ip addr show
netstat -tlnp | grep :8000
ss -tlnp | grep :8000

# Docker 네트워크 확인
docker network ls
docker network inspect bridge
```

## ⚡ **즉시 해결 방법**

### A. 보안 그룹 빠른 수정
```
1. AWS 콘솔 → EC2 → Security Groups
2. 인스턴스의 보안그룹 선택
3. Inbound rules → Edit → Add rules:
   - Type: All Traffic, Source: 0.0.0.0/0 (임시)
4. Save rules
5. 접속 테스트
```

### B. EC2 Instance Connect로 내부 확인
```
1. AWS 콘솔 → EC2 → Instances
2. 인스턴스 선택 → Connect
3. EC2 Instance Connect 탭 → Connect
4. 내부에서 진단:

# 방화벽 임시 비활성화
sudo ufw disable

# Docker 서비스 재시작
sudo systemctl restart docker
cd /opt/vizierai
docker-compose down
docker-compose up -d

# 포트 확인
curl http://localhost:8000/health
```

### C. 긴급 복구 명령어 (EC2 내부에서)
```bash
# 전체 재시작
sudo ufw disable && \
sudo systemctl restart docker && \
cd /opt/vizierai && \
docker-compose down && \
docker system prune -f && \
git pull && \
docker-compose up -d --build
```

## 🔍 **단계별 진단**

### 1단계: 보안그룹 확인 (AWS 콘솔)
- Inbound rules에 포트 8000, 8001, 22 있는지
- Source가 0.0.0.0/0 또는 적절한 IP인지

### 2단계: EC2 내부 접속 (Instance Connect)
- `curl http://localhost:8000/health` 작동하는지
- `docker ps` 컨테이너 실행 중인지

### 3단계: 방화벽 확인
- `sudo ufw status` 방화벽 상태
- 필요시 `sudo ufw disable`

### 4단계: 서비스 재시작
- `docker-compose restart`
- 또는 완전 재배포

## 📞 **가장 빠른 해결책**

**보안그룹에 임시로 "All Traffic" 룰 추가** → **EC2 Instance Connect로 내부 진단** 