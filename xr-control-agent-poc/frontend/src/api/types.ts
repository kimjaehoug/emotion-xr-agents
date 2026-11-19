// 백엔드 Pydantic 스키마와 1:1로 대응하는 타입 정의.
// 참고: backend/app/schemas/api.py, action_plan.py, state_report.py

export type StateLevel = "NORMAL" | "WATCH" | "ACTION_REQUIRED" | "UNKNOWN";

export type PlanGoal =
  | "MAINTAIN_CURRENT_STATE"
  | "REDUCE_COGNITIVE_BURDEN"
  | "SUPPORT_ATTENTION_RECOVERY"
  | "REDUCE_ACCUMULATED_FATIGUE"
  | "REDUCE_CONTENT_STIMULATION"
  | "CONTINUE_OBSERVATION";

export type PlanRoute =
  | "NO_ACTION"
  | "OBSERVATION"
  | "CONTENT_RECOMMENDATION"
  | "XR_OPTIMIZATION"
  | "BREAK_SUGGESTION";

export type ActionType =
  | "OBSERVE"
  | "KEEP_CURRENT_STATE"
  | "RECOMMEND_CONTENT"
  | "UPDATE_XR_PARAMETER"
  | "SUGGEST_BREAK";

export type XrParameter =
  | "visual_complexity"
  | "audio_stimulation"
  | "interaction_density"
  | "information_density"
  | "motion_intensity";

export type PlannerSource = "qwen3.5_9b" | "rule_based_fallback" | string;

// ----------------------------------------------------------------------
// StateReport (상태 인지 Agent 산출물 / XR Control Agent 입력)
// ----------------------------------------------------------------------
export interface MetricGapLite {
  status: "above_baseline" | "below_baseline" | "within_range" | "unknown";
  deviation?: number | null;
  relative_deviation?: number | null;
  trend?: "increasing" | "decreasing" | "stable" | "insufficient_data";
  persistent?: boolean;
  current?: number | null;
  baseline?: number | null;
}

export interface BaselineInfo {
  source?: "personal" | "group_default" | "none";
  version?: string | null;
  reliability?: number | null;
}

export interface EmotionContext {
  label?: string | null;
  intensity?: number | null;
  confidence?: number | null;
}

export interface CandidateCause {
  type: string;
  factor: string;
  confidence: number;
}

export interface ContextSummary {
  content_id?: string | null;
  content_type?: string | null;
  difficulty?: number | null;
  visual_complexity?: number | null;
  audio_stimulation?: number | null;
  interaction_density?: number | null;
  elapsed_time_min?: number | null;
}

export interface StateReport {
  state_report_id: string;
  user_id: string;
  session_id: string;
  timestamp: string;
  state_level: StateLevel;
  baseline?: BaselineInfo;
  cognitive_gap?: Record<string, MetricGapLite>;
  emotion_context?: EmotionContext | null;
  context_summary?: ContextSummary;
  candidate_causes?: CandidateCause[];
  analysis_confidence: number;
  requires_response?: boolean;
  additional_observation_required?: boolean;
  warnings?: string[];
  possible_contributing_factors?: string[];
  narrative_observation?: string | null;
}

// ----------------------------------------------------------------------
// ActionPlan / PlanAction
// ----------------------------------------------------------------------
export interface PlanAction {
  action_type: ActionType;
  xr_parameter?: XrParameter | null;
  target_content_id?: string | null;
  delta?: number | null;
  final_value?: number | null;
  requires_confirmation: boolean;
  rationale: string;
  confidence?: number | null;
}

export interface ActionPlan {
  plan_id: string;
  state_report_id: string;
  user_id: string;
  session_id: string;
  goal: PlanGoal;
  route: PlanRoute;
  planner_source: PlannerSource;
  actions: PlanAction[];
  confidence: number;
  warnings: string[];
  narrative?: string | null;
  content_candidates: Record<string, unknown>[];
  created_at: string;
  executed: boolean;
  idempotent_replay: boolean;
  // 백엔드가 아직 노출하지 않는 필드(있다면 활용, Prompt Preview 탭에서 사용).
  prompt_preview?: string | null;
  sanitized_prompt?: string | null;
}

export type PlanResponse = ActionPlan;

