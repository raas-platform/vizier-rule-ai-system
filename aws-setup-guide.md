# 🔐 AWS IAM 설정 가이드 (GitHub Actions EC2 스케줄러용)

## 1단계: AWS IAM 사용자 생성

### AWS Console에서:

1. **IAM 콘솔** 접속: https://console.aws.amazon.com/iam/
2. **사용자** → **사용자 추가**
3. **사용자 이름**: `github-ec2-scheduler`
4. **액세스 유형**: ✅ 프로그래밍 방식 액세스
5. **다음: 권한**

## 2단계: IAM 정책 생성

### 사용자 지정 정책 생성:

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

### 정책 이름: `EC2-Scheduler-Policy`

## 3단계: 사용자에 정책 연결

1. 생성한 정책을 사용자에 연결
2. **액세스 키 ID**와 **비밀 액세스 키** 복사 (한 번만 표시됨!)

## 4단계: GitHub Secrets 설정

GitHub 저장소에서:

1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** 클릭

### 추가할 Secrets:

| Secret 이름 | 값 |
|-------------|---|
| `AWS_ACCESS_KEY_ID` | IAM 사용자의 액세스 키 ID |
| `AWS_SECRET_ACCESS_KEY` | IAM 사용자의 비밀 액세스 키 |
| `EC2_INSTANCE_ID` | EC2 인스턴스 ID |

## 5단계: 인스턴스 ID 확인

### EC2 콘솔에서:
1. **EC2 콘솔** → **인스턴스**
2. 해당 인스턴스 선택
3. **인스턴스 ID** 복사 (예: `i-0123456789abcdef0`)

### 또는 EC2에서 직접:
```bash
curl -s http://169.254.169.254/latest/meta-data/instance-id
```

## 6단계: 스케줄 시간 설정

현재 설정된 시간 (한국 시간 기준):
- **중지**: 오후 7시 (UTC 10:00)
- **시작**: 오전 10시 (UTC 1:00)

### 시간 변경을 원할 경우:
```yaml
schedule:
  - cron: '0 10 * * *'  # 오후 7시 중지
  - cron: '0 1 * * *'   # 오전 10시 시작
```

## 7단계: 테스트 실행

1. GitHub Actions 탭에서 **EC2 자동 스케줄러** 워크플로우 찾기
2. **Run workflow** 클릭
3. Action 선택:
   - `start`: 인스턴스 시작
   - `stop`: 인스턴스 중지
   - `status`: 상태 확인

## 🎯 완료 후 기대 효과

- ✅ **자동 중지**: 매일 오후 7시
- ✅ **자동 시작**: 매일 오전 10시  
- ✅ **IP 추적**: 새 IP 자동 확인
- ✅ **앱 재시작**: Docker Compose 자동 실행
- ✅ **비용 절약**: 월 62.5% 절약 (~$18/월)
- ✅ **GitHub Actions**: 실행 로그로 상태 확인 가능

## 🚨 주의사항

1. **인스턴스 ID**: 실제 값으로 워크플로우 수정 필요
2. **시간대**: UTC 기준으로 설정됨 (한국시간 -9시간)
3. **SSH 키**: `STAGING_SSH_KEY` Secret에 올바른 키 설정 필요

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

## 📞 지원

설정 중 문제가 발생하면:
1. GitHub Actions 실행 로그 확인
2. AWS CloudTrail에서 API 호출 기록 확인
3. IAM 정책 권한 재확인 