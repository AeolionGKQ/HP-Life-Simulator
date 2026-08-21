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

export interface LLMConnectionResult {
  success: boolean;
  model: string;
  message: string;
  latency_ms: number;
}

export interface EraInfo {
  id: string;
  name: string;
  years: string;
  eyebrow: string;
  title: string;
  description: string;
  mainline: string;
  atmosphere: string;
  available: boolean;
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
  value: string | null;
  category: string;
  appendable: boolean;
  available: boolean;
}

export interface SetupView {
  current_step: number;
  completed: boolean;
  steps_total: number;
  era_id: string;
  current: {
    step: number;
    title: string;
    description: string;
    options: SetupOption[];
    selection_mode: "single" | "append" | "text" | "confirm";
  };
  answers: Record<string, unknown>;
  attribute_initialization: Record<string, any>;
}

export interface PlayerStateResponse {
  session_id: string;
  state_version: number;
  state: Record<string, any>;
}

export interface CourseOption {
  id: string;
  name: string;
  description: string;
  category: string;
  available: boolean;
  unavailable_reason: string | null;
  skill_id: string;
  skill_level: number;
}

export interface CourseSkill {
  id: string;
  name: string;
  description: string;
  level: number;
  experience: number;
  source: string;
  course_id: string;
}

export interface CourseSelection {
  status: "pending" | "completed" | null;
  phase: "elective" | "newt" | null;
  min_courses: number;
  max_courses: number;
  available_course_ids: string[];
}

export interface CourseResult {
  id: string;
  name: string;
  grade: string;
}

export interface CourseHistoryEntry {
  school_year: string;
  grade: string;
  active_courses: string[];
  selected_courses: string[];
  skill_progression: Record<string, number>;
}

export interface CourseView {
  session_id: string;
  state_version: number;
  grade: string;
  school_year: string;
  term: string;
  active_courses: CourseOption[];
  selection_options: CourseOption[];
  editable_phase: "elective" | "newt" | null;
  elective_courses: string[];
  newt_courses: string[];
  skills: CourseSkill[];
  owl_results: CourseResult[];
  newt_results: CourseResult[];
  course_selection: CourseSelection | null;
  course_history: CourseHistoryEntry[];
}

export interface CourseSelectionRequest {
  expected_state_version: number;
  selection_phase: "elective" | "newt";
  course_ids: string[];
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

export interface NPCState {
  npc_id: string;
  is_original_character: boolean;
  state: Record<string, any>;
}

export interface PlayerChanges {
  inventory_add: Array<Record<string, any>>;
  inventory_remove: string[];
  status_add: Array<Record<string, any>>;
  status_remove: string[];
  skill_add: Array<Record<string, any>>;
  skill_remove: string[];
  skill_deltas: Record<string, number>;
  skill_experience_deltas: Record<string, number>;
  course_skill_deltas: Record<string, number>;
  trait_add: Array<Record<string, any>>;
  trait_remove: string[];
  resource_deltas: Array<{
    id: string;
    delta: number;
    reason_code: string;
    reason: string;
  }>;
  dimension_deltas: Array<{
    id: string;
    delta: number;
    reason_code: string;
    reason: string;
  }>;
  resource_cap_deltas: Array<Record<string, any>>;
  dimension_cap_deltas: Array<Record<string, any>>;
  reputation_deltas: Record<string, number>;
  relationship_deltas: Array<Record<string, any>>;
  relationship_creations: Array<Record<string, any>>;
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
      current_date: string;
      location_id: string;
      time_advance_minutes?: number;
    };
    choices: Array<{
      id: string;
      label: string;
      kind: string;
      risk: "low" | "medium" | "high" | "fatal";
      effects_hint: string;
      effects: {
        gains: Array<{
          id: string;
          name: string;
          type: string;
          direction: string;
          description: string;
        }>;
        losses: Array<{
          id: string;
          name: string;
          type: string;
          direction: string;
          description: string;
        }>;
        note: string;
      };
    }>;
    worldline: {
      offset_rate: number;
      delta: number;
      reason: string;
      affected_nodes: string[];
    };
    player_changes: PlayerChanges;
    applied_changes: PlayerChanges;
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
    const detail = body.detail;
    const message = typeof detail === "string"
      ? detail
      : detail
        ? JSON.stringify(detail)
        : `请求失败（${response.status}）`;
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  llmConfig: () => request<LLMConfigStatus>("/api/config/llm"),
  eras: () => request<EraInfo[]>("/api/content/eras"),
  updateLlmConfig: (payload: { base_url: string; api_key: string; model: string }) =>
    request<LLMConfigStatus>("/api/config/llm", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  testLlm: (payload?: { base_url: string; api_key: string; model: string }) =>
    request<LLMConnectionResult>("/api/llm/test", {
      method: "POST",
      body: payload ? JSON.stringify(payload) : undefined,
    }),
  sessions: () => request<GameSession[]>("/api/sessions"),
  createSession: (name: string) =>
    request<GameSession>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  renameSession: (id: string, name: string) =>
    request<GameSession>(`/api/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteSession: (id: string) =>
    request<void>(`/api/sessions/${id}`, { method: "DELETE" }),
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
  initializeAttributes: (id: string) =>
    request<SetupView>(`/api/sessions/${id}/attributes/initialize`, {
      method: "POST",
    }),
  state: (id: string) => request<PlayerStateResponse>(`/api/sessions/${id}/state`),
  courses: (id: string) => request<CourseView>(`/api/sessions/${id}/courses`),
  acknowledgeDepartureNotice: (id: string) =>
    request<PlayerStateResponse>(`/api/sessions/${id}/departure-notice/acknowledge`, {
      method: "POST",
    }),
  selectCourses: (id: string, payload: CourseSelectionRequest) =>
    request<CourseView>(`/api/sessions/${id}/courses`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  journal: (id: string) => request<JournalEntry[]>(`/api/sessions/${id}/journal`),
  relationships: (id: string) =>
    request<Relationship[]>(`/api/sessions/${id}/relationships`),
  npcs: (id: string) => request<NPCState[]>(`/api/sessions/${id}/npcs`),
  turns: (id: string) => request<StoredTurn[]>(`/api/sessions/${id}/turns`),
  action: (
    id: string,
    payload: {
      client_action_id: string;
      expected_state_version: number;
    kind:
      | "choice"
      | "free_text"
      | "fast_forward"
      | "fate_intervention"
      | "reshape_fate";
    choice_id?: string;
    free_text?: string;
    fate_instruction?: string;
    reshape_instruction?: string;
    },
  ) =>
    request<TurnResult>(`/api/sessions/${id}/actions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

