# EC2 디스크 용량 늘리기 가이드

## 1. AWS 콘솔에서 EBS 볼륨 크기 조정

### Step 1: EC2 대시보드에서 볼륨 찾기
1. **AWS 콘솔 → EC2 → Volumes** 이동
2. 또는 **Instances → 인스턴스 선택 → Storage 탭**에서 볼륨 ID 클릭

### Step 2: 볼륨 크기 수정
1. **볼륨 선택 → Actions → Modify Volume**
2. **Size (GiB)** 값 변경 (예: 8GB → 20GB)
3. **Modify** 버튼 클릭
4. **Yes** 클릭하여 확인

### Step 3: 볼륨 상태 확인
- **State**가 `modifying` → `completed`로 변경될 때까지 대기 (보통 1-2분)

## 2. EC2 인스턴스에서 파일시스템 확장

**볼륨 크기 조정 후 반드시 필요한 작업입니다!**

### EC2 Instance Connect에서 실행:

```bash
# 1. 현재 디스크 상태 확인
lsblk
df -h

# 2. 파티션 정보 확인
sudo fdisk -l

# 3. 파일시스템 확장 (대부분의 경우)
sudo resize2fs /dev/xvda1

# 또는 (파일시스템 타입에 따라)
sudo xfs_growfs /

# 4. 확장 결과 확인
df -h
```

## 3. 추천 설정

### 무료 티어 사용자:
- **8GB → 20GB** (월 20GB까지 무료)

### 일반 사용자:
- **8GB → 30GB** (안정적인 개발 환경)

## 4. 원라이너 스크립트 (인스턴스에서 실행)

```bash
# 파일시스템 자동 확장
sudo resize2fs /dev/xvda1 && df -h
```

## 5. 주의사항

⚠️ **중요:**
- 볼륨 크기는 줄일 수 없습니다 (늘리기만 가능)
- 인스턴스 중지 없이 실시간으로 가능합니다
- 확장 후 반드시 파일시스템 확장 명령을 실행해야 합니다

## 6. 비용
- **gp3 볼륨**: $0.08/GB/월
- **20GB 기준**: 월 약 $1.6 (약 2,000원)

## 트러블슈팅

### 만약 resize2fs가 안 된다면:
```bash
# 파일시스템 타입 확인
df -T

# ext4인 경우
sudo resize2fs /dev/xvda1

# xfs인 경우  
sudo xfs_growfs /
``` 