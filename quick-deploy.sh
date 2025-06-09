#!/bin/bash

# 🚀 VizierAI 빠른 운영 배포 스크립트
# 서버 접속 후 바로 실행 가능한 원라이너

echo "🚀 VizierAI 빠른 운영 배포를 시작합니다..."

# 색상 코드
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 함수 정의
log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# 1. 디렉토리 이동 및 확인
log "1. 프로젝트 디렉토리 확인..."
if [ ! -d "/opt/vizierai" ]; then
    warn "/opt/vizierai 디렉토리가 없습니다. 생성합니다..."
    sudo mkdir -p /opt/vizierai
    sudo chown $USER:$USER /opt/vizierai
    cd /opt/vizierai
    git clone https://github.com/yeonjae-work/vizier-rule-ai-system.git .
else
    cd /opt/vizierai
fi

# 2. Git 업데이트
log "2. 최신 코드 가져오기..."
git fetch --all
git reset --hard origin/main  # 강제 업데이트
git pull origin main

# 3. 기존 서비스 정리
log "3. 기존 서비스 정리..."
docker-compose down 2>/dev/null || true
docker system prune -f 2>/dev/null || true

# 4. 환경 설정
log "4. 환경 설정..."
cp env.template .env 2>/dev/null || warn "env.template을 찾을 수 없습니다"

# 프로덕션 환경 변수 설정
{
    echo "ENVIRONMENT=production"
    echo "DEBUG=false"
    echo "LOG_LEVEL=info"
    echo "PORT=8000"
    echo "WORKERS=4"
    echo "ALLOWED_ORIGINS=*"
    echo "# API 키는 수동으로 설정하세요"
    echo "OPENAI_API_KEY=your_openai_key_here"
    echo "ANTHROPIC_API_KEY=your_anthropic_key_here"
    echo "GOOGLE_API_KEY=your_google_key_here"
} >> .env

# 5. Docker 서비스 시작
log "5. Docker 서비스 시작..."
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d --build
elif docker compose version >/dev/null 2>&1; then
    docker compose up -d --build
else
    error "Docker Compose를 찾을 수 없습니다"
fi

# 6. 헬스체크 대기
log "6. 서비스 시작 대기..."
sleep 30

for i in {1..12}; do  # 60초 대기
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        log "✅ 서비스가 정상 시작되었습니다!"
        break
    fi
    echo -n "."
    sleep 5
    if [ $i -eq 12 ]; then
        error "서비스 시작 실패"
    fi
done

# 7. 배포 완료 확인
log "7. 배포 상태 확인..."
echo
echo "🎉 배포가 완료되었습니다!"
echo
echo "📊 서비스 상태:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo
echo "🔗 접속 URL:"
echo "  - API: http://$(curl -s ifconfig.me):8000"
echo "  - 문서: http://$(curl -s ifconfig.me):8000/docs"
echo "  - 헬스체크: http://$(curl -s ifconfig.me):8000/health"
echo
echo "📝 다음 단계:"
echo "  1. API 키 설정: vim .env"
echo "  2. 서비스 재시작: docker-compose restart"
echo "  3. 로그 확인: docker-compose logs -f"
echo
echo "🔧 유용한 명령어:"
echo "  - 로그 보기: docker-compose logs -f"
echo "  - 상태 확인: docker ps"
echo "  - 재시작: docker-compose restart"
echo "  - 중지: docker-compose down" 