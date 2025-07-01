"""
룰 분석기 v2 (RuleAnalyzer)

리팩토링된 룰 분석기로 기능별로 분리된 클래스들을 조합하여 사용합니다.

구성 요소:
- ConditionAnalyzer: 조건 분석 및 파싱
- IssueDetector: 이슈 검출 및 검증
- AIEnhancer: AI 기반 개선 및 통찰
- MetricsGenerator: 성능 및 품질 메트릭 생성
- ReportGenerator: 보고서 및 요약 생성

이 버전은 기존 RuleAnalyzer와 호환되는 인터페이스를 제공하면서
내부 구조를 모듈화하여 유지보수성과 확장성을 향상시켰습니다.
"""

import time
from typing import Any, Dict, Optional
from datetime import datetime

from ..models.rule import Rule
from ..models.validation_result import (
    ConditionIssue,
    ReportMetadata,
    StructureInfo,
    ValidationResult,
)
from ..utils.logger import get_logger
from .analyzers import (
    AIEnhancer,
    ConditionAnalyzer,
    IssueDetector,
    MetricsGenerator,
    ReportGenerator,
)


class RuleAnalyzerV2:
    """
    리팩토링된 룰 분석 서비스 v2

    이 클래스는 룰 분석 기능을 여러 전문화된 컴포넌트로 분리하여
    각각의 책임을 명확히 하고 유지보수성을 향상시켰습니다.

    주요 특징:
    - 단일 책임 원칙 준수
    - 모듈화된 구조
    - 확장 가능한 아키텍처
    - 기존 API와 완전 호환
    """

    def __init__(self):
        """RuleAnalyzerV2 초기화"""
        self.logger = get_logger(__name__)

        # 각 분석 컴포넌트 초기화
        self.condition_analyzer = ConditionAnalyzer()
        self.issue_detector = IssueDetector(self.condition_analyzer)
        self.ai_enhancer = AIEnhancer()
        self.metrics_generator = MetricsGenerator(self.condition_analyzer)
        self.report_generator = ReportGenerator(self.condition_analyzer)

        self.logger.info("RuleAnalyzerV2 초기화 완료 - 모듈화된 구조")

    async def analyze_rule(self, rule: Rule) -> ValidationResult:
        """
        룰을 분석하고 검증 결과를 반환

        Args:
            rule (Rule): 분석할 룰 객체

        Returns:
            ValidationResult: 종합적인 검증 결과
        """
        analysis_start_time = time.time()

        try:
            # 룰 기본 정보 추출
            rule_name = self._extract_rule_name(rule)
            _ = self._extract_rule_id(rule)

            self.logger.info(f"룰 분석 시작 (v2): {rule_name}")

            # 1단계: 조건 파싱 및 분석
            conditions = self.condition_analyzer.parse_rule_conditions(rule)
            _ = self.condition_analyzer.infer_field_types(rule, conditions)
            structure_metrics = self.condition_analyzer.calculate_structure_metrics(
                conditions, rule
            )

            # 2단계: 이슈 검출
            issues = await self.issue_detector.detect_all_issues(
                rule, conditions, structure_metrics["complexity_score"]
            )

            # 3단계: 이슈 최적화
            optimized_issues = self.report_generator.optimize_issues(issues)

            # 4단계: AI 기반 개선
            await self.ai_enhancer.enhance_issues_batch(optimized_issues, rule)

            # 5단계: 메트릭 생성
            analysis_end_time = time.time()

            # 구조 정보 생성
            structure_info = StructureInfo(
                depth=structure_metrics["depth"],
                condition_count=structure_metrics["condition_count"],
                condition_node_count=structure_metrics["condition_node_count"],
                field_condition_count=structure_metrics["field_condition_count"],
                unique_fields=structure_metrics["unique_fields"],
            )

            # 필드 분석
            field_analysis = await self.metrics_generator.generate_field_analysis(
                conditions, optimized_issues
            )

            # 논리 흐름 분석
            logic_flow = self.metrics_generator.generate_logic_flow_analysis(conditions)

            # 성능 메트릭
            performance_metrics = self.metrics_generator.generate_performance_metrics(
                conditions, structure_metrics["complexity_score"]
            )

            # 품질 메트릭
            quality_metrics = self.metrics_generator.generate_quality_metrics(
                optimized_issues, structure_info, conditions
            )

            # 보고서 메타데이터
            report_metadata = self.metrics_generator.generate_report_metadata(
                rule, analysis_start_time, analysis_end_time
            )

            # AIEnhancer 메타 추가
            enhancer_stats = self.ai_enhancer.get_stats()
            report_metadata.validation_model = enhancer_stats.get("model_used")
            report_metadata.validation_ai_latency_ms = enhancer_stats.get("total_latency_ms")

            # 6단계: 보고서 생성
            rule_summary = self.report_generator.generate_rule_summary(rule, conditions)
            issues_summary = self.report_generator.generate_issues_summary(
                optimized_issues, rule_name
            )
            issue_counts = self.report_generator.calculate_issue_counts(
                optimized_issues
            )

            # AI 기반 콘텐츠 생성
            ai_comment = await self.ai_enhancer.generate_ai_comment(
                rule, optimized_issues, structure_info, conditions
            )
            ai_insights = await self.ai_enhancer.generate_ai_insights(
                rule, optimized_issues, structure_info, conditions
            )
            improvement_recommendations = (
                await self.ai_enhancer.generate_improvement_recommendations(
                    rule, optimized_issues, conditions
                )
            )
            risk_assessment = await self.ai_enhancer.generate_risk_assessment(
                optimized_issues, structure_info
            )

            # 7단계: 최종 결과 조합
            is_valid = len([i for i in optimized_issues if i.severity == "error"]) == 0

            result = ValidationResult(
                is_valid=is_valid,
                summary=issues_summary,
                issue_counts=issue_counts,
                issues=optimized_issues,
                structure=structure_info,
                rule_summary=rule_summary,
                complexity_score=structure_metrics["complexity_score"],
                ai_comment=ai_comment,
                # 확장된 분석 정보
                field_analysis=field_analysis,
                logic_flow=logic_flow,
                performance_metrics=performance_metrics,
                quality_metrics=quality_metrics,
                report_metadata=report_metadata,
                # AI 생성 콘텐츠
                ai_insights=ai_insights,
                improvement_recommendations=improvement_recommendations,
                risk_assessment=risk_assessment,
                ai_summary_md=None,  # placeholder, will set below
            )

            # 요약 Markdown 생성 및 주입 -----------------------------------
            try:
                result.ai_summary_md = self._build_ai_summary_md(result)
            except Exception as md_err:
                self.logger.warning(
                    f"ai_summary_md 생성 실패: {md_err}", exc_info=True
                )

            analysis_time_ms = int((analysis_end_time - analysis_start_time) * 1000)
            self.logger.info(
                f"룰 분석 완료 (v2): {rule_name}, "
                f"이슈 {len(optimized_issues)}건, "
                f"소요시간 {analysis_time_ms}ms"
            )

            return result

        except Exception as e:
            self.logger.error(f"룰 분석 중 치명적 오류 (v2): {str(e)}", exc_info=True)
            return self._create_error_result(rule, str(e), analysis_start_time)

    def _extract_rule_name(self, rule: Rule) -> str:
        """룰에서 이름 추출"""
        if hasattr(rule, "ruleName") and rule.ruleName:
            return rule.ruleName
        elif hasattr(rule, "name") and rule.name:
            return rule.name
        return "Unknown Rule"

    def _extract_rule_id(self, rule: Rule) -> Optional[str]:
        """룰에서 ID 추출"""
        if hasattr(rule, "ruleUuid") and rule.ruleUuid:
            return rule.ruleUuid
        elif hasattr(rule, "id") and rule.id:
            return rule.id
        return None

    def _create_error_result(
        self, rule: Rule, error_message: str, start_time: float
    ) -> ValidationResult:
        """
        오류 발생 시 기본 ValidationResult 생성

        Args:
            rule (Rule): 분석하려던 룰
            error_message (str): 오류 메시지
            start_time (float): 분석 시작 시간

        Returns:
            ValidationResult: 오류 정보가 포함된 결과
        """
        rule_name = self._extract_rule_name(rule)
        rule_id = self._extract_rule_id(rule)
        analysis_time_ms = int((time.time() - start_time) * 1000)

        # 조건 개수를 안전하게 계산
        condition_count = 0
        try:
            conditions = self.condition_analyzer.parse_rule_conditions(rule)
            condition_count = len(conditions) if conditions else 0
        except Exception:
            pass  # 오류 시 0으로 유지

        error_issue = ConditionIssue(
            condUuid=None,
            keyName=None,
            dispName=None,
            issue_type="missing_condition",
            severity="error",
            location="전체 룰",
            explanation=f"룰 분석 중 오류: {error_message}",
            suggestion="룰의 형식과 조건을 확인하세요.",
        )

        return ValidationResult(
            is_valid=False,
            summary=f"룰 '{rule_name}'에 총 1가지 유형, 1건의 오류가 발견되었습니다.",
            issue_counts={"missing_condition": 1},
            issues=[error_issue],
            structure=StructureInfo(
                depth=1,
                condition_count=condition_count,
                condition_node_count=condition_count,
                field_condition_count=0,
                unique_fields=[],
            ),
            rule_summary="룰 분석 중 오류가 발생하여 요약을 생성할 수 없습니다.",
            complexity_score=0,
            ai_comment=None,
            # 기본값으로 설정
            field_analysis=[],
            logic_flow=None,
            performance_metrics=None,
            quality_metrics=None,
            report_metadata=ReportMetadata(
                analysis_timestamp=datetime.now().isoformat(),
                ruleUuid=rule_id,
                ruleName=rule_name,
                total_analysis_time_ms=analysis_time_ms,
            ),
            ai_insights=None,
            improvement_recommendations=None,
            risk_assessment=None,
            ai_summary_md=None,
        )

    # === 기존 API 호환성을 위한 메서드들 ===

    def get_field_type(self, field: str) -> str:
        """
        필드 타입 조회 (기존 API 호환성)

        Args:
            field (str): 필드명

        Returns:
            str: 필드 타입
        """
        return self.condition_analyzer.get_field_type(field)

    def is_valid_operator(self, field: str, operator: str) -> bool:
        """
        연산자 유효성 확인 (기존 API 호환성)

        Args:
            field (str): 필드명
            operator (str): 연산자

        Returns:
            bool: 유효성 여부
        """
        return self.condition_analyzer.is_valid_operator(field, operator)

    def is_valid_type(self, field: str, value: Any) -> bool:
        """
        타입 유효성 확인 (기존 API 호환성)

        Args:
            field (str): 필드명
            value (Any): 값

        Returns:
            bool: 유효성 여부
        """
        return self.condition_analyzer.is_valid_type(field, value)

    # === 성능 및 디버깅 정보 ===

    def get_component_info(self) -> Dict[str, str]:
        """
        각 컴포넌트의 정보 반환

        Returns:
            Dict[str, str]: 컴포넌트 정보
        """
        return {
            "condition_analyzer": "조건 분석 및 파싱 담당",
            "issue_detector": "7가지 이슈 타입 검출 담당",
            "ai_enhancer": "AI 기반 개선 및 통찰 담당",
            "metrics_generator": "성능 및 품질 메트릭 생성 담당",
            "report_generator": "보고서 및 요약 생성 담당",
        }

    def get_analysis_statistics(self) -> Dict[str, Any]:
        """
        분석 통계 정보 반환

        Returns:
            Dict[str, Any]: 통계 정보
        """
        return {
            "version": "2.0",
            "architecture": "modular",
            "components": 5,
            "supported_issue_types": 7,
            "ai_enhanced": True,
            "performance_optimized": True,
        }

    def _build_ai_summary_md(self, vr: ValidationResult) -> str:
        """ValidationResult를 기반으로 요약 Markdown 문자열을 생성합니다."""
        # severity별 카운트 계산
        error_cnt = len([i for i in vr.issues if i.severity == "error"])
        warning_cnt = len([i for i in vr.issues if i.severity == "warning"])
        quality_score = (
            vr.quality_metrics.overall_score if vr.quality_metrics else None
        )
        
        # 전체 처리 시간 우선 사용 (폴백: 기존 분석 시간)
        if vr.report_metadata and vr.report_metadata.total_processing_time_ms:
            analysis_time_s = vr.report_metadata.total_processing_time_ms / 1000.0
        elif vr.report_metadata and vr.report_metadata.validation_ai_latency_ms:
            analysis_time_s = vr.report_metadata.validation_ai_latency_ms / 1000.0
        else:
            analysis_time_s = 0.0
            
        model = (
            vr.report_metadata.validation_model
            if vr.report_metadata and vr.report_metadata.validation_model
            else "LLM"
        )
        risk_level = (
            vr.risk_assessment.get("overall_risk_level")
            if vr.risk_assessment and isinstance(vr.risk_assessment, dict)
            else "중간"
        )

        # 컴팩트한 요약 헤더 (제목과 내용 분리)
        md_lines = [
            "🤖 **AI 룰 검증 요약**",
            "",  # 빈 줄 추가
            f"❌ 오류 {error_cnt}건 · ⚠️ 경고 {warning_cnt}건"
        ]
        
        # 품질 점수와 위험도를 별도 줄에 표시
        quality_info = f"📊 {quality_score}/100" if quality_score is not None else "📊 N/A"
        md_lines.append(f"{quality_info} | 🛡️ {risk_level} | 🕒 {analysis_time_s:.1f}s · {model}")

        # 이슈 타입별 개수와 설명을 간결하게 표시
        if vr.issue_counts:
            # 이슈 타입별 한글명 매핑
            issue_type_names = {
                "missing_condition": "조건 누락(missing_condition)",
                "type_mismatch": "타입 불일치(type_mismatch)", 
                "invalid_operator": "잘못된 연산자(invalid_operator)",
                "duplicate_condition": "중복 조건(duplicate_condition)",
                "self_contradiction": "자기 모순(self_contradiction)",
                "ambiguous_branch": "모호한 분기(ambiguous_branch)",
                "complexity_warning": "복잡도 경고(complexity_warning)"
            }
            
            breakdown_list = []
            for k, v in vr.issue_counts.items():
                if v > 0:
                    issue_name = issue_type_names.get(k, f"기타({k})")
                    breakdown_list.append(f"{issue_name} {v}건")
            
            if breakdown_list:
                md_lines.extend([
                    "",  # 빈 줄 추가
                    f"🐞 **이슈 타입**: {', '.join(breakdown_list)}",
                    ""   # 빈 줄 추가
                ])

        # 상세 진단 섹션 (890px 최적화)
        if vr.issues and any(issue.severity in ("error", "warning") for issue in vr.issues):
            md_lines.extend([
                "---",
                "",  # 빈 줄 추가
                "**🔍 상세 진단**",
                ""   # 빈 줄 추가
            ])
            
            for idx, issue in enumerate(vr.issues):
                if issue.severity in ("error", "warning"):
                    # 필드명과 이슈 타입을 한 줄에 표시
                    display_name = issue.dispName if issue.dispName else (issue.keyName or "(전역)")
                    severity_icon = "❌" if issue.severity == "error" else "⚠️"
                    
                    # 텍스트 이스케이프 처리
                    system_analysis = str(issue.explanation).replace("|", "\\|").replace("\n", " ")
                    ai_analysis = (
                        str(issue.ai_explanation).replace("|", "\\|").replace("\n", " ")
                        if issue.ai_explanation
                        else "AI 분석 없음"
                    )
                    suggestion = (
                        str(issue.ai_suggestion).replace("|", "\\|").replace("\n", " ")
                        if issue.ai_suggestion
                        else str(issue.suggestion).replace("|", "\\|").replace("\n", " ")
                    )
                    
                    # 컴팩트한 카드 스타일 (줄바꿈과 공백 추가)
                    md_lines.extend([
                        f"**{severity_icon} `{display_name}`** · `{issue.issue_type}`",
                        f"📋 **문제**: {system_analysis}",
                        f"🤖 **AI 분석**: {ai_analysis}",
                        f"💡 **해결책**: {suggestion}",
                        ""  # 각 이슈 후 빈 줄 추가
                    ])
        else:
            # 이슈가 없을 때
            md_lines.extend([
                "---",
                "",  # 빈 줄 추가
                "✅ **진단 결과**: 심각한 이슈가 발견되지 않았습니다.",
                ""   # 빈 줄 추가
            ])

        # AI 종합 의견 섹션
        md_lines.extend([
            "---",
            "",  # 빈 줄 추가
            "**💬 AI 종합 의견**",
            ""   # 빈 줄 추가
        ])
        
        if vr.ai_comment:
            comment_text = str(vr.ai_comment).strip().replace("|", "\\|").replace("\n", " ")
            md_lines.append(comment_text)
        else:
            # AI 코멘트가 없을 때 기본 메시지
            if error_cnt > 0:
                md_lines.append(f"🔍 {error_cnt}건의 오류가 발견되어 즉시 수정이 필요합니다.")
            elif warning_cnt > 0:
                md_lines.append(f"⚠️ {warning_cnt}건의 경고가 있어 개선을 권장합니다.")
            else:
                md_lines.append("✅ 룰 구조가 양호하며 특별한 문제가 발견되지 않았습니다.")

        return "\n".join(md_lines)
