#!/bin/bash

# VizierAI HTTPS 설정 스크립트
echo "🔒 VizierAI HTTPS 설정을 시작합니다..."

# nginx 설치
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx

# nginx 설정 파일 생성
sudo tee /etc/nginx/sites-available/vizierai << 'EOF'
server {
    listen 80;
    server_name vizierai.duckdns.org;
    
    # Let's Encrypt 도전을 위한 설정
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # 모든 HTTP 요청을 HTTPS로 리다이렉트
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name vizierai.duckdns.org;

    # SSL 인증서 (certbot이 자동으로 설정)
    # ssl_certificate /etc/letsencrypt/live/vizierai.duckdns.org/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/vizierai.duckdns.org/privkey.pem;

    # SSL 보안 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # 보안 헤더
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # 프로덕션 API (포트 8000) - HTTPS로 서비스
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 지원 (필요시)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 스테이징 API (포트 8001) - /staging 경로로 접근
    location /staging/ {
        proxy_pass http://localhost:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# nginx 사이트 활성화
sudo ln -sf /etc/nginx/sites-available/vizierai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# nginx 설정 테스트
sudo nginx -t

# nginx 재시작
sudo systemctl reload nginx

echo "🔒 SSL 인증서를 발급받습니다..."

# Let's Encrypt SSL 인증서 발급
sudo certbot --nginx -d vizierai.duckdns.org --non-interactive --agree-tos --email admin@vizierai.duckdns.org

# 자동 갱신 설정
sudo systemctl enable certbot.timer

echo "✅ HTTPS 설정이 완료되었습니다!"
echo "🌐 접속 URL: https://vizierai.duckdns.org"
echo "🧪 스테이징 URL: https://vizierai.duckdns.org/staging" 