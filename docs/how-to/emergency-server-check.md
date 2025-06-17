# 🚨 긴급 서버 상태 확인 및 복구 가이드

## 현재 상황
- ❌ 54.180.109.51:8000 접속 불가
- ❌ 54.180.109.51:8001 접속 불가  
- ❌ ping 응답 없음
- **결론**: EC2 인스턴스가 중지되었거나 IP가 변경됨

## 🔥 즉시 해야 할 일

### 1. AWS 콘솔 접속
```
1. https://console.aws.amazon.com/ec2/ 접속
2. 로그인 (AWS 계정 필요)
3. 왼쪽 메뉴에서 "Instances" 클릭
```

### 2. 인스턴스 찾기
```
검색 방법:
- IP로 검색: 54.180.109.51
- 이름으로 검색: vizierai, production, staging
- 모든 인스턴스 확인
```

### 3. 인스턴스 상태 확인
```
상태 확인 사항:
✅ Instance state: running/stopped/terminated
✅ Status checks: 2/2 checks passed  
✅ Public IPv4 address: 현재 IP 주소
✅ Security groups: 포트 열림 상태
```

### 4. 인스턴스가 중지된 경우
```
1. 인스턴스 선택
2. "Instance state" → "Start instance" 클릭
3. 2-3분 대기 후 새로운 IP 주소 확인
```

### 5. IP 주소가 변경된 경우
```
새 IP로 접속 시도:
curl -f http://새로운IP:8000/health
```

## 🚀 서버 시작 후 배포 방법

### A. 자동 배포 (GitHub Actions)
```bash
# GitHub Secrets 업데이트 필요 (새 IP인 경우)
# 그 후 다시 배포 트리거
```

### B. 수동 배포 (EC2 Instance Connect)
```bash
# 1. AWS 콘솔에서 인스턴스 Connect
# 2. 아래 명령어 실행:

sudo mkdir -p /opt/vizierai && sudo chown $USER:$USER /opt/vizierai && cd /opt/vizierai && git clone https://github.com/yeonjae-work/vizier-rule-ai-system.git . && docker-compose down 2>/dev/null || true && cp env.template .env && echo -e "ENVIRONMENT=production\nDEBUG=false\nLOG_LEVEL=info\nPORT=8000\nWORKERS=4\nALLOWED_ORIGINS=*" >> .env && docker-compose up -d --build
```

### C. 빠른 배포 스크립트
```bash
curl -fsSL https://raw.githubusercontent.com/yeonjae-work/vizier-rule-ai-system/main/quick-deploy.sh | bash
```

## 🔍 트러블슈팅

### 인스턴스를 찾을 수 없는 경우
- 다른 AWS 리전 확인 (서울, 버지니아 등)
- terminated 상태일 수 있음 → 새 인스턴스 생성 필요

### 보안 그룹 문제
```
Inbound rules 확인:
- SSH (22): 0.0.0.0/0 또는 My IP
- HTTP (8000): 0.0.0.0/0
- HTTP (8001): 0.0.0.0/0
```

### 새 인스턴스 생성이 필요한 경우
```
1. Launch instance
2. Ubuntu 22.04 LTS 선택
3. t3.medium 또는 t3.large
4. 키페어 생성/선택
5. 보안그룹: SSH, HTTP 포트 오픈
6. 인스턴스 시작 후 quick-deploy.sh 실행
```

## ⚡ 긴급 연락처
- AWS 지원팀: https://console.aws.amazon.com/support/
- 인스턴스 상태 API: aws ec2 describe-instances

## 📞 다음 단계
1. 🔴 **즉시**: AWS 콘솔에서 인스턴스 상태 확인
2. 🟡 **서버 시작**: stopped 상태면 start
3. 🟢 **배포 실행**: 서버 정상 후 배포 재실행 