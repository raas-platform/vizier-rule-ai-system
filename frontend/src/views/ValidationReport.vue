<template>
  <div class="validation-report">
    <h2>룰 검증 및 리포트</h2>
    <p class="description">기존 룰의 논리적 오류를 검증하고 상세 리포트를 생성합니다.</p>
    
    <div class="card">
      <form @submit.prevent="validateRule">
        <div class="form-group">
          <label for="rule-json">룰 JSON:</label>
          <textarea
            id="rule-json"
            v-model="ruleJson"
            rows="10"
            placeholder="검증할 룰의 JSON을 입력하세요"
            required
          ></textarea>
          <div v-if="jsonError" class="error">{{ jsonError }}</div>
        </div>
        
        <div class="form-actions">
          <button type="button" class="btn btn-primary" @click="validateRule" :disabled="isLoading">
            {{ isLoading ? '처리 중...' : '룰 검증하기' }}
          </button>
          <button type="button" class="btn btn-secondary" @click="generateReport" :disabled="!validationResult || isGeneratingReport">
            {{ isGeneratingReport ? '처리 중...' : '리포트 생성하기' }}
          </button>
        </div>
      </form>
    </div>
    
    <div v-if="error" class="error-message card">
      <h3>오류 발생</h3>
      <p>{{ error }}</p>
    </div>
    
    <div v-if="validationResult" class="validation-result card">
      <div class="result-header" :class="{ 'valid': validationResult.is_valid, 'invalid': !validationResult.is_valid }">
        <h3>{{ validationResult.is_valid ? '룰이 유효합니다' : '룰에 문제가 있습니다' }}</h3>
        <div class="result-badge" :class="{ 'valid': validationResult.is_valid, 'invalid': !validationResult.is_valid }">
          {{ validationResult.is_valid ? '유효' : '오류' }}
        </div>
      </div>
      
      <div class="summary">
        <h4>요약:</h4>
        <p>{{ validationResult.summary }}</p>
      </div>
      
      <div v-if="validationResult.structure" class="rule-structure">
        <h4>룰 구조:</h4>
        <ul>
          <li>조건 깊이: {{ validationResult.structure.depth }}</li>
          <li>조건 개수: {{ validationResult.structure.condition_count }}</li>
          <li>사용된 필드: {{ validationResult.structure.unique_fields.join(', ') }}</li>
        </ul>
      </div>
      
      <div v-if="validationResult.issue_counts" class="issue-counts">
        <h4>이슈 요약:</h4>
        <ul>
          <li v-for="(count, type) in validationResult.issue_counts" :key="type">
            {{ getIssueTypeText(type) }}: {{ count }}개
          </li>
        </ul>
      </div>
      
      <div v-if="validationResult.issues && validationResult.issues.length > 0" class="issues">
        <h4>발견된 문제:</h4>
        <ul class="issue-list">
          <li v-for="(issue, index) in validationResult.issues" :key="index" class="issue-item" :class="issue.severity">
            <div class="issue-header">
              <span class="issue-badge" :class="issue.severity">{{ getSeverityText(issue.severity) }}</span>
              <span v-if="issue.field" class="issue-field">{{ issue.field }}</span>
              <span v-if="issue.issue_type" class="issue-type">{{ getIssueTypeText(issue.issue_type) }}</span>
              <span v-if="issue.message" class="issue-message">{{ issue.message }}</span>
            </div>
            <div v-if="issue.location" class="issue-location">
              위치: {{ issue.location }}
            </div>
            <div v-if="issue.explanation" class="issue-explanation">
              {{ issue.explanation }}
            </div>
            <div v-if="issue.suggestion" class="issue-suggestion">
              {{ issue.suggestion }}
            </div>
          </li>
        </ul>
      </div>
    </div>
    
    <div v-if="reportResult" class="report-result card">
      <div class="result-header">
        <h3>상세 리포트</h3>
        <div v-if="reportResult.rule_name" class="rule-name">{{ getKoreanRuleName(reportResult.rule_name) }}</div>
      </div>
      
      <div class="report-content" v-html="formattedReport"></div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'
import apiService from '../services/apiService'
import type { Rule, ValidationResult } from '../types/rule'
import { marked } from 'marked'

