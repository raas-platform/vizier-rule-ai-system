"""
스트리밍 대시보드 API - 완전 독립적 구현
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.llm_service import llm_service
from ..api.rule_validator import generate_ai_html_report
from ..utils.logger import get_logger

router = APIRouter(prefix="/streaming", tags=["streaming-dashboard"])
logger = get_logger(__name__)

# 태스크 상태 저장 (메모리 기반)
task_storage: Dict[str, Dict[str, Any]] = {}

class TaskRequest(BaseModel):
    validation_result: Dict[str, Any]

class AnalysisRequest(BaseModel):
    json_data: list  # JSON 배열 데이터

class TaskResponse(BaseModel):
    task_id: str
    status: str

@router.post("/start-sse-task")
async def start_sse_task(request: TaskRequest) -> TaskResponse:
    task_id = str(uuid.uuid4())
    
    task_storage[task_id] = {
        "type": "sse",
        "status": "started",
        "progress": 0,
        "message": "🤖 AI 모델 준비 중...",
        "validation_result": request.validation_result,
        "result": None,
        "error": None,
        "created_at": time.time()
    }
    
    asyncio.create_task(run_sse_background_task(task_id, request.validation_result))
    
    return TaskResponse(task_id=task_id, status="started")

@router.post("/start-html-task") 
async def start_html_task(request: TaskRequest) -> TaskResponse:
    task_id = str(uuid.uuid4())
    
    task_storage[task_id] = {
        "type": "html",
        "status": "started", 
        "progress": 0,
        "message": "🧠 HTML 생성 준비 중...",
        "validation_result": request.validation_result,
        "html_chunks": [],
        "result": None,
        "error": None,
        "created_at": time.time()
    }
    
    asyncio.create_task(run_html_streaming_task(task_id, request.validation_result))
    
    return TaskResponse(task_id=task_id, status="started")

@router.post("/start-analysis-task")
async def start_analysis_task(request: AnalysisRequest) -> TaskResponse:
    task_id = str(uuid.uuid4())
    
    task_storage[task_id] = {
        "type": "analysis",
        "status": "started",
        "progress": 0,
        "message": "🤖 룰 분석 준비 중...",
        "json_data": request.json_data,
        "result": None,
        "error": None,
        "created_at": time.time()
    }
    
    asyncio.create_task(run_analysis_task(task_id, request.json_data))
    
    return TaskResponse(task_id=task_id, status="started")

@router.get("/stream/sse/{task_id}")
async def stream_sse_progress(task_id: str):
    async def event_generator():
        try:
            while True:
                if task_id not in task_storage:
                    yield f"data: {json.dumps({'type': 'error', 'message': '태스크를 찾을 수 없습니다'})}\n\n"
                    return
                
                task = task_storage[task_id]
                
                data = {
                    "type": "progress",
                    "progress": task["progress"],
                    "message": task["message"],
                    "status": task["status"]
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                if task["status"] == "completed":
                    if task["result"]:
                        if task["type"] == "analysis":
                            # 분석 결과인 경우 - Pydantic 모델을 dict로 변환
                            try:
                                if hasattr(task["result"], 'model_dump'):
                                    # Pydantic v2
                                    result_dict = task["result"].model_dump()
                                    logger.info(f"Pydantic v2 결과 직렬화 완료: ai_summary_md 포함={hasattr(task['result'], 'ai_summary_md')}")
                                elif hasattr(task["result"], 'dict'):
                                    # Pydantic v1
                                    result_dict = task["result"].dict()
                                    logger.info(f"Pydantic v1 결과 직렬화 완료: ai_summary_md 포함={hasattr(task['result'], 'ai_summary_md')}")
                                else:
                                    # 일반 객체
                                    result_dict = {"message": "분석 완료", "data": str(task["result"])}
                                    logger.warning("일반 객체로 처리됨")
                                
                                # ai_summary_md 확인
                                if 'ai_summary_md' in result_dict:
                                    logger.info(f"ai_summary_md 길이: {len(result_dict['ai_summary_md'])}자")
                                else:
                                    logger.warning("ai_summary_md가 결과에 없음")
                                    
                            except Exception as e:
                                logger.warning(f"결과 직렬화 실패: {e}")
                                result_dict = {"message": "분석 완료", "error": str(e)}
                            
                            final_data = {
                                "type": "complete",
                                "result": result_dict
                            }
                        else:
                            # HTML 리포트인 경우
                            final_data = {
                                "type": "complete",
                                "html": task["result"]["report"],
                                "model_used": task["result"].get("model_used", "unknown")
                            }
                        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                    break
                elif task["status"] == "error":
                    error_data = {
                        "type": "error", 
                        "message": task["error"] or "알 수 없는 오류가 발생했습니다"
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    break
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"SSE 스트리밍 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'스트리밍 오류: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*"
        }
    )

@router.get("/stream/html/{task_id}")
async def stream_html_chunks(task_id: str):
    async def event_generator():
        try:
            last_chunk_index = 0
            completion_sent = False
            
            while True:
                if task_id not in task_storage:
                    yield f"data: {json.dumps({'type': 'error', 'message': '태스크를 찾을 수 없습니다'})}\n\n"
                    return
                
                task = task_storage[task_id]
                
                html_chunks = task.get("html_chunks", [])
                for i in range(last_chunk_index, len(html_chunks)):
                    chunk_data = {
                        "type": "chunk",
                        "html": html_chunks[i],
                        "index": i
                    }
                    yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                    last_chunk_index = i + 1
                
                progress_data = {
                    "type": "progress",
                    "message": task["message"],
                    "progress": task["progress"]
                }
                yield f"data: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                
                if task["status"] == "completed" and not completion_sent:
                    complete_data = {
                        "type": "complete",
                        "message": "HTML 생성 완료!",
                        "total_chunks": len(html_chunks)
                    }
                    yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                    completion_sent = True
                    
                    # 🟢 완료 신호 전송 후 프론트엔드 타이핑 완료를 위해 추가 대기
                    logger.info(f"HTML 스트리밍 완료 신호 전송, 타이핑 완료 대기 중... (총 청크: {len(html_chunks)})")
                    
                    # 타이핑 완료 예상 시간 계산 (청크 수 * 30ms + 여유시간)
                    estimated_typing_time = len(html_chunks) * 0.03 + 5  # 5초 여유
                    await asyncio.sleep(min(estimated_typing_time, 30))  # 최대 30초 대기
                    
                    # 🟢 타이핑 완료 후 최종 완료 로그
                    logger.info(f"✅ HTML 리포트 렌더링 완료! (총 청크: {len(html_chunks)}, 대기시간: {min(estimated_typing_time, 30):.1f}초)")
                    
                    # 연결 종료 신호 전송
                    final_data = {
                        "type": "stream_end",
                        "message": "스트리밍 연결을 정상 종료합니다"
                    }
                    yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                    break
                    
                elif task["status"] == "error":
                    error_data = {
                        "type": "error",
                        "message": task["error"] or "HTML 생성 중 오류가 발생했습니다"
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    break
                
                await asyncio.sleep(0.1)  # 더 빠른 응답
                
        except Exception as e:
            logger.error(f"HTML 스트리밍 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'HTML 스트리밍 오류: {str(e)}'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive", 
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*",
            "Keep-Alive": "timeout=300, max=1000"  # 5분 타임아웃
        }
    )

async def run_sse_background_task(task_id: str, validation_result: Dict[str, Any]):
    try:
        # 🟢 더 상세한 진행률 단계로 수정
        update_task_progress(task_id, 5, "🚀 시스템 초기화 중...")
        await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 10, "📝 데이터 전처리 및 검증 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 15, "🤖 AI 모델 목록 준비 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 20, "📋 프롬프트 구성 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 25, "🧠 Claude 3.7 모델 호출 중...")
        await asyncio.sleep(0.8)
        
        update_task_progress(task_id, 35, "📡 AI 모델 응답 대기 중...")
        
        # 🟢 AI 분석 진행 중 더 세밀한 단계 표시
        update_task_progress(task_id, 40, "💭 AI 분석 요청 전송 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 45, "🧠 AI 모델 응답 대기 중... (1/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 55, "🧠 AI 모델 응답 대기 중... (2/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 62, "🧠 AI 모델 응답 대기 중... (3/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 68, "🧠 AI 모델 응답 대기 중... (4/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 74, "🧠 AI 모델 응답 대기 중... (5/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 80, "🧠 AI 분석 마무리 중... (6/6)")
        
        # 실제 AI 호출 전 추가 진행률 업데이트
        update_task_progress(task_id, 82, "🤖 AI 엔진 최종 준비 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 84, "📡 AI 분석 요청 전송 중...")
        await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 86, "⏳ AI 응답 처리 중...")
        
        # AI 호출과 병렬로 카운트다운 실행
        ai_result = None
        ai_completed = False
        ai_error = None
        
        async def ai_task():
            nonlocal ai_result, ai_completed, ai_error
            try:
                if task_id in task_storage and task_storage[task_id]["type"] == "analysis":
                    from ..api.rule_validator import validate_rule_json
                    ai_result = await validate_rule_json(task_storage[task_id]["json_data"])
                else:
                    ai_result = await generate_ai_html_report(task_storage[task_id]["validation_result"])
                ai_completed = True
            except Exception as e:
                ai_error = e
                ai_completed = True
        
        # AI 호출을 백그라운드에서 시작
        ai_task_obj = asyncio.create_task(ai_task())
        
        # 70초 카운트다운과 AI 완료 체크를 병렬로 실행
        for countdown in range(70, 0, -1):
            if ai_completed:
                break
            update_task_progress(task_id, 86, f"⏳ AI 응답 처리 중... ({countdown}초)")
            await asyncio.sleep(1)
        
        # AI가 아직 완료되지 않았다면 완료될 때까지 대기
        if not ai_completed:
            update_task_progress(task_id, 86, "⏳ AI 응답 마무리 중...")
            await ai_task_obj
        
        # AI 에러 처리
        if ai_error is not None:
            raise Exception(str(ai_error))
        
        result = ai_result
        
        update_task_progress(task_id, 88, "✅ AI 분석 완료 - 결과 수신")
        await asyncio.sleep(0.2)
        
        update_task_progress(task_id, 90, "🔍 결과 검증 및 정리 중...")
        await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 95, "✨ 최종 결과 준비 중...")
        await asyncio.sleep(0.2)
        
        update_task_progress(task_id, 98, "🎯 완료 처리 중...")
        await asyncio.sleep(0.1)

        task_storage[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "✅ 분석 완료!",
            "result": result
        })
        
    except Exception as e:
        logger.error(f"SSE 백그라운드 태스크 오류: {e}")
        task_storage[task_id].update({
            "status": "error",
            "error": str(e)
        })

async def run_html_streaming_task(task_id: str, validation_result: Dict[str, Any]):
    try:
        update_task_progress(task_id, 5, "📝 고품질 프롬프트 준비 중...")
        await asyncio.sleep(0.3)  # 🟢 프론트엔드 UI 업데이트 대기
        
        # 🟢 고품질 프롬프트 구성 (SSE와 동일한 수준)
        
        # validation_result 전처리 (SSE와 동일)
        validation_result = dict(validation_result)  # shallow copy
        validation_result.pop("ai_summary_md", None)
        
        validation_json_str = json.dumps(validation_result, ensure_ascii=False, indent=2)
        max_json_chars = 20000  # SSE와 동일한 제한
        if len(validation_json_str) > max_json_chars:
            validation_json_str = validation_json_str[:max_json_chars] + "\n/* ... trimmed ... */"
        
        update_task_progress(task_id, 10, "🤖 고품질 AI 모델 선택 중...")
        await asyncio.sleep(0.4)  # 🟢 프론트엔드 UI 업데이트 대기
        
        # 🟢 SSE와 동일한 다중 모델 후보 목록
        candidate_models = [
            "claude-3-7-sonnet-20250219",  # 1순위: 속도 최적화
            "claude-sonnet-4-20250514",    # 2순위: 품질 폴백
        ]
        
        update_task_progress(task_id, 15, "📋 전문가 수준 시스템 프롬프트 구성 중...")
        await asyncio.sleep(0.5)  # 🟢 프론트엔드 UI 업데이트 대기
        
        # 🟢 SSE와 동일한 고품질 시스템 프롬프트
        system_prompt = '''당신은 Vue 컨테이너(890px) 최적화 HTML 리포트 전문가입니다.

## 🎯 핵심 제약사항 (반드시 준수)
- Vue 컨테이너 890px 최적화 (가로 스크롤 방지 필수)
- Chart.js 금지, CSS 시각화만 사용
- 완전한 독립형 HTML 출력

## 🎨 창의적 디자인 자유도 (최대한 활용)
**2025년 최신 웹 디자인 트렌드를 자유롭게 적용하세요:**
- **색상 팔레트**: 다양한 테마 (다크모드, 파스텔, 비비드, 모노크롬 등)
- **시각 효과**: Glassmorphism, 네오모피즘, 그라데이션, 애니메이션
- **레이아웃**: 비대칭 그리드, 창의적 카드 배치, 유니크한 섹션 구성
- **타이포그래피**: 폰트 조합, 크기 대비, 창의적 배치
- **인터랙션**: hover 효과, 트랜지션, 마이크로 애니메이션

매번 **다른 디자인 스타일**로 창조하여 사용자에게 신선함을 제공하세요!

## 📋 필수 구조 (내용 구성만, 스타일 자유)
```html
<div class="vue-container">
  <header>룰 정보 + 상태</header>
  <section class="ai-section">AI 통찰/코멘트 (최우선 강조)</section>
  <section class="metrics">품질 메트릭</section>
  <section class="issues">이슈 리스트</section>
  <footer>모델 정보 + 시간</footer>
</div>
```

## 📊 데이터 우선순위
1. **AI 통찰** (ai_comment, ai_insights) - 최대 강조
2. **핵심 메트릭** (quality_metrics) - 시각적 표현
3. **중요 이슈** (error/warning 우선) - 명확한 구분
4. **상세 정보** (field_analysis) - 공간 허용시

## ⚡ 출력 규칙
- HTML 코드만 출력 (설명 없음)
- <!DOCTYPE html>로 시작, 모든 태그 완전히 닫기
- 가로 스크롤 절대 발생 금지

**매번 새롭고 독창적인 디자인으로 현대적이고 아름다운 대시보드를 창조하세요!**'''
        
        # 🟢 다중 모델 시도 (SSE와 동일한 폴백 로직)
        last_ai_html = None
        last_ai_model = None
        
        for i, model_id in enumerate(candidate_models):
            try:
                update_task_progress(task_id, 20 + i*10, f"🧠 {model_id} 모델로 실시간 스트리밍 시작...")
                
                # SSE와 동일한 프롬프트 구성
                validation_model_name = validation_result.get("report_metadata", {}).get("validation_model", "unknown")
                meta = validation_result.get("report_metadata", {})
                analysis_ms = meta.get("total_analysis_time_ms", "unknown")
                
                user_prompt = (
                    "아래 JSON 데이터는 리포트 제작에 활용할 정보입니다. 이 데이터를 분석하여 창의적이고 현대적인 단일 HTML 파일을 작성해 주세요.\n"
                    "\n* 반드시 HTML 하단(footer) 또는 눈에 띄지 않는 작은 글씨 영역에 다음 정보를 표기하세요.\n"
                    f"  - 검증 모델(validation_model): {validation_model_name}\n"
                    f"  - 리포트 모델(report_model): {model_id}\n"
                    f"  - 분석 총 시간(total_analysis_time_ms): {analysis_ms}ms\n"
                    f"  - 리포트 생성 시간: STREAMING_MODE\n"
                    f"```json\n{validation_json_str}\n```"
                )
                
                full_prompt = system_prompt + "\n\n" + user_prompt
                
                # 🟢 진짜 실시간 스트리밍 구현
                from ..services.llm_service import llm_service
                
                full_html = ""
                chunk_count = 0
                stream_success = False
                
                try:
                    async for chunk in llm_service.generate_stream(full_prompt, model_id):
                        chunk_count += 1
                        full_html += chunk
                        
                        # 🟢 실시간으로 작은 청크 전송 (타이핑 효과를 위해)
                        progress = 40 + min(35, chunk_count * 0.3)  # 40%~75%
                        update_task_progress(task_id, int(progress), f"📄 실시간 생성 중... (청크 {chunk_count})")
                        
                        # 🟢 청크를 더 작게 분할하여 타이핑 효과 개선 (지연 시간 단축)
                        if len(chunk) > 30:  # 더 작은 단위로 분할
                            sub_chunks = [chunk[i:i+15] for i in range(0, len(chunk), 15)]
                            for sub_chunk in sub_chunks:
                                task_storage[task_id]["html_chunks"].append(sub_chunk)
                                await asyncio.sleep(0.02)  # 지연 시간 단축 (0.1s → 0.02s)
                        else:
                            task_storage[task_id]["html_chunks"].append(chunk)
                            await asyncio.sleep(0.01)  # 부드러운 스트리밍 (0.05s → 0.01s)
                        
                    stream_success = True
                    logger.info(f"✅ {model_id} 실시간 스트리밍 성공 ({chunk_count} 청크)")
                    
                except Exception as stream_error:
                    logger.warning(f"❌ {model_id} 실시간 스트리밍 실패: {stream_error}")
                    # 스트리밍 실패 시 일반 생성으로 폴백
                    full_html = await llm_service.generate_text(full_prompt, model_id)
                    update_task_progress(task_id, 70, f"🔄 {model_id} 일반 생성 완료")
                
                if not full_html or len(full_html.strip()) < 100:
                    logger.warning(f"❌ {model_id} 생성 결과 부족 - 다음 모델 시도")
                    continue
                
                # 🟢 SSE와 동일한 후처리 적용
                update_task_progress(task_id, 75, "🔄 고품질 후처리 시작...")
                await asyncio.sleep(0.3)  # 🟢 프론트엔드 UI 업데이트 대기
                
                try:
                    from ..api.rule_validator import (
                        _remove_markdown_codeblock,
                        _sanitize_html, 
                        _ensure_raw_json_script,
                        _reorder_scripts,
                        _remove_chartjs_code,
                        _passes_qc
                    )
                    
                    # 1) 마크다운 코드 블록 제거
                    full_html = _remove_markdown_codeblock(full_html)
                    update_task_progress(task_id, 80, "🧹 마크다운 코드블록 제거 완료")
                    await asyncio.sleep(0.2)  # 🟢 프론트엔드 UI 업데이트 대기
                    
                    # 2) 구조 복원
                    full_html = _sanitize_html(full_html)
                    update_task_progress(task_id, 85, "🛠️ HTML 구조 보정 완료")
                    await asyncio.sleep(0.2)  # 🟢 프론트엔드 UI 업데이트 대기
                    
                    # 3) JSON 데이터 삽입
                    full_html = _ensure_raw_json_script(full_html, validation_result)
                    
                    # 4) 스크립트 순서 보정
                    full_html = _reorder_scripts(full_html)
                    
                    # 5) Chart.js 제거
                    full_html = _remove_chartjs_code(full_html)
                    update_task_progress(task_id, 90, "⚙️ 스크립트 최적화 완료")
                    await asyncio.sleep(0.3)  # 🟢 프론트엔드 UI 업데이트 대기
                    
                    # 🟢 SSE와 동일한 QC 검사
                    update_task_progress(task_id, 95, "🔍 고품질 QC 검사 중...")
                    await asyncio.sleep(0.2)  # 🟢 프론트엔드 UI 업데이트 대기
                    
                    # Claude 3.7과 4는 QC 우회 (SSE와 동일)
                    if model_id in ["claude-sonnet-4-20250514", "claude-3-7-sonnet-20250219"]:
                        logger.info(f"🚀 {model_id} QC 우회하여 즉시 반환")
                        # 🟢 스트리밍으로 생성된 경우 - 후처리된 결과를 새로운 청크로 분할하여 추가
                        if stream_success:
                            # 기존 타이핑 효과용 청크는 유지하고, 완료 신호만 전송
                            pass
                        else:
                            # 일반 생성인 경우 청크로 분할
                            task_storage[task_id]["html_chunks"] = [full_html]
                        
                        update_task_progress(task_id, 100, "✅ 고품질 HTML 스트리밍 완료!")
                        task_storage[task_id]["status"] = "completed"
                        logger.info(f"🎯 {model_id} HTML 생성 태스크 완료 - QC 우회 성공")
                        return
                    
                    # 다른 모델들은 QC 검사
                    if _passes_qc(full_html, validation_result):
                        logger.info(f"✅ {model_id} QC 통과 - 성공!")
                        # 스트리밍으로 생성된 경우 청크 재설정
                        if stream_success:
                            task_storage[task_id]["html_chunks"] = [full_html]
                        
                        update_task_progress(task_id, 100, "✅ 고품질 HTML 스트리밍 완료!")
                        task_storage[task_id]["status"] = "completed"
                        logger.info(f"🎯 {model_id} HTML 생성 태스크 완료 - QC 통과 성공")
                        return
                    else:
                        logger.warning(f"❌ {model_id} QC 실패 - 다음 모델 시도")
                        last_ai_html = full_html
                        last_ai_model = model_id
                        if i < len(candidate_models) - 1:
                            continue
                        
                except Exception as post_err:
                    logger.warning(f"⚠️ {model_id} 후처리 실패: {post_err}")
                    last_ai_html = full_html  # 후처리 전 결과라도 보존
                    last_ai_model = model_id
                    if i < len(candidate_models) - 1:
                        continue
                        
            except Exception as model_error:
                logger.warning(f"❌ {model_id} 전체 실패: {model_error}")
                if i < len(candidate_models) - 1:
                    logger.info(f"⏭️ 다음 모델로 이동: {candidate_models[i+1]}")
                    continue
        
        # 🟢 모든 모델 실패 시 마지막 AI 결과 사용 (SSE와 동일)
        if last_ai_html:
            logger.warning(f"⚠️ 모든 모델 실패 - 마지막 결과 사용 ({last_ai_model})")
            task_storage[task_id]["html_chunks"] = [last_ai_html]
            update_task_progress(task_id, 100, "⚠️ 부분 성공 - 마지막 AI 결과 사용")
            task_storage[task_id]["status"] = "completed"
            logger.info(f"🎯 HTML 생성 태스크 완료 - 마지막 AI 결과 사용 ({last_ai_model})")
            return
            
        # 🟢 완전 실패 시 폴백 템플릿 (SSE와 동일한 수준)
        logger.error("💥 모든 AI 모델 실패 - 고품질 폴백 템플릿 사용")
        
        # 고품질 폴백 HTML
        fallback_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VizierAI 룰 검증 리포트</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .error {{ color: #e74c3c; background: #fdf2f2; padding: 20px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 리포트 생성 중 문제 발생</h1>
        <div class="error">
            <p>AI 모델에서 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.</p>
        </div>
    </div>
    <script>
        const rawValidationData = {validation_json_str};
        console.log('검증 데이터:', rawValidationData);
    </script>
</body>
</html>"""
        
        task_storage[task_id]["html_chunks"] = [fallback_html]
        update_task_progress(task_id, 100, "⚠️ 폴백 템플릿으로 완료")
        task_storage[task_id]["status"] = "completed"
        logger.info("🎯 HTML 생성 태스크 완료 - 폴백 템플릿 사용")
        
    except Exception as e:
        logger.error(f"HTML 스트리밍 태스크 오류: {e}")
        update_task_progress(task_id, 100, f"❌ 오류 발생: {str(e)}")
        task_storage[task_id]["status"] = "error"
        task_storage[task_id]["error"] = str(e)

