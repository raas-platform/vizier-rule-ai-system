# Vizier 로컬 테스트 화면

Vizier의 룰 디자인 화면처럼 **트리 모양으로 조건을 만들고, "검증"을 눌러 서버 결과를 트리 노드에 다시 표시**하는 단일 HTML 파일입니다. 빌드나 설치 없이 브라우저로 열면 됩니다. 화면에 JSON을 직접 입력하거나 보여주지 않습니다.

## 실행

1. 백엔드 실행 (기본 포트 8000)
   ```bash
   pip install -r backend/requirements.txt google-generativeai sqlalchemy
   uvicorn backend.app.main:app --port 8000
   ```
   레포 루트에서 실행하세요. 또는 `docker compose up`.
2. `tools/vizier-mock/index.html`을 브라우저로 엽니다(더블클릭). 서버 CORS가 모든 오리진을 허용해서 `file://`로 열어도 호출됩니다.
3. 상단 "서버" 주소를 확인하고 "연결 확인"을 누릅니다(`GET /health`). EC2 서버를 볼 때는 주소만 바꾸면 됩니다.

## 화면

- **샘플**: 레포 루트의 `test_*.json` 9개를 트리로 불러옵니다. "새 룰"은 빈 AND 그룹에서 시작합니다.
- **조건 트리**
  - 그룹 노드: AND/OR 버튼을 누르면 전환, `+ 조건`, `+ 그룹`, `삭제`
  - 조건 노드: 누르면 편집 칸이 열림(표시명, 키, 연산자, 값, 타입). 연산자는 목록에서 고르거나 직접 입력
- **검증**: 트리를 룰 배열로 바꿔 `POST /rules/validate-json`으로 보냅니다.
  - 상단 요약: 유효 여부, 요약 문장, 오류/경고 수, 유형별 건수, 품질 점수, AI 코멘트
  - 각 조건 노드: 응답 `issues`의 `condUuid`로 매칭해 오류(빨강)/경고(노랑)/통과(초록) 표시, 설명·AI 설명·제안을 노드 아래에 표시
  - `condUuid`가 없거나 트리에 없는 이슈는 트리 아래 "룰 전체에 대한 이슈"에 표시
- 트리를 고치면 이전 검증 결과는 지워집니다(낡은 결과가 남지 않도록).

## 샘플 갱신

`test_*.json`을 바꾸거나 추가했다면:

```bash
python tools/vizier-mock/sync_samples.py
```
