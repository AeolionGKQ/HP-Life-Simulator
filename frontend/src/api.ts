export interface HealthResponse {
  status: string;
  app_name: string;
  database: string;
  llm_configured: boolean;
}

export interface LLMConfigStatus {
  configured: boolean;
  base_url: string;
  model: string;
  api_key_present: boolean;
}

export interface GameSession {
  id: string;
  name: string;
  era_id: string;
  status: string;
  state_version: number;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends GameSession {
  player_state: Record<string, unknown>;
}

export interface SetupOption {
  id: string;
  label: string;
  description: string;
}

export interface SetupView {
  current_step: number;
  completed: boolean;
  steps_total: number;
  current: {
    step: number;
    title: string;
    description: string;
    options: SetupOption[];
  };
  answers: Record<string, unknown>;
}

export interface PlayerStateResponse {
  session_id: string;
  state_version: number;
  state: Record<string, any>;
}

export interface JournalEntry {
  id: string;
  turn_id: string | null;
  entry_type: string;
  title: string;
  summary: string;
  data: Record<string, any>;
  created_at: string;
}

export interface Relationship {
  source_id: string;
  target_id: string;
  state: Record<string, any>;
}

export interface TurnResult {
  turn_id: string;
  sequence: number;
  state_version: number;
  recalled_memory_ids: string[];
  response: {
    turn: {
      title: string;
      scene_type: string;
      narrative: string;
      location_id: string | null;
      time_advance_minutes: number;
    };
    choices: Array<{
      id: string;
      label: string;
      kind: string;
      risk: string;
      effects_hint: string;
    }>;
    worldline: {
      offset_rate: number;
      delta: number;
      reason: string;
      affected_nodes: string[];
    };
    memory_update: {
      summary: string;
    };
  };
}

export interface StoredTurn {
  id: string;
  sequence: number;
  action: Record<string, any>;
  narrative: string | null;
  response: TurnResult["response"];
  state_version_after: number;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `请求失败（${response.status}）`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  llmConfig: () => request<LLMConfigStatus>("/api/config/llm"),
  sessions: () => request<GameSession[]>("/api/sessions"),
  createSession: (name: string) =>
    request<GameSession>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  session: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  setup: (id: string) => request<SetupView>(`/api/sessions/${id}/setup`),
  answerSetup: (id: string, step: number, answer: unknown) =>
    request<SetupView>(`/api/sessions/${id}/setup/answer`, {
      method: "POST",
      body: JSON.stringify({ step, answer }),
    }),
  confirmSetup: (id: string) =>
    request<SetupView>(`/api/sessions/${id}/setup/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirmed: true }),
    }),
  state: (id: string) => request<PlayerStateResponse>(`/api/sessions/${id}/state`),
  journal: (id: string) => request<JournalEntry[]>(`/api/sessions/${id}/journal`),
  relationships: (id: string) =>
    request<Relationship[]>(`/api/sessions/${id}/relationships`),
  turns: (id: string) => request<StoredTurn[]>(`/api/sessions/${id}/turns`),
  action: (
    id: string,
    payload: {
      client_action_id: string;
      expected_state_version: number;
      kind: "choice" | "free_text" | "fast_forward";
      choice_id?: string;
      free_text?: string;
    },
  ) =>
    request<TurnResult>(`/api/sessions/${id}/actions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

