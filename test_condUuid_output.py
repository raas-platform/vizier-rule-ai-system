#!/usr/bin/env python3
import asyncio
import json
import sys
sys.path.append('./backend')

from app.models.rule import Rule
from app.services.rule_analyzer_v2 import RuleAnalyzerV2

async def test_condUuid_output():
    """condUuid 정보가 출력에 포함되는지 테스트"""
    
    print("=== condUuid 출력 테스트 ===")
    
    # JSON 파일 읽기
    with open('test_new_rule.json', 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    
    rule_json = rules_data[0]
    test_rule = Rule(**rule_json)
    
    print(f"📊 테스트 룰: {rule_json['ruleName']}")
    
    # 분석기 초기화
    analyzer = RuleAnalyzerV2()
    
    # 룰 분석 실행
    result = await analyzer.analyze_rule(test_rule)
    
    print(f"\n✅ 분석 완료!")
    print(f"- 유효성: {'🟢 유효' if result.is_valid else '🔴 오류 있음'}")
    print(f"- 이슈 수: {len(result.issues)}")
    
    # Structure 정보 확인
    print(f"\n📋 구조 정보:")
    print(f"  * 깊이: {result.structure.depth}")
    print(f"  * 전체 조건 노드 수: {result.structure.condition_node_count}")
    print(f"  * 필드 조건 수: {result.structure.field_condition_count}")
    print(f"  * 고유 필드 수: {len(result.structure.unique_fields)}")
    
    # 이슈에서 condUuid 확인
    print(f"\n🚨 이슈에서 condUuid 확인:")
    for i, issue in enumerate(result.issues[:5], 1):  # 처음 5개만 표시
        print(f"  이슈 {i}:")
        print(f"    - condUuid: {issue.condUuid}")
        print(f"    - issue_type: {issue.issue_type}")
        print(f"    - field: {issue.field}")
        print(f"    - severity: {issue.severity}")
    
    # JSON 출력 샘플
    print(f"\n📤 JSON 출력 샘플:")
    print("Structure:")
    structure_dict = result.structure.model_dump()
    print(json.dumps(structure_dict, indent=2, ensure_ascii=False)[:500] + "...")
    
    print("\nFirst Issue:")
    if result.issues:
        first_issue_dict = result.issues[0].model_dump()
        print(json.dumps(first_issue_dict, indent=2, ensure_ascii=False))
    
    # condUuid 통계
    condUuid_stats = {
        "total_issues": len(result.issues),
        "issues_with_condUuid": len([i for i in result.issues if i.condUuid is not None]),
        "issues_without_condUuid": len([i for i in result.issues if i.condUuid is None]),
    }
    
    print(f"\n📊 condUuid 통계:")
    print(f"  * 전체 이슈 수: {condUuid_stats['total_issues']}")
    print(f"  * condUuid 있는 이슈: {condUuid_stats['issues_with_condUuid']}")
    print(f"  * condUuid 없는 이슈: {condUuid_stats['issues_without_condUuid']}")
    
    # 이슈 타입별 condUuid 현황
    issue_type_condUuid = {}
    for issue in result.issues:
        issue_type = issue.issue_type
        if issue_type not in issue_type_condUuid:
            issue_type_condUuid[issue_type] = {"with_uuid": 0, "without_uuid": 0}
        
        if issue.condUuid:
            issue_type_condUuid[issue_type]["with_uuid"] += 1
        else:
            issue_type_condUuid[issue_type]["without_uuid"] += 1
    
    print(f"\n📋 이슈 타입별 condUuid 현황:")
    for issue_type, stats in issue_type_condUuid.items():
        total = stats["with_uuid"] + stats["without_uuid"]
        uuid_rate = (stats["with_uuid"] / total) * 100 if total > 0 else 0
        print(f"  * {issue_type}: {stats['with_uuid']}/{total} ({uuid_rate:.1f}%)")

if __name__ == "__main__":
    asyncio.run(test_condUuid_output()) 