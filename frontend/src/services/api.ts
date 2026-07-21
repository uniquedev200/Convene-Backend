const getApiBaseUrl = () => {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("convene_api_base");
    if (saved) return saved;
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

export const API_BASE = getApiBaseUrl();

export interface Preset {
  preset_id: string;
  display_name: string;
  personas: string[];
}

export interface ToolInfo {
  name: string;
  description: string;
}

export interface DebateCreateInput {
  preset_id: string;
  question: string;
  options: string[];
  constraints: {
    team_size: number;
    timeline: string;
    budget?: string;
  };
}

export interface ToolCall {
  tool_name: string;
  query: string;
  result_summary: string;
}

export interface AgentStance {
  agent_name: string;
  option: string;
  score: number;
  reasoning: string;
  tool_calls_used?: ToolCall[];
}

export interface CrossExamMessage {
  from_agent: string;
  to_agent: string;
  challenge: string;
  response: string;
}

export interface OptionResult {
  option: string;
  average_score: number;
  why_it_lost?: string;
}

export interface ConsensusResult {
  winning_option: string;
  confidence_pct: number;
  agreement_pct: number;
  rationale: string;
  option_breakdown: OptionResult[];
  risks?: string[];
}

export interface DebateResult {
  debate_id: string;
  question: string;
  preset_id: string;
  options: string[];
  status: string;
  created_at: string;
  agent_stances: AgentStance[];
  cross_exam_transcript: CrossExamMessage[];
  consensus: ConsensusResult;
  user_id: string | null;
}

export interface DebateSummary {
  id: string;
  question: string;
  preset_id: string;
  status: string;
  created_at: string;
}

export function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("convene_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const api = {
  async getPresets(): Promise<Preset[]> {
    const res = await fetch(`${API_BASE}/presets`);
    if (!res.ok) throw new Error("Failed to load presets");
    return res.json();
  },

  async getTools(): Promise<Record<string, ToolInfo[]>> {
    const res = await fetch(`${API_BASE}/tools`);
    if (!res.ok) throw new Error("Failed to load tools");
    return res.json();
  },

  async signup(email: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signup failed");
    return data;
  },

  async login(email: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    return data;
  },

  async exchangeOAuthToken(accessToken: string) {
    const res = await fetch(`${API_BASE}/auth/oauth-exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: accessToken }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "OAuth exchange failed");
    return data;
  },

  async createDebate(input: DebateCreateInput): Promise<{ debate_id: string }> {
    const res = await fetch(`${API_BASE}/debate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(input),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to create debate");
    return data;
  },

  async getDebateResult(debateId: string): Promise<DebateResult> {
    const res = await fetch(`${API_BASE}/debate/${debateId}/result`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Failed to retrieve debate result");
    }
    return res.json();
  },

  async getMyDebates(): Promise<DebateSummary[]> {
    const res = await fetch(`${API_BASE}/debates/mine`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Failed to retrieve debates history");
    return res.json();
  },
};
