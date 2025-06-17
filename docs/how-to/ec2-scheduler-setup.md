# 💰 EC2 자동 스케줄러 설정 완료 가이드

## ✅ 설정 체크리스트

### 1단계: AWS IAM 설정 (필수)

- [ ] **AWS Console** 접속: https://console.aws.amazon.com/iam/
- [ ] **IAM 사용자 생성**: `github-ec2-scheduler`
- [ ] **프로그래밍 방식 액세스** 선택
- [ ] **사용자 지정 정책 생성**:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:StartInstances", 
                "ec2:StopInstances"
            ],
            "Resource": "*"
        }
    ]
}
```

- [ ] **액세스 키 ID** 및 **비밀 액세스 키** 복사

### 2단계: GitHub Secrets 설정 (필수)

GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**

- [ ] `AWS_ACCESS_KEY_ID`: IAM 사용자 액세스 키
- [ ] `AWS_SECRET_ACCESS_KEY`: IAM 사용자 비밀 키
- [ ] `EC2_INSTANCE_ID`: EC2 인스턴스 ID (아래에서 확인)

### 3단계: 인스턴스 ID 확인

#### 방법 1: GitHub Actions 실행
1. **Actions** 탭에서 **"EC2 인스턴스 ID 확인"** 워크플로우 실행
2. AWS 자격증명 설정 후 인스턴스 ID 확인

#### 방법 2: AWS Console
1. **EC2 Console**: https://console.aws.amazon.com/ec2/
2. **인스턴스** 탭에서 현재 서버 선택
3. **인스턴스 ID** 복사 (예: `i-0123456789abcdef0`)

### 4단계: 테스트 실행

- [ ] **GitHub Actions** → **EC2 자동 스케줄러** → **Run workflow**
- [ ] Action 선택: `status` (상태 확인)
- [ ] 실행 결과 확인

## 📅 스케줄 시간

- **자동 중지**: 매일 오후 7시 (KST)
- **자동 시작**: 매일 오전 10시 (KST)

### 시간 수정을 원할 경우:

`.github/workflows/ec2-scheduler.yml` 파일의 cron 설정 변경:

```yaml
schedule:
  # 오후 7시 중지 (UTC 10:00)
  - cron: '0 10 * * *'
  # 오전 10시 시작 (UTC 1:00)  
  - cron: '0 1 * * *'
```

## 💰 예상 비용 절약

| 항목 | 현재 | 스케줄링 후 | 절약액 |
|------|------|-------------|--------|
| **일일 운영** | 24시간 | 9시간 | 62.5% ↓ |
| **월 비용** | ~$30 | ~$11.25 | **$18.75** |
| **연 비용** | ~$360 | ~$135 | **$225** |

## 🎯 완료 후 기능

### ✅ 자동 기능
- 매일 오후 7시 EC2 자동 중지
- 매일 오전 10시 EC2 자동 시작
- 새로운 IP 주소 자동 확인
- Docker 애플리케이션 자동 재시작

### 🎛️ 수동 제어
- GitHub Actions에서 언제든 수동 시작/중지 가능
- 상태 확인 기능
- 슬랙 알림 (선택사항)

## 🚨 주의사항

1. **IP 주소 변경**: 매일 시작 시 새로운 IP 할당 (자동 추적됨)
2. **데이터 보존**: EBS 볼륨은 유지되므로 데이터 손실 없음
3. **SSH 접속**: 새 IP로 접속 필요 (GitHub Actions 로그에서 확인)

## 🆘 문제 해결

### AWS 자격증명 오류
```bash
# AWS CLI 설치 및 설정 확인
aws configure list
aws sts get-caller-identity
```

### 인스턴스 찾기 실패
1. AWS Console에서 올바른 리전(ap-northeast-2) 확인
2. 인스턴스가 실행 중인지 확인
3. IAM 권한이 올바른지 확인

### GitHub Actions 실행 실패
1. Secrets가 올바르게 설정되었는지 확인
2. 인스턴스 ID가 정확한지 확인
3. AWS 리전이 일치하는지 확인

---

## 🎉 설정 완료!

모든 단계 완료 후, **연간 $225 절약**하는 완전 자동화된 EC2 스케줄러가 작동합니다! 