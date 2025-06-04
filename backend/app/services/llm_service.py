import json
import os
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.config import settings

class LLMService:
    """Service for interacting with LLM"""
    
    def __init__(self):
        """Initialize LLM service with API key from settings"""
        try:
            api_key = os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY
            if not api_key:
                print("경고: OpenAI API 키가 설정되어 있지 않습니다. 대체 응답 모드로 작동합니다.")
                self.client = None
                self.model = None
                self.fake_mode = True
                return
                
            elif api_key.startswith("sk-your-") or api_key == "sk-your-valid-openai-api-key":
                print("경고: 기본 OpenAI API 키가 변경되지 않았습니다. 대체 응답 모드로 작동합니다.")
                self.client = None
                self.model = None
                self.fake_mode = True
                return
            
            self.client = OpenAI(api_key=api_key)
            self.model = os.environ.get("LLM_MODEL") or settings.LLM_MODEL
            self.fake_mode = False
            print(f"LLM 서비스 초기화 완료 - 사용 모델: {self.model}")
        except Exception as e:
            print(f"LLM 서비스 초기화 오류: {str(e)}. 대체 응답 모드로 작동합니다.")
            self.client = None
            self.model = None
            self.fake_mode = True
    
    async def call_llm(self, prompt: str, system_message: str = None) -> str:
        """
        Call LLM with prompt and optional system message
        
        Args:
            prompt: User prompt to send to LLM
            system_message: Optional system message for context
            
        Returns:
            LLM response as string
        """
        # API 키가 없거나 대체 모드인 경우
        if self.fake_mode:
            return self._generate_fallback_response(prompt, system_message)
            
        try:
            messages = []
            
            # 시스템 메시지 추가
            if system_message:
                messages.append({"role": "system", "content": system_message})
                
            # 사용자 프롬프트 추가
            messages.append({"role": "user", "content": prompt})
            
            # ChatCompletion API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1
            )
            
            # 응답 추출
            content = response.choices[0].message.content
            return content
        
        except Exception as e:
            print(f"LLM API 호출 오류: {str(e)}. 대체 응답을 생성합니다.")
            return self._generate_fallback_response(prompt, system_message)
    
    def _generate_fallback_response(self, prompt: str, system_message: str = None) -> str:
        """API 호출 실패 시 대체 응답 생성"""
        print("대체 응답 생성 중...")
        
        # 프롬프트에 '리포트'가 포함되어 있는지 확인
        if "리포트" in prompt.lower() or "report" in prompt.lower():
            return """# 🔍 룰 분석 리포트

## 📌 기본 정보
- **상태**: API 키 미설정으로 인한 대체 리포트
- **설명**: OpenAI API 키가 설정되지 않아 자동 생성된 대체 리포트입니다.

## ⚠️ 설정 필요
OpenAI API 키가 설정되어 있지 않거나 유효하지 않습니다. 다음 단계를 수행하세요:

1. OpenAI API 키를 발급받으세요: https://platform.openai.com/account/api-keys
2. 환경 변수 'OPENAI_API_KEY'에 발급받은 키를 설정하세요.
3. 서버를 재시작하세요.

## 📝 관리자 안내
- 환경 변수로 API 키 설정: `export OPENAI_API_KEY=your-key-here`
- 환경 파일(.env)에 API 키 설정: `OPENAI_API_KEY=your-key-here`

정상적인 리포트 생성을 위해 API 키를 설정해주세요."""
        
        # 그 외 일반적인 요청인 경우
        return "LLM 서비스를 사용할 수 없습니다. OpenAI API 키를 설정해주세요."
    
    async def generate_json(self, prompt: str, system_message: str = None) -> Dict[str, Any]:
        """
        Generate JSON from prompt
        
        Args:
            prompt: User prompt describing what JSON to generate
            system_message: Optional system message for context
            
        Returns:
            Generated JSON as dict
            
        Raises:
            ValueError: If API key is not set
            Exception: If API call fails or JSON parsing fails
        """
        if system_message is None:
            system_message = "You are a helpful assistant that generates valid JSON based on user requirements. Always respond with valid JSON only."
        
        response = await self.call_llm(prompt, system_message)
        
        # Extract JSON from response (handling cases where LLM might add markdown code blocks)
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {str(e)}, 응답: {response}")
            raise Exception(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {str(e)}") 