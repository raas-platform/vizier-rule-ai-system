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
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@router.get("/stream/html/{task_id}")
async def stream_html_chunks(task_id: str):
    async def event_generator():
        try:
            last_chunk_index = 0
            
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
                
                if task["status"] == "completed":
                    complete_data = {
                        "type": "complete",
                        "message": "HTML 생성 완료!"
                    }
                    yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                    break
                elif task["status"] == "error":
                    error_data = {
                        "type": "error",
                        "message": task["error"] or "HTML 생성 중 오류가 발생했습니다"
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                    break
                
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"HTML 스트리밍 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'HTML 스트리밍 오류: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive", 
            "Access-Control-Allow-Origin": "*"
        }
    )

async def run_sse_background_task(task_id: str, validation_result: Dict[str, Any]):
    try:
        update_task_progress(task_id, 10, "🤖 AI 모델 준비 중...")
        await asyncio.sleep(1)
        
        update_task_progress(task_id, 30, "🧠 Claude 모델로 리포트 생성 중...")
        await asyncio.sleep(2)
        
        update_task_progress(task_id, 60, "🔄 품질 검사 및 후처리 중...")
        
        result = await generate_ai_html_report(validation_result)
        
        update_task_progress(task_id, 90, "✨ 최종 처리 중...")
        await asyncio.sleep(1)
        
        task_storage[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "✅ 리포트 생성 완료!",
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
        update_task_progress(task_id, 10, "📝 프롬프트 준비 중...")
        
        validation_json_str = json.dumps(validation_result, ensure_ascii=False, indent=2)
        
        prompt = f"""이 JSON 데이터를 분석하여 현대적이고 아름다운 HTML 리포트를 생성해주세요.

## 요구사항:
- 완전한 독립형 HTML (CSS, JS 인라인)
- Vue 컨테이너 890px 최적화
- 2025년 최신 웹 디자인 트렌드 적용
- 차트나 외부 라이브러리 금지

## 데이터:
```json
{validation_json_str}
```

HTML 코드만 응답해주세요."""

        update_task_progress(task_id, 30, "🤖 AI 모델 호출 중...")
        
        model = "claude-3-sonnet-20240229"
        full_html = await llm_service.generate_text(prompt, model)
        
        chunks = split_html_into_chunks(full_html)
        
        for i, chunk in enumerate(chunks):
            progress = 40 + (i / len(chunks)) * 50
            update_task_progress(task_id, int(progress), f"📄 HTML 생성 중... ({i+1}/{len(chunks)})")
            
            task_storage[task_id]["html_chunks"].append(chunk)
            await asyncio.sleep(0.3)
        
        update_task_progress(task_id, 100, "✅ HTML 생성 완료!")
        task_storage[task_id]["status"] = "completed"
        
    except Exception as e:
        logger.error(f"HTML 스트리밍 태스크 오류: {e}")
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
