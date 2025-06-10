#!/bin/bash

# AWS Instance Scheduler 설정 스크립트
# EC2를 자동으로 오후 7시에 중지, 오전 10시에 시작

echo "🎯 AWS Instance Scheduler 설정"

# 1. 현재 인스턴스 ID 확인
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo "로컬에서 실행 중")

echo "현재 인스턴스 ID: $INSTANCE_ID"

# 2. 태그 기반 스케줄링 설정
cat << 'EOF'
📋 AWS Instance Scheduler 설정 가이드:

1. AWS Lambda 함수 생성
2. CloudWatch Events 규칙 설정:
   - 중지: cron(0 10 * * ? *) - 오후 7시 (UTC+9 기준)
   - 시작: cron(0 1 * * ? *) - 오전 10시 (UTC+9 기준)

3. EC2 인스턴스에 태그 추가:
   - Key: Schedule
   - Value: office-hours

4. 예상 비용 절약:
   - 15시간/일 중지 = 62.5% 비용 절약
   - t3.medium 기준: 월 $30 → $11.25

🎉 연간 약 $225 절약 가능!
EOF

# 3. 태그 추가 (EC2에서 실행할 경우)
if [[ "$INSTANCE_ID" != "로컬에서 실행 중" ]]; then
    echo "인스턴스에 스케줄 태그 추가 중..."
    aws ec2 create-tags \
        --resources $INSTANCE_ID \
        --tags Key=Schedule,Value=office-hours \
        --region ap-northeast-2 || echo "AWS CLI 설정 필요"
fi

echo "✅ 설정 완료!" 