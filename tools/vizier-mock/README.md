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

Vizier 화면과 같은 배치입니다: **가운데 조건 트리 + 오른쪽 AI 패널("AI Report")**.

- **샘플**: 레포 루트의 `test_*.json` 9개를 트리로 불러옵니다. "새 룰"은 AND 그룹에 빈 조건 하나로 시작합니다.
- **조건 트리**: 최상위 그룹에서 아래로 갈라지는 조직도형 트리입니다. 트리가 넓으면 자동으로 축소(최소 65%)되고 `−`/`+`/`맞춤`으로 조절합니다.
  - 검증 후 이슈가 있는 조건 박스에 `⚠ N` 아이콘과 빨간(오류)/노란(경고만) 테두리, 이슈 없는 조건은 초록 "통과". 노드에 설명 글은 넣지 않습니다.
  - 박스를 누르면 선택 표시가 되고, **편집은 트리 아래 "편집" 영역**에서 합니다(그룹: AND/OR, 조건 추가, 하위 그룹, 삭제 / 조건: 표시명·키·연산자·값·타입).
- **검증**: `POST /rules/validate-json` → AI 패널 위쪽에 서버가 준 `ai_summary_md`를 markdown으로 그립니다(판정, 오류·경고 건수, 요약, 종합 의견, 룰 전체 이슈). 응답에 `rule_description`이 있으면 맨 위에 "이 룰은" 칸(설명, 목적(추정)).
- **조건 클릭**: 요약 아래 "선택한 조건"에 서버가 준 `condition_details_md[condUuid]`를 그립니다. 다른 조건을 누르면 바뀝니다.
- markdown은 raw HTML을 그리지 않고 글자로 보여 주며(marked의 html 렌더러를 이스케이프로 바꿈), DOMPurify로 한 번 더 거릅니다. 서버도 두 필드에서 `<`, `>`, `[`, `]` 등을 이스케이프합니다.
- 화면에 JSON은 보여 주지 않습니다.
- **리포트**: AI 패널 아래 "리포트" 버튼(또는 패널의 "리포트" 탭).
  - 검증 전에는 꺼져 있고, 검증하면 켜지며, 트리·룰 정보를 고치면 다시 꺼지고(이전 결과·리포트도 지움) 재검증하면 켜집니다.
  - MD / HTML을 고르면 `POST /rules/report/stream`(SSE)으로 받은 내용을 **패널 안에 실시간으로** 그립니다. MD는 markdown 렌더, HTML은 `sandbox` iframe(스크립트 불가). 작성 중에는 진행 막대·상태·"중지", 실패하면 사유, 완료되면 "다운로드"(`룰이름_검증리포트_YYYYMMDD-HHmm.md|html`).
  - "검증 요약" 탭으로 돌아가 조건 설명을 볼 수 있습니다. 리포트를 쓰는 중에 조건을 눌러도 작성은 뒤에서 계속되고, "리포트" 탭으로 다시 오면 이어서 보입니다.
  - 패널이 좁으면 "넓게"로 패널 폭을 키웁니다.
  - 서버에 `REPORT_API_KEY`가 설정되어 있고 이 화면 주소가 `REPORT_ALLOWED_ORIGINS`에 없으면 형식 선택 화면의 "API 키" 칸에 키를 넣으세요(브라우저에만 저장).
  - 서버에 `ANTHROPIC_API_KEY`가 있어야 합니다. markdown 렌더는 cdnjs의 marked·DOMPurify를 쓰며, 못 불러오면 원문으로 보여 줍니다.

## 샘플 갱신

`test_*.json`을 바꾸거나 추가했다면:

```bash
python tools/vizier-mock/sync_samples.py
```
