# EC2 디스크 정리 명령어 가이드

## 1. 현재 디스크 사용량 확인
```bash
df -h
du -sh /home/ubuntu/* 2>/dev/null | sort -h
```

## 2. Docker 관련 정리 (가장 효과적!)
```bash
# 사용하지 않는 Docker 이미지 삭제
sudo docker image prune -a -f

# 중지된 컨테이너 삭제
sudo docker container prune -f

# 사용하지 않는 볼륨 삭제
sudo docker volume prune -f

# 사용하지 않는 네트워크 삭제
sudo docker network prune -f

# 모든 Docker 캐시 삭제 (가장 강력!)
sudo docker system prune -a -f --volumes
```

## 3. 시스템 캐시 및 로그 정리
```bash
# APT 패키지 캐시 정리
sudo apt clean
sudo apt autoclean
sudo apt autoremove -y

# 시스템 로그 정리 (30일 이전 로그 삭제)
sudo journalctl --vacuum-time=30d

# 임시 파일 정리
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*
```

## 4. 애플리케이션 로그 정리
```bash
# 현재 디렉토리의 로그 파일 확인
find /home/ubuntu -name "*.log" -type f -exec ls -lh {} \;

# 큰 로그 파일이 있다면 삭제 또는 압축
# sudo rm /path/to/large.log
# 또는 로그 파일 비우기
# sudo truncate -s 0 /path/to/large.log
```

## 5. 정리 후 확인
```bash
# 디스크 사용량 다시 확인
df -h

# Docker 디스크 사용량 확인
sudo docker system df
```

## 6. 즉시 실행 원라이너
**가장 효과적인 Docker 정리 (한 번에 실행):**
```bash
sudo docker system prune -a -f --volumes && sudo apt clean && sudo apt autoremove -y && df -h
```

## 주의사항
- `docker system prune -a` 명령은 사용 중이지 않은 모든 이미지를 삭제합니다
- 실행 중인 컨테이너는 삭제되지 않으니 안전합니다
- 정리 전에 중요한 데이터가 있는지 확인하세요 