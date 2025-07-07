"""
Template Manager

Jinja2 템플릿을 관리하고 HTML 리포트를 생성합니다.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, Template

from .models import ReportData, ReportResult


class TemplateManager:
    """템플릿 관리 및 HTML 생성을 담당하는 클래스"""

    def __init__(self, templates_dir: Path = None):
        """
        TemplateManager 초기화
        
        Args:
            templates_dir: 템플릿 디렉토리 경로. None이면 패키지 내 기본 템플릿 사용
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True
        )

    def get_default_template(self) -> str:
        """기본 HTML 템플릿 반환"""
        return """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <title>{{ rule_name }} – 검증 리포트</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 24px; 
            background: #f9fafb; 
            font-size: 14px;
            line-height: 1.6;
        }
        .container { 
            max-width: 890px; 
            width: 100%; 
            height: auto; 
            margin: 0 auto;
        }
        h1 { 
            margin-top: 0; 
            margin-bottom: 24px;
            font-size: 18px;
            color: #1f2937;
            font-weight: 700;
        }
        h2 { 
            font-size: 16px; 
            margin: 24px 0 16px 0;
            color: #374151;
            font-weight: 600;
        }
        .summary { 
            background: #ffffff; 
            border-radius: 8px; 
            padding: 24px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 32px;
        }
        .summary p {
            font-size: 14px;
            margin: 12px 0;
        }
        .issues { margin-top: 32px; }
        .issue { 
            background: #fff; 
            padding: 20px 24px; 
            border-left: 5px solid #3b82f6; 
            margin-bottom: 16px; 
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .issue.error { border-left-color: #ef4444; }
        .issue.warning { border-left-color: #f59e0b; }
        .issue strong {
            font-size: 16px;
            font-weight: 600;
        }
        .issue small {
            font-size: 11px;
            color: #6b7280;
        }
        pre.json { 
            background: #f1f5f9; 
            padding: 20px; 
            overflow-x: auto; 
            border-radius: 6px;
            font-size: 12px;
            line-height: 1.4;
            border: 1px solid #e5e7eb;
        }
        footer {
            font-size: 12px;
            color: #6b7280;
            margin-top: 40px;
            text-align: right;
            padding-top: 16px;
            border-top: 1px solid #e5e7eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ rule_name }} – 검증 리포트</h1>
        <div class="summary">
            <h2>요약</h2>
            <p>{{ summary }}</p>
            <p>유효성: {{ '✅' if is_valid else '❌' }}</p>
        </div>

        {% if issues %}
        <div class="issues">
            <h2>발견된 이슈 ({{ issues|length }}건)</h2>
            {% for issue in issues %}
            <div class="issue {{ issue.severity | default('info') }}">
                <strong>{{ issue.type }}</strong> – {{ issue.message }}
                {% if issue.path %}<br /><small>경로: {{ issue.path }}</small>{% endif %}
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p>이슈가 발견되지 않았습니다 🎉</p>
        {% endif %}

        <h2>원본 구조 (JSON)</h2>
        <pre class="json">{{ json_dumps(structure, 2) }}</pre>

        <footer>
            검증 모델: {{ validation_model }} | 리포트 모델: {{ report_model }}<br/>
            분석 총 시간: {{ metadata.total_analysis_time_ms or 'N/A' }}ms |
            리포트 생성 시간: {{ metadata.report_generation_time_ms or 'N/A' }}ms
        </footer>
    </div>
</body>
</html>"""

    def generate_html_report(self, report_data: ReportData) -> ReportResult:
        """
        HTML 리포트 생성
        
        Args:
            report_data: 리포트 생성에 필요한 데이터
            
        Returns:
            ReportResult: 생성된 리포트 결과
        """
        render_start = time.time()
        
        try:
            # 템플릿 로드 시도, 실패시 기본 템플릿 사용
            try:
                template = self.env.get_template("report_template.html")
            except:
                template = Template(self.get_default_template())
            
            # 템플릿 컨텍스트 구성
            context = {
                "rule_name": report_data.rule_name,
                "summary": report_data.summary,
                "is_valid": report_data.is_valid,
                "issues": [issue.model_dump() for issue in report_data.issues],
                "structure": report_data.structure,
                "metadata": report_data.metadata.model_dump(),
                "validation_model": report_data.metadata.validation_model or "unknown",
                "report_model": "template",
                "now": datetime.now(),
                "json_dumps": lambda d, i: json.dumps(d, indent=i, ensure_ascii=False),
            }
            
            # HTML 렌더링
            html_content = template.render(**context)
            
            render_time_ms = int((time.time() - render_start) * 1000)
            
            # 메타데이터 업데이트
            report_data.metadata.report_generation_time_ms = render_time_ms
            report_data.metadata.report_generated_by = "template"
            report_data.metadata.report_model = "template"
            
            # 시간 정보를 포함하여 재렌더링
            context["metadata"] = report_data.metadata.model_dump()
            html_content = template.render(**context)
            
            return ReportResult(
                report=html_content,
                model_used="template",
                generation_time_ms=render_time_ms,
                report_generated_by="template"
            )
            
        except Exception as e:
            render_time_ms = int((time.time() - render_start) * 1000)
            
            # 에러 발생시 최소한의 HTML 반환
            minimal_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <title>리포트 생성 실패</title>
    <style>body{{font-family:monospace;white-space:pre-wrap;padding:24px}}</style>
</head>
<body>
    <h1>리포트 생성 실패</h1>
    <p>오류: {str(e)}</p>
    <h2>Raw 데이터</h2>
    <pre>{json.dumps(report_data.model_dump(), ensure_ascii=False, indent=2)}</pre>
</body>
</html>"""
            
            return ReportResult(
                report=minimal_html,
                model_used="static_fallback",
                generation_time_ms=render_time_ms,
                report_generated_by="static",
                note=f"template_error: {str(e)}"
            ) 