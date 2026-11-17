# Vizier 로컬 테스트 화면

Vizier 화면의 "검증" 버튼 흐름만 흉내 낸 단일 HTML 파일입니다. 빌드나 설치 없이 동작합니다.

## 사용법

1. 백엔드 실행 (기본 포트 8000)
   ```bash
   cd backend
   uvicorn app.main:app --port 8000
   ```
   또는 `docker compose up`
2. `tools/vizier-mock/index.html`을 브라우저로 직접 엽니다(더블클릭).
3. 상단 "서버" 주소를 확인하고 "연결 확인"을 누릅니다. EC2 서버를 볼 때는 주소를 바꾸면 됩니다.
4. 샘플을 고르거나 룰 JSON을 붙여넣고 "검증"을 누릅니다.

- 요청: `POST /rules/validate-json`, 본문은 룰 배열(첫 번째 룰만 검증). 단일 객체를 넣으면 배열로 감싸서 보냅니다.
- 결과: 요약, 이슈 표(condUuid/keyName, 설명, AI 설명), 원본 응답 JSON.
- 샘플은 레포 루트의 `test_*.json` 파일을 그대로 넣어 두었습니다.
- 서버 CORS가 `*` 허용이라 `file://`로 열어도 호출됩니다.
