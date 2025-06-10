.PHONY: help install test lint format clean dev build deploy health

# 기본 변수
PYTHON = python3
PIP = pip3
BACKEND_DIR = backend
VENV = venv
PORT = 8000

# 색상 코드
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

help: ## 도움말 표시
	@echo "🚀 VizierAI 개발 도구"
	@echo ""
	@echo "사용 가능한 명령어:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## 의존성 설치
	@echo "$(YELLOW)📦 의존성 설치 중...$(NC)"
	$(PIP) install -r requirements.txt
	$(PIP) install -r backend/requirements.txt
	@echo "$(GREEN)✅ 의존성 설치 완료$(NC)"

install-dev: ## 개발 의존성 설치
	@echo "$(YELLOW)🛠️  개발 의존성 설치 중...$(NC)"
	$(PIP) install black isort flake8 mypy pytest pytest-cov bandit safety
	@echo "$(GREEN)✅ 개발 의존성 설치 완료$(NC)"

venv: ## 가상환경 생성
	@echo "$(YELLOW)🔧 가상환경 생성 중...$(NC)"
	$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)✅ 가상환경 생성 완료$(NC)"
	@echo "$(BLUE)활성화 명령: source $(VENV)/bin/activate$(NC)"

env: ## .env 파일 생성
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)🔧 .env 파일 생성 중...$(NC)"; \
		cp env.template .env; \
		echo "$(GREEN)✅ .env 파일 생성 완료$(NC)"; \
		echo "$(BLUE)💡 .env 파일을 편집하여 API 키를 설정하세요$(NC)"; \
	else \
		echo "$(GREEN)✅ .env 파일이 이미 존재합니다$(NC)"; \
	fi

format: ## 코드 포맷팅
	@echo "$(YELLOW)🎨 코드 포맷팅 중...$(NC)"
	black $(BACKEND_DIR)/
	isort $(BACKEND_DIR)/
	@echo "$(GREEN)✅ 코드 포맷팅 완료$(NC)"

lint: ## 코드 린트 검사
	@echo "$(YELLOW)🔍 코드 린트 검사 중...$(NC)"
	flake8 $(BACKEND_DIR)/ --max-line-length=88 --extend-ignore=E203,W503
	mypy $(BACKEND_DIR)/app --ignore-missing-imports
	@echo "$(GREEN)✅ 린트 검사 완료$(NC)"

security: ## 보안 검사
	@echo "$(YELLOW)🔒 보안 검사 중...$(NC)"
	bandit -r $(BACKEND_DIR)/ -f json -o bandit-report.json || true
	safety check -r requirements.txt || true
	@echo "$(GREEN)✅ 보안 검사 완료$(NC)"

test: ## 테스트 실행
	@echo "$(YELLOW)🧪 테스트 실행 중...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) -m pytest -v
	@echo "$(GREEN)✅ 테스트 완료$(NC)"

test-cov: ## 커버리지 포함 테스트
	@echo "$(YELLOW)📊 커버리지 테스트 실행 중...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) -m pytest --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)✅ 커버리지 테스트 완료$(NC)"
	@echo "$(BLUE)💡 htmlcov/index.html에서 상세 리포트 확인$(NC)"

dev: env ## 개발 서버 실행
	@echo "$(YELLOW)🚀 개발 서버 시작 중...$(NC)"
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

build: ## Docker 이미지 빌드
	@echo "$(YELLOW)🐳 Docker 이미지 빌드 중...$(NC)"
	docker-compose build
	@echo "$(GREEN)✅ Docker 이미지 빌드 완료$(NC)"

up: env ## Docker Compose로 서비스 시작
	@echo "$(YELLOW)🚀 서비스 시작 중...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✅ 서비스 시작 완료$(NC)"
	@echo "$(BLUE)💡 http://localhost:$(PORT)에서 확인하세요$(NC)"

down: ## Docker Compose 서비스 중지
	@echo "$(YELLOW)🛑 서비스 중지 중...$(NC)"
	docker-compose down
	@echo "$(GREEN)✅ 서비스 중지 완료$(NC)"

logs: ## Docker 로그 확인
	docker-compose logs -f

health: ## 헬스체크
	@echo "$(YELLOW)🏥 헬스체크 실행 중...$(NC)"
	@curl -f http://localhost:$(PORT)/health && echo "$(GREEN)✅ 서비스 정상$(NC)" || echo "$(RED)❌ 서비스 오류$(NC)"

deploy-staging: ## 스테이징 배포
	@echo "$(YELLOW)🧪 스테이징 배포 중...$(NC)"
	./deploy-production.sh staging
	@echo "$(GREEN)✅ 스테이징 배포 완료$(NC)"

deploy-prod: ## 프로덕션 배포
	@echo "$(YELLOW)🏭 프로덕션 배포 중...$(NC)"
	./deploy-production.sh production
	@echo "$(GREEN)✅ 프로덕션 배포 완료$(NC)"

clean: ## 임시 파일 정리
	@echo "$(YELLOW)🧹 임시 파일 정리 중...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "$(GREEN)✅ 정리 완료$(NC)"

all-checks: format lint security test ## 모든 검사 실행
	@echo "$(GREEN)🎉 모든 검사 완료!$(NC)"

ci-setup: install install-dev ## CI 환경 설정
	@echo "$(GREEN)🔧 CI 환경 설정 완료$(NC)"

quick-start: venv install env dev ## 빠른 시작 (전체 설정)
	@echo "$(GREEN)🚀 빠른 시작 완료!$(NC)" 