# EC2 Lambda 스케줄러 함수 코드

## 🟢 **1단계: EC2 시작 Lambda 함수**

### 함수 정보
- **Function name**: `ec2-start`
- **Runtime**: Python 3.9
- **Instance ID**: `i-02ee2d78b6c2ae934`

### Python 코드
```python
import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    
    # VizierAI EC2 인스턴스 ID
    instance_id = 'i-02ee2d78b6c2ae934'
    
    try:
        # 인스턴스 시작
        response = ec2.start_instances(InstanceIds=[instance_id])
        
        print(f"Started instance {instance_id}")
        print(f"Response: {response}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully started instance {instance_id}',
                'instance_id': instance_id,
                'state': response['StartingInstances'][0]['CurrentState']['Name']
            })
        }
    except Exception as e:
        print(f"Error starting instance: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to start instance {instance_id}',
                'details': str(e)
            })
        }
```

## 🔴 **2단계: EC2 정지 Lambda 함수**

### 함수 정보
- **Function name**: `ec2-stop`
- **Runtime**: Python 3.9
- **Instance ID**: `i-02ee2d78b6c2ae934`

### Python 코드
```python
import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    
    # VizierAI EC2 인스턴스 ID
    instance_id = 'i-02ee2d78b6c2ae934'
    
    try:
        # 인스턴스 정지
        response = ec2.stop_instances(InstanceIds=[instance_id])
        
        print(f"Stopped instance {instance_id}")
        print(f"Response: {response}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully stopped instance {instance_id}',
                'instance_id': instance_id,
                'state': response['StoppingInstances'][0]['CurrentState']['Name']
            })
        }
    except Exception as e:
        print(f"Error stopping instance: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to stop instance {instance_id}',
                'details': str(e)
            })
        }
```

## 🔐 **3단계: IAM 역할 생성**

### 권한 정책 (JSON)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:DescribeInstances"
            ],
            "Resource": [
                "arn:aws:ec2:ap-northeast-2:*:instance/i-02ee2d78b6c2ae934"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

## ⏰ **4단계: EventBridge 스케줄 설정**

### 평일 오전 9시 시작 (한국시간)
- **Rule name**: `start-vizierai-weekday-morning`
- **Schedule expression**: `cron(0 0 * * MON-FRI ?)`  # UTC 00:00 = 한국시간 09:00
- **Target**: Lambda function `ec2-start`

### 평일 오후 6시 정지 (한국시간)
- **Rule name**: `stop-vizierai-weekday-evening`
- **Schedule expression**: `cron(0 9 * * MON-FRI ?)`  # UTC 09:00 = 한국시간 18:00
- **Target**: Lambda function `ec2-stop`

### 주말 정지 (토요일 아침)
- **Rule name**: `stop-vizierai-weekend`
- **Schedule expression**: `cron(0 21 * * FRI ?)`  # 금요일 UTC 21:00 = 토요일 한국시간 06:00
- **Target**: Lambda function `ec2-stop`

## 🧪 **5단계: 테스트 이벤트**

### 시작 테스트
```json
{
  "action": "start",
  "source": "manual-test"
}
```

### 정지 테스트
```json
{
  "action": "stop",
  "source": "manual-test"
}
```

## 📋 **생성 순서**

1. **IAM 역할** 생성 및 정책 연결
2. **Lambda 함수** 2개 생성 (ec2-start, ec2-stop)
3. **EventBridge 규칙** 3개 생성 (시작, 정지, 주말정지)
4. **테스트** 실행으로 정상 작동 확인

## 💰 **예상 비용**
- **Lambda 실행**: 월 $0.01 미만
- **EventBridge**: 월 $0.01 미만
- **총 비용**: 월 $0.02 미만

이 설정으로 **월 $10+ 절약** 가능! 🎉 