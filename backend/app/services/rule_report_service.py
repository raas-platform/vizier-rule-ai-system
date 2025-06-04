from typing import Dict, Any, List
import json
from app.services.llm_service import LLMService
from app.models.validation_result import ValidationResult, ConditionIssue
from app.models.rule import Rule

class RuleReportService:
    """Service for generating rule analysis reports"""

    def __init__(self):
        """Initialize rule report service with LLM service"""
        self.llm_service = LLMService()

    async def generate_report(self, rule: Rule, validation_result: ValidationResult = None) -> Dict[str, Any]:
        """룰에 대한 상세 리포트 생성"""
        try:
            # 중요: conditions가 빈 배열인 경우 특별 처리
            if not rule.conditions:
                print("경고: 룰의 conditions 배열이 비어 있습니다. 샘플 조건으로 대체합니다.")
                # 샘플 조건을 추가하여 리포트 생성이 가능하도록 함
                # 원본 룰은 수정하지 않고 복사본 만들기
                rule_copy = Rule(
                    name=rule.name,
                    description=rule.description,
                    conditions=[{
                        "field": "sample_field",
                        "operator": "==",
                        "value": "sample_value",
                        "conditions": None
                    }],
                    action=rule.action,
                    id=rule.id,
                    priority=rule.priority,
                    enabled=rule.enabled
                )
                # 빈 조건임을 나타내는 플래그 추가
                empty_conditions = True
            else:
                rule_copy = rule
                empty_conditions = False
            
            # LLM을 사용한 리포트 생성
            rule_json = rule_copy.model_dump()
            
            # 검증 결과가 없는 경우 새로 분석
            if validation_result is None:
                from app.services.rule_analyzer import RuleAnalyzer
                analyzer = RuleAnalyzer()
                validation_result = await analyzer.analyze_rule(rule_copy)
                
            prompt = self._create_report_prompt(rule_json, validation_result)
            system_message = self._get_system_message()
            
            # LLM 서비스 호출 시 예외 처리 강화
            try:
                report = await self.llm_service.call_llm(prompt, system_message)
                
                # LLM 응답 검증 및 수정 - 이슈 유형 개수와 총 이슈 건수가 validation_result와 일치하는지 확인
                report = self._validate_and_fix_report(report, validation_result)
            
                # 빈 조건 배열이었던 경우 관련 메시지 추가
                if empty_conditions:
                    report += "\n\n## ⚠️ 빈 조건 알림\n룰에 조건이 정의되어 있지 않습니다. 룰 사용 전 조건을 반드시 추가해주세요."
            
                return {
                    "report": report,
                    "rule_id": rule.id or "N/A",
                    "rule_name": rule.name
                }
            except Exception as llm_error:
                print(f"LLM 서비스 호출 오류: {str(llm_error)}")
                # LLM 서비스 관련 오류 메시지를 포함하여 대체 리포트 생성
                return self._generate_fallback_report(rule, validation_result, str(llm_error))
            
        except Exception as e:
            print(f"리포트 생성 중 예상치 못한 오류: {str(e)}")
            # 일반적인 오류에 대한 대체 리포트 생성
            return self._generate_fallback_report(rule, validation_result, str(e))

    async def generate_report_from_results(self, rule_json: Dict[str, Any], analysis_result: ValidationResult) -> Dict[str, Any]:
        """기존 분석 결과를 활용하여 리포트 생성"""
        try:
            # 기존 분석 결과를 활용한 리포트 생성
            prompt = self._create_report_prompt(rule_json, analysis_result)
            system_message = self._get_system_message()
            
            report = await self.llm_service.call_llm(prompt, system_message)
            
            # 룰 ID와 이름 추출
            rule_id = rule_json.get("ruleId", rule_json.get("id", "N/A"))
            rule_name = rule_json.get("name", "Unnamed Rule")
            
            return {
                "report": report,
                "rule_id": rule_id,
                "rule_name": rule_name
            }
        except Exception as e:
            print(f"리포트 생성 오류: {str(e)}")
            # LLM 서비스 호출 실패 시 대체 리포트 생성
            # Rule 객체로 변환하지 않고 기본 정보로 대체 리포트 생성
            fallback_report = f"""# ✅ 룰 오류 검토 보고서

## 📌 기본 정보
- **룰 ID**: {rule_json.get("ruleId", rule_json.get("id", "N/A"))}
- **룰명**: {rule_json.get("name", "Unnamed Rule")}
- **설명**: {rule_json.get("description", "설명 없음")}
- **우선순위**: {rule_json.get("priority", "N/A")}

## 🔍 분석 오류
죄송합니다. 현재 룰 분석 서비스에 일시적인 문제가 발생했습니다. 나중에 다시 시도해주세요.
"""
            
            return {
                "report": fallback_report,
                "rule_id": rule_json.get("ruleId", rule_json.get("id", "N/A")),
                "rule_name": rule_json.get("name", "Unnamed Rule")
            }

    def _create_report_prompt(self, rule_json: Dict[str, Any], validation_result: ValidationResult) -> str:
        # validation_result가 None인 경우 처리
        if validation_result is None:
            # 기본 프롬프트 생성 (오류 리포트)
            rule_id = rule_json.get("ruleId", rule_json.get("id", "Unknown"))
            rule_name = rule_json.get("name", "Unnamed Rule")
            
            return f"""
# 룰 분석 리포트

## ✅ 1. 기본 정보

| 항목 | 내용 |
|------|------|
| 룰 ID | {rule_id} |
| 룰명 | {rule_name} |
| 우선순위 | {rule_json.get("priority", "N/A")} |
| 설명 | {rule_json.get("description", "설명 없음")} |

## 🧠 2. 조건 구조 요약

데이터 처리 중 오류가 발생하여 구조를 분석할 수 없습니다.

## ⚠️ 3. 검출된 오류

| 유형 | 상세 내용 |
|------|-----------|
| - | 분석 중 오류가 발생하여 검출된 오류가 없습니다. |

## 📌 총평

이 룰은 형식 오류로 인해 정확한 분석이 어렵습니다. 룰 JSON 형식을 확인하고 다시 시도해 주세요.
"""
            
        rule_id = rule_json.get("ruleId", rule_json.get("id", "Unknown"))
        rule_name = rule_json.get("name", "Unnamed Rule")
        
        # 최상위 연산자 판별
        top_level_operator = "N/A"
        conditions = rule_json.get("conditions", [])
        if isinstance(conditions, dict):
            # 앵커 패턴(객체 형태)인 경우
            top_level_operator = conditions.get("operator", "N/A")
        elif isinstance(conditions, list) and conditions:
            # 배열 형태일 때는 첫 번째 조건이 group이면 해당 field를 최상위 연산자로 간주
            if any(c.get("operator") == "group" for c in conditions if isinstance(c, dict)):
                for condition in conditions:
                    if isinstance(condition, dict) and condition.get("operator") == "group":
                        top_level_operator = condition.get("field", "") 
                        break
            else:
                # 모두 기본 조건일 경우 묵시적으로 AND로 간주
                top_level_operator = "AND (묵시적)"
        
        # 필드명 매핑 정보 (가독성을 위한 설명 추가)
        field_mappings = {
            "MBL_ACT_MEM_PCNT": "무선 회선 수",
            "ENTR_STUS_CD": "가입 상태",
            "MRKT_CD": "마켓 코드",
            "IOT_MEM_PCNT": "IoT 회선 수",
            "AGE": "나이",
            "USER_TYPE": "사용자 유형",
            "SCORE": "점수",
            "PROD_CD": "상품 코드"
        }

        # 구조 정보 추출
        depth = 1
        condition_node_count = 0
        field_condition_count = 0
        unique_fields = []
        
        if hasattr(validation_result, "structure"):
            depth = validation_result.structure.depth
            condition_node_count = getattr(validation_result.structure, "condition_node_count", 0)
            field_condition_count = getattr(validation_result.structure, "field_condition_count", 0)
            unique_fields = validation_result.structure.unique_fields
            
            # 이전 버전과의 호환성: condition_count를 condition_node_count로 사용
            if condition_node_count == 0 and hasattr(validation_result.structure, "condition_count"):
                condition_node_count = validation_result.structure.condition_count

        # 사용된 필드 목록 생성 (연산자 제외)
        field_list_text = ""
        if unique_fields:
            for field in unique_fields:
                # AND, OR, GROUP 같은 연산자는 제외
                if field and field.upper() not in ["OR", "AND", "GROUP"] and field != "placeholder":
                    description = field_mappings.get(field, "")
                    if description:
                        field_list_text += f"  - {field} ({description})\n"
                    else:
                        field_list_text += f"  - {field}\n"
        else:
            field_list_text = "  없음\n"

        # 이슈 유형별 정보 수집
        issues_by_type = {}
        if hasattr(validation_result, 'issues'):
            for issue in validation_result.issues:
                # 그룹 연산자는 필드로 간주하지 않음
                if hasattr(issue, 'field') and issue.field and issue.field.upper() in ["OR", "AND", "GROUP"]:
                    continue
                    
                issue_type = getattr(issue, 'issue_type', 'unknown')
                if issue_type not in issues_by_type:
                    issues_by_type[issue_type] = []
                issues_by_type[issue_type].append(issue)

        # 이슈 유형별 상세 내용 생성
        issue_details = {}

        # 이슈 타입 매핑
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

        # 이슈 개수 계산 - issue_counts와 일치하도록 함
        total_issue_count = sum(validation_result.issue_counts.values()) if hasattr(validation_result, 'issue_counts') else sum(len(issues) for issues in issues_by_type.values())
        issue_type_count = len(validation_result.issue_counts) if hasattr(validation_result, 'issue_counts') else len(issues_by_type)

        # 실제 이슈 유형과 validation_result.issue_counts 간 일치 확인
        if hasattr(validation_result, 'issue_counts') and issues_by_type:
            # validation_result.issue_counts에 있으나 issues_by_type에 없는 이슈 유형이 있는지 확인
            for issue_type in validation_result.issue_counts:
                if issue_type not in issues_by_type:
                    print(f"경고: {issue_type} 이슈 유형이 issue_counts에는 있으나 issues에는 없습니다.")
            
            # issues_by_type에 있으나 validation_result.issue_counts에 없는 이슈 유형이 있는지 확인
            for issue_type in issues_by_type:
                if issue_type not in validation_result.issue_counts:
                    print(f"경고: {issue_type} 이슈 유형이 issues에는 있으나 issue_counts에는 없습니다.")

        for issue_type, issues in issues_by_type.items():
            details = []
            fields_with_issues = {}
            
            for issue in issues:
                field = getattr(issue, 'field', None)
                # 연산자는 필드로 간주하지 않음
                if field and field.upper() in ["OR", "AND", "GROUP"]:
                    continue
                    
                # 필드별로 이슈 그룹화
                if field not in fields_with_issues:
                    fields_with_issues[field] = []
                
                fields_with_issues[field].append({
                    "explanation": getattr(issue, 'explanation', ''),
                    "location": getattr(issue, 'location', ''),
                    "suggestion": getattr(issue, 'suggestion', '')
                })
            
            # 필드 단위로 세부 내용 구성
            issue_type_name = issue_type_mapping.get(issue_type, issue_type)
            
            # 이슈 개수를 issue_counts 기준으로 정확하게 표시
            issue_count = validation_result.issue_counts.get(issue_type, len(issues)) if hasattr(validation_result, 'issue_counts') else len(issues)
            
            issue_details[issue_type] = {
                "name": issue_type_name,
                "count": issue_count,  # validation_result의 issue_counts 값과 일치
                "fields": []
            }
            
            for field, field_issues in fields_with_issues.items():
                field_name = field if field else "전체 룰"
                
                # 필드별 설명 구성
                field_desc = []
                for idx, issue in enumerate(field_issues):
                    location = issue.get("location", "")
                    explanation = issue.get("explanation", "")
                    
                    # 위치 정보가 있는 경우에만 포함
                    if location:
                        field_desc.append(f"- {explanation} (위치: {location})")
                    else:
                        field_desc.append(f"- {explanation}")
                
                # 중복 제거
                field_desc = list(set(field_desc))
                
                issue_details[issue_type]["fields"].append({
                    "field": field_name,
                    "descriptions": field_desc
                })

        # 이슈 요약 구성
        issue_summary = ""
        
        if validation_result.is_valid:
            issue_summary = "✅ 모든 검증을 통과했습니다."
        elif total_issue_count > 0:
            # 명확한 이슈 카운트 표시 - validation_result.issue_counts 기준
            issue_summary = f"총 {issue_type_count}가지 유형의 이슈가 발견되었으며, {total_issue_count}건의 개별 이슈가 있습니다."
            
            # 오류와 경고 개수
            error_count = len([i for i in validation_result.issues if getattr(i, 'severity', '') == "error"])
            warning_count = len([i for i in validation_result.issues if getattr(i, 'severity', '') == "warning"])
            
            if error_count > 0:
                issue_summary += f" {error_count}개의 오류를 수정해야 룰이 정상 작동합니다."
            if warning_count > 0:
                issue_summary += f" {warning_count}개의 경고가 있지만 룰은 작동 가능합니다."
        else:
            issue_summary = "이슈 정보가 제공되지 않았습니다."
        
        # 정확한 이슈 카운트 정보 제공 (LLM 프롬프트에 직접 포함)
        issue_counts_info = ""
        if hasattr(validation_result, 'issue_counts') and validation_result.issue_counts:
            # issue_counts 객체의 키 수와 값 합계 계산
            issue_type_count = len(validation_result.issue_counts)
            total_issue_count = sum(validation_result.issue_counts.values())
            
            issue_counts_info = f"## 🔢 정확한 이슈 카운트 정보 (LLM 전용)\n"
            issue_counts_info += f"- issue_counts 객체: {json.dumps(validation_result.issue_counts, ensure_ascii=False)}\n"
            issue_counts_info += f"- 이슈 유형 수: {issue_type_count}가지 (issue_counts 키 개수)\n"
            issue_counts_info += f"- 총 이슈 건수: {total_issue_count}건 (issue_counts 값 합계)\n"
            issue_counts_info += f"- issues 배열 길이: {len(validation_result.issues)}개\n\n"
            
            # 이슈 유형별 요약
            issue_counts_info += "### 이슈 유형별 카운트 (정확히 이 건수로 보고할 것):\n"
            for issue_type, count in validation_result.issue_counts.items():
                type_name = issue_type_mapping.get(issue_type, issue_type)
                issue_counts_info += f"- {type_name}: {count}건\n"
            
            # 이슈 개수 불일치 확인 - 경고 메시지 추가
            if len(validation_result.issues) != total_issue_count:
                issue_counts_info += f"\n⚠️ 주의: issue_counts 합계({total_issue_count})와 issues 배열 길이({len(validation_result.issues)})가 일치하지 않습니다. 반드시 issue_counts 기준으로 보고하세요.\n"
                
            # 추가 지침
            issue_counts_info += "\n### 리포트 생성 지침:\n"
            issue_counts_info += "1. 이슈 요약은 위 issue_counts 객체를 기준으로 작성하세요.\n"
            issue_counts_info += "2. 존재하지 않는 조건을 추론하거나 임의로 만들지 마세요.\n"
            issue_counts_info += "3. 같은 필드 내에 여러 이슈가 있더라도 실제 issues[] 항목 개수로 카운트하세요.\n"
            issue_counts_info += "4. 자기모순(self_contradiction) 이슈가 있으면 가장 먼저 언급하세요.\n"
            issue_counts_info += "5. 이슈 요약에 정확한 유형 수와 총 건수를 다음 형식으로 표시하세요: '총 {issue_type_count}가지 유형의 오류, 총 {total_issue_count}건 감지됨.'\n"
        
        # 마크다운 리포트 템플릿 구성
        markdown_report = f"""
# ✅ 룰 오류 검토 보고서

## 📌 1. 기본 정보

| 항목 | 내용 |
|------|------|
| 룰 ID | {rule_id} |
| 룰명 | {rule_name} |
| 우선순위 | {rule_json.get("priority", "N/A")} |
| 설명 | {rule_json.get("description", "설명 없음")} |

## 🧠 2. 조건 구조 요약

| 항목 | 내용 |
|------|------|
| 최상위 연산자 | {top_level_operator} |
| 중첩 단계 | {depth} |
| 조건 총 개수 | {condition_node_count} |
| 필드 조건 수 | {field_condition_count} |
| 사용된 필드 목록 | {f"{len(unique_fields)}개 필드"} |

사용된 필드:
{field_list_text}

## ⚠️ 3. 검출된 이슈 요약

**이슈 요약:** {issue_summary}

{issue_counts_info}

"""

        # 이슈가 없는 경우
        if not issue_details:
            markdown_report += "검출된 이슈가 없습니다."
        else:
            # 이슈 유형별 상세 내용 추가
            for issue_type, detail in issue_details.items():
                issue_type_name = detail["name"]
                issue_count = detail["count"]
                
                markdown_report += f"\n### {issue_type_name}: {issue_count}건\n\n"
                
                for field_info in detail["fields"]:
                    field_name = field_info["field"]
                    if field_name == "None":
                        field_name = "전체 룰"
                        
                    markdown_report += f"**{field_name}**\n"
                    for desc in field_info["descriptions"]:
                        markdown_report += f"{desc}\n"
                    markdown_report += "\n"
        
        # 총평 추가
        recommendation = ""
        if validation_result.is_valid:
            recommendation = "이 룰은 모든 검증을 통과했습니다. 바로 적용 가능합니다."
        elif len([i for i in validation_result.issues if getattr(i, 'severity', '') == "error"]) > 0:
            recommendation = "이 룰에는 수정이 필요한 오류가 있습니다. 위 내용을 참고하여 수정 후 다시 검증해주세요."
        else:
            recommendation = "이 룰에는 경고만 있으므로 적용 가능합니다. 다만, 경고 사항을 검토하시면 더 나은 룰이 될 수 있습니다."
            
        markdown_report += f"\n## 📌 총평\n\n{recommendation}\n"
        
        return markdown_report

    def _get_system_message(self) -> str:
        """리포트 생성을 위한 시스템 메시지"""
        return """
📌 역할:
당신은 룰 분석 시스템의 리포트 생성기입니다. 사용자가 제공한 분석 결과(`issue_counts`, `issues`, `summary`)를 바탕으로 정확하고 일관된 리포트를 생성해야 합니다.

📌 절대 지켜야 할 원칙:

1. **오로지 `issues[]` 배열의 항목만 리포트에 포함하세요**
   - 존재하지 않는 이슈는 상상하지 마세요
   - validate-json 결과에 없는 조건(예: `< 0`, `>=`)을 생성하지 마세요

2. **issue_counts 기준으로 유형별 건수만 요약하세요**
   - `"총 4가지 유형, 4건"`은 issue_counts의 키 수와 값 합계를 반영하세요

3. **항목 이름, 필드명, 조건 위치는 `issues[]`에 나온 그대로 사용하세요**

4. **complexity_warning**과 같은 구조적 경고는 해당 issue_type이 **명시적으로 존재할 때만 출력하세요**

이슈 요약 및 설명 규칙:
1. 총 이슈 수와 유형 수는 아래와 같이 요약해야 합니다:
   ```
   총 [issue_counts의 키 개수]가지 유형의 오류, 총 [issue_counts의 값 합계]건 감지됨.
   - [이슈 유형 1]: [개수]건
   - [이슈 유형 2]: [개수]건
   - [이슈 유형 3]: [개수]건
   ```

2. 각 이슈는 실제 발생한 위치(location)를 정확히 표시하세요. 예: "조건 5, 6"
3. 중복 조건과 자기모순은 항상 어떤 필드에서 발생했는지 명확히 표시하세요.
4. 이슈 유형별로 그룹화하여 설명하되, issue_counts의 건수와 일치하게 설명하세요.
5. 자기모순 이슈는 가장 높은 우선순위로 다루고, 해당 필드에 대한 다른 이슈는 언급하지 마세요.

📌 금지 사항:
1. 존재하지 않는 연산자나 조건을 임의로 추가하지 마세요
2. "조건 4" 같은 위치 정보는 issues[].location만 사용하세요
3. 정확한 수치, 정확한 항목만 요약하고, 리포트의 모든 내용이 분석기 결과와 1:1로 대응되어야 합니다.

이슈 타입 변환 매핑표:
- invalid_operator: 잘못된 연산자
- type_mismatch: 타입 오류
- duplicate_condition: 조건 겹침
- self_contradiction: 자기모순
- structure_complexity: 중첩 과도
- missing_condition: 누락 조건
- analysis_error: 분석 오류
- invalid_structure: 구조 오류

중요: validate에서 제공하지 않은 정보는 절대 추가하지 마세요. 사용자에게 오해를 줄 수 있습니다.
responses는 반드시 한국어로만 작성하세요. 영어를 사용하지 마세요.
"""

    def _generate_fallback_report(self, rule: Rule, validation_result: ValidationResult, error_msg: str = None) -> Dict[str, Any]:
        """LLM 서비스 호출 실패 시 대체 리포트 생성"""
        rule_id = rule.id or "Unknown"
        rule_name = rule.name or "Unnamed Rule"
        
        # 조건 개수 정보 추가
        conditions_info = f"조건 {len(rule.conditions)}개" if rule.conditions else "조건 없음"
        
        # 오류 메시지 표시 로직 추가
        error_section = ""
        if error_msg:
            error_section = f"""
## 🛑 오류 상세 정보
```
{error_msg}
```
"""
        
        # 검증 결과가 있는 경우 기본 정보 표시
        validation_section = ""
        if validation_result:
            is_valid = "✅ 문제 없음" if validation_result.is_valid else "❌ 문제 있음"
            issues_count = len(validation_result.issues) if validation_result.issues else 0
            validation_section = f"""
## 📊 검증 결과 요약
- **유효성**: {is_valid}
- **이슈 개수**: {issues_count}개
"""

        return {
            "report": f"""# 🔍 룰 분석 리포트: {rule_id} - {rule_name}

## 📌 기본 정보
- **룰 ID**: {rule_id}
- **룰명**: {rule_name}
- **설명**: {rule.description or '없음'}
- **우선순위**: {rule.priority}
- **상태**: {'활성화' if rule.enabled else '비활성화'}
- **조건**: {conditions_info}

{validation_section}

## ⚠️ 서비스 알림
죄송합니다. 현재 룰 분석 서비스에 일시적인 문제가 발생했습니다.
{error_section}
## 📝 원본 룰 정보
```json
{json.dumps(rule.model_dump(), indent=2, ensure_ascii=False)}
```""",
            "rule_id": rule_id,
            "rule_name": rule_name
        }

    def _validate_and_fix_report(self, report: str, validation_result: ValidationResult) -> str:
        """LLM이 생성한 리포트를 검증하고 필요한 경우 수정합니다"""
        # 이슈 유형 수와 총 이슈 건수 확인
        issue_type_count = len(validation_result.issue_counts) if hasattr(validation_result, 'issue_counts') and validation_result.issue_counts else 0
        total_issue_count = sum(validation_result.issue_counts.values()) if hasattr(validation_result, 'issue_counts') and validation_result.issue_counts else 0
        
        print(f"\n[리포트 검증] 실제 이슈: {issue_type_count}가지 유형, {total_issue_count}건")
        print(f"[리포트 검증] issue_counts: {validation_result.issue_counts}")
        
        if issue_type_count == 0 or total_issue_count == 0:
            return report  # 이슈가 없으면 그대로 반환
        
        # 리포트에서 "총 X가지 유형의 오류, 총 Y건 감지됨" 패턴 찾기
        import re
        
        # 더 유연한 패턴 매칭 (다양한 표현 방식 고려)
        summary_patterns = [
            r"총\s+(\d+)가지\s+유형의\s+오류,\s+총\s+(\d+)건\s+감지됨",
            r"총\s+(\d+)가지\s+유형[,의]?\s+총\s+(\d+)건[의]?\s+(이슈|오류)",
            r"총\s+(\d+)가지\s+유형[의]?\s+(이슈|오류)[,가]?\s+총\s+(\d+)건"
        ]
        
        matched_pattern = None
        reported_type_count = 0
        reported_issue_count = 0
        
        # 각 패턴 시도
        for pattern in summary_patterns:
            match = re.search(pattern, report)
            if match:
                matched_pattern = pattern
                if len(match.groups()) == 2:
                    reported_type_count = int(match.group(1))
                    reported_issue_count = int(match.group(2))
                elif len(match.groups()) == 3 and "가지" in pattern:
                    reported_type_count = int(match.group(1))
                    reported_issue_count = int(match.group(3))
                break
        
        print(f"[리포트 검증] 보고된 이슈: {reported_type_count}가지 유형, {reported_issue_count}건")
        
        # 이슈 유형과 건수를 정확하게 표현하는 요약 생성
        correct_issue_summary = f"총 {issue_type_count}가지 유형의 오류, 총 {total_issue_count}건 감지됨."
        
        # 각 이슈 유형별 카운트 추가
        issue_type_list = []
        for issue_type, count in validation_result.issue_counts.items():
            issue_type_kr = self._get_issue_type_kr_name(issue_type)
            issue_type_list.append(f"- {issue_type_kr}: {count}건")
        
        correct_issue_details = "\n".join(issue_type_list)
        
        # LLM 응답이 정확한지 확인
        if matched_pattern:
            # 보고된 수치가 실제 수치와 다른 경우 수정
            if reported_type_count != issue_type_count or reported_issue_count != total_issue_count:
                print(f"[리포트 검증] 불일치 감지: 보고된({reported_type_count}/{reported_issue_count}) vs 실제({issue_type_count}/{total_issue_count})")
                
                # 패턴 교체
                report = re.sub(matched_pattern, correct_issue_summary, report)
                
                # 이슈 유형별 카운트 정보 수정
                # "이슈 요약:" 이후 내용 찾기
                summary_section_match = re.search(r"(\*\*이슈 요약:.*?\n)((.*?\n)+?)###", report, re.DOTALL)
                if summary_section_match:
                    old_summary = summary_section_match.group(2)
                    report = report.replace(old_summary, f"{correct_issue_summary}\n{correct_issue_details}\n\n")
                    print("[리포트 검증] 이슈 요약 섹션 수정 완료")
                else:
                    print("[리포트 검증] 이슈 요약 섹션을 찾을 수 없음")
            else:
                print("[리포트 검증] 수치 일치, 수정 불필요")
        else:
            # 요약 부분을 찾지 못한 경우
            print("[리포트 검증] 이슈 요약 패턴 미발견, 강제 삽입 시도")
            
            # "## ⚠️ 3. 검출된 이슈 요약" 섹션 찾기
            if "## ⚠️ 3. 검출된 이슈 요약" in report:
                # 기존 이슈 요약 내용 대체
                summary_start = report.find("## ⚠️ 3. 검출된 이슈 요약")
                summary_end = report.find("###", summary_start)
                if summary_end == -1:  # "###"가 없는 경우 다음 섹션 찾기
                    summary_end = report.find("## 📌", summary_start)
                
                if summary_end != -1:
                    # 원래 섹션 추출
                    original_section = report[summary_start:summary_end]
                    
                    # 새 내용 생성
                    new_section = f"## ⚠️ 3. 검출된 이슈 요약\n\n**이슈 요약:** {correct_issue_summary}\n{correct_issue_details}\n\n"
                    
                    # 교체
                    report = report.replace(original_section, new_section)
                    print("[리포트 검증] 이슈 요약 섹션 전체 교체")
                else:
                    # 요약 헤더만 있고 내용이 없는 경우
                    summary_text = f"\n\n**이슈 요약:** {correct_issue_summary}\n{correct_issue_details}\n\n"
                    report = report.replace("## ⚠️ 3. 검출된 이슈 요약", f"## ⚠️ 3. 검출된 이슈 요약{summary_text}")
                    print("[리포트 검증] 이슈 요약 내용 추가")
        
        # 각 이슈 유형 섹션 수정
        # 존재하지 않는 이슈 유형 섹션 제거 (issue_counts에 없는 유형)
        allowed_issue_types_kr = [self._get_issue_type_kr_name(issue_type) for issue_type in validation_result.issue_counts.keys()]
        
        # 각 이슈 유형 섹션 찾기
        issue_section_pattern = r"### (.+?):\s+(\d+)건"
        
        for match in re.finditer(issue_section_pattern, report):
            issue_type_kr = match.group(1)
            reported_count = int(match.group(2))
            
            # 유효한 이슈 타입인지 확인
            if issue_type_kr not in allowed_issue_types_kr:
                # 해당 섹션의 끝 찾기
                section_start = match.start()
                next_section = re.search(r"###", report[section_start + 1:])
                section_end = next_section.start() + section_start + 1 if next_section else report.find("## 📌", section_start)
                
                if section_end > section_start:
                    # 섹션 삭제
                    original_section = report[section_start:section_end]
                    report = report.replace(original_section, "")
                    print(f"[리포트 검증] 유효하지 않은 이슈 유형 '{issue_type_kr}' 섹션 제거")
            else:
                # 이슈 개수가 불일치할 경우 수정
                for issue_type, count in validation_result.issue_counts.items():
                    issue_type_kr_check = self._get_issue_type_kr_name(issue_type)
                    if issue_type_kr == issue_type_kr_check and reported_count != count:
                        # 개수 수정
                        old_section_header = f"### {issue_type_kr}: {reported_count}건"
                        new_section_header = f"### {issue_type_kr}: {count}건"
                        report = report.replace(old_section_header, new_section_header)
                        print(f"[리포트 검증] 이슈 유형 '{issue_type_kr}' 개수 수정: {reported_count} → {count}")
        
        # 누락된 이슈 유형 섹션 추가
        for issue_type, count in validation_result.issue_counts.items():
            issue_type_kr = self._get_issue_type_kr_name(issue_type)
            section_pattern = f"### {issue_type_kr}:"
            
            if section_pattern not in report:
                # 첫 이슈 섹션 찾기
                first_section_match = re.search(r"### (.+?):", report)
                if first_section_match:
                    # 첫 이슈 섹션 앞에 추가
                    first_section_start = first_section_match.start()
                    insert_point = first_section_start
                    
                    # 이슈 샘플 추출 (첫 번째 발견된 issues 항목)
                    sample_issue = None
                    for issue in validation_result.issues:
                        if issue.issue_type == issue_type:
                            sample_issue = issue
                            break
                    
                    # 추가할 섹션 내용
                    new_section = f"### {issue_type_kr}: {count}건\n\n"
                    
                    if sample_issue:
                        field = sample_issue.field if sample_issue.field else "전체 룰"
                        explanation = sample_issue.explanation if hasattr(sample_issue, 'explanation') else ""
                        location = sample_issue.location if hasattr(sample_issue, 'location') else ""
                        
                        new_section += f"**{field}**\n"
                        if location:
                            new_section += f"- {explanation} (위치: {location})\n\n"
                        else:
                            new_section += f"- {explanation}\n\n"
                    else:
                        new_section += f"**이슈 정보 없음**\n- validation_result에는 있으나 상세 정보가 없습니다.\n\n"
                    
                    # 보고서에 삽입
                    report = report[:insert_point] + new_section + report[insert_point:]
                    print(f"[리포트 검증] 누락된 이슈 유형 '{issue_type_kr}' 섹션 추가")
                else:
                    # 첫 이슈 섹션을 찾지 못한 경우 총평 앞에 추가
                    total_assessment = "## 📌 총평"
                    if total_assessment in report:
                        insert_point = report.find(total_assessment)
                        
                        new_section = f"### {issue_type_kr}: {count}건\n\n"
                        
                        # 이슈 샘플 추출
                        sample_issue = None
                        for issue in validation_result.issues:
                            if issue.issue_type == issue_type:
                                sample_issue = issue
                                break
                        
                        if sample_issue:
                            field = sample_issue.field if sample_issue.field else "전체 룰"
                            explanation = sample_issue.explanation if hasattr(sample_issue, 'explanation') else ""
                            location = sample_issue.location if hasattr(sample_issue, 'location') else ""
                            
                            new_section += f"**{field}**\n"
                            if location:
                                new_section += f"- {explanation} (위치: {location})\n\n"
                            else:
                                new_section += f"- {explanation}\n\n"
                        else:
                            new_section += f"**이슈 정보 없음**\n- validation_result에는 있으나 상세 정보가 없습니다.\n\n"
                        
                        report = report[:insert_point] + new_section + report[insert_point:]
                        print(f"[리포트 검증] 누락된 이슈 유형 '{issue_type_kr}' 섹션을 총평 앞에 추가")
        
        print("[리포트 검증] 완료")
        return report

    def _get_issue_type_kr_name(self, issue_type: str) -> str:
        """이슈 타입의 한글 이름 반환"""
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
        return issue_type_mapping.get(issue_type, issue_type)

    def _generate_issue_summary(self, validation_result: ValidationResult) -> str:
        """이슈 요약 생성"""
        if not hasattr(validation_result, 'issue_counts') or not validation_result.issue_counts:
            if not validation_result.issues:
                return "모든 검증을 통과했습니다."
            # 이슈 개수 카운트 (issue_counts가 없는 경우에만 직접 계산)
            issue_types = {}
            for issue in validation_result.issues:
                if issue.issue_type not in issue_types:
                    issue_types[issue.issue_type] = 0
                issue_types[issue.issue_type] += 1
                
            issue_type_count = len(issue_types)
            total_issue_count = len(validation_result.issues)
        else:
            # issue_counts 객체에서 직접 정보 추출
            issue_types = validation_result.issue_counts
            issue_type_count = len(validation_result.issue_counts)
            total_issue_count = sum(validation_result.issue_counts.values())
        
        # 이슈가 없는 경우
        if total_issue_count == 0:
            return "모든 검증을 통과했습니다."
        
        # 이슈 요약 생성 - 단순화된 포맷으로 통일
        summary = f"총 {issue_type_count}가지 유형의 오류, 총 {total_issue_count}건 감지됨."
        
        # 각 이슈 유형별로 필드 정보 추가
        type_counts = []
        for issue_type, count in issue_types.items():
            type_name = self._get_issue_type_kr_name(issue_type)
            
            # 해당 이슈 타입의 필드들 추출
            fields = []
            for issue in validation_result.issues:
                if issue.issue_type == issue_type:
                    if issue.field and issue.field not in fields:
                        fields.append(issue.field)
            
            # 필드 정보가 있으면 추가
            if fields:
                field_str = ", ".join(fields)
                type_counts.append(f"- {type_name}: {count}건 ({field_str})")
            else:
                type_counts.append(f"- {type_name}: {count}건")
        
        # 이슈 타입별 요약 추가
        if type_counts:
            summary += "\n" + "\n".join(type_counts)
        
        return summary
