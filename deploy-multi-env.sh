#!/bin/bash

# VizierAI 다중 환경 배포 스크립트
# 사용법: ./deploy-multi-env.sh [development|staging|production]

set -e

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 로깅 함수
log() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
info() { echo -e "${PURPLE}ℹ️ $1${NC}"; }

# 환경 설정
DEPLOY_ENV=${1:-development}

case $DEPLOY_ENV in
    development)
        PORT=8888
        DOMAIN="localhost:8888"
        DOCKER_COMPOSE_PROFILE=""
        WORKERS=1
        ;;
    staging)
        PORT=8001
        DOMAIN="vizierai.duckdns.org:8001"
        DOCKER_COMPOSE_PROFILE="--profile staging"
        WORKERS=2
        ;;
    production)
        PORT=8000
        DOMAIN="vizierai.duckdns.org"
        DOCKER_COMPOSE_PROFILE="--profile production"
        WORKERS=4
        ;;
    *)
        error "지원하지 않는 환경입니다. [development|staging|production] 중 선택하세요."
        ;;
esac

echo "🚀 VizierAI ${DEPLOY_ENV} 환경 배포를 시작합니다..."
info "배포 설정: ${DEPLOY_ENV} 환경, 포트: ${PORT}, 도메인: ${DOMAIN}"

# 환경 변수 파일 설정
ENV_FILE=".env.${DEPLOY_ENV}"
if [ ! -f "$ENV_FILE" ]; then
    error "환경 파일 ${ENV_FILE}을 찾을 수 없습니다."
fi

# 현재 .env 파일 백업
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d-%H%M%S)
    warning "기존 .env 파일을 백업했습니다."
fi

# 환경별 .env 파일 적용
cp "$ENV_FILE" .env
success "환경 설정 파일 적용: $ENV_FILE -> .env"

# Docker 환경 변수 설정
export ENVIRONMENT=$DEPLOY_ENV
export PORT=$PORT
export WORKERS=$WORKERS

log "1. 사전 검사..."

# Docker 확인
if ! command -v docker &> /dev/null; then
    error "Docker가 설치되지 않았습니다."
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    error "Docker Compose가 설치되지 않았습니다."
fi

success "Docker 환경 확인 완료"

log "2. 기존 서비스 정리..."
docker-compose down 2>/dev/null || true
docker system prune -f -a --volumes 2>/dev/null || warning "Docker 정리 중 일부 오류 발생"
success "기존 서비스 정리 완료"

log "3. 이미지 빌드..."
if docker-compose build --no-cache; then
    success "이미지 빌드 완료"
else
    error "이미지 빌드 실패"
fi

log "4. 서비스 시작..."
if docker-compose up -d $DOCKER_COMPOSE_PROFILE; then
    success "서비스 시작 완료"
else
    error "서비스 시작 실패"
fi

log "5. 헬스체크 대기..."
HEALTH_URL="http://localhost:${PORT}/health"
MAX_WAIT=60
WAIT_TIME=0

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if curl -f -s "$HEALTH_URL" > /dev/null 2>&1; then
        success "서비스가 정상적으로 시작되었습니다!"
        break
    fi
    echo -n "."
    sleep 3
    WAIT_TIME=$((WAIT_TIME + 3))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    error "서비스 헬스체크 타임아웃"
fi

log "6. 배포 상태 확인..."
echo
echo "🎉 ${DEPLOY_ENV} 환경 배포가 완료되었습니다!"
echo
echo "📊 컨테이너 상태:"
docker-compose ps

echo
echo "🔗 접속 정보:"
case $DEPLOY_ENV in
    development)
        echo "  - API: http://localhost:${PORT}"
        echo "  - 문서: http://localhost:${PORT}/docs"
        echo "  - 헬스체크: http://localhost:${PORT}/health"
        ;;
    staging|production)
        echo "  - API: http://${DOMAIN}"
        echo "  - 문서: http://${DOMAIN}/docs"
        echo "  - 헬스체크: http://${DOMAIN}/health"
        ;;
esac

echo
echo "📝 유용한 명령어:"
echo "  - 로그 보기: docker-compose logs -f"
echo "  - 서비스 재시작: docker-compose restart"
echo "  - 서비스 중지: docker-compose down"
echo "  - 컨테이너 상태: docker-compose ps"

echo
echo "🔧 다음 단계:"
echo "  1. API 키 설정 확인: vi .env"
echo "  2. 서비스 모니터링: docker-compose logs -f vizierai-api"

if [ "$DEPLOY_ENV" != "development" ]; then
    echo "  3. 도메인 DNS 설정 확인"
    echo "  4. 방화벽 포트 ${PORT} 열기"
fi

echo
success "배포 스크립트 실행 완료!" 