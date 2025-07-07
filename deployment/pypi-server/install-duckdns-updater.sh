#!/bin/bash

# DuckDNS 자동 업데이트 설치 스크립트
# EC2 인스턴스에서 실행하세요

set -e

echo "🔧 DuckDNS 자동 업데이트 설치 중..."

# 1. 스크립트 복사 및 실행 권한 설정
sudo cp update-duckdns.sh /home/ubuntu/rass-pypi-server/
sudo chmod +x /home/ubuntu/rass-pypi-server/update-duckdns.sh
sudo chown ubuntu:ubuntu /home/ubuntu/rass-pypi-server/update-duckdns.sh

# 2. systemd 서비스 파일 설치
sudo cp duckdns-updater.service /etc/systemd/system/
sudo cp duckdns-updater.timer /etc/systemd/system/

# 3. 로그 파일 생성
sudo touch /var/log/duckdns-update.log
sudo chown ubuntu:ubuntu /var/log/duckdns-update.log

# 4. systemd 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable duckdns-updater.service
sudo systemctl enable duckdns-updater.timer

# 5. 타이머 시작
sudo systemctl start duckdns-updater.timer

# 6. 즉시 한 번 실행
sudo systemctl start duckdns-updater.service

echo "✅ DuckDNS 자동 업데이트 설치 완료!"
echo ""
echo "📋 상태 확인 명령어:"
echo "   sudo systemctl status duckdns-updater.timer"
echo "   sudo systemctl status duckdns-updater.service"
echo "   tail -f /var/log/duckdns-update.log"
echo ""
echo "⚠️  중요: update-duckdns.sh 파일에서 YOUR_DUCKDNS_TOKEN을 실제 토큰으로 교체하세요!"
echo "   sudo nano /home/ubuntu/rass-pypi-server/update-duckdns.sh" 