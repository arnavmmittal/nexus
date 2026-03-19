/**
 * Nexus API Client
 * Handles all communication with the backend FastAPI server
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiOptions extends RequestInit {
  params?: Record<string, string>;
}

// Types matching backend schemas
export interface Skill {
  id: string;
  user_id: string;
  name: string;
  category: string;
  current_level: number;
  current_xp: number;
  total_xp: number;
  xp_for_next_level: number;
  level_progress: number;
  created_at: string;
  last_practiced: string | null;
}

export interface SkillCreate {
  name: string;
  category: string;
}

export interface SkillXPLogCreate {
  xp_amount: number;
  source?: string;
  description?: string;
}

export interface Goal {
  id: string;
  user_id: string;
  title: string;
  domain: string;
  target_type: string;
  target_value: number | null;
  current_value: number;
  unit: string | null;
  deadline: string | null;
  status: string;
  progress_percentage: number;
  is_completed: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface GoalCreate {
  title: string;
  domain: string;
  target_type?: string;
  target_value?: number;
  unit?: string;
  deadline?: string;
}

export interface GoalProgressCreate {
  new_value: number;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
}

export interface TodaysFocusData {
  date: string;
  focus_goals: Array<{
    id: string;
    title: string;
    progress: number;
    deadline: string | null;
  }>;
  active_streaks: Array<{
    activity: string;
    count: number;
    longest: number;
  }>;
  daily_tasks: Array<unknown>;
}

export interface SkillsWidgetData {
  top_skills: Array<{
    id: string;
    name: string;
    category: string;
    level: number;
    progress: number;
    total_xp: number;
  }>;
  recently_practiced: Array<{
    id: string;
    name: string;
    last_practiced: string | null;
  }>;
  weekly_xp: number;
  total_skills: number;
}

export interface GoalsWidgetData {
  active_count: number;
  completed_count: number;
  by_domain: Record<string, Array<{
    id: string;
    title: string;
    progress: number;
    deadline: string | null;
  }>>;
  recently_completed: Array<{
    id: string;
    title: string;
    completed_at: string | null;
  }>;
}

export interface MoneyWidgetData {
  status: string;
  message: string;
  summary: {
    net_worth: number | null;
    monthly_spending: number | null;
    monthly_income: number | null;
    savings_rate: number | null;
  };
}

export interface HealthWidgetData {
  status: string;
  message: string;
  summary: {
    steps_today: number | null;
    sleep_hours: number | null;
    exercise_minutes: number | null;
    heart_rate: number | null;
  };
}

export interface SynthesizeRequest {
  text: string;
  voice_id?: string;
  stability?: number;
  similarity_boost?: number;
  style?: number;
}

export interface VoiceChatRequest {
  text: string;
  conversation_id?: string;
  voice_id?: string;
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
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return response.json();
  }

  // ============ Chat endpoints ============
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return this.request('/api/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getChatHistory(conversationId: string) {
    return this.request<{ conversation_id: string; messages: Array<{ role: string; content: string }> }>(
      '/api/chat/history',
      { params: { conversation_id: conversationId } }
    );
  }

  async clearChatHistory(conversationId: string) {
    return this.request(`/api/chat/history/${conversationId}`, {
      method: 'DELETE',
    });
  }

  // WebSocket URL for streaming chat
  getWebSocketUrl(): string {
    const wsProtocol = this.baseUrl.startsWith('https') ? 'wss' : 'ws';
    const wsBase = this.baseUrl.replace(/^https?/, wsProtocol);
    return `${wsBase}/api/chat/stream`;
  }

  // ============ Skills endpoints ============
  async getSkills(options?: { category?: string; limit?: number; offset?: number }): Promise<Skill[]> {
    const params: Record<string, string> = {};
    if (options?.category) params.category = options.category;
    if (options?.limit) params.limit = String(options.limit);
    if (options?.offset) params.offset = String(options.offset);

    return this.request('/api/skills', { params: Object.keys(params).length ? params : undefined });
  }

  async createSkill(data: SkillCreate): Promise<Skill> {
    return this.request('/api/skills', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getSkill(skillId: string): Promise<{ skill: Skill; history: Array<unknown> }> {
    return this.request(`/api/skills/${skillId}`);
  }

  async logSkillXP(skillId: string, data: SkillXPLogCreate): Promise<Skill> {
    return this.request(`/api/skills/${skillId}/log`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteSkill(skillId: string): Promise<void> {
    return this.request(`/api/skills/${skillId}`, {
      method: 'DELETE',
    });
  }

  // ============ Goals endpoints ============
  async getGoals(options?: { status?: string; domain?: string; limit?: number; offset?: number }): Promise<Goal[]> {
    const params: Record<string, string> = {};
    if (options?.status) params.status_filter = options.status;
    if (options?.domain) params.domain = options.domain;
    if (options?.limit) params.limit = String(options.limit);
    if (options?.offset) params.offset = String(options.offset);

    return this.request('/api/goals', { params: Object.keys(params).length ? params : undefined });
  }

  async createGoal(data: GoalCreate): Promise<Goal> {
    return this.request('/api/goals', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getGoal(goalId: string): Promise<{ goal: Goal; progress_history: Array<unknown> }> {
    return this.request(`/api/goals/${goalId}`);
  }

  async updateGoal(goalId: string, data: Partial<GoalCreate & { status?: string }>): Promise<Goal> {
    return this.request(`/api/goals/${goalId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async logGoalProgress(goalId: string, data: GoalProgressCreate): Promise<Goal> {
    return this.request(`/api/goals/${goalId}/progress`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteGoal(goalId: string): Promise<void> {
    return this.request(`/api/goals/${goalId}`, {
      method: 'DELETE',
    });
  }

  // ============ Widget data endpoints ============
  async getTodaysFocus(): Promise<TodaysFocusData> {
    return this.request('/api/widgets/today');
  }

  async getMoneyData(): Promise<MoneyWidgetData> {
    return this.request('/api/widgets/money');
  }

  async getSkillsWidget(): Promise<SkillsWidgetData> {
    return this.request('/api/widgets/skills');
  }

  async getHealthData(): Promise<HealthWidgetData> {
    return this.request('/api/widgets/health');
  }

  async getGoalsWidget(): Promise<GoalsWidgetData> {
    return this.request('/api/widgets/goals');
  }

  // ============ Voice endpoints ============
  async synthesizeSpeech(data: SynthesizeRequest): Promise<Response> {
    const response = await fetch(`${this.baseUrl}/api/voice/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Voice API Error: ${response.status}`);
    }

    return response;
  }

  async voiceChat(data: VoiceChatRequest): Promise<Response> {
    const response = await fetch(`${this.baseUrl}/api/voice/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Voice Chat Error: ${response.status}`);
    }

    return response;
  }

  async voiceChatText(data: VoiceChatRequest): Promise<{ conversation_id: string; text_response: string }> {
    return this.request('/api/voice/chat/text', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async transcribeAudio(audioBlob: Blob, language?: string): Promise<{ text: string; language: string | null }> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.webm');
    if (language) {
      formData.append('language', language);
    }

    const response = await fetch(`${this.baseUrl}/api/voice/transcribe`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `Transcription Error: ${response.status}`);
    }

    return response.json();
  }

  async getVoices(): Promise<{ voices: Array<{ voice_id: string; name: string }> }> {
    return this.request('/api/voice/voices');
  }

  async getVoiceStatus(): Promise<{ status: string; tts_provider?: string; error?: string }> {
    return this.request('/api/voice/status');
  }

  // ============ Memory endpoints ============
  async searchMemory(query: string): Promise<Array<{ content: string; score: number }>> {
    return this.request('/api/memory/search', {
      params: { query },
    });
  }
}

export const api = new ApiClient(API_BASE_URL);
export default api;
