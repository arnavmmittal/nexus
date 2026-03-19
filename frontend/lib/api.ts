/**
 * Nexus API Client
 * Handles all communication with the backend FastAPI server
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiOptions extends RequestInit {
  params?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options;

    let url = `${this.baseUrl}${endpoint}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        ...fetchOptions.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Chat endpoints
  async sendMessage(content: string) {
    return this.request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async getChatHistory() {
    return this.request('/api/chat/history');
  }

  // Widget data endpoints
  async getTodaysFocus() {
    return this.request('/api/widgets/today');
  }

  async getMoneyData() {
    return this.request('/api/widgets/money');
  }

  async getSkillsData() {
    return this.request('/api/widgets/skills');
  }

  async getHealthData() {
    return this.request('/api/widgets/health');
  }

  async getGoalsData() {
    return this.request('/api/widgets/goals');
  }

  // Skills endpoints
  async getSkills() {
    return this.request('/api/skills');
  }

  async logSkillXP(skillId: string, xp: number, description?: string) {
    return this.request(`/api/skills/${skillId}/log`, {
      method: 'POST',
      body: JSON.stringify({ xp_amount: xp, description }),
    });
  }

  // Goals endpoints
  async getGoals() {
    return this.request('/api/goals');
  }

  async updateGoalProgress(goalId: string, value: number) {
    return this.request(`/api/goals/${goalId}/progress`, {
      method: 'POST',
      body: JSON.stringify({ new_value: value }),
    });
  }

  // Memory endpoints
  async searchMemory(query: string) {
    return this.request('/api/memory/search', {
      params: { query },
    });
  }
}

export const api = new ApiClient(API_BASE_URL);
export default api;
