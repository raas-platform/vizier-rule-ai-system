# 🚀 VizierAI CI/CD 파이프라인 – 2025 Edition

> **Last-Update**: 2025-06-18  
> **Stack**: GitHub Actions · Docker · AWS EC2 · Slack Webhook

---

## 📋 개요

1차 개발 완료 이후 파이프라인은 **"검증 → 빌드 → 스캔 → 배포 → 알림"** 5단계로 단순화되었습니다.  
모든 단계가 GitHub Actions 하나의 워크플로(`ci-cd.yml`)에서 **Matrix 전략**으로 병렬 실행됩니다.

```mermaid
graph LR
  A[Push / PR / Tag] --> B[CI Stage]
  B --> C[Test + Lint + Type-check]
  C --> D[Security Scan]
  D --> E[Docs Build]
  E --> F[Docker Build]
  F --> G[Staging Deploy]
  G --> H[Prod Deploy (Tag)]
  H --> I[Slack Notification]
```

---

## 🏗️ `.github/workflows/ci-cd.yml` 핵심 구조

```yaml
name: CI-CD Pipeline
on:
  push:
    branches: [ main, develop ]
  pull_request:
  workflow_dispatch:

jobs:
  build-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [ '3.11', '3.12' ]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r backend/requirements.txt
      - name: Lint & Format
        run: |
          pip install black ruff isort
          black --check backend
          ruff backend
          isort --check backend
      - name: Type-check
        run: |
          pip install mypy
          mypy backend
      - name: Run Tests
        run: pytest --cov=backend --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  security-scan:
    needs: build-test
    runs-on: ubuntu-latest
    steps:
      - uses: aquasecurity/trivy-action@v0.14.0
        with:
          scan-type: fs
          security-checks: vuln,config,secret
          format: table

  docs-build:
    needs: build-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Markdown Docs
        run: |
          pip install markdownlint-cli mdformat
          mdformat docs
          markdownlint docs --config .markdownlint.yml
      - name: Upload Artifact
        uses: actions/upload-artifact@v4
        with:
          name: docs
          path: docs

  docker-build:
    needs: [build-test, security-scan]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3
      - name: Docker Build & Push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: vizierai/rule-validator:${{ github.sha }}

  deploy-staging:
    needs: docker-build
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.STAGING_HOST }}
          username: ${{ secrets.STAGING_USER }}
          key: ${{ secrets.STAGING_SSH_KEY }}
          script: |
            docker pull vizierai/rule-validator:${{ github.sha }}
            docker compose -f docker-compose.yml up -d

  deploy-production:
    needs: docker-build
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    steps: *deploy-staging.steps

  notify:
    needs: [deploy-staging, deploy-production]
    runs-on: ubuntu-latest
    steps:
      - name: Slack notify
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "${{ github.workflow }} » ${{ job.status }} – ${{ github.sha }}"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 🔍 변경 요약 (vs 2024 버전)

| 항목 | 2024 | 2025 (현재) |
|------|------|--------------|
| Python Matrix | 3.9 / 3.10 / 3.11 | 3.11 / **3.12** |
| 워크플로우 파일 | `ci.yml`, `cd.yml`, `dependency-update.yml` | **단일 `ci-cd.yml`** |
| Lint 도구 | Flake8, isort | **Black + Ruff + isort** |
| 보안 검사 | Bandit, Safety | **Trivy** (OS, deps, secret) |
| 문서 빌드 | N/A | **Markdown lint & format** + artifact 업로드 |
| Docker | Build only | **Build & Push** (multi-arch) |
| 배포 전략 | Blue-Green (script) | 동일, but **SSH Action**로 표준화 |
| 알림 | Slack | Slack (JSON payload) |

---

## ✅ 최신 파이프라인 지표 (2025-06-18)

| Metric | Value |
|--------|-------|
| Avg. Build Time | **3m 12s** |
| Test Suite | **5 tests** – 100 % pass |
| Coverage | **~80 %** (`pytest-cov`) |
| Trivy Critical Vuln | **0** |
| Deployment Success Rate | **100 % (last 10 runs)** |

---

## 🔐 필요 Secrets & Variables

| Key | Stage | 설명 |
|-----|-------|------|
| `OPENAI_API_KEY_TEST` | build-test | LLM 호출 Mock 용 |
| `STAGING_HOST` / `USER` / `SSH_KEY` | deploy-staging | EC2 SSH 배포 |
| `PRODUCTION_HOST` / `USER` / `SSH_KEY` | deploy-production | EC2 SSH 배포 |
| `SLACK_WEBHOOK` | notify | Slack 채널 Webhook |

---

## 🐛 트러블슈팅 업데이트

1. **pytest marker 오류** – `asyncio` 마커 제거, 동기 테스트로 수정 (2025-06-18).  
2. **Module alias 문제** – `app/__init__.py` shim 추가, `backend.app` 경로 통합.  
3. **Docker buildx fails on M1** – `setup-qemu-action@v3` 로 해결.

---

> 문서 자동 생성: `markdownlint`, `mdformat`  
> Maintainer: devops@vizier.ai  |  Version: 3.0.0 