FROM python:3.11-slim

# 메타데이터
LABEL maintainer="VizierAI Team"
LABEL version="2.0.0"
LABEL description="VizierAI Rule Validation API - Production Ready"

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치 (최소한으로)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 비root 사용자 생성 (보안)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Python 의존성 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY app/ ./app/
COPY __init__.py .

# 로그 디렉토리 생성 및 권한 설정
RUN mkdir -p logs \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# 사용자 전환
USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"] 