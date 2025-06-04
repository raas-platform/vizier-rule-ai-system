from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from app.models.rule import Rule
from app.models.validation_result import ValidationResult
from app.models.rule_json_validation_request import RuleJsonValidationRequest
from app.models.report import RuleReportRequest, RuleReportResponse
from app.services.rule_analyzer import RuleAnalyzer
from app.services.rule_report_service import RuleReportService
import json
import traceback

router = APIRouter()

@router.post("/report", response_model=RuleReportResponse)
async def generate_report(request: RuleReportRequest):
    """룰에 대한 상세 분석 리포트 생성"""
    try:
        # 리포트 서비스 초기화
        report_service = RuleReportService()
        
        # 룰 JSON을 Rule 객체로 변환 (rule_validator.py에서 재사용)
        rule_json = request.rule_json
        rule = convert_json_to_rule(rule_json)
        
        # 기존 분석 결과가 있는 경우 활용, 없으면 새로 분석
        validation_result = None
        if request.validation_result:
            # 검증 결과를 ValidationResult 객체로 변환
            validation_result = ValidationResult(**request.validation_result)
            print(f"[DEBUG] 기존 validation_result 사용: {validation_result.issue_counts}")
        else:
            # 새로 분석 실행
            analyzer = RuleAnalyzer()
            validation_result = await analyzer.analyze_rule(rule)
            print(f"[DEBUG] 새로 분석한 validation_result: {validation_result.issue_counts}")
        
        # 검증 결과 데이터 일관성 검사
        if hasattr(validation_result, 'issue_counts'):
            issue_count_sum = sum(validation_result.issue_counts.values())
            issue_count = len(validation_result.issues) if validation_result.issues else 0
            
            # issue_counts와 issues 개수가 불일치할 경우 issue_counts 다시 계산
            if issue_count_sum != issue_count:
                print(f"[경고] issue_counts({issue_count_sum})와 issues 개수({issue_count})가 불일치! issue_counts 재계산")
                recalculated_counts = {}
                for issue in validation_result.issues:
                    if issue.issue_type not in recalculated_counts:
                        recalculated_counts[issue.issue_type] = 0
                    recalculated_counts[issue.issue_type] += 1
                
                # 재계산된 값으로 업데이트
                validation_result.issue_counts = recalculated_counts
                print(f"[DEBUG] 재계산된 issue_counts: {validation_result.issue_counts}")
        
        # 리포트 생성
        report_result = await report_service.generate_report(rule, validation_result)
        
        # 리포트 후처리 - 이슈 요약 강제 수정
        report_result = force_fix_issue_summary(report_result, validation_result)
        
        return RuleReportResponse(
            report=report_result["report"],
            rule_id=report_result["rule_id"],
            rule_name=report_result["rule_name"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리포트 생성 중 오류: {str(e)}")

def convert_json_to_rule(rule_json) -> Rule:
    """JSON 형식의 룰을 Rule 객체로 변환"""
    try:
        # 룰 ID 필드 이름 통합 (ruleId 또는 id 모두 지원)
        if "ruleId" in rule_json and "id" not in rule_json:
            rule_json["id"] = rule_json["ruleId"]
        elif "id" in rule_json and "ruleId" not in rule_json:
            rule_json["ruleId"] = rule_json["id"]
        
        # JSON에 rule_json 필드가 중첩되어 있는 경우 처리
        if "rule_json" in rule_json:
            return Rule(**rule_json["rule_json"])
        else:
            return Rule(**rule_json)
    except Exception as e:
        print(f"룰 객체 변환 중 오류: {str(e)}")
        raise HTTPException(status_code=400, detail=f"룰 형식 오류: {str(e)}")
        
def force_fix_issue_summary(report_result: Dict[str, Any], validation_result: ValidationResult) -> Dict[str, Any]:
    """이슈 요약 부분을 강제로 수정합니다"""
    if not validation_result or not hasattr(validation_result, 'issue_counts') or not validation_result.issue_counts:
        return report_result  # 검증 결과가 없으면 그대로 반환
    
    print("\n[DEBUG] ===== 이슈 요약 강제 수정 시작 =====")
    
    report_text = report_result["report"]
    
    # 이슈 유형 수와 총 이슈 건수 계산
    issue_type_count = len(validation_result.issue_counts)
    total_issue_count = sum(validation_result.issue_counts.values())
    
    print(f"\n[이슈 요약 강제 수정] 실제 이슈: {issue_type_count}가지 유형, {total_issue_count}건")
    print(f"[DEBUG] issue_counts: {validation_result.issue_counts}")
    
    # 이슈 타입별 카운트 생성 (필드 정보 포함)
    issue_types_list = []
    issue_type_mapping = {
        "duplicate_condition": "조건 겹침",
        "invalid_operator": "잘못된 연산자",
        "type_mismatch": "타입 오류",
        "self_contradiction": "자기모순",
        "structure_complexity": "중첩 과도",
        "missing_condition": "누락 조건",
        "analysis_error": "분석 오류",
        "invalid_structure": "구조 오류"
    }
    
    # 타입별 필드 정보 추가
    for issue_type, count in validation_result.issue_counts.items():
        type_name = issue_type_mapping.get(issue_type, issue_type)
        
        # 해당 이슈 타입의 필드들 추출
        fields = []
        for issue in validation_result.issues:
            if issue.issue_type == issue_type:
                if issue.field and issue.field not in fields:
                    fields.append(issue.field)
        
        # 필드 정보가 있으면 추가
        if fields:
            field_str = ", ".join(fields)
            issue_types_list.append(f"- {type_name}: {count}건 ({field_str})")
        else:
            issue_types_list.append(f"- {type_name}: {count}건")
    
    # 이슈 요약 부분 생성
    correct_summary = f"총 {issue_type_count}가지 유형의 오류, 총 {total_issue_count}건 감지됨."
    correct_details = "\n".join(issue_types_list)
    
    print(f"[DEBUG] 정확한 이슈 요약:\n{correct_summary}\n{correct_details}")
    
    # "## ⚠️ 3. 검출된 이슈 요약" 부분 찾기 (여러 패턴 시도)
    import re
    
    # 다양한 이슈 요약 섹션 패턴 시도
    summary_section_patterns = [
        r"(## ⚠️ 3. 검출된 이슈 요약\s*\n)(.+?)(\n###|\n##|$)",
        r"(## ⚠️.*?검출된 이슈.*?\n)(.+?)(\n###|\n##|$)",
        r"(## 검출된 이슈.*?\n)(.+?)(\n###|\n##|$)",
        r"(## 검출된 오류.*?\n)(.+?)(\n###|\n##|$)",
        r"(##.*?이슈 요약.*?\n)(.+?)(\n###|\n##|$)"
    ]
    
    summary_match = None
    matched_pattern = None
    
    # 각 패턴 시도
    for pattern in summary_section_patterns:
        match = re.search(pattern, report_text, re.DOTALL)
        if match:
            summary_match = match
            matched_pattern = pattern
            print(f"[DEBUG] 일치한 패턴: {matched_pattern}")
            print(f"[DEBUG] 일치한, 섹션 콘텐츠: {match.group(2)}")
            break
    
    if summary_match:
        # 기존 내용 추출
        header = summary_match.group(1)
        old_content = summary_match.group(2)
        end_marker = summary_match.group(3)
        
        # 새 내용 생성
        new_content = f"\n**이슈 요약:** {correct_summary}\n{correct_details}\n"
        
        # 교체
        fixed_report = report_text.replace(
            header + old_content + end_marker,
            header + new_content + end_marker
        )
        
        print(f"[이슈 요약 강제 수정] 이슈 요약 섹션 수정 완료 (패턴: {matched_pattern})")
        report_result["report"] = fixed_report
    else:
        print("[이슈 요약 강제 수정] 이슈 요약 섹션을 찾을 수 없음, 새로 추가")
        print(f"[DEBUG] 보고서 내용 미리보기: {report_text[:200]}...")
        
        # 요약 섹션이 없으면 새로 추가 (총평 앞에)
        total_section = "## 📌 총평"
        if total_section in report_text:
            # 총평 섹션 앞에 추가
            insert_point = report_text.find(total_section)
            new_section = f"## ⚠️ 검출된 이슈 요약\n\n**이슈 요약:** {correct_summary}\n{correct_details}\n\n"
            fixed_report = report_text[:insert_point] + new_section + report_text[insert_point:]
            report_result["report"] = fixed_report
            print("[이슈 요약 강제 수정] 새 이슈 요약 섹션 추가 완료")
        else:
            # 문서 끝에 추가
            new_section = f"\n\n## ⚠️ 검출된 이슈 요약\n\n**이슈 요약:** {correct_summary}\n{correct_details}\n"
            report_result["report"] = report_text + new_section
            print("[이슈 요약 강제 수정] 문서 끝에 이슈 요약 섹션 추가")
    
    # 이슈 섹션 완전히 갱신 - 모든 섹션을 지우고 새로 생성
    # 먼저 모든 이슈 섹션 삭제
    for issue_type_en, issue_type_kr in issue_type_mapping.items():
        section_pattern = f"### {issue_type_kr}: \\d+건.*?(?=###|## |$)"
        report_result["report"] = re.sub(section_pattern, "", report_result["report"], flags=re.DOTALL)
    
    # 그 다음 새 이슈 섹션 추가
    for issue_type, count in validation_result.issue_counts.items():
        if count <= 0:
            continue  # 개수가 0이면 건너뜀
            
        type_name = issue_type_mapping.get(issue_type, issue_type)
        
        # 이슈 내용 모으기
        issue_content = f"### {type_name}: {count}건\n\n"
        
        # 필드별로 그룹화
        field_issues = {}
        for issue in validation_result.issues:
            if issue.issue_type == issue_type:
                field = issue.field if issue.field else "전체 룰"
                if field not in field_issues:
                    field_issues[field] = []
                field_issues[field].append(issue)
        
        # 필드별로 내용 추가
        for field, issues in field_issues.items():
            issue_content += f"**{field}**\n"
            for issue in issues:
                explanation = issue.explanation
                location = issue.location
                if location:
                    issue_content += f"- {explanation} (위치: {location})\n"
                else:
                    issue_content += f"- {explanation}\n"
            issue_content += "\n"
        
        # 해당 위치에 추가
        total_assessment = "## 📌 총평"
        if total_assessment in report_result["report"]:
            # 총평 앞에 추가
            insert_point = report_result["report"].find(total_assessment)
            report_result["report"] = report_result["report"][:insert_point] + issue_content + report_result["report"][insert_point:]
        else:
            # 마지막에 추가
            report_result["report"] += "\n" + issue_content
    
    print("[DEBUG] ===== 이슈 요약 강제 수정 완료 =====")
    return report_result
