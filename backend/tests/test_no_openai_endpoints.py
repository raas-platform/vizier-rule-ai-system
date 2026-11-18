"""GPT(OpenAI) 차단: 키가 있어도 OpenAI 제공업체가 없고, gpt 모델 요청은 API에서 거부된다.

대상: /api/llm/generate, /api/llm/generate/stream, /api/prompts/execute
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.api import llm_endpoints, prompt_endpoints
from backend.app.main import app
from backend.app.services import llm_service as llm_module
from backend.app.services import prompt_service as prompt_module

GPT_IDS = ["gpt-6.1-sol", "gpt-4o", "openai/gpt-5"]


class RecordingProvider:
    """호출되면 기록만 남기는 가짜 제공업체 (실제 API 호출 없음)."""

    def __init__(self):
        self.calls = []

    async def generate_text(self, prompt, config, fast=False, schema=None):
        self.calls.append(config.model_name)
        return "ok"

    async def generate_stream(self, prompt, config):
        self.calls.append(config.model_name)
        yield "ok"


@pytest.fixture
def svc(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-be-used")
    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(llm_module.settings, "google_api_key", None)
    service = llm_module.LLMService()
    assert "openai" not in service.providers
    rec = RecordingProvider()
    service.providers = {name: rec for name in service.providers}
    monkeypatch.setattr(llm_endpoints, "llm_service", service)
    monkeypatch.setattr(prompt_module, "llm_service", service)
    app.dependency_overrides[prompt_endpoints.get_db] = lambda: None
    yield service, rec
    app.dependency_overrides.pop(prompt_endpoints.get_db, None)


client = TestClient(app)


@pytest.mark.parametrize("model_id", GPT_IDS)
def test_generate_rejects_gpt(svc, model_id):
    _, rec = svc
    r = client.post("/api/llm/generate", json={"prompt": "hi", "model_id": model_id})
    assert r.status_code == 400 and "사용할 수 없습니다" in r.text
    r = client.post("/api/llm/generate/stream", json={"prompt": "hi", "model_id": model_id})
    assert r.status_code == 400
    assert rec.calls == []


@pytest.mark.parametrize("model_id", GPT_IDS)
def test_prompt_execute_rejects_gpt(svc, model_id):
    _, rec = svc
    r = client.post("/api/prompts/execute",
                    json={"prompt_id": 0, "model_id": model_id, "custom_content": "hi"})
    assert r.status_code in (400, 404) and "사용할 수 없습니다" in r.text
    assert rec.calls == []


def test_models_list_has_no_gpt(svc):
    r = client.get("/api/llm/models")
    assert r.status_code == 200
    ids = [m.get("model_id") or m.get("id") or "" for m in r.json()]
    assert ids and not [i for i in ids if "gpt" in i.lower() or "openai" in i.lower()]


def test_claude_still_works(svc):
    _, rec = svc
    r = client.post("/api/llm/generate", json={"prompt": "hi", "model_id": "claude-sonnet-5-5"})
    assert r.status_code == 200, r.text
    assert rec.calls == ["claude-sonnet-5-5"]
