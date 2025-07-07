"""
PromptBuilder 서비스

다양한 목적의 LLM 프롬프트를 동적으로 생성하는 메인 서비스입니다.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from .models import (
    PromptInput, PromptResult, PromptType, PromptMetadata,
    CustomizationOptions
)
from .exceptions import (
    PromptBuilderException, InvalidPromptTypeException,
    TemplateNotFoundException
)

logger = logging.getLogger(__name__)


class PromptBuilderService:
    """프롬프트 빌더 서비스"""
    
    def __init__(self):
        self.templates = self._load_templates()
        logger.info("PromptBuilderService initialized")
    
    def _load_templates(self) -> Dict[str, str]:
        """프롬프트 템플릿 로드"""
        return {
            # 기존 개발자 활동 관련 템플릿
            "daily_summary": """
🔍 {developer_name}님의 {date} 개발 활동 요약

📊 전체 통계:
- 커밋 수: {commit_count}개
- 변경 파일: {files_changed}개
- 추가된 라인: {lines_added}줄
- 삭제된 라인: {lines_deleted}줄

🚀 주요 작업 내용:
{main_activities}

📈 코드 품질:
- 평균 복잡도: {avg_complexity}
- 사용 언어: {languages_used}

⏰ 작업 패턴:
- 피크 시간: {peak_hours}
            """.strip(),
            
            "code_review": """
📋 {developer_name}님의 코드 리뷰 요약

🔍 변경사항 분석:
{code_changes}

✅ 개선사항:
{improvements}
            """.strip(),
            
            # 룰 검증 시스템 전용 템플릿들 (새로 추가)
            "rule_analysis": """
🔍 룰 분석 요청

**분석 대상 룰:**
```json
{rule_json}
```

**분석 요청 사항:**
{analysis_scope}

**상세 분석 지침:**
1. 룰 구조의 논리적 일관성 검토
2. 조건문의 정확성 및 완전성 평가
3. 성능 최적화 가능성 검토
4. 보안 및 안정성 측면 검토
5. 유지보수성 및 확장성 평가

**출력 형식:**
- 발견된 이슈들을 심각도별로 분류
- 각 이슈에 대한 구체적인 개선 방안 제시
- 전체적인 룰 품질 점수 (1-10점)
- 추가 권장사항

언어: {language}
상세도: {detail_level}
            """.strip(),
            
            "rule_validation": """
🔧 룰 검증 요청

**검증 대상:**
```json
{rule_json}
```

**검증 유형:** {validation_type}

**검증 기준:**
- 문법적 정확성 (Syntax Validation)
- 논리적 일관성 (Logic Validation)
- 성능 효율성 (Performance Validation)
- 보안 취약점 (Security Validation)

**검증 결과 요구사항:**
1. 각 검증 항목별 통과/실패 여부
2. 실패 항목에 대한 구체적인 오류 설명
3. 수정 방안 및 예시 코드
4. 검증 통과를 위한 체크리스트

**추가 컨텍스트:**
{context}

언어: {language}
            """.strip(),
            
            "html_report": """
📊 HTML 리포트 생성 요청

**리포트 데이터:**
{analysis_result}

**리포트 설정:**
- 제목: {report_title}
- 테마: {theme}
- 차트 포함: {include_charts}

**리포트 구성 요소:**
1. 요약 섹션 (Executive Summary)
2. 상세 분석 결과 (Detailed Analysis)
3. 이슈 목록 및 우선순위 (Issues & Priorities)
4. 개선 권장사항 (Recommendations)
5. 성능 메트릭 (Performance Metrics)
6. 시각화 차트 (Charts & Graphs)

**HTML 생성 지침:**
- 반응형 디자인 적용
- 모던하고 직관적인 UI
- 인터랙티브 요소 포함
- 프린트 친화적 스타일
- 접근성 고려 (WCAG 2.1 AA 준수)

**출력 형식:**
완전한 HTML 문서 (<!DOCTYPE html>부터 </html>까지)

언어: {language}
            """.strip(),
            
            "issue_detection": """
🚨 이슈 검출 요청

**검출 대상 룰:**
```json
{rule_data}
```

