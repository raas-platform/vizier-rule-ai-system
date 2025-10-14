# 다단계 빌드를 사용한 최적화된 Python 컨테이너
FROM python:3.14-slim as builder

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 보안을 위한 비루트 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY backend/app/ ./app/
COPY backend/__init__.py .

# 로그 디렉토리 생성 및 권한 설정
RUN mkdir -p logs \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# 비루트 사용자로 전환
USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"] 