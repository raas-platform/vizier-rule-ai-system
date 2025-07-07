#!/bin/bash

# DuckDNS 자동 업데이트 스크립트
# EC2 인스턴스의 현재 퍼블릭 IP를 DuckDNS에 자동으로 업데이트

# 설정
DOMAIN="raas-pypi"
TOKEN="8a91f417-4055-4b37-8b20-3aed44ed453b"
LOGFILE="/var/log/duckdns-update.log"

# 현재 퍼블릭 IP 가져오기
CURRENT_IP=$(curl -s http://checkip.amazonaws.com/)
if [ -z "$CURRENT_IP" ]; then
    CURRENT_IP=$(curl -s https://ipv4.icanhazip.com/)
fi

# IP 주소 유효성 검사
if [[ ! $CURRENT_IP =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    echo "$(date): 유효하지 않은 IP 주소: $CURRENT_IP" >> $LOGFILE
    exit 1
fi

# DuckDNS 업데이트 실행
RESPONSE=$(curl -s "https://www.duckdns.org/update?domains=$DOMAIN&token=$TOKEN&ip=$CURRENT_IP")

# 결과 로깅
if [ "$RESPONSE" = "OK" ]; then
    echo "$(date): DuckDNS 업데이트 성공 - IP: $CURRENT_IP" >> $LOGFILE
else
    echo "$(date): DuckDNS 업데이트 실패 - 응답: $RESPONSE" >> $LOGFILE
fi

# 선택사항: PyPI 서버 재시작 (IP 변경 시)
# sudo systemctl restart rass-pypi 