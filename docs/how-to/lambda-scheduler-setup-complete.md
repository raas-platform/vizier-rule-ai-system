# 🎉 Lambda EC2 스케줄러 설정 완료!

## ✅ 생성된 리소스

### 1. IAM 역할
- **역할명**: `lambda-ec2-scheduler`
- **권한**: EC2 시작/정지, CloudWatch 로그 작성

### 2. Lambda 함수
- **ec2-start**: EC2 인스턴스 시작 (i-02ee2d78b6c2ae934)
- **ec2-stop**: EC2 인스턴스 정지 (i-02ee2d78b6c2ae934)
- **타임아웃**: 30초
- **런타임**: Python 3.9

### 3. EventBridge 스케줄
- **ec2-start-rule**: 평일 오전 10시 (한국시간) - `cron(0 1 ? * MON-FRI *)`
- **ec2-stop-rule**: 평일 오후 7시 (한국시간) - `cron(0 10 ? * MON-FRI *)`

## 📊 비용 절약 효과

### 현재 비용 (24/7 운영)
- t3.small: $0.0208/시간 × 24시간 × 30일 = **$14.98/월**

### 스케줄러 적용 후 (평일 9시간만 운영)
- t3.small: $0.0208/시간 × 9시간 × 22일 = **$4.12/월**
- Lambda 비용: ~$0.20/월 (매일 2회 실행)
- **총 비용: $4.32/월**

### 💰 **월 절약액: $10.66 (71% 절약!)**

## 🔧 관리 명령어

### Lambda 함수 수동 실행
```bash
# EC2 시작
aws lambda invoke --function-name ec2-start response.json

# EC2 정지
aws lambda invoke --function-name ec2-stop response.json
```

### 스케줄 확인
```bash
# EventBridge 규칙 확인
aws events list-rules --name-prefix "ec2-"

# Lambda 함수 목록
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `ec2-`)].FunctionName'
```

### 스케줄 수정
```bash
# 시작 시간 변경 (예: 오전 8시 KST)
aws events put-rule --name "ec2-start-rule" --schedule-expression "cron(0 23 ? * SUN-THU *)"

# 정지 시간 변경 (예: 오후 8시 KST)
aws events put-rule --name "ec2-stop-rule" --schedule-expression "cron(0 11 ? * MON-FRI *)"
```

## 🚨 주의사항

1. **시간대**: 모든 스케줄은 UTC 기준입니다
   - 한국시간 = UTC + 9시간
   - 오전 10시 KST = 오전 1시 UTC
   - 오후 7시 KST = 오전 10시 UTC

2. **인스턴스 상태**: 이미 실행 중인 인스턴스를 시작하려 해도 오류가 발생하지 않습니다

3. **로그 확인**: CloudWatch Logs에서 Lambda 실행 로그를 확인할 수 있습니다

## 🎯 다음 단계

1. **모니터링**: CloudWatch에서 Lambda 실행 상태 확인
2. **알림 설정**: SNS를 통한 실패 알림 설정 (선택사항)
3. **비용 추적**: AWS Cost Explorer에서 실제 절약 효과 확인

---

**🎉 축하합니다! VizierAI EC2 인스턴스가 이제 자동으로 스케줄링됩니다!**

- **평일 오전 10시**: 자동 시작 ✅
- **평일 오후 7시**: 자동 정지 ✅
- **주말**: 완전 정지 상태 💤
- **월 비용**: $14.98 → $4.32 (71% 절약) 💰 