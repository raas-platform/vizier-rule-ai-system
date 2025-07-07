"""
룰 분석기 v2 (RuleAnalyzer) - PyPI 모듈 기반 리팩토링

PyPI에 배포된 RaaS 모듈들을 사용하여 리팩토링:
- raas_rule_analyzer: 룰 파싱 및 분석
- raas_report_generator: 리포트 생성
- 기존 로컬 analyzers 코드 제거

구성 요소:
- RuleParser: 룰 파싱 (from raas_rule_analyzer)
- ReportGenerator: 리포트 생성 (from raas_report_generator)
- AIEnhancer: AI 기반 개선 (로컬 유지 - LLM 통합)
"""

import time
from typing import Any, Dict, Optional
from datetime import datetime

# PyPI 모듈 import
from raas_rule_analyzer import RuleParser, Rule, ValidationResult, ConditionIssue
from raas_report_generator import ReportGenerator

# 로컬 모듈 import
from ..models.rule import Rule as LocalRule
from ..models.validation_result import (
    ConditionIssue as LocalConditionIssue,
    ReportMetadata,
    StructureInfo,
    ValidationResult as LocalValidationResult,
)
from ..utils.logger import get_logger
from .analyzers.ai_enhancer import AIEnhancer  # AI 기능만 로컬 유지


