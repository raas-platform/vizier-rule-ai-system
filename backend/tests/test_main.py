"""
기본 API 테스트
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """헬스체크 테스트"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"

def test_docs():
    """API 문서 테스트"""
    response = client.get("/docs")
    assert response.status_code == 200

def test_openapi():
    """OpenAPI 스키마 테스트"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data

@pytest.mark.asyncio
async def test_rule_validation():
    """룰 검증 API 기본 테스트"""
    test_rule = {
        "name": "테스트 룰",
        "conditions": [
            {
                "field": "user_age",
                "operator": ">=",
                "value": 18
            }
        ],
        "actions": ["allow_access"]
    }
    
    response = client.post("/rules/validate-json", json=test_rule)
    # 200이거나 422(유효성 검사 실패) 둘 다 허용
    assert response.status_code in [200, 422]

def test_invalid_endpoint():
    """존재하지 않는 엔드포인트 테스트"""
    response = client.get("/invalid-endpoint")
    assert response.status_code == 404 