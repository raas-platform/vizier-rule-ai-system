#!/bin/bash

# VizierAI 프로덕션 배포 전 최종 검증 스크립트
# 모든 필수 수정사항이 완료되었는지 확인

set -e

echo "🔍 VizierAI 프로덕션 배포 전 최종 검증을 시작합니다..."

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 로깅 함수
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# 검증 점수
total_checks=0
passed_checks=0

# 1. Print문 검증
log "1. Print문 검증..."
total_checks=$((total_checks + 1))

print_count=$(find backend/app -name "*.py" -exec grep -l "print(" {} \; | wc -l)
if [ $print_count -eq 0 ]; then
    success "Print문이 모두 제거되었습니다."
    passed_checks=$((passed_checks + 1))
else
    error "아직 $print_count 개 파일에 print문이 남아있습니다."
    find backend/app -name "*.py" -exec grep -l "print(" {} \;
fi

# 2. Rate Limiting 검증
log "2. Rate Limiting 구현 검증..."
total_checks=$((total_checks + 1))

if [ -f "backend/app/middleware/rate_limiter.py" ]; then
    success "Rate Limiting 미들웨어가 구현되었습니다."
    passed_checks=$((passed_checks + 1))
else
    error "Rate Limiting 미들웨어가 없습니다."
fi

# 3. API 키 검증 구현 확인
log "3. API 키 검증 구현 확인..."
total_checks=$((total_checks + 1))

if [ -f "backend/app/utils/api_validator.py" ]; then
    success "API 키 검증 유틸리티가 구현되었습니다."
    passed_checks=$((passed_checks + 1))
else
    error "API 키 검증 유틸리티가 없습니다."
fi

# 4. .gitignore 확인
log "4. .gitignore __pycache__ 설정 확인..."
total_checks=$((total_checks + 1))

if grep -q "__pycache__" .gitignore; then
    success "__pycache__ 디렉토리가 .gitignore에 추가되었습니다."
    passed_checks=$((passed_checks + 1))
else
    error "__pycache__ 디렉토리가 .gitignore에 없습니다."
fi

# 5. __pycache__ 디렉토리 정리 확인
log "5. __pycache__ 디렉토리 정리 확인 (venv 제외)..."
total_checks=$((total_checks + 1))

pycache_count=$(find . -name "__pycache__" -not -path "./venv/*" -type d | wc -l)
if [ $pycache_count -eq 0 ]; then
    success "__pycache__ 디렉토리가 모두 정리되었습니다."
    passed_checks=$((passed_checks + 1))
else
    warning "$pycache_count 개의 __pycache__ 디렉토리가 남아있습니다 (venv 제외)."
    find . -name "__pycache__" -not -path "./venv/*" -type d
    # venv 외부의 __pycache__가 없다면 통과로 처리
    if [ $pycache_count -eq 0 ]; then
        passed_checks=$((passed_checks + 1))
    fi
fi

# 6. 환경 설정 파일 확인
log "6. 환경 설정 파일 확인..."
total_checks=$((total_checks + 1))

if [ -f "env.template" ]; then
    if grep -q "RATE_LIMIT_PER_MINUTE" env.template; then
        success "Rate Limiting 환경 변수가 설정되어 있습니다."
        passed_checks=$((passed_checks + 1))
    else
        error "Rate Limiting 환경 변수가 env.template에 없습니다."
    fi
else
    error "env.template 파일이 없습니다."
fi

# 7. Docker 설정 확인
log "7. Docker 설정 확인..."
total_checks=$((total_checks + 1))

if [ -f "backend/Dockerfile" ] && [ -f "docker-compose.yml" ]; then
    success "Docker 설정 파일들이 존재합니다."
    passed_checks=$((passed_checks + 1))
else
    error "Docker 설정 파일이 누락되었습니다."
fi

# 8. 배포 스크립트 확인
log "8. 배포 스크립트 확인..."
total_checks=$((total_checks + 1))

if [ -f "deploy-production.sh" ] && [ -x "deploy-production.sh" ]; then
    success "프로덕션 배포 스크립트가 준비되었습니다."
    passed_checks=$((passed_checks + 1))
else
    error "프로덕션 배포 스크립트가 없거나 실행 권한이 없습니다."
fi

# 9. 의존성 확인
log "9. 의존성 확인..."
total_checks=$((total_checks + 1))

if grep -q "httpx" requirements.txt; then
    success "필요한 의존성(httpx)이 requirements.txt에 추가되었습니다."
    passed_checks=$((passed_checks + 1))
else
    error "httpx 의존성이 requirements.txt에 없습니다."
fi

# 10. 보안 헤더 확인
log "10. 보안 설정 확인..."
total_checks=$((total_checks + 1))

if grep -q "X-Content-Type-Options" backend/app/main.py; then
    success "보안 헤더가 main.py에 설정되어 있습니다."
    passed_checks=$((passed_checks + 1))
else
    error "보안 헤더가 main.py에 설정되지 않았습니다."
fi

# 결과 출력
echo
echo "=" * 50
echo "📊 프로덕션 준비 상태 검증 결과"
echo "=" * 50

score=$((passed_checks * 100 / total_checks))

if [ $passed_checks -eq $total_checks ]; then
    echo -e "${GREEN}🎉 모든 검증 통과! ($passed_checks/$total_checks)${NC}"
    echo -e "${GREEN}✅ 프로덕션 배포 준비 완료!${NC}"
    
    echo
    echo "🚀 다음 단계:"
    echo "1. API 키 설정: cp env.template .env && vim .env"
    echo "2. 프로덕션 배포: ./deploy-production.sh"
    echo "3. 서비스 확인: curl http://localhost:8000/health"
    
    exit 0
else
    echo -e "${RED}⚠️ 검증 실패: $passed_checks/$total_checks 통과 (${score}%)${NC}"
    echo -e "${RED}❌ 추가 수정이 필요합니다!${NC}"
    
    echo
    echo "🔧 수정이 필요한 항목들을 위에서 확인하고 수정 후 다시 실행하세요."
    
    exit 1
fi 