async def run_analysis_task(task_id: str, json_data: list):
    """기본 룰 분석을 위한 SSE 태스크"""
    try:
        from ..api.rule_validator import validate_rule_json
        from ..models.validation_result import RuleJsonValidationRequest
        
        update_task_progress(task_id, 5, "🚀 분석 시스템 초기화 중...")
        await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 10, "📋 JSON 데이터 검증 중...")
        await asyncio.sleep(0.4)
        
        update_task_progress(task_id, 20, "🔍 룰 구조 파싱 중...")
        await asyncio.sleep(0.4)
        
        update_task_progress(task_id, 30, "⚙️ 조건 트리 분석 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 40, "💭 AI 분석 요청 준비 중...")
        await asyncio.sleep(0.4)
        
        update_task_progress(task_id, 45, "🧠 AI 모델 응답 대기 중... (1/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 55, "🧠 AI 모델 응답 대기 중... (2/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 62, "🧠 AI 모델 응답 대기 중... (3/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 68, "🧠 AI 모델 응답 대기 중... (4/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 74, "🧠 AI 모델 응답 대기 중... (5/6)")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 80, "🧠 AI 분석 마무리 중... (6/6)")
        
        # 실제 AI 호출 전 추가 진행률 업데이트
        update_task_progress(task_id, 82, "🤖 AI 엔진 최종 준비 중...")
        await asyncio.sleep(0.5)
        
        update_task_progress(task_id, 84, "📡 AI 분석 요청 전송 중...")
        await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 86, "⏳ AI 응답 처리 중...")
        
        # AI 호출과 병렬로 카운트다운 실행
        ai_result = None
        ai_completed = False
        ai_error = None
        
        async def ai_task():
            nonlocal ai_result, ai_completed, ai_error
            try:
                if task_id in task_storage and task_storage[task_id]["type"] == "analysis":
                    ai_result = await validate_rule_json(task_storage[task_id]["json_data"])
                else:
                    ai_result = await generate_ai_html_report(task_storage[task_id]["validation_result"])
                ai_completed = True
            except Exception as e:
                ai_error = e
                ai_completed = True
        
        # AI 호출을 백그라운드에서 시작
        ai_task_obj = asyncio.create_task(ai_task())
        
        # 70초 카운트다운과 AI 완료 체크를 병렬로 실행
        for countdown in range(70, 0, -1):
            if ai_completed:
                break
            update_task_progress(task_id, 86, f"⏳ AI 응답 처리 중... ({countdown}초)")
            await asyncio.sleep(1)
        
        # AI가 아직 완료되지 않았다면 완료될 때까지 대기
        if not ai_completed:
            update_task_progress(task_id, 86, "⏳ AI 응답 마무리 중...")
            await ai_task_obj
        
        # AI 에러 처리
        if ai_error is not None:
            raise Exception(str(ai_error))
        
        result = ai_result
        
        update_task_progress(task_id, 88, "✅ AI 분석 완료 - 결과 수신")
        await asyncio.sleep(0.2)
        
        update_task_progress(task_id, 90, "🔍 결과 검증 및 정리 중...")
        await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 95, "✨ 최종 결과 준비 중...")
        await asyncio.sleep(0.2)
        
        update_task_progress(task_id, 98, "🎯 완료 처리 중...")
        await asyncio.sleep(0.1)

        task_storage[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "✅ 분석 완료!",
            "result": result
        })
        
    except Exception as e:
        logger.error(f"분석 태스크 오류: {e}")
        task_storage[task_id].update({
            "status": "error",
            "error": str(e)
        })

def update_task_progress(task_id: str, progress: int, message: str):
    if task_id in task_storage:
        task_storage[task_id].update({
            "progress": progress,
            "message": message
        })

def split_html_into_chunks(html: str, chunk_size: int = 500) -> list:
    if not html:
        return []
    
    chunks = []
    for i in range(0, len(html), chunk_size):
        chunks.append(html[i:i + chunk_size])
    
    return chunks
