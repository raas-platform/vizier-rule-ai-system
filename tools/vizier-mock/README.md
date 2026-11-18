# Vizier 로컬 테스트 화면

Vizier의 룰 디자인 화면처럼 **트리 모양으로 조건을 만들고, "검증"을 눌러 서버 결과를 트리 노드에 다시 표시**하는 단일 HTML 파일입니다. 빌드나 설치 없이 브라우저로 열면 됩니다. 화면에 JSON을 직접 입력하거나 보여주지 않습니다.

## 실행

1. 백엔드 실행 (기본 포트 8000)
   ```bash
   pip install -r backend/requirements.txt google-generativeai sqlalchemy
   uvicorn backend.app.main:app --port 8000
   ```
   레포 루트에서 실행하세요. 또는 `docker compose up`.
2. 화면을 로컬 웹서버로 엽니다. 서버 CORS가 정해진 Origin만 허용하므로 `file://`(더블클릭)로 열면 호출이 막힙니다.
   ```bash
   python -m http.server 5500 -d tools/vizier-mock
   ```
   브라우저에서 `http://localhost:5500`을 엽니다. `localhost`/`127.0.0.1`(모든 포트)은 `ENVIRONMENT`가 `production`이 아닐 때만 허용됩니다. 레포 루트에 `env.template`을 복사한 `.env`가 있으면 `ENVIRONMENT=production`이 들어 있으니 `development`로 바꾸세요.
3. 상단 "서버" 주소를 확인하고 "연결 확인"을 누릅니다(`GET /health`). EC2 서버를 볼 때는 주소만 바꾸면 됩니다.

## 화면

- **샘플**: 레포 루트의 `test_*.json` 9개를 트리로 불러옵니다. "새 룰"은 AND 그룹에 빈 조건 하나로 시작합니다.
- **조건 트리**: 최상위 그룹에서 아래로 갈라지는 조직도형 트리입니다. 그룹(AND/OR)과 조건이 박스로, 부모-자식이 선으로 연결됩니다.
  - 박스를 누르면 오른쪽 패널에서 편집합니다. 그룹: AND/OR 전환, `+ 조건 추가`, `+ 하위 그룹 추가`, 삭제. 조건: 표시명·키·연산자·값·타입 편집, 같은 그룹에 조건 추가, 삭제
  - 트리가 넓으면 자동으로 축소(최소 65%)됩니다. `−`/`+`/`맞춤` 버튼으로 조절
- **검증**: 트리를 룰 배열로 바꿔 `POST /rules/validate-json`으로 보냅니다.
  - 상단 요약: 유효 여부, 요약 문장, 오류/경고 수, 유형별 건수, 품질 점수, AI 코멘트
  - 각 조건 박스: 응답 `issues`의 `condUuid`로 매칭해 오류(빨강)/경고(노랑)/통과(초록) 배지 표시. 박스를 누르면 오른쪽 패널에 설명·AI 설명·제안 표시. 검증 후에는 문제가 있는 첫 조건이 자동 선택됨
  - `condUuid`가 없거나 트리에 없는 이슈는 상단 요약의 "룰 전체에 대한 이슈"에 표시
- 트리를 고치면 이전 검증 결과는 지워집니다(낡은 결과가 남지 않도록).

## 샘플 갱신

`test_*.json`을 바꾸거나 추가했다면:

```bash
python tools/vizier-mock/sync_samples.py
```