export default defineComponent({
  name: 'ValidationReport',
  setup() {
    const ruleJson = ref('')
    const isLoading = ref(false)
    const isGeneratingReport = ref(false)
    const error = ref<string | null>(null)
    const validationResult = ref<ValidationResult | null>(null)
    const ruleSummary = ref<string | null>(null)
    const reportResult = ref<{ report: string, rule_id?: string, rule_name?: string } | null>(null)
    const formattedReport = ref<string>('')
    const originalJsonData = ref<any>(null)
    
    // severity 값을 한국어로 변환하는 함수
    const getSeverityText = (severity: string): string => {
      switch (severity) {
        case 'error':
          return '오류';
        case 'warning':
          return '경고';
        case 'info':
          return '정보';
        default:
          return severity;
      }
    }
    
    // 이슈 타입을 한국어로 변환하는 함수
    const getIssueTypeText = (issueType: string | undefined): string => {
      if (!issueType) return '';
      
      switch (issueType) {
        case 'duplicate_condition':
          return '중복 조건';
        case 'invalid_operator':
          return '잘못된 연산자';
        case 'contradiction':
          return '모순 조건';
        case 'type_mismatch':
          return '타입 불일치';
        case 'nested_redundancy':
          return '중첩 중복';
        case 'empty_group':
          return '빈 그룹';
        default:
          return issueType;
      }
    }
    
    // 룰 이름을 한국어로 변환하는 함수
    const getKoreanRuleName = (ruleName: string): string => {
      if (ruleName === 'Unnamed Rule') {
        return '이름 없는 룰';
      }
      return ruleName;
    }
    
    const jsonError = computed(() => {
      if (!ruleJson.value) return null
      
      try {
        JSON.parse(ruleJson.value)
        return null
      } catch (err: any) {
        return 'JSON 형식이 올바르지 않습니다: ' + err.message
      }
    })
    
    // 이모지 문자열을 실제 이모지로 변환하는 함수
    const parseEmojis = (text: string): string => {
      // 이모지 및 특수 기호 매핑
      const emojiMap: Record<string, string> = {
        ':white_check_mark:': '✅',
        ':x:': '❌',
        ':warning:': '⚠️',
        ':information_source:': 'ℹ️',
        ':bulb:': '💡',
        ':mag:': '🔍',
        ':chart_with_upwards_trend:': '📈',
        ':page_facing_up:': '📄',
        ':pushpin:': '📌',
        ':memo:': '📝',
        '#': '# ',
        '##': '## ',
        '###': '### ',
        '####': '#### ',
        '🔸': '• ',
        '✅': '✅ ',
        '❌': '❌ ',
        '⚠️': '⚠️ ',
        '💡': '💡 ',
        '📌': '📌 ',
        '📝': '📝 '
      }
      
      // 텍스트 내의 이모지 코드를 실제 이모지로 변환
      Object.entries(emojiMap).forEach(([code, emoji]) => {
        const regex = new RegExp(code.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
        text = text.replace(regex, emoji)
      })
      
      return text
    }
    
    // 마크다운 텍스트를 HTML로 변환하는 함수
    const renderMarkdown = (text: string): string => {
      try {
        // 이모지 파싱
        const textWithEmojis = parseEmojis(text)
        
        // 마크다운을 HTML로 변환
        const renderedHtml = marked.parse(textWithEmojis)
        console.log('렌더링된 HTML 결과 (일부):', renderedHtml.substring(0, 200))
        return renderedHtml
      } catch (error) {
        console.error('마크다운 렌더링 오류:', error)
        return `<p style="color: red;">보고서 형식 오류: ${error}</p><pre>${text}</pre>`
      }
    }
    
    const validateRule = async () => {
      if (jsonError.value) return
      
      error.value = null
      isLoading.value = true
      validationResult.value = null
      ruleSummary.value = null
      
      try {
        // JSON을 파싱
        const parsedData = JSON.parse(ruleJson.value)
        console.log('파싱된 룰 JSON:', parsedData);
        
        // 백업: 원본 JSON 데이터 저장
        originalJsonData.value = parsedData;
        
        // rule_json이 있는지 확인하고 적절한 요청 객체 생성
        const requestData = parsedData.rule_json ? parsedData : { rule_json: parsedData };
        
        // 직접 API 호출
        const response = await apiService.post('/api/v1/rules/validate-json', requestData);
        console.log('검증 응답:', response.data);
        
        // 응답 데이터를 저장
        validationResult.value = response.data;
      } catch (err: any) {
        console.error('검증 오류:', err);
        error.value = err.message || '처리 중 오류가 발생했습니다.';
      } finally {
        isLoading.value = false;
      }
    }
    
    const generateReport = async () => {
      if (!validationResult.value) return
      
      error.value = null
      isGeneratingReport.value = true
      reportResult.value = null
      formattedReport.value = ''
      
      try {
        console.log('====== 리포트 생성 API 호출 시작 ======');
        
        // 원본 JSON 데이터 가져오기 - 중요한 부분을 로그로 확인
        const originalRuleText = ruleJson.value;
        console.log('원본 룰 JSON 텍스트(일부):', originalRuleText.substring(0, 200));
        
        // JSON 파싱
        const parsedData = JSON.parse(originalRuleText);
        console.log('파싱된 데이터 구조(타입):', Object.prototype.toString.call(parsedData));
        console.log('파싱된 데이터 최상위 키:', Object.keys(parsedData));
        
        // rule_json이 있는지 확인
        const hasRuleJson = 'rule_json' in parsedData;
        console.log('rule_json 키 존재 여부:', hasRuleJson);
        
        // 실제 룰 데이터 추출
        const actualRuleData = hasRuleJson ? parsedData.rule_json : parsedData;
        console.log('실제 룰 데이터 키:', Object.keys(actualRuleData));
        
        // 조건 구조 검사
        if (actualRuleData.conditions) {
          const conditionsType = Object.prototype.toString.call(actualRuleData.conditions);
          console.log('조건 데이터 타입:', conditionsType);
          
          if (conditionsType === '[object Object]') {
            console.log('조건 객체 구조:', JSON.stringify(actualRuleData.conditions).substring(0, 200));
          } else if (conditionsType === '[object Array]') {
            console.log('조건 배열 길이:', actualRuleData.conditions.length);
          }
        } else {
          console.log('조건 데이터 없음');
        }
        
        // 필수 필드가 없는 경우 기본값 추가
        const preparedData = {
          name: actualRuleData.name || 'Unnamed Rule',
          description: actualRuleData.description || '',
          id: actualRuleData.id || actualRuleData.ruleId || 'R000',
          priority: actualRuleData.priority || 1,
          enabled: actualRuleData.enabled !== undefined ? actualRuleData.enabled : true,
          action: actualRuleData.action || {},
          conditions: [] // 기본값으로 빈 배열 설정
        };
        
        // 조건 데이터 특수 처리
        if (actualRuleData.conditions) {
          const conditionsType = Object.prototype.toString.call(actualRuleData.conditions);
          
          if (conditionsType === '[object Object]') {
            // 객체 형태의 조건 처리 (앵커 패턴)
            console.log('앵커 패턴 조건 구조 처리');
            preparedData.conditions = actualRuleData.conditions;
          } else if (conditionsType === '[object Array]') {
            // 배열 형태의 조건 처리
            console.log('배열 형태 조건 처리');
            preparedData.conditions = actualRuleData.conditions;
          } else {
            console.warn('조건 타입 불일치, 빈 배열로 대체');
            preparedData.conditions = [];
          }
        } else {
          console.warn('조건 데이터 없음, 빈 배열로 설정');
          preparedData.conditions = [];
        }
        
        console.log('전처리된 데이터(일부):', JSON.stringify(preparedData).substring(0, 200));
        
        // 원본 룰 데이터 전송
        const requestData = { rule_json: preparedData };
        console.log('리포트 API 요청 데이터(일부):', JSON.stringify(requestData).substring(0, 200));
        
        const response = await apiService.post('/api/v1/rules/report', requestData);
        console.log('리포트 응답 상태:', response.status);
        console.log('리포트 응답 데이터:', response.data);
        
        if (response.data && response.data.report) {
          reportResult.value = {
            report: response.data.report,
            rule_id: response.data.rule_id || 'Unknown',
            rule_name: response.data.rule_name || 'Unnamed Rule'
          };
          
          // 마크다운 렌더링
          console.log('마크다운 렌더링 시작');
          console.log('원본 마크다운(일부):', response.data.report.substring(0, 200));
          formattedReport.value = renderMarkdown(response.data.report);
          console.log('마크다운 렌더링 완료');
        } else {
          error.value = '리포트 데이터가 없거나 잘못된 형식입니다';
          console.error('잘못된 리포트 응답:', response.data);
        }
      } catch (err: any) {
        console.error('리포트 생성 오류:', err);
        error.value = err.message || '리포트 생성 중 오류가 발생했습니다.';
      } finally {
        isGeneratingReport.value = false;
        console.log('====== 리포트 생성 종료 ======');
      }
    }
    
    return {
      ruleJson,
      isLoading,
      isGeneratingReport,
      error,
      jsonError,
      validationResult,
      ruleSummary,
      reportResult,
      formattedReport,
      getSeverityText,
      getIssueTypeText,
      getKoreanRuleName,
      validateRule,
      generateReport
    }
  }
})
</script>

<style scoped>
.validation-report {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 3rem;
}

.description {
  margin-bottom: 1.5rem;
  color: var(--secondary-color);
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-actions {
  margin-top: 1.5rem;
}

.error-message {
  background-color: #fef2f2;
  border-left: 4px solid var(--danger-color);
  padding: 1rem;
  margin-top: 1.5rem;
}

.error-message h3 {
  color: var(--danger-color);
  margin-bottom: 0.5rem;
}

.card {
  background: #fff;
  border-radius: 0.8rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 1.5rem;
  margin-bottom: 2rem;
  transition: all 0.3s ease;
}

.validation-result, .report-result {
  margin-top: 2rem;
  overflow: hidden;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e5e7eb;
}

.result-header.valid h3 {
  color: var(--success-color);
}

.result-header.invalid h3 {
  color: var(--danger-color);
}

.result-badge {
  padding: 0.3rem 0.8rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.result-badge.valid {
  background-color: #dcfce7;
  color: #166534;
}

.result-badge.invalid {
  background-color: #fee2e2;
  color: #b91c1c;
}

.summary, .rule-summary, .rule-structure, .issue-counts {
  margin-bottom: 1.5rem;
  line-height: 1.6;
  padding: 1rem;
  background-color: #f9fafb;
  border-radius: 0.5rem;
}

.summary h4, .rule-summary h4, .rule-structure h4, .issue-counts h4 {
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
  color: #1f2937;
}

.issues {
  margin-top: 1.5rem;
}

.issue-list {
  list-style-type: none;
  padding: 0;
}

.issue-item {
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 0.6rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.issue-item.error {
  background-color: #fee2e2;
  border-left: 4px solid #b91c1c;
}

.issue-item.warning {
  background-color: #fef3c7;
  border-left: 4px solid #d97706;
}

.issue-item.info {
  background-color: #e0f2fe;
  border-left: 4px solid #0284c7;
}

.issue-header {
  display: flex;
  align-items: center;
  margin-bottom: 0.75rem;
}

.issue-badge {
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  margin-right: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.issue-badge.error {
  background-color: #b91c1c;
  color: white;
}

.issue-badge.warning {
  background-color: #d97706;
  color: white;
}

.issue-badge.info {
  background-color: #0284c7;
  color: white;
}

.issue-field {
  font-weight: 600;
  margin-right: 0.5rem;
}

.issue-type {
  font-size: 0.8rem;
  background-color: #f3f4f6;
  padding: 0.2rem 0.5rem;
  border-radius: 0.3rem;
  color: #4b5563;
}

.issue-location {
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
  color: #4b5563;
  background-color: rgba(255, 255, 255, 0.5);
  padding: 0.3rem 0.5rem;
  border-radius: 0.3rem;
}

.issue-explanation, .issue-suggestion {
  font-size: 0.875rem;
  margin-top: 0.5rem;
  background-color: rgba(255, 255, 255, 0.5);
  padding: 0.5rem;
  border-radius: 0.4rem;
}

.issue-suggestion {
  font-style: italic;
}

/* 리포트 스타일 개선 */
.report-result {
  position: relative;
  overflow: visible;
}

.report-result::before {
  content: '';
  position: absolute;
  top: -1.5rem;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #4f46e5, #6366f1, #818cf8);
  border-radius: 3px;
}

.report-result .result-header {
  background-color: #f8fafc;
  margin: -1.5rem -1.5rem 1.5rem -1.5rem;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
  border-radius: 0.8rem 0.8rem 0 0;
}

.report-result .result-header h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #334155;
}

.rule-name {
  font-size: 0.95rem;
  color: #64748b;
  font-weight: 500;
  background-color: #f1f5f9;
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
}

.report-content {
  line-height: 1.7;
  font-size: 0.95rem;
  color: #334155;
  padding: 0.5rem 0;
}

.report-content :deep(h1) {
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 2rem;
  margin-bottom: 1rem;
  color: #1e293b;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 0.5rem;
}

.report-content :deep(h2) {
  font-size: 1.3rem;
  font-weight: 600;
  margin-top: 1.8rem;
  margin-bottom: 0.9rem;
  color: #334155;
}

.report-content :deep(h3) {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 1.6rem;
  margin-bottom: 0.8rem;
  color: #475569;
}

.report-content :deep(p) {
  margin-bottom: 1.2rem;
  line-height: 1.7;
}

.report-content :deep(strong) {
  font-weight: 600;
  color: #1e293b;
}

.report-content :deep(em) {
  font-style: italic;
  color: #475569;
}

.report-content :deep(ul), 
.report-content :deep(ol) {
  margin-left: 1.5rem;
  margin-bottom: 1.2rem;
  margin-top: 0.5rem;
}

.report-content :deep(li) {
  margin-bottom: 0.5rem;
}

.report-content :deep(a) {
  color: #3b82f6;
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: all 0.2s;
}

.report-content :deep(a:hover) {
  color: #2563eb;
}

.report-content :deep(code) {
  background-color: #f1f5f9;
  padding: 0.2rem 0.4rem;
  border-radius: 0.25rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9rem;
  color: #0f172a;
  border: 1px solid #e2e8f0;
}

.report-content :deep(pre) {
  background-color: #f8fafc;
  padding: 1.2rem;
  border-radius: 0.6rem;
  overflow-x: auto;
  margin: 1.5rem 0;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.report-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
  border: none;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #334155;
}

.report-content :deep(blockquote) {
  margin: 1.5rem 0;
  padding: 0.8rem 1.2rem;
  border-left: 4px solid #818cf8;
  background-color: #f8fafc;
  color: #475569;
  font-style: italic;
  border-radius: 0 0.4rem 0.4rem 0;
}

.report-content :deep(blockquote p) {
  margin-bottom: 0;
}

.report-content :deep(hr) {
  margin: 2rem 0;
  border: 0;
  height: 1px;
  background: #e2e8f0;
}

.report-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  font-size: 0.9rem;
}

.report-content :deep(th) {
  background-color: #f1f5f9;
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #334155;
  border: 1px solid #e2e8f0;
}

.report-content :deep(td) {
  padding: 0.75rem 1rem;
  border: 1px solid #e2e8f0;
  vertical-align: top;
}

.report-content :deep(tr:nth-child(even)) {
  background-color: #f8fafc;
}

.btn-primary {
  background-color: #4f46e5;
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.btn-primary:hover {
  background-color: #4338ca;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.btn-primary:disabled {
  background-color: #a5b4fc;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #6b7280;
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-left: 0.5rem;
}

.btn-secondary:hover {
  background-color: #4b5563;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.btn-secondary:disabled {
  background-color: #d1d5db;
  cursor: not-allowed;
}

textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  line-height: 1.5;
  transition: border-color 0.2s, box-shadow 0.2s;
  resize: vertical;
}

textarea:focus {
  outline: none;
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.2);
}

.error {
  color: #dc2626;
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

.issue-message {
  font-weight: 500;
  margin-left: 0.5rem;
}
</style> 