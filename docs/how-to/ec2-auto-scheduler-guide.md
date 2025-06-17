# EC2 자동 스케줄러 설정 가이드

## 📋 **개요**
- **목적**: 개발 환경 비용 절약 (밤/주말 자동 중지)
- **방법**: AWS Lambda + EventBridge 사용
- **예상 절약**: 월 50-70% 비용 절감

## 🛠️ **방법 1: AWS Lambda + EventBridge (추천)**

### Step 1: IAM 역할 생성
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:DescribeInstances",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
```

### Step 2: Lambda 함수 생성 (Python)
```python
import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    
    # 태그로 대상 인스턴스 필터링
    instances = ec2.describe_instances(
        Filters=[
            {
                'Name': 'tag:AutoScheduler',
                'Values': ['true']
            },
            {
                'Name': 'instance-state-name',
                'Values': ['running', 'stopped']
            }
        ]
    )
    
    instance_ids = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])
    
    if not instance_ids:
        return {
            'statusCode': 200,
            'body': json.dumps('No instances found with AutoScheduler tag')
        }
    
    action = event.get('action', 'stop')
    
    if action == 'start':
        ec2.start_instances(InstanceIds=instance_ids)
        print(f"Started instances: {instance_ids}")
    elif action == 'stop':
        ec2.stop_instances(InstanceIds=instance_ids)
        print(f"Stopped instances: {instance_ids}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'{action.title()}ped instances: {instance_ids}')
    }
```

### Step 3: EventBridge 규칙 생성

**중지 스케줄 (평일 오후 6시)**
```
Name: stop-ec2-instances
Schedule expression: cron(0 9 * * MON-FRI ?)  # UTC 기준 (한국시간 -9시간)
Target: Lambda function
Input: {"action": "stop"}
```

**시작 스케줄 (평일 오전 9시)**
```
Name: start-ec2-instances  
Schedule expression: cron(0 0 * * MON-FRI ?)  # UTC 기준 (한국시간 -9시간)
Target: Lambda function
Input: {"action": "start"}
```

## 🏷️ **방법 2: EC2 인스턴스 태그 설정**

**현재 인스턴스에 태그 추가:**
1. **EC2 콘솔 → Instances → 인스턴스 선택**
2. **Tags 탭 → Manage tags**
3. **Add tag**:
   - **Key**: `AutoScheduler`
   - **Value**: `true`

## ⚡ **방법 3: AWS Instance Scheduler (고급)**

### CloudFormation 템플릿 배포
```bash
# AWS CLI로 Instance Scheduler 배포
aws cloudformation create-stack \
  --stack-name instance-scheduler \
  --template-url https://s3.amazonaws.com/solutions-reference/aws-instance-scheduler/latest/instance-scheduler.template \
  --parameters ParameterKey=TagName,ParameterValue=Schedule \
  --capabilities CAPABILITY_IAM
```

### 스케줄 설정 예시
```json
{
  "type": "schedule",
  "name": "development-hours",
  "periods": [
    {
      "description": "Work hours",
      "begintime": "09:00",
      "endtime": "18:00",
      "weekdays": ["mon-fri"]
    }
  ],
  "timezone": "Asia/Seoul"
}
```

## 🛡️ **방법 4: Auto Scaling Groups (권장 - 운영환경)**

### Launch Template 생성
```yaml
LaunchTemplate:
  ImageId: ami-xxxxxxxxx  # 현재 AMI
  InstanceType: t3.small
  SecurityGroupIds: 
    - sg-xxxxxxxxx
  IamInstanceProfile: 
    Name: EC2-Instance-Profile
  UserData: |
    #!/bin/bash
    # Docker 및 애플리케이션 자동 시작 스크립트
    systemctl start docker
    cd /home/ubuntu/vizier-rule-ai-system
    docker-compose -f docker-compose.prod.yml up -d
```

### Auto Scaling Group 설정
```yaml
AutoScalingGroup:
  MinSize: 0          # 최소 인스턴스 수
  MaxSize: 1          # 최대 인스턴스 수  
  DesiredCapacity: 1  # 원하는 인스턴스 수
  ScheduledActions:
    - ScheduledActionName: "start-weekday-morning"
      Recurrence: "0 0 * * MON-FRI"  # 평일 오전 9시 (UTC)
      DesiredCapacity: 1
    - ScheduledActionName: "stop-weekday-evening"  
      Recurrence: "0 9 * * MON-FRI"  # 평일 오후 6시 (UTC)
      DesiredCapacity: 0
```

## 📱 **방법 5: 간단한 스크립트 (로컬 실행)**

### Bash 스크립트
```bash
#!/bin/bash
# ec2-scheduler.sh

INSTANCE_ID="i-xxxxxxxxx"  # 본인 인스턴스 ID
ACTION=$1  # start 또는 stop

if [ "$ACTION" = "start" ]; then
    aws ec2 start-instances --instance-ids $INSTANCE_ID
    echo "Instance $INSTANCE_ID starting..."
elif [ "$ACTION" = "stop" ]; then
    aws ec2 stop-instances --instance-ids $INSTANCE_ID  
    echo "Instance $INSTANCE_ID stopping..."
else
    echo "Usage: $0 [start|stop]"
fi
```

### Crontab 설정 (로컬 컴퓨터)
```bash
# crontab -e
# 평일 오전 9시 시작
0 9 * * 1-5 /path/to/ec2-scheduler.sh start

# 평일 오후 6시 중지  
0 18 * * 1-5 /path/to/ec2-scheduler.sh stop
```

## 💰 **비용 절약 효과**

### 현재 비용 (24시간 실행)
- **t3.small**: $0.0208/시간 × 24시간 × 30일 = **$14.98/월**

### 스케줄러 적용 후 (9시간만 실행)  
- **t3.small**: $0.0208/시간 × 9시간 × 22일 = **$4.12/월**
- **절약**: $10.86/월 (72% 절감)

## 🎯 **추천 방법**

### 개발 환경
- **Lambda + EventBridge** (간단, 저렴)

### 운영 환경  
- **Auto Scaling Groups** (고가용성, 자동 복구)

### 개인 프로젝트
- **로컬 스크립트 + Crontab** (무료)

## ⚠️ **주의사항**

1. **데이터베이스**: RDS도 별도 스케줄링 필요
2. **Elastic IP**: 인스턴스 중지 시에도 요금 발생
3. **로드 밸런서**: ALB/NLB도 별도 관리 필요
4. **타임존**: UTC 기준으로 설정 (한국시간 -9시간)

어떤 방법을 사용하고 싶으신가요? 