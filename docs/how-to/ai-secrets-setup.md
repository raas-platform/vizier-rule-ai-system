# 🔑 AI 기능 활성화용 GitHub Secrets 설정

## 필수 API 키들

GitHub Repository → Settings → Secrets and variables → Actions → New repository secret

### 🧪 스테이징 환경용
```
OPENAI_API_KEY_STAGING=sk-proj-your-staging-key...
ANTHROPIC_API_KEY_STAGING=sk-ant-your-staging-key...
GOOGLE_API_KEY_STAGING=AIza-your-staging-key...
SECRET_KEY_STAGING=your-32-character-staging-secret-key
```

### 🏭 프로덕션 환경용
```
OPENAI_API_KEY_PROD=sk-proj-your-production-key...
ANTHROPIC_API_KEY_PROD=sk-ant-your-production-key...
GOOGLE_API_KEY_PROD=AIza-your-production-key...
SECRET_KEY_PROD=your-32-character-production-secret-key
```

### 💻 개발 환경용 (선택사항)
```
OPENAI_API_KEY_DEV=sk-proj-your-dev-key...
ANTHROPIC_API_KEY_DEV=sk-ant-your-dev-key...
GOOGLE_API_KEY_DEV=AIza-your-dev-key...
```

## API 키 획득 방법

### OpenAI API 키
1. https://platform.openai.com/api-keys 접속
2. "Create new secret key" 클릭
3. 이름 설정 후 키 생성
4. 생성된 키를 복사 (한 번만 표시됨)

### Anthropic API 키  
1. https://console.anthropic.com/ 접속
2. "API Keys" 메뉴 선택
3. "Create Key" 클릭
4. 생성된 키를 복사

### Google AI API 키
1. https://aistudio.google.com/app/apikey 접속
2. "Create API key" 클릭
3. 프로젝트 선택 또는 생성
4. 생성된 키를 복사

## 안전한 SECRET_KEY 생성
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 외부 GUI에서 사용할 API 엔드포인트들

### 🤖 LLM 모델 관리
- `GET /api/llm/models` - 사용 가능한 모델 목록 (드롭다운용)
- `GET /api/llm/models/{model_id}/status` - 모델 상태 확인
- `POST /api/llm/generate` - 텍스트 생성 (모델 선택)

### 📝 프롬프트 관리  
- `GET /api/prompts/` - 프롬프트 목록 (드롭다운용)
- `GET /api/prompts/categories/list` - 카테고리 목록
- `POST /api/prompts/execute` - 프롬프트 실행 (모델 + 프롬프트 조합)

### 🎯 API 사용 예시 (GUI에서 호출)
```javascript
// 1. 사용 가능한 모델 목록 가져오기
const models = await fetch('/api/llm/models').then(r => r.json());

// 2. 프롬프트 목록 가져오기  
const prompts = await fetch('/api/prompts/').then(r => r.json());

// 3. 선택된 모델 + 프롬프트로 실행
const result = await fetch('/api/prompts/execute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prompt_id: selectedPromptId,
    model_id: selectedModelId, 
    variables: { /* 프롬프트 변수들 */ }
  })
});
``` 