import sys
import json
import asyncio
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule

# 8개의 테스트 JSON 파일 목록
TEST_FILES = [
    "test_duplicate_condition.json",
    "test_invalid_operator.json", 
    "test_missing_condition.json",
    "test_self_contradiction.json",
    "test_type_mismatch.json",
    "test_all_errors_combined.json",
    "test_ambiguous_branch.json",
    "test_complexity_warning.json"
]

async def test_json_file(file_path):
    """개별 JSON 파일 테스트"""
    print(f"\n{'='*80}")
    print(f"📁 테스트 파일: {file_path}")
    print(f"{'='*80}")
    
    try:
        # JSON 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            rule_data = json.load(f)
        
        # JSON이 배열 형태라면 첫 번째 요소 사용
        if isinstance(rule_data, list):
            rule_data = rule_data[0]
        
        print(f"📊 룰 이름: {rule_data['ruleName']}")
        print(f"📝 룰 설명: {rule_data['ruleMsg']}")
        print(f"🔑 룰 UUID: {rule_data['ruleUuid']}")
        
        # 조건 트리 깊이 계산
        depth = _calculate_tree_depth(rule_data['conditionTree'])
        print(f"🌳 조건 트리 깊이: {depth}")
        
        # RuleAnalyzer 실행
        analyzer = RuleAnalyzerV2()
        
        # Pydantic 모델로 변환
        test_rule = Rule(**rule_data)
        
        # 룰 분석 실행
        result = await analyzer.analyze_rule(test_rule)
        
        print(f"\n✅ 분석 완료!")
        print(f"- 유효성: {'🟢 유효' if result.is_valid else '🔴 오류 있음'}")
        print(f"- 요약: {result.summary}")
        print(f"- 이슈 수: {len(result.issues)}")
        print(f"- 구조 정보:")
        print(f"  * 깊이: {result.structure.depth}")
        print(f"  * 전체 조건 노드 수: {result.structure.condition_node_count}")
        print(f"  * 필드 조건 수: {result.structure.field_condition_count}")
        print(f"  * 고유 필드 수: {len(result.structure.unique_fields)}")
        print(f"  * 필드 목록: {list(result.structure.unique_fields)}")
        print(f"- 복잡도 점수: {result.complexity_score}")
        
        if result.issues:
            print(f"\n📋 발견된 이슈들 ({len(result.issues)}건):")
            
            # 심각도별로 그룹화
            errors = [i for i in result.issues if i.severity == "error"]
            warnings = [i for i in result.issues if i.severity == "warning"]
            
            if errors:
                print(f"  🔴 오류 ({len(errors)}건):")
                for i, issue in enumerate(errors, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.explanation}")
                    print(f"       위치: {issue.location}")
                    
            if warnings:
                print(f"  🟡 경고 ({len(warnings)}건):")
                for i, issue in enumerate(warnings, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.explanation}")
                    print(f"       위치: {issue.location}")
        else:
            print(f"\n🎉 이슈가 발견되지 않았습니다!")
            
        if result.ai_comment:
            print(f"\n🤖 AI 조언: {result.ai_comment}")
            
        return True, len(result.issues), len([i for i in result.issues if i.severity == "error"])
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, 0, 0

def _calculate_tree_depth(condition_tree, current_depth=1):
    """conditionTree의 깊이 계산"""
    if not condition_tree or 'condition' not in condition_tree:
        return current_depth
    
    max_depth = current_depth
    for item in condition_tree['condition']:
        if 'logicType' in item:  # 중첩된 논리 연산자
            nested_depth = _calculate_tree_depth(item, current_depth + 1)
            max_depth = max(max_depth, nested_depth)
    
    return max_depth

async def run_all_tests():
    """모든 테스트 JSON 파일을 실행"""
    print("🚀 8개 테스트 JSON 파일 분석을 시작합니다!")
    print(f"테스트 파일 목록: {TEST_FILES}")
    
    success_count = 0
    total_issues = 0
    total_errors = 0
    results = []
    
    for file_path in TEST_FILES:
        success, issues, errors = await test_json_file(file_path)
        results.append({
            'file': file_path,
            'success': success,
            'issues': issues,
            'errors': errors
        })
        
        if success:
            success_count += 1
            total_issues += issues
            total_errors += errors
    
    # 결과 요약
    print(f"\n{'='*80}")
    print(f"📊 전체 테스트 결과 요약")
    print(f"{'='*80}")
    print(f"✅ 성공한 테스트: {success_count}/{len(TEST_FILES)}개")
    print(f"📋 총 발견된 이슈: {total_issues}개")
    print(f"🔴 총 오류: {total_errors}개")
    print(f"🟡 총 경고: {total_issues - total_errors}개")
    
    print(f"\n📂 파일별 상세 결과:")
    for result in results:
        status = "✅ 성공" if result['success'] else "❌ 실패"
        print(f"  {result['file']}: {status} (이슈: {result['issues']}개, 오류: {result['errors']}개)")
    
    if success_count == len(TEST_FILES):
        print(f"\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
    else:
        print(f"\n⚠️ {len(TEST_FILES) - success_count}개 테스트에서 실패가 발생했습니다.")

if __name__ == "__main__":
    asyncio.run(run_all_tests()) 