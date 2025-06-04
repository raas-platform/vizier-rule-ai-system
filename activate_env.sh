#!/bin/bash

# vizierAI 프로젝트 가상환경 활성화 스크립트
echo "vizierAI 가상환경을 활성화합니다..."
source "$(dirname "$0")/venv/bin/activate"

echo "가상환경이 활성화되었습니다: $VIRTUAL_ENV" 