import axios from 'axios';
import type {
  Rule,
  RuleValidationResponse,
  RuleReportRequest,
  RuleReportResponse
} from '../types/rule';

// API 설정
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// 디버깅을 위한 인터셉터 추가
apiClient.interceptors.request.use(
  (config) => {
    console.log('API 요청:', config.method, config.url, config.data);
    return config;
  },
  (error) => {
    console.error('API 요청 에러:', error);
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    console.log('API 응답:', response.status, response.data);
    return response;
  },
  (error) => {
    console.error('API 응답 에러:', error.response?.status, error.response?.data);
    return Promise.reject(error);
  }
);

// API 오류 핸들러
const handleApiError = (error: any): never => {
  console.error('API Error:', error);
  
  let errorMessage = 'API 요청 중 오류가 발생했습니다';
  
  if (error.response) {
    // 서버에서 응답한 오류
    const serverError = error.response.data;
    errorMessage = serverError.detail || `서버 오류: ${error.response.status}`;
  } else if (error.request) {
    // 요청은 보냈지만 응답이 없는 경우
    errorMessage = '서버에서 응답이 없습니다. 네트워크를 확인해주세요.';
  }
  
  throw new Error(errorMessage);
};

// API 서비스
export default {
  // 룰 검증 API
  async validateRuleJson(ruleJson: any): Promise<RuleValidationResponse> {
    try {
      console.log('validateRuleJson 요청:', ruleJson);
      const formattedRequest = { rule_json: ruleJson };
      const response = await apiClient.post<RuleValidationResponse>('/api/v1/rules/validate-json', formattedRequest);
      console.log('validateRuleJson 응답:', response.data);
      return response.data;
    } catch (error) {
      console.error('validateRuleJson 에러:', error);
      return handleApiError(error);
    }
  },
  
  // 룰 리포트 생성 API
  async generateRuleReport(request: RuleReportRequest): Promise<RuleReportResponse> {
    try {
      console.log('generateRuleReport 요청:', request);
      const response = await apiClient.post<RuleReportResponse>('/api/v1/rules/report', request);
      console.log('generateRuleReport 응답:', response.data);
      return response.data;
    } catch (error) {
      console.error('generateRuleReport 에러:', error);
      return handleApiError(error);
    }
  },

  async post(url: string, data: any): Promise<any> {
    try {
      const response = await apiClient.post(url, data);
      return response;
    } catch (error) {
      console.error('API 요청 에러:', error);
      return handleApiError(error);
    }
  }
}; 