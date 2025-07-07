"""
룰 분석기 패키지 - PyPI 모듈 기반 리팩토링

이 패키지는 PyPI에 배포된 RaaS 모듈들과 로컬 AI 기능을 조합하여 제공합니다:

PyPI 모듈 (raas_rule_analyzer):
- RuleParser: 룰 파싱 및 변환
- ConditionAnalyzer: 조건 분석 및 파싱
- IssueDetector: 이슈 검출 및 검증
- MetricsGenerator: 성능 및 품질 메트릭 생성
- ReportGenerator: 보고서 및 요약 생성

로컬 모듈:
- AIEnhancer: AI 기반 개선 및 통찰 (LLM 통합)
"""

# PyPI 모듈에서 import
from raas_rule_analyzer.analyzers import (
    RuleParser,
    ConditionAnalyzer,
    IssueDetector,
    MetricsGenerator,
    ReportGenerator,
    RuleAnalyzer,
)

# 로컬 모듈에서 import
from .ai_enhancer import AIEnhancer

__all__ = [
    # PyPI 모듈 (raas_rule_analyzer)
    "RuleParser",
    "ConditionAnalyzer",
    "IssueDetector",
    "MetricsGenerator",
    "ReportGenerator",
    "RuleAnalyzer",
    
    # 로컬 모듈
    "AIEnhancer",
]

# 버전 정보
__version__ = "2.0.0-pypi"
__description__ = "PyPI 모듈 기반 룰 분석기 패키지"
