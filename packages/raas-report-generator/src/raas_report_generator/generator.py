"""
Report Generator

리포트 생성 및 요약 기능을 제공하는 메인 클래스입니다.
"""

import time
from typing import Any, Dict, List, Optional

from .models import IssueInfo, ReportData, ReportMetadata, ReportResult
from .templates import TemplateManager


class ReportGenerator:
    """
    리포트 생성 및 요약을 담당하는 메인 클래스
    
    이 클래스는 다음 기능들을 제공합니다:
    - 룰 구조 및 내용 요약
    - 이슈 검출 결과 요약  
    - HTML 리포트 생성
    - 메타데이터 관리
    """

    def __init__(self, template_manager: TemplateManager = None):
        """
        ReportGenerator 초기화
        
        Args:
            template_manager: 템플릿 매니저. None이면 기본 매니저 생성
        """
        self.template_manager = template_manager or TemplateManager()

    def generate_rule_summary(self, rule_data: Dict[str, Any]) -> str:
        """
        룰 요약 생성
        
        Args:
            rule_data: 룰 데이터
            
        Returns:
            str: 생성된 룰 요약
        """
        try:
            rule_name = rule_data.get("ruleName", rule_data.get("name", "Unknown Rule"))
            conditions = rule_data.get("conditions", [])
            
            if not conditions:
                return f"룰 '{rule_name}'에는 조건이 없습니다."
            
            condition_count = len(conditions) if isinstance(conditions, list) else 1
            
            # 기본 요약 생성
            summary_parts = [
                f"룰 '{rule_name}'은 {condition_count}개의 조건을 포함합니다."
            ]
            
            # 조건 타입 분석
            if isinstance(conditions, list):
                operators = set()
                for condition in conditions:
                    if isinstance(condition, dict):
                        operator = condition.get("operator", condition.get("op"))
                        if operator:
                            operators.add(operator)
                
                if operators:
                    summary_parts.append(f"사용된 연산자: {', '.join(sorted(operators))}")
            
            return " ".join(summary_parts)
            
        except Exception as e:
            return f"룰 요약 생성 중 오류가 발생했습니다: {str(e)}"

    def generate_issues_summary(self, issues: List[Dict[str, Any]], rule_name: str = "Unknown") -> str:
        """
        이슈 검출 결과 요약 생성
        
        Args:
            issues: 검출된 이슈들
            rule_name: 룰 이름
            
        Returns:
            str: 생성된 이슈 요약
        """
        try:
            if not issues:
                return f"룰 '{rule_name}' 검증이 완료되었습니다. 문제가 발견되지 않았습니다."
            
            # 이슈 타입별 카운트
            issue_type_counts = {}
            error_count = 0
            warning_count = 0
            
            for issue in issues:
                # 심각도별 카운트
                severity = issue.get("severity", "info")
                if severity == "error":
                    error_count += 1
                elif severity == "warning":
                    warning_count += 1
                
                # 타입별 카운트
                issue_type = issue.get("type", issue.get("issue_type", "unknown"))
                if issue_type not in issue_type_counts:
                    issue_type_counts[issue_type] = 0
                issue_type_counts[issue_type] += 1
            
            # 요약 문장 구성
            total_issue_count = len(issues)
            issue_type_count = len(issue_type_counts)
            
            summary_parts = [
                f"룰 '{rule_name}'에 총 {issue_type_count}가지 유형, {total_issue_count}건의 이슈가 발견되었습니다."
            ]
            
            # 심각도별 요약
            if error_count > 0:
                summary_parts.append(f"심각한 오류 {error_count}건을 수정해야 룰이 정상 작동합니다.")
            
            if warning_count > 0:
                summary_parts.append(f"경고 {warning_count}건을 검토하여 개선할 수 있습니다.")
            
            # 주요 이슈 타입 언급
            if issue_type_counts:
                top_issues = sorted(issue_type_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                issue_mentions = [f"{issue_type}({count}건)" for issue_type, count in top_issues]
                summary_parts.append(f"주요 이슈: {', '.join(issue_mentions)}")
            
            return " ".join(summary_parts)
            
        except Exception as e:
            return f"이슈 요약 생성 중 오류가 발생했습니다: {str(e)}"

    def generate_report_metadata(
        self, 
        rule_data: Dict[str, Any], 
        analysis_start_time: float = None,
        analysis_end_time: float = None
    ) -> ReportMetadata:
        """
        보고서 메타데이터 생성
        
        Args:
            rule_data: 룰 데이터
            analysis_start_time: 분석 시작 시간
            analysis_end_time: 분석 종료 시간
            
        Returns:
            ReportMetadata: 보고서 메타데이터
        """
        # 룰 정보 추출
        rule_name = rule_data.get("ruleName", rule_data.get("name", "Unknown Rule"))
        rule_id = rule_data.get("ruleUuid", rule_data.get("id"))
        
        # 분석 시간 계산
        analysis_time_ms = None
        if analysis_start_time and analysis_end_time:
            analysis_time_ms = int((analysis_end_time - analysis_start_time) * 1000)
        
        return ReportMetadata(
            rule_uuid=rule_id,
            rule_name=rule_name,
            total_analysis_time_ms=analysis_time_ms,
        )

    def generate_html_report(
        self, 
        rule_data: Dict[str, Any],
        issues: List[Dict[str, Any]] = None,
        metadata: ReportMetadata = None
    ) -> ReportResult:
        """
        HTML 리포트 생성
        
        Args:
            rule_data: 룰 데이터
            issues: 이슈 목록
            metadata: 메타데이터
            
        Returns:
            ReportResult: 생성된 리포트 결과
        """
        if issues is None:
            issues = []
        
        if metadata is None:
            metadata = self.generate_report_metadata(rule_data)
        
        # 룰 이름 추출
        rule_name = rule_data.get("ruleName", rule_data.get("name", "Unknown Rule"))
        
        # 요약 생성
        rule_summary = self.generate_rule_summary(rule_data)
        issues_summary = self.generate_issues_summary(issues, rule_name)
        
        # 전체 요약 조합
        summary = f"{rule_summary} {issues_summary}"
        
        # 유효성 판단 (error가 없으면 유효)
        is_valid = not any(issue.get("severity") == "error" for issue in issues)
        
        # 이슈 정보 변환
        issue_objects = []
        for issue in issues:
            issue_objects.append(IssueInfo(
                type=issue.get("type", issue.get("issue_type", "unknown")),
                message=issue.get("message", ""),
                severity=issue.get("severity", "info"),
                path=issue.get("path")
            ))
        
        # 리포트 데이터 구성
        report_data = ReportData(
            rule_name=rule_name,
            summary=summary,
            is_valid=is_valid,
            issues=issue_objects,
            structure=rule_data,
            metadata=metadata
        )
        
        # HTML 리포트 생성
        return self.template_manager.generate_html_report(report_data)

    def create_report_from_validation_result(self, validation_result: Dict[str, Any]) -> ReportResult:
        """
        검증 결과로부터 리포트 생성
        
        Args:
            validation_result: 검증 결과 데이터
            
        Returns:
            ReportResult: 생성된 리포트 결과
        """
        # 구조화된 데이터 추출
        structure = validation_result.get("structure", {})
        issues = validation_result.get("issues", [])
        report_metadata = validation_result.get("report_metadata", {})
        
        # 메타데이터 변환
        metadata = ReportMetadata(**report_metadata) if report_metadata else ReportMetadata()
        
        return self.generate_html_report(
            rule_data=structure,
            issues=issues,
            metadata=metadata
        ) 