#!/bin/bash

# VizierAI API 키 설정 스크립트
# 실제 API 키들을 안전하게 .env 파일에 설정합니다.

echo "🔑 VizierAI API 키 설정을 시작합니다..."

# 현재 .env 파일 백업
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 기존 .env 파일을 백업했습니다."
fi

# OpenAI API 키 입력
echo ""
echo "🤖 OpenAI API 키를 입력해주세요:"
echo "   (sk-로 시작하는 키를 입력하세요. 입력 시 화면에 표시되지 않습니다)"
read -s OPENAI_KEY
if [[ $OPENAI_KEY == sk-* ]]; then
    sed -i '' "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
    echo "✅ OpenAI API 키가 설정되었습니다."
else
    echo "❌ 올바른 OpenAI API 키 형식이 아닙니다. (sk-로 시작해야 함)"
    exit 1
fi

# Anthropic API 키 입력
echo ""
echo "🤖 Anthropic API 키를 입력해주세요:"
echo "   (sk-ant-로 시작하는 키를 입력하세요. 입력 시 화면에 표시되지 않습니다)"
read -s ANTHROPIC_KEY
if [[ $ANTHROPIC_KEY == sk-ant-* ]]; then
    sed -i '' "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$ANTHROPIC_KEY/" .env
    echo "✅ Anthropic API 키가 설정되었습니다."
else
    echo "❌ 올바른 Anthropic API 키 형식이 아닙니다. (sk-ant-로 시작해야 함)"
    exit 1
fi

# Google API 키 입력
echo ""
echo "🤖 Google API 키를 입력해주세요:"
echo "   (AI... 형식의 키를 입력하세요. 입력 시 화면에 표시되지 않습니다)"
read -s GOOGLE_KEY
if [[ $GOOGLE_KEY == AI* ]]; then
    sed -i '' "s/GOOGLE_API_KEY=.*/GOOGLE_API_KEY=$GOOGLE_KEY/" .env
    echo "✅ Google API 키가 설정되었습니다."
else
    echo "❌ 올바른 Google API 키 형식이 아닙니다. (AI...로 시작해야 함)"
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