// ----------------------------------------------------------------------
// Execute / Confirmation / Feedback
// ----------------------------------------------------------------------
export interface ConfirmationResponse {
  confirmation_id: string;
  plan_id: string;
  user_id: string;
  session_id: string;
  action_index: number;
  action: PlanAction;
  status: "PENDING" | "ACCEPTED" | "REJECTED";
  created_at: string;
  resolved_at?: string | null;
}

export interface ExecutionResponse {
  execution_id: string;
  plan_id: string;
  confirmation_id?: string | null;
  user_id: string;
  session_id: string;
  action: PlanAction;
  status: "SUCCESS" | "FAILED" | string;
  result: Record<string, unknown>;
  feedback_effect?: "positive" | "neutral" | "negative" | null;
  created_at: string;
}

export interface ExecuteResponse {
  plan_id: string;
  already_executed: boolean;
  confirmations: ConfirmationResponse[];
  executions: ExecutionResponse[];
}

export interface ConfirmationDecisionRequest {
  decision: "ACCEPTED" | "REJECTED";
}

export interface FeedbackRequest {
  execution_id: string;
  effect: "positive" | "neutral" | "negative";
  comment?: string | null;
}

export interface FeedbackResponse {
  execution_id: string;
  effect: string;
  profile_updated: boolean;
}

// ----------------------------------------------------------------------
// Memory (Episode / Summary)
// ----------------------------------------------------------------------
export interface XrEpisodeResponse {
  id: number;
  user_id: string;
  session_id: string;
  state_report_id: string;
  state_level: string;
  route: string;
  planner_source: string;
  plan: Record<string, unknown>;
  created_at: string;
}

export interface XrSummaryResponse {
  user_id: string;
  summary: Record<string, unknown>;
  recent_episode_count: number;
  updated_at?: string | null;
}

// ----------------------------------------------------------------------
// Users / Policies / Actions / Contents
// ----------------------------------------------------------------------
export interface UserProfile {
  auto_control_allowed: boolean;
  forbidden_categories: string[];
  sensitivities: Record<string, number>;
  rejected_actions: string[];
  notes?: string | null;
}

export interface UserResponse {
  user_id: string;
  profile: UserProfile;
  created_at: string;
  updated_at: string;
}

export interface PolicyResponse {
  id: number;
  policy_key: string;
  state_level: string;
  min_confidence: number;
  allowed_routes: string[];
  description?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ActionCatalogResponse {
  id: number;
  action_type: string;
  xr_parameter?: string | null;
  category?: string | null;
  max_delta?: number | null;
  requires_confirmation: boolean;
  description?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ContentResponse {
  id: number;
  content_id: string;
  title: string;
  content_type: string;
  category?: string | null;
  difficulty: number;
  visual_complexity: number;
  audio_stimulation: number;
  interaction_density: number;
  tags: string[];
  is_active: boolean;
  created_at: string;
}

// ----------------------------------------------------------------------
// Seed / LLM
// ----------------------------------------------------------------------
export interface SeedResponse {
  message: string;
  users_created: string[];
  policies_created: number;
  actions_created: number;
  contents_created: number;
}

export interface LLMHealthResponse {
  reachable: boolean;
  base_url: string;
  model: string;
  detail?: string | null;
}

export interface TestLLMRequest {
  system_prompt?: string | null;
  user_prompt: string;
}

export interface TestLLMResponse {
  raw_output: string;
  parsed?: Record<string, unknown> | null;
  parse_error?: string | null;
}

export interface HealthResponse {
  status: string;
  app: string;
  database_url: string;
  local_llm: LLMHealthResponse;
}

export interface ApiErrorBody {
  detail?: string;
}

// Memory v2 (책 3장: 원시 증거 → 지식 카드 → 작업 메모리)
export interface MemoryCardView {
  card_id: string;
  memory_type: string;
  key: string;
  value: Record<string, unknown> | boolean | null;
  backstory: string;
  confidence: number;
  evidence: string[];
  valid_from: string | null;
  valid_to: string | null;
  superseded_by?: string | null;
}

export interface XrMemoryOverview {
  user_id: string;
  layers: Record<string, number>;
  current_cards: MemoryCardView[];
  card_history: MemoryCardView[];
}
