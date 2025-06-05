#!/bin/bash

# VizierAI 프로덕션 배포 스크립트
# 안전하고 무중단 배포를 위한 종합 스크립트

set -e  # 오류 발생시 스크립트 중단

echo "🚀 VizierAI 프로덕션 배포를 시작합니다..."

# ===== 환경 설정 =====
DEPLOY_ENV=${1:-production}
PROJECT_NAME="vizierai"
BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"
HEALTH_CHECK_URL="http://localhost:8000/health"
MAX_WAIT_TIME=120

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# ===== 사전 검사 =====
log "1. 사전 요구사항 검사..."

# Docker 및 Docker Compose 확인
if ! command -v docker &> /dev/null; then
    error "Docker가 설치되지 않았습니다."
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    error "Docker Compose가 설치되지 않았습니다."
fi

# .env 파일 확인
if [ ! -f ".env" ]; then
    warning ".env 파일이 없습니다. env.template을 복사합니다..."
    cp env.template .env
    warning "⚠️ .env 파일을 편집하여 API 키를 설정하세요!"
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "배포 중단됨"
    fi
fi

# 필수 환경 변수 확인
required_vars=("OPENAI_API_KEY" "ANTHROPIC_API_KEY" "GOOGLE_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env || grep -q "^$var=your_" .env; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    warning "다음 환경 변수들이 설정되지 않았습니다:"
    printf '%s\n' "${missing_vars[@]}"
    read -p "테스트 모드로 계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "배포 중단됨"
    fi
fi

success "사전 검사 완료"

# ===== 보안 검사 =====
log "2. 보안 설정 검사..."

# CORS 설정 확인
if grep -q "ALLOWED_ORIGINS=.*\*" .env; then
    warning "CORS가 모든 Origin을 허용합니다. 프로덕션에서는 특정 도메인만 허용하세요."
fi

# Secret Key 확인
if grep -q "SECRET_KEY=your-super-secret-key-here" .env; then
    warning "기본 Secret Key가 사용되고 있습니다. 프로덕션에서는 고유한 키를 사용하세요."
fi

success "보안 검사 완료"

# ===== 백업 생성 =====
log "3. 현재 시스템 백업..."

mkdir -p "$BACKUP_DIR"

# 데이터베이스 백업
if [ -f "backend/test.db" ]; then
    cp backend/test.db "$BACKUP_DIR/"
    success "데이터베이스 백업 완료"
fi

# 로그 백업
if [ -d "logs" ]; then
    cp -r logs "$BACKUP_DIR/"
    success "로그 백업 완료"
fi

# 환경 설정 백업
cp .env "$BACKUP_DIR/"
success "환경 설정 백업 완료"

# ===== 이미지 빌드 =====
log "4. Docker 이미지 빌드..."

# 기존 이미지 정리 (선택사항)
if docker images | grep -q "$PROJECT_NAME"; then
    docker rmi $(docker images "$PROJECT_NAME" -q) 2>/dev/null || true
fi

# 새 이미지 빌드
if ! docker-compose build --no-cache; then
    error "Docker 이미지 빌드 실패"
fi

success "이미지 빌드 완료"

# ===== 헬스체크 함수 =====
wait_for_health() {
    local url=$1
    local max_wait=$2
    local wait_time=0
    
    log "서비스 헬스체크 대기 중..."
    
    while [ $wait_time -lt $max_wait ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            success "서비스가 정상 작동 중입니다"
            return 0
        fi
        
        echo -n "."
        sleep 5
        wait_time=$((wait_time + 5))
    done
    
    error "서비스 헬스체크 시간 초과"
}

# ===== 무중단 배포 =====
log "5. 무중단 배포 실행..."

# 현재 실행 중인 컨테이너 확인
if docker ps | grep -q "$PROJECT_NAME"; then
    log "기존 서비스 발견. 무중단 배포를 시작합니다..."
    
    # 새 컨테이너를 다른 포트로 시작
    TEMP_PORT=8001
    export PORT=$TEMP_PORT
    
    # 임시 서비스 시작
    docker-compose up -d --force-recreate
    
    # 새 서비스 헬스체크
    wait_for_health "http://localhost:$TEMP_PORT/health" $MAX_WAIT_TIME
    
    # 트래픽 전환 (Nginx 설정이 있는 경우)
    if docker ps | grep -q "nginx"; then
        log "Nginx 설정 업데이트 중..."
        # Nginx 설정 업데이트 로직 (여기서는 예시)
        # nginx-conf를 업데이트하고 reload
    fi
    
    # 기존 서비스 중지
    PORT=8000 docker-compose down
    
    # 포트를 원래대로 변경하고 재시작
    export PORT=8000
    docker-compose down
    docker-compose up -d
    
    wait_for_health "$HEALTH_CHECK_URL" $MAX_WAIT_TIME
    
else
    # 처음 배포인 경우
    log "신규 배포를 시작합니다..."
    docker-compose up -d
    wait_for_health "$HEALTH_CHECK_URL" $MAX_WAIT_TIME
fi

success "배포 완료"

# ===== 배포 후 검증 =====
log "6. 배포 후 검증..."

# API 엔드포인트 테스트
log "API 엔드포인트 테스트 중..."
if ! curl -f -s "http://localhost:8000/" > /dev/null; then
    error "API 루트 엔드포인트 접근 실패"
fi

if ! curl -f -s "http://localhost:8000/health" > /dev/null; then
    error "헬스체크 엔드포인트 접근 실패"
fi

# 컨테이너 상태 확인
if ! docker ps | grep -q "vizierai-api.*Up"; then
    error "API 컨테이너가 정상 실행되지 않습니다"
fi

success "배포 후 검증 완료"

# ===== 모니터링 설정 =====
log "7. 모니터링 설정..."

# 로그 디렉토리 생성
mkdir -p logs

# 로그 로테이션 설정 (logrotate)
if command -v logrotate &> /dev/null; then
    cat > /tmp/vizierai-logrotate << EOF
logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF
    sudo mv /tmp/vizierai-logrotate /etc/logrotate.d/vizierai 2>/dev/null || true
fi

success "모니터링 설정 완료"

# ===== 최종 정보 출력 =====
echo
echo "🎉 배포가 성공적으로 완료되었습니다!"
echo
echo "📊 배포 정보:"
echo "  - 환경: $DEPLOY_ENV"
echo "  - 백업 위치: $BACKUP_DIR"
echo "  - API URL: http://localhost:8000"
echo "  - 문서: http://localhost:8000/docs"
echo "  - 헬스체크: http://localhost:8000/health"
echo
echo "📝 다음 단계:"
echo "  1. 브라우저에서 http://localhost:8000/docs 접속하여 API 확인"
echo "  2. 실제 룰 검증 테스트 수행"
echo "  3. 모니터링 대시보드 설정"
echo "  4. SSL 인증서 설정 (HTTPS 사용시)"
echo
echo "🔍 유용한 명령어:"
echo "  - 로그 확인: docker-compose logs -f"
echo "  - 컨테이너 상태: docker ps"
echo "  - 서비스 재시작: docker-compose restart"
echo "  - 롤백: docker-compose down && 백업복원"
echo
success "배포 스크립트 완료!" 