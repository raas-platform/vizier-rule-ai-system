#!/bin/bash

# VizierAI API 키 설정 스크립트 (명령줄 인자 방식)
# 사용법: ./set_api_keys.sh <OPENAI_KEY> <ANTHROPIC_KEY> <GOOGLE_KEY>

if [ $# -ne 3 ]; then
    echo "❌ 사용법: $0 <OPENAI_KEY> <ANTHROPIC_KEY> <GOOGLE_KEY>"
    echo ""
    echo "예시:"
    echo "  $0 sk-proj-... sk-ant-... AIza..."
    echo ""
    echo "또는 직접 .env 파일을 편집하세요:"
    echo "  nano .env"
    exit 1
fi

OPENAI_KEY=$1
ANTHROPIC_KEY=$2
GOOGLE_KEY=$3

echo "🔑 API 키 설정을 시작합니다..."

# .env 파일 백업
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 기존 .env 파일을 백업했습니다."
fi

# API 키 형식 검증 및 설정
if [[ $OPENAI_KEY == sk-* ]]; then
    sed -i '' "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
    echo "✅ OpenAI API 키가 설정되었습니다."
else
    echo "❌ 올바른 OpenAI API 키 형식이 아닙니다. (sk-로 시작해야 함)"
    exit 1
fi

if [[ $ANTHROPIC_KEY == sk-ant-* ]]; then
    sed -i '' "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$ANTHROPIC_KEY/" .env
    echo "✅ Anthropic API 키가 설정되었습니다."
else
    echo "❌ 올바른 Anthropic API 키 형식이 아닙니다. (sk-ant-로 시작해야 함)"
    exit 1
fi

if [[ $GOOGLE_KEY == AI* ]]; then
    sed -i '' "s/GOOGLE_API_KEY=.*/GOOGLE_API_KEY=$GOOGLE_KEY/" .env
    echo "✅ Google API 키가 설정되었습니다."
else
    echo "❌ 올바른 Google API 키 형식이 아닙니다. (AI로 시작해야 함)"
    exit 1
fi

echo ""
echo "🎉 모든 API 키가 성공적으로 설정되었습니다!"
echo ""
echo "설정된 키들 (마스킹됨):"
echo "  - OpenAI: ${OPENAI_KEY:0:7}...${OPENAI_KEY: -4}"
echo "  - Anthropic: ${ANTHROPIC_KEY:0:10}...${ANTHROPIC_KEY: -4}"
echo "  - Google: ${GOOGLE_KEY:0:5}...${GOOGLE_KEY: -4}"
echo ""
echo "🚀 이제 배포를 진행할 수 있습니다:"
echo "   ./deploy-production.sh" 