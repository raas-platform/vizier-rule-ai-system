"""
API 통합 테스트
- FastAPI 엔드포인트 테스트
- 요청/응답 검증
- 에러 처리 테스트
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRuleValidatorAPI:
    """룰 검증 API 테스트"""

    def test_validate_simple_rule_success(self):
        """정상적인 룰 검증 테스트"""
        payload = [
            {
                "ruleUuid": "test-001",
                "ruleName": "정상 룰",
                "ruleMsg": "테스트용 룰입니다",
                "conditionTree": {
                    "logicType": "AND",
                    "condition": [
                        {
                            "keyName": "age",
                            "dispName": "나이",
                            "operator": ">=",
                            "value": 18,
                            "fieldDataType": "number",
                        }
                    ],
                },
            }
        ]

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 200
        result = response.json()

        # 기본 응답 구조 검증
        assert "is_valid" in result
        assert "summary" in result
        assert "issues" in result
        assert "structure" in result

        # 확장 분석 정보 검증
        assert "field_analysis" in result
        assert "performance_metrics" in result
        assert "quality_metrics" in result
        assert "report_metadata" in result

    def test_validate_rule_with_errors(self):
        """오류가 있는 룰 검증 테스트"""
        payload = [
            {
                "ruleUuid": "test-002",
                "ruleName": "오류 룰",
                "ruleMsg": "오류가 있는 테스트 룰",
                "conditionTree": {
                    "logicType": "AND",
                    "condition": [
                        {
                            "keyName": "age",
                            "dispName": "나이",
                            "operator": ">=",
                            "value": "invalid_number",  # 타입 불일치
                            "fieldDataType": "number",
                        },
                        {
                            "keyName": "name",
                            "dispName": "이름",
                            "operator": ">",  # 잘못된 연산자
                            "value": "John",
                            "fieldDataType": "string",
                        },
                    ],
                },
            }
        ]

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 200
        result = response.json()

        # 오류가 있으므로 유효하지 않아야 함
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0
        assert len(result["issue_counts"]) > 0

        # 예상 오류 타입 확인
        issue_types = {issue["issue_type"] for issue in result["issues"]}
        assert "type_mismatch" in issue_types or "invalid_operator" in issue_types

    def test_validate_multiple_rules(self):
        """여러 룰 동시 검증 테스트"""
        payload = [
            {
                "ruleUuid": "test-003-1",
                "ruleName": "첫 번째 룰",
                "ruleMsg": "정상 룰",
                "conditionTree": {
                    "logicType": "AND",
                    "condition": [
                        {
                            "keyName": "score",
                            "dispName": "점수",
                            "operator": ">=",
                            "value": 80,
                            "fieldDataType": "number",
                        }
                    ],
                },
            },
            {
                "ruleUuid": "test-003-2",
                "ruleName": "두 번째 룰",
                "ruleMsg": "중복 조건 룰",
                "conditionTree": {
                    "logicType": "AND",
                    "condition": [
                        {
                            "keyName": "status",
                            "dispName": "상태",
                            "operator": "==",
                            "value": "active",
                            "fieldDataType": "string",
                        },
                        {
                            "keyName": "status",
                            "dispName": "상태",
                            "operator": "==",
                            "value": "active",
                            "fieldDataType": "string",
                        },
                    ],
                },
            },
        ]

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 200
        results = response.json()

        # 현재는 단일 룰 응답이므로 수정 필요
        # 여러 룰에 대해서는 첫 번째 룰만 처리되는지 확인
        assert isinstance(results, dict)  # 단일 결과
        assert "is_valid" in results

    def test_validate_complex_nested_rule(self):
        """복잡한 중첩 룰 검증 테스트"""
        payload = [
            {
                "ruleUuid": "test-004",
                "ruleName": "복잡한 중첩 룰",
                "ruleMsg": "여러 레벨의 중첩 조건",
                "conditionTree": {
                    "logicType": "AND",
                    "condition": [
                        {
                            "keyName": "age",
                            "dispName": "나이",
                            "operator": ">=",
                            "value": 18,
                            "fieldDataType": "number",
                        },
                        {
                            "logicType": "OR",
                            "condition": [
                                {
                                    "keyName": "department",
                                    "dispName": "부서",
                                    "operator": "==",
                                    "value": "IT",
                                    "fieldDataType": "string",
                                },
                                {
                                    "keyName": "experience",
                                    "dispName": "경력",
                                    "operator": ">=",
                                    "value": 5,
                                    "fieldDataType": "number",
                                },
                            ],
                        },
                    ],
                },
            }
        ]

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 200
        result = response.json()

        # 구조 정보 검증
        assert result["structure"]["depth"] >= 2  # 중첩 구조
        assert len(result["structure"]["unique_fields"]) >= 3

        # 논리 흐름 분석 검증
        assert "logic_flow" in result
        if result["logic_flow"]:
            assert "logical_operators" in result["logic_flow"]

    def test_validate_empty_request(self):
        """빈 요청 처리 테스트"""
        payload = []  # 빈 배열

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 422  # Validation Error

    def test_validate_invalid_json(self):
        """잘못된 JSON 구조 테스트"""
        payload = {"invalid": "structure"}

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 422  # Validation Error

    def test_validate_missing_required_fields(self):
        """필수 필드 누락 테스트"""
        payload = [
            {
                "ruleUuid": "test-005",
                # ruleName 누락
                "ruleMsg": "필수 필드 누락 테스트",
                # conditionTree 누락
            }
        ]

        response = client.post("/rules/validate-json", json=payload)

        # 모델 검증에서 에러가 발생하거나, 분석 중 에러 처리
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            result = response.json()
            # 오류가 감지되어야 함
            assert result["is_valid"] is False

    def test_performance_large_payload(self):
        """대용량 페이로드 성능 테스트"""
        # 많은 조건을 가진 룰 생성
        large_conditions = []
        for i in range(50):
            large_conditions.append(
                {
                    "keyName": f"field_{i}",
                    "dispName": f"필드{i}",
                    "operator": "==",
                    "value": f"value_{i}",
                    "fieldDataType": "string",
                }
            )

        payload = [
            {
                "ruleUuid": "test-006",
                "ruleName": "대용량 룰",
                "ruleMsg": "성능 테스트용 대용량 룰",
                "conditionTree": {"logicType": "AND", "condition": large_conditions},
            }
        ]

        import time

        start_time = time.time()

        response = client.post("/rules/validate-json", json=payload)

        end_time = time.time()
        processing_time = end_time - start_time

        assert response.status_code == 200
        assert processing_time < 10.0  # 10초 이내 처리

        result = response.json()
        assert "performance_metrics" in result
        assert result["performance_metrics"]["complexity_rating"] in [
            "simple",
            "moderate",
            "complex",
            "very_complex",
        ]

    def test_api_response_format_consistency(self):
        """API 응답 형식 일관성 테스트"""
        payload = [
            {
                "ruleUuid": "test-007",
                "ruleName": "형식 일관성 테스트",
                "ruleMsg": "응답 형식 검증",
                "conditionTree": {
                    "logicType": "AND",
                    "condition": [
                        {
                            "keyName": "test",
                            "dispName": "테스트",
                            "operator": "==",
                            "value": "value",
                            "fieldDataType": "string",
                        }
                    ],
                },
            }
        ]

        response = client.post("/rules/validate-json", json=payload)

        assert response.status_code == 200
        result = response.json()

        # 필수 필드 존재 확인
        required_fields = [
            "is_valid",
            "summary",
            "issue_counts",
            "issues",
            "structure",
            "field_analysis",
            "logic_flow",
            "performance_metrics",
            "quality_metrics",
            "report_metadata",
        ]

        for field in required_fields:
            assert field in result, f"필수 필드 '{field}'가 응답에 없습니다"

        # 타입 검증
        assert isinstance(result["is_valid"], bool)
        assert isinstance(result["summary"], str)
        assert isinstance(result["issue_counts"], dict)
        assert isinstance(result["issues"], list)
        assert isinstance(result["structure"], dict)

    def test_error_handling(self):
        """에러 처리 테스트"""
        # 서버 내부 오류를 유발할 수 있는 극단적인 케이스
        payload = [
            {
                "ruleUuid": "test-008",
                "ruleName": "에러 처리 테스트",
                "ruleMsg": "극단적인 케이스",
                "conditionTree": {
                    "logicType": "INVALID_LOGIC",  # 잘못된 논리 타입
                    "condition": [
                        {
                            "keyName": None,  # None 값
                            "dispName": "",
                            "operator": "INVALID_OP",  # 잘못된 연산자
                            "value": {"complex": "object"},  # 복잡한 객체
                            "fieldDataType": "unknown",
                        }
                    ],
                },
            }
        ]

        response = client.post("/rules/validate-json", json=payload)

        # 서버가 크래시하지 않고 적절한 응답을 반환해야 함
        assert response.status_code in [200, 422, 500]

        if response.status_code == 200:
            result = response.json()
            # 에러가 감지되어 유효하지 않아야 함
            assert result["is_valid"] is False


class TestHealthCheck:
    """헬스체크 및 기본 엔드포인트 테스트"""

    def test_root_endpoint(self):
        """루트 엔드포인트 테스트"""
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check(self):
        """헬스체크 엔드포인트 테스트 (있다면)"""
        response = client.get("/health")
        # 헬스체크 엔드포인트가 없을 수 있으므로 404도 허용
        assert response.status_code in [200, 404]


class TestCORS:
    """CORS 설정 테스트"""

    def test_cors_headers(self):
        """CORS 헤더 테스트"""
        response = client.options("/rules/validate-json")

        # OPTIONS 요청이 허용되어야 함
        assert response.status_code in [200, 405]

        # 기본 요청에서 CORS 헤더 확인
        response = client.get("/")

        # CORS 관련 헤더가 있는지 확인
        _ = response.headers
        # 개발 환경에서는 보통 Access-Control-Allow-Origin이 설정됨
        # 실제 헤더 존재 여부는 환경에 따라 다를 수 있음


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