class RuleAnalyzerV2:
    """
    PyPI 모듈 기반 룰 분석 서비스 v2

    이 클래스는 PyPI에 배포된 RaaS 모듈들을 조합하여 사용합니다:
    - raas_rule_analyzer: 룰 파싱 및 기본 분석
    - raas_report_generator: 리포트 생성
    - 로컬 AIEnhancer: LLM 통합 기능

    주요 특징:
    - PyPI 모듈 조합 사용
    - 중복 코드 제거
    - 기존 API 완전 호환
    """

    def __init__(self):
        """RuleAnalyzerV2 초기화 - PyPI 모듈 기반"""
        self.logger = get_logger(__name__)

        # PyPI 모듈 초기화
        self.rule_parser = RuleParser()
        self.report_generator = ReportGenerator()
        
        # 로컬 AI 기능 초기화
        self.ai_enhancer = AIEnhancer()

        self.logger.info("RuleAnalyzerV2 초기화 완료 - PyPI 모듈 기반")

    async def analyze_rule(self, rule: LocalRule) -> LocalValidationResult:
        """
        룰을 분석하고 검증 결과를 반환 (PyPI 모듈 사용)

        Args:
            rule (LocalRule): 분석할 룰 객체

        Returns:
            LocalValidationResult: 종합적인 검증 결과
        """
        analysis_start_time = time.time()
        
        try:
            # 룰 기본 정보 추출
            rule_name = self._extract_rule_name(rule)
            rule_id = self._extract_rule_id(rule)
            
            # AI Enhancer 통계 초기화
            self.ai_enhancer.reset_stats()
            
            self.logger.info(f"룰 분석 시작 (PyPI 모듈 기반): {rule_name}")

            # 1단계: PyPI 모듈로 룰 파싱 및 분석
            # 로컬 Rule을 PyPI Rule로 변환
            pypi_rule = self._convert_to_pypi_rule(rule)
            
            # PyPI 모듈로 기본 분석 수행
            pypi_result = await self._analyze_with_pypi_modules(pypi_rule)
            
            # 2단계: AI 기반 개선 (로컬 기능)
            enhanced_result = await self._enhance_with_ai(pypi_result, rule)
            
            # 3단계: 로컬 ValidationResult로 변환
            final_result = self._convert_to_local_result(enhanced_result, rule, analysis_start_time)

            analysis_end_time = time.time()
            analysis_time_ms = int((analysis_end_time - analysis_start_time) * 1000)
            
            self.logger.info(
                f"룰 분석 완료 (PyPI 모듈 기반): {rule_name}, "
                f"소요시간 {analysis_time_ms}ms"
            )

            return final_result

        except Exception as e:
            self.logger.error(f"룰 분석 중 치명적 오류 (PyPI 모듈): {str(e)}", exc_info=True)
            return self._create_error_result(rule, str(e), analysis_start_time)

    def _convert_to_pypi_rule(self, local_rule: LocalRule) -> Rule:
        """로컬 Rule을 PyPI Rule로 변환"""
        # 필요한 필드들을 추출하여 PyPI Rule 생성
        rule_data = {
            "ruleUuid": getattr(local_rule, "ruleUuid", None),
            "ruleName": getattr(local_rule, "ruleName", getattr(local_rule, "name", "Unknown")),
            "ruleMsg": getattr(local_rule, "ruleMsg", ""),
            "conditionTree": getattr(local_rule, "conditionTree", None),
        }
        
        # PyPI RuleParser로 파싱
        return self.rule_parser.parse_rule(rule_data)

    async def _analyze_with_pypi_modules(self, pypi_rule: Rule) -> ValidationResult:
        """PyPI 모듈들을 사용한 기본 분석"""
        try:
            # raas_rule_analyzer의 RuleAnalyzer 사용
            from raas_rule_analyzer.analyzers import RuleAnalyzer
            
            # PyPI RuleAnalyzer 초기화
            pypi_analyzer = RuleAnalyzer()
            
            # 룰 데이터를 dict 형태로 변환 (PyPI 모듈 API 요구사항)
            rule_data = {
                "ruleUuid": pypi_rule.ruleUuid,
                "ruleName": pypi_rule.ruleName,
                "ruleMsg": pypi_rule.ruleMsg,
                "conditionTree": pypi_rule.conditionTree.model_dump() if pypi_rule.conditionTree else None,
            }
            
            # PyPI 모듈로 종합 분석 수행
            analysis_result = pypi_analyzer.analyze_rule_comprehensive(
                rule_data=rule_data,
                include_condition_analysis=True,
                include_issue_detection=True,
                include_metrics=True,
                generate_report=False  # 리포트는 별도 처리
            )
            
            # PyPI 분석 결과를 ValidationResult로 변환
            is_valid = analysis_result.get("status") == "success"
            
            # 이슈 정보 추출
            issues = []
            issue_detection = analysis_result.get("issue_detection", {})
            if issue_detection and "issues" in issue_detection:
                for issue in issue_detection["issues"]:
                    issues.append(ConditionIssue(
                        type=issue.get("category", "unknown"),
                        severity=issue.get("severity", "warning"),
                        message=issue.get("message", ""),
                        description=issue.get("description", ""),
                        field=issue.get("field"),
                        operator=issue.get("operator"),
                        value=issue.get("value"),
                        condUuid=issue.get("condition_uuid"),
                        ai_explanation=None,  # AI 개선 단계에서 추가
                        ai_recommendation=None,
                        ai_impact_analysis=None,
                    ))
            
            # 구조 정보 추출
            condition_analysis = analysis_result.get("condition_analysis", {})
            structure_info = {
                "depth": condition_analysis.get("max_depth", 1),
                "condition_count": condition_analysis.get("total_conditions", 0),
                "complexity_score": condition_analysis.get("complexity_score", 0),
                "unique_fields": condition_analysis.get("unique_fields", []),
            }
            
            # ValidationResult 생성
            result = ValidationResult(
                is_valid=is_valid and len([i for i in issues if i.severity == "error"]) == 0,
                summary=f"PyPI 모듈 분석 완료: {len(issues)}개 이슈 발견",
                issues=issues,
                structure_info=structure_info
            )
            
            self.logger.info(f"PyPI 모듈 분석 완료: {len(issues)}개 이슈 발견")
            return result
            
        except Exception as e:
            self.logger.error(f"PyPI 모듈 분석 오류: {str(e)}", exc_info=True)
            # 기본 결과 반환
            return ValidationResult(
                is_valid=False,
                summary=f"PyPI 모듈 분석 오류: {str(e)}",
                issues=[],
                structure_info={}
            )

    async def _enhance_with_ai(self, pypi_result: ValidationResult, local_rule: LocalRule) -> ValidationResult:
        """AI 기반 개선 (로컬 AIEnhancer 사용)"""
        try:
            # PyPI 결과의 이슈들을 로컬 ConditionIssue로 변환
            local_issues = []
            for issue in pypi_result.issues:
                local_issue = LocalConditionIssue(
                    type=issue.type,
                    severity=issue.severity,
                    message=issue.message,
                    description=issue.description,
                    field=issue.field,
                    operator=issue.operator,
                    value=issue.value,
                    condUuid=issue.condUuid,
                    ai_explanation=None,
                    ai_recommendation=None,
                    ai_impact_analysis=None,
                )
                local_issues.append(local_issue)
            
            # AI 배치 개선 적용
            if local_issues:
                await self.ai_enhancer.enhance_issues_batch(local_issues, local_rule)
                self.logger.info(f"AI 개선 완료: {len(local_issues)}개 이슈 처리")
            
            # 개선된 이슈들을 다시 PyPI ValidationResult에 반영
            enhanced_issues = []
            for local_issue in local_issues:
                enhanced_issue = ConditionIssue(
                    type=local_issue.type,
                    severity=local_issue.severity,
                    message=local_issue.message,
                    description=local_issue.description,
                    field=local_issue.field,
                    operator=local_issue.operator,
                    value=local_issue.value,
                    condUuid=local_issue.condUuid,
                    ai_explanation=local_issue.ai_explanation,
                    ai_recommendation=local_issue.ai_recommendation,
                    ai_impact_analysis=local_issue.ai_impact_analysis,
                )
                enhanced_issues.append(enhanced_issue)
            
            # 개선된 결과 생성
            enhanced_result = ValidationResult(
                is_valid=pypi_result.is_valid,
                summary=pypi_result.summary,
                issues=enhanced_issues,
                structure_info=pypi_result.structure_info
            )
            
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"AI 개선 오류: {str(e)}", exc_info=True)
            # 개선 실패 시 원본 결과 반환
            return pypi_result

    def _convert_to_local_result(self, pypi_result: ValidationResult, local_rule: LocalRule, start_time: float) -> LocalValidationResult:
        """PyPI ValidationResult를 로컬 ValidationResult로 변환"""
        analysis_time_ms = int((time.time() - start_time) * 1000)
        
        # PyPI 이슈들을 로컬 이슈로 변환
        local_issues = []
        for issue in pypi_result.issues:
            local_issue = LocalConditionIssue(
                type=issue.type,
                severity=issue.severity,
                message=issue.message,
                description=issue.description,
                field=issue.field,
                operator=issue.operator,
                value=issue.value,
                condUuid=issue.condUuid,
                ai_explanation=issue.ai_explanation,
                ai_recommendation=issue.ai_recommendation,
                ai_impact_analysis=issue.ai_impact_analysis,
            )
            local_issues.append(local_issue)
        
        # 이슈 카운트 계산
        issue_counts = {}
        for issue in local_issues:
            issue_type = issue.type
            if issue_type in issue_counts:
                issue_counts[issue_type] += 1
            else:
                issue_counts[issue_type] = 1
        
        # 구조 정보 변환
        structure_info = pypi_result.structure_info
        structure = StructureInfo(
            depth=structure_info.get("depth", 1),
            condition_count=structure_info.get("condition_count", 0),
            condition_node_count=structure_info.get("condition_count", 0),
            field_condition_count=structure_info.get("condition_count", 0),
            unique_fields=structure_info.get("unique_fields", []),
        )
        
        # 복잡성 점수
        complexity_score = structure_info.get("complexity_score", 0)
        
        # 요약 생성
        error_count = len([i for i in local_issues if i.severity == "error"])
        warning_count = len([i for i in local_issues if i.severity == "warning"])
        
        if error_count > 0:
            summary = f"룰 검증 실패: {error_count}개 오류, {warning_count}개 경고 발견"
        elif warning_count > 0:
            summary = f"룰 검증 완료: {warning_count}개 경고 발견"
        else:
            summary = "룰 검증 완료: 이슈 없음"
        
        # AI 통계 수집
        ai_stats = self.ai_enhancer.get_stats()
        
        # 로컬 ValidationResult 생성
        return LocalValidationResult(
            is_valid=pypi_result.is_valid,
            summary=summary,
            issue_counts=issue_counts,
            issues=local_issues,
            structure=structure,
            rule_summary=f"룰 '{self._extract_rule_name(local_rule)}' 분석 완료",
            complexity_score=complexity_score,
            ai_comment=f"PyPI 모듈 기반 분석으로 {len(local_issues)}개 이슈 검출",
            field_analysis=[],  # 향후 PyPI 모듈에서 지원 시 추가
            logic_flow=None,    # 향후 PyPI 모듈에서 지원 시 추가
            performance_metrics=None,  # 향후 PyPI 모듈에서 지원 시 추가
            quality_metrics=None,      # 향후 PyPI 모듈에서 지원 시 추가
            report_metadata=ReportMetadata(
                analysis_timestamp=datetime.now().isoformat(),
                ruleUuid=self._extract_rule_id(local_rule),
                ruleName=self._extract_rule_name(local_rule),
                total_analysis_time_ms=analysis_time_ms,
                validation_model=ai_stats.get("model_used"),
                validation_ai_latency_ms=ai_stats.get("total_latency_ms"),
                total_processing_time_ms=analysis_time_ms,
            ),
            ai_insights=None,              # 향후 추가
            improvement_recommendations=None,  # 향후 추가
            risk_assessment=None,          # 향후 추가
            ai_summary_md=None,           # 향후 추가
        )

    def _extract_rule_name(self, rule: LocalRule) -> str:
        """룰에서 이름 추출"""
        if hasattr(rule, "ruleName") and rule.ruleName:
            return rule.ruleName
        elif hasattr(rule, "name") and rule.name:
            return rule.name
        return "Unknown Rule"

    def _extract_rule_id(self, rule: LocalRule) -> Optional[str]:
        """룰에서 ID 추출"""
        if hasattr(rule, "ruleUuid") and rule.ruleUuid:
            return rule.ruleUuid
        elif hasattr(rule, "id") and rule.id:
            return rule.id
        return None

    def _create_error_result(
        self, rule: LocalRule, error_message: str, start_time: float
    ) -> LocalValidationResult:
        """
        오류 발생 시 기본 ValidationResult 생성

        Args:
            rule (LocalRule): 분석하려던 룰
            error_message (str): 오류 메시지
            start_time (float): 분석 시작 시간

        Returns:
            LocalValidationResult: 오류 정보가 포함된 결과
        """
        rule_name = self._extract_rule_name(rule)
        rule_id = self._extract_rule_id(rule)
        analysis_time_ms = int((time.time() - start_time) * 1000)

        # 조건 개수를 안전하게 계산
        condition_count = 0
        try:
            conditions = self.rule_parser.parse_rule_conditions(rule)
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

        return LocalValidationResult(
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
        return self.rule_parser.get_field_type(field)

    def is_valid_operator(self, field: str, operator: str) -> bool:
        """
        연산자 유효성 확인 (기존 API 호환성)

        Args:
            field (str): 필드명
            operator (str): 연산자

        Returns:
            bool: 유효성 여부
        """
        return self.rule_parser.is_valid_operator(field, operator)

    def is_valid_type(self, field: str, value: Any) -> bool:
        """
        타입 유효성 확인 (기존 API 호환성)

        Args:
            field (str): 필드명
            value (Any): 값

        Returns:
            bool: 유효성 여부
        """
        return self.rule_parser.is_valid_type(field, value)

    # === 성능 및 디버깅 정보 ===

    def get_component_info(self) -> Dict[str, str]:
        """
        각 컴포넌트의 정보 반환

        Returns:
            Dict[str, str]: 컴포넌트 정보
        """
        return {
            "rule_parser": "룰 파싱 및 분석 담당",
            "report_generator": "보고서 및 요약 생성 담당",
            "ai_enhancer": "AI 기반 개선 및 통찰 담당",
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
            "components": 3,
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
            "",
            f"❌ 오류 {error_cnt}건 · ⚠️ 경고 {warning_cnt}건"
        ]
        
        # 품질 점수와 위험도를 별도 줄에 표시
        quality_info = f"📊 {quality_score}/100" if quality_score is not None else "📊 N/A"
        md_lines.append(f"{quality_info} | 🛡️ {risk_level} | 🕒 {analysis_time_s:.1f}s · {model}")

        # 이슈 타입별 개수와 설명을 간결하게 표시
        if vr.issue_counts:
            # 이슈 타입별 한글명(영문명) 매핑
            issue_type_names = {
                "missing_condition": "조건 누락(missing_condition)",
                "type_mismatch": "타입 불일치(type_mismatch)", 
                "invalid_operator": "잘못된 연산자(invalid_operator)",
                "duplicate_condition": "중복 조건(duplicate_condition)",
                "self_contradiction": "자기 모순(self_contradiction)",
                "ambiguous_branch": "모호한 분기(ambiguous_branch)",
                "complexity_warning": "복잡도 경고(complexity_warning)"
            }
            
            # 이슈 타입별 간단한 설명 매핑
            issue_descriptions = {
                "missing_condition": "필수 조건이 누락됨",
                "type_mismatch": "데이터 타입이 맞지 않음", 
                "invalid_operator": "지원하지 않는 연산자 사용",
                "duplicate_condition": "동일한 조건이 중복됨",
                "self_contradiction": "조건들이 서로 모순됨",
                "ambiguous_branch": "분기 조건이 모호함",
                "complexity_warning": "룰 구조가 너무 복잡함"
            }
            
            breakdown_list = []
            description_list = []
            for k, v in vr.issue_counts.items():
                if v > 0:
                    issue_name = issue_type_names.get(k, f"기타({k})")
                    issue_desc = issue_descriptions.get(k, f"기타 이슈")
                    breakdown_list.append(f"{issue_name} {v}건")
                    description_list.append(f"{k} - {issue_desc}")
            
            if breakdown_list:
                md_lines.extend([
                    "",
                    f"🐞 **발견된 이슈**: {', '.join(breakdown_list)}",
                    "",
                    f"📝 **이슈 설명**: {' | '.join(description_list)}",
                    ""
                ])

        # 상세 진단 섹션 (890px 최적화)
        if vr.issues and any(issue.severity in ("error", "warning") for issue in vr.issues):
            md_lines.extend([
                "",
                "",
                "---",
                "",
                "**🔍 상세 진단**",
                ""
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
                        "",
                        f"📋 **문제**: {system_analysis}",
                        "",
                        f"🤖 **AI 분석**: {ai_analysis}",
                        "",
                        f"💡 **해결책**: {suggestion}",
                        "",
                        "---",
                        ""  # 각 이슈 후 구분선과 빈 줄
                    ])
        else:
            # 이슈가 없을 때
            md_lines.extend([
                "",
                "",
                "---",
                "",
                "✅ **진단 결과**: 심각한 이슈가 발견되지 않았습니다.",
                ""
            ])

        # AI 종합 의견 섹션
        md_lines.extend([
            "",
            "",
            "---",
            "",
            "**💬 AI 종합 의견**",
            ""
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
