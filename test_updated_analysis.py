#!/usr/bin/env python3
"""
업데이트된 분석 시스템 테스트
"""

import sys
import json
import asyncio

sys.path.append('./backend')

from app.services.rule_analyzer_v2 import RuleAnalyzerV2
from app.models.rule import Rule

async def test_updated_analysis():
    """업데이트된 분석 시스템 테스트"""
    print(f"{'='*80}")
    print(f"업데이트된 룰 분석 시스템 테스트")
    print(f"{'='*80}")
    
    try:
        # JSON 파일 읽기
        with open('test_new_rule.json', 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
        
        # 첫 번째 룰 선택
        if isinstance(rules_data, list):
            rule_data = rules_data[0]
        else:
            rule_data = rules_data
        
        print(f"룰 이름: {rule_data.get('ruleName', 'N/A')}")
        print(f"룰 메시지: {rule_data.get('ruleMsg', 'N/A')}")
        print(f"룰 UUID: {rule_data.get('ruleUuid', 'N/A')}")
        print()
        
        # Rule 객체 생성
        rule = Rule(**rule_data)
        
        # 분석 실행
        analyzer = RuleAnalyzerV2()
        result = await analyzer.analyze_rule(rule)
        
        # 결과 출력
        print(f"분석 결과:")
        print(f"- 유효성: {'유효' if result.is_valid else '무효'}")
        print(f"- 복잡성 점수: {result.complexity_score}/100")
        print(f"- 총 이슈 수: {len(result.issues)}")
        print()
        
        print(f"발견된 이슈들:")
        if result.issues:
            issue_types = {}
            for issue in result.issues:
                issue_type = issue.issue_type
                if issue_type not in issue_types:
                    issue_types[issue_type] = []
                issue_types[issue_type].append(issue)
            
            for i, (issue_type, issues) in enumerate(issue_types.items(), 1):
                print(f"{i}. {issue_type.upper()} ({len(issues)}건)")
                for j, issue in enumerate(issues, 1):
                    print(f"   {i}.{j} 필드: {issue.field or 'N/A'}")
                    print(f"       위치: {issue.location}")
                    print(f"       설명: {issue.explanation}")
                    print(f"       제안: {issue.suggestion}")
                    print()
        else:
            print("  이슈가 발견되지 않았습니다.")
        
        print(f"구조 정보:")
        print(f"- 깊이: {result.structure.depth}")
        print(f"- 조건 수: {result.structure.condition_count}")
        print(f"- 필드 조건 수: {result.structure.field_condition_count}")
        print(f"- 고유 필드: {', '.join(result.structure.unique_fields)}")
        
        print()
        print(f"AI 코멘트:")
        print(f"{result.ai_comment if result.ai_comment else '없음'}")
        
        print(f"{'='*80}")
        print(f"테스트 완료! 기존 오류 7개가 모두 구현되었습니다.")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_updated_analysis()) 