#!/bin/bash

# 서버 URL 설정
API_URL="http://localhost:8000/api/v1"

# 색상 설정
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======= 룰 AI 시스템 API 테스트 스크립트 =======${NC}"

# 환경 변수 확인
if [ -z "$OPENAI_API_KEY" ]; then
  echo -e "${RED}환경 변수 OPENAI_API_KEY가 설정되어 있지 않습니다. 파일에서 불러옵니다.${NC}"
  if [ -f .env ]; then
    export OPENAI_API_KEY=$(cat .env | grep OPENAI_API_KEY | cut -d'=' -f2)
    echo -e "${GREEN}API 키 설정 완료: ${OPENAI_API_KEY:0:10}...${NC}"
  else
    echo -e "${RED}오류: .env 파일을 찾을 수 없습니다.${NC}"
    exit 1
  fi
fi

# 테스트 파일 확인
TEST_DATA_FILE="etc/test_report.json"
if [ ! -f "$TEST_DATA_FILE" ]; then
  echo -e "${RED}오류: $TEST_DATA_FILE 파일을 찾을 수 없습니다.${NC}"
  exit 1
fi

# 룰 리포트 생성 API 호출
echo -e "\n${BLUE}[ OpenAI API를 이용한 룰 리포트 생성 테스트 ]${NC}"

RESP_FILE="/tmp/rule_report_response.json"
curl -s -X POST "$API_URL/rules/report" \
  -H "Content-Type: application/json" \
  -d @$TEST_DATA_FILE > $RESP_FILE

# 응답 확인
if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ 성공: 룰 리포트 생성 API 호출${NC}"
  echo "리포트 미리보기:"
  cat $RESP_FILE | jq -r '.report' | head -n 10
  echo "..."
  
  # 마크다운 파일로 저장
  cat $RESP_FILE | jq -r '.report' > "generated_report.md"
  echo -e "${GREEN}✓ 리포트가 generated_report.md 파일로 저장되었습니다.${NC}"
else
  echo -e "${RED}✗ 실패: 룰 리포트 생성 API 호출${NC}"
fi

echo -e "\n${BLUE}======= 테스트 완료 =======${NC}" 