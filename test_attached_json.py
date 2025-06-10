import sys
import json
sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from original_rule_analyzer import RuleAnalyzer
from app.models.rule import Rule
import asyncio

async def test_json_file():
    """첨부된 JSON 파일을 기존 분석기와 v2로 모두 테스트"""
    
    print("=== 첨부된 JSON 파일 분석 테스트 ===")
    
    # JSON 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    # 첫 번째 룰만 테스트
    rule_json = rules_data[0]
    
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    print(f"📝 룰 설명: {rule_json['ruleMsg']}")
    
    # Pydantic 모델로 변환
    test_rule = Rule(**rule_json)
    
    print("\n" + "="*60)
    print("🔄 기존 RuleAnalyzer 테스트")
    print("="*60)
    
    try:
        # 기존 분석기 테스트
        original_analyzer = RuleAnalyzer()
        original_result = await original_analyzer.analyze_rule(test_rule)
        
        print(f"✅ 기존 분석기 결과:")
        print(f"- 유효성: {'🟢 유효' if original_result.is_valid else '🔴 오류 있음'}")
        print(f"- 요약: {original_result.summary}")
        print(f"- 이슈 수: {len(original_result.issues)}")
        print(f"- 복잡도 점수: {original_result.complexity_score}")
        
        if original_result.issues:
            print(f"\n📋 발견된 이슈들 ({len(original_result.issues)}건):")
            
            # 심각도별로 그룹화
            errors = [i for i in original_result.issues if i.severity == "error"]
            warnings = [i for i in original_result.issues if i.severity == "warning"]
            
            if errors:
                print(f"  🔴 오류 ({len(errors)}건):")
                for i, issue in enumerate(errors, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.field} - {issue.explanation}")
                    
            if warnings:
                print(f"  🟡 경고 ({len(warnings)}건):")
                for i, issue in enumerate(warnings, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.field} - {issue.explanation}")
        else:
            print(f"\n🎉 이슈가 발견되지 않았습니다!")
            
    except Exception as e:
        print(f"❌ 기존 분석기 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        original_result = None
    
    print("\n" + "="*60)
    print("🆕 RuleAnalyzerV2 테스트")
    print("="*60)
    
    try:
        # V2 분석기 테스트
        v2_analyzer = RuleAnalyzerV2()
        v2_result = await v2_analyzer.analyze_rule(test_rule)
        
        print(f"✅ V2 분석기 결과:")
        print(f"- 유효성: {'🟢 유효' if v2_result.is_valid else '🔴 오류 있음'}")
        print(f"- 요약: {v2_result.summary}")
        print(f"- 이슈 수: {len(v2_result.issues)}")
        print(f"- 복잡도 점수: {v2_result.complexity_score}")
        
        if v2_result.issues:
            print(f"\n📋 발견된 이슈들 ({len(v2_result.issues)}건):")
            
            # 심각도별로 그룹화
            errors = [i for i in v2_result.issues if i.severity == "error"]
            warnings = [i for i in v2_result.issues if i.severity == "warning"]
            
            if errors:
                print(f"  🔴 오류 ({len(errors)}건):")
                for i, issue in enumerate(errors, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.field} - {issue.explanation}")
                    
            if warnings:
                print(f"  🟡 경고 ({len(warnings)}건):")
                for i, issue in enumerate(warnings, 1):
                    print(f"    {i}. [{issue.issue_type}] {issue.field} - {issue.explanation}")
        else:
            print(f"\n🎉 이슈가 발견되지 않았습니다!")
            
    except Exception as e:
        print(f"❌ V2 분석기 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        v2_result = None
    
    print("\n" + "="*60)
    print("📊 비교 결과")
    print("="*60)
    
    if original_result and v2_result:
        print(f"📈 이슈 수 비교:")
        print(f"  - 기존: {len(original_result.issues)}건")
        print(f"  - V2:   {len(v2_result.issues)}건")
        print(f"  - 차이: {len(original_result.issues) - len(v2_result.issues):+d}건")
        
        # 이슈 타입별 비교
        original_types = set(issue.issue_type for issue in original_result.issues)
        v2_types = set(issue.issue_type for issue in v2_result.issues)
        
        print(f"\n📋 이슈 타입 비교:")
        print(f"  - 기존에만 있는 타입: {original_types - v2_types}")
        print(f"  - V2에만 있는 타입: {v2_types - original_types}")
        print(f"  - 공통 타입: {original_types & v2_types}")
        
        if len(original_result.issues) > len(v2_result.issues):
            print(f"\n⚠️  V2에서 놓친 이슈들:")
            for issue in original_result.issues:
                # V2에서 동일한 이슈가 있는지 확인
                v2_has_same = any(
                    v2_issue.issue_type == issue.issue_type and
                    v2_issue.field == issue.field and
                    v2_issue.explanation == issue.explanation
                    for v2_issue in v2_result.issues
                )
                if not v2_has_same:
                    print(f"  - [{issue.issue_type}] {issue.field}: {issue.explanation}")
    
    return original_result, v2_result

if __name__ == "__main__":
    original, v2 = asyncio.run(test_json_file())
    print("\n🎯 분석 완료!") 