**검출 범위:** {detection_scope}
**심각도 필터:** {severity_filter}

**검출 카테고리:**
1. **문법 오류 (Syntax Issues)**
   - 잘못된 JSON 구조
   - 필수 필드 누락
   - 타입 불일치

2. **논리 오류 (Logic Issues)**
   - 모순된 조건문
   - 도달 불가능한 코드
   - 순환 참조

3. **성능 문제 (Performance Issues)**
   - 비효율적인 조건 순서
   - 중복 계산
   - 메모리 사용량 과다

4. **보안 취약점 (Security Issues)**
   - 입력 검증 부족
   - 권한 검사 누락
   - 데이터 노출 위험

**출력 형식:**
각 이슈별로 다음 정보 포함:
- 이슈 ID 및 제목
- 심각도 레벨 (Critical/High/Medium/Low)
- 위치 정보 (파일/라인)
- 상세 설명
- 수정 방안
- 예상 영향도

언어: {language}
            """.strip(),
            
            "rule_optimization": """
⚡ 룰 최적화 요청

**최적화 대상:**
```json
{rule_json}
```

**최적화 목표:**
- 실행 성능 향상
- 메모리 사용량 최소화
- 코드 가독성 개선
- 유지보수성 향상

**최적화 영역:**
1. **조건 순서 최적화**
   - 빈번한 조건을 앞쪽으로 배치
   - 계산 비용이 낮은 조건 우선 처리

2. **중복 제거**
   - 동일한 조건문 통합
   - 반복 계산 캐싱

3. **구조 개선**
   - 중첩 깊이 최소화
   - 명확한 변수명 사용

4. **성능 튜닝**
   - 인덱스 활용
   - 배치 처리 적용

**출력 형식:**
- 최적화 전/후 비교
- 성능 개선 예상치
- 구체적인 수정 코드
- 적용 시 주의사항

언어: {language}
            """.strip(),
            
            "performance_metrics": """
📈 성능 메트릭 분석 요청

**분석 대상:**
{performance_data}

**메트릭 카테고리:**
1. **실행 성능**
   - 평균 응답 시간
   - 처리량 (TPS)
   - 에러율

2. **리소스 사용량**
   - CPU 사용률
   - 메모리 사용량
   - 네트워크 I/O

3. **품질 지표**
   - 코드 복잡도
   - 테스트 커버리지
   - 기술 부채 점수

**분석 결과 요구사항:**
- 각 메트릭별 현재 상태
- 벤치마크 대비 성능
- 개선 우선순위
- 액션 플랜

언어: {language}
            """.strip()
        }
    
    async def build_prompt(self, input_data: PromptInput) -> PromptResult:
        """프롬프트 생성 메인 메서드"""
        try:
            template = self._select_template(input_data.prompt_type)
            context_data = self._build_context(input_data)
            rendered_prompt = self._render_template(template, context_data)
            optimized_prompt = self._optimize_token_usage(rendered_prompt)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(optimized_prompt),
                language="korean"
            )
            
            return PromptResult(
                prompt=optimized_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=input_data.prompt_type.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build prompt: {str(e)}")
    
    def build_daily_summary_prompt(self, aggregated_data: Dict[str, Any], 
                                  target_developer: str) -> PromptResult:
        """일일 요약용 프롬프트 생성 (동기 버전)"""
        try:
            template = self._select_template(PromptType.DAILY_SUMMARY)
            
            # 컨텍스트 구성
            dev_stats = aggregated_data.get("developer_stats", {})
            target_stats = None
            
            # 대상 개발자 찾기
            for dev_email, stats in dev_stats.items():
                if stats.get("developer") == target_developer:
                    target_stats = stats
                    break
            
            if not target_stats:
                raise PromptBuilderException(f"Developer '{target_developer}' not found in stats")
            
            context_data = {
                "developer_name": target_developer,
                "date": aggregated_data.get("date", "Unknown"),
                "commit_count": target_stats.get("commit_count", 0),
                "files_changed": target_stats.get("files_changed", 0),
                "lines_added": target_stats.get("lines_added", 0),
                "lines_deleted": target_stats.get("lines_deleted", 0),
                "main_activities": self._format_activities(target_stats.get("activities", [])),
                "avg_complexity": target_stats.get("avg_complexity", "N/A"),
                "languages_used": ", ".join(target_stats.get("languages", [])),
                "peak_hours": self._format_peak_hours(target_stats.get("peak_hours", []))
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language="korean"
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.DAILY_SUMMARY.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build daily summary prompt: {str(e)}")
    
    # 룰 검증 시스템 전용 메서드들 (새로 추가)
    def build_rule_analysis_prompt(self, rule_json: Dict[str, Any], 
                                  analysis_scope: str = "전체 분석",
                                  customization: Optional[CustomizationOptions] = None) -> PromptResult:
        """룰 분석용 프롬프트 생성"""
        try:
            template = self._select_template(PromptType.RULE_ANALYSIS)
            
            if customization is None:
                customization = CustomizationOptions()
            
            context_data = {
                "rule_json": json.dumps(rule_json, indent=2, ensure_ascii=False),
                "analysis_scope": analysis_scope,
                "language": customization.language,
                "detail_level": customization.detail_level
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language=customization.language
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.RULE_ANALYSIS.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build rule analysis prompt: {str(e)}")
    
    def build_rule_validation_prompt(self, rule_json: Dict[str, Any], 
                                   validation_type: str = "전체 검증",
                                   context: Optional[str] = None,
                                   customization: Optional[CustomizationOptions] = None) -> PromptResult:
        """룰 검증용 프롬프트 생성"""
        try:
            template = self._select_template(PromptType.RULE_VALIDATION)
            
            if customization is None:
                customization = CustomizationOptions()
            
            context_data = {
                "rule_json": json.dumps(rule_json, indent=2, ensure_ascii=False),
                "validation_type": validation_type,
                "context": context or "추가 컨텍스트 없음",
                "language": customization.language
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language=customization.language
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.RULE_VALIDATION.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build rule validation prompt: {str(e)}")
    
    def build_html_report_prompt(self, analysis_result: Dict[str, Any], 
                               report_title: str = "룰 분석 리포트",
                               theme: str = "modern",
                               include_charts: bool = True,
                               customization: Optional[CustomizationOptions] = None) -> PromptResult:
        """HTML 리포트 생성용 프롬프트 생성"""
        try:
            template = self._select_template(PromptType.HTML_REPORT)
            
            if customization is None:
                customization = CustomizationOptions()
            
            context_data = {
                "analysis_result": json.dumps(analysis_result, indent=2, ensure_ascii=False),
                "report_title": report_title,
                "theme": theme,
                "include_charts": "예" if include_charts else "아니오",
                "language": customization.language
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language=customization.language
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.HTML_REPORT.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build HTML report prompt: {str(e)}")
    
    def build_issue_detection_prompt(self, rule_data: Dict[str, Any], 
                                   detection_scope: List[str] = None,
                                   severity_filter: Optional[str] = None,
                                   customization: Optional[CustomizationOptions] = None) -> PromptResult:
        """이슈 검출용 프롬프트 생성"""
        try:
            template = self._select_template(PromptType.ISSUE_DETECTION)
            
            if customization is None:
                customization = CustomizationOptions()
            
            if detection_scope is None:
                detection_scope = ["syntax", "logic", "performance", "security"]
            
            context_data = {
                "rule_data": json.dumps(rule_data, indent=2, ensure_ascii=False),
                "detection_scope": ", ".join(detection_scope),
                "severity_filter": severity_filter or "모든 심각도",
                "language": customization.language
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language=customization.language
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.ISSUE_DETECTION.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build issue detection prompt: {str(e)}")
    
    def build_rule_optimization_prompt(self, rule_json: Dict[str, Any], 
                                     customization: Optional[CustomizationOptions] = None) -> PromptResult:
        """룰 최적화용 프롬프트 생성"""
        try:
            template = self._select_template(PromptType.RULE_OPTIMIZATION)
            
            if customization is None:
                customization = CustomizationOptions()
            
            context_data = {
                "rule_json": json.dumps(rule_json, indent=2, ensure_ascii=False),
                "language": customization.language
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language=customization.language
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.RULE_OPTIMIZATION.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build rule optimization prompt: {str(e)}")
    
    def build_performance_metrics_prompt(self, performance_data: Dict[str, Any], 
                                       customization: Optional[CustomizationOptions] = None) -> PromptResult:
        """성능 메트릭 분석용 프롬프트 생성"""
        try:
            template = self._select_template(PromptType.PERFORMANCE_METRICS)
            
            if customization is None:
                customization = CustomizationOptions()
            
            context_data = {
                "performance_data": json.dumps(performance_data, indent=2, ensure_ascii=False),
                "language": customization.language
            }
            
            rendered_prompt = self._render_template(template, context_data)
            
            metadata = PromptMetadata(
                template_version="1.0",
                token_count=self._estimate_token_count(rendered_prompt),
                language=customization.language
            )
            
            return PromptResult(
                prompt=rendered_prompt,
                metadata=metadata,
                context_data=context_data,
                template_used=PromptType.PERFORMANCE_METRICS.value
            )
            
        except Exception as e:
            raise PromptBuilderException(f"Failed to build performance metrics prompt: {str(e)}")
    
    # 유틸리티 메서드들
    def get_available_rule_templates(self) -> List[str]:
        """룰 검증 관련 사용 가능한 템플릿 목록 반환"""
        rule_templates = [
            PromptType.RULE_ANALYSIS.value,
            PromptType.RULE_VALIDATION.value,
            PromptType.RULE_OPTIMIZATION.value,
            PromptType.HTML_REPORT.value,
            PromptType.ISSUE_DETECTION.value,
            PromptType.PERFORMANCE_METRICS.value
        ]
        return rule_templates
    
    def validate_rule_input(self, rule_data: Dict[str, Any]) -> bool:
        """룰 데이터 유효성 검사"""
        try:
            # 기본적인 JSON 구조 검증
            if not isinstance(rule_data, dict):
                return False
            
            # 필수 필드 검증 (예시)
            required_fields = ["id", "conditions"]
            for field in required_fields:
                if field not in rule_data:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rule validation error: {e}")
            return False
    
    # 기존 헬퍼 메서드들
    def _select_template(self, prompt_type: PromptType) -> str:
        """템플릿 선택"""
        template = self.templates.get(prompt_type.value)
        if not template:
            raise TemplateNotFoundException(f"Template not found for type: {prompt_type}")
        return template
    
    def _build_context(self, input_data: PromptInput) -> Dict[str, Any]:
        """컨텍스트 구성"""
        return {
            "aggregated_data": input_data.aggregated_data,
            "target_developer": input_data.target_developer,
            "customization": input_data.customization,
            "context": input_data.context
        }
    
    def _render_template(self, template: str, context_data: Dict[str, Any]) -> str:
        """템플릿 렌더링"""
        try:
            return template.format(**context_data)
        except KeyError as e:
            raise PromptBuilderException(f"Missing template variable: {e}")
    
    def _optimize_token_usage(self, prompt: str) -> str:
        """토큰 사용량 최적화"""
        # 기본적인 최적화: 불필요한 공백 제거
        lines = prompt.split('\n')
        optimized_lines = [line.strip() for line in lines if line.strip()]
        return '\n'.join(optimized_lines)
    
    def _estimate_token_count(self, text: str) -> int:
        """토큰 수 추정 (간단한 추정법)"""
        # 대략적인 추정: 한글 1글자 = 1토큰, 영어 4글자 = 1토큰
        korean_chars = len([c for c in text if ord(c) >= 0xAC00 and ord(c) <= 0xD7A3])
        other_chars = len(text) - korean_chars
        return korean_chars + (other_chars // 4)
    
    def _format_activities(self, activities: List[str]) -> str:
        """활동 목록 포맷팅"""
        if not activities:
            return "활동 정보 없음"
        return '\n'.join([f"- {activity}" for activity in activities[:5]])
    
    def _format_peak_hours(self, peak_hours: List[int]) -> str:
        """피크 시간 포맷팅"""
        if not peak_hours:
            return "정보 없음"
        return f"{min(peak_hours)}시 ~ {max(peak_hours)}시" 