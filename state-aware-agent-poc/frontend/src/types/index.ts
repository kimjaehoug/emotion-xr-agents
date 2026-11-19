/** API 타입 정의 */

export type StateLevel = 'NORMAL' | 'WATCH' | 'ACTION_REQUIRED' | 'UNKNOWN'

export interface UserProfile {
  preferred_content_types: string[]
  sensory_sensitivity: Record<string, number>
  xr_experience_level: string
  accessibility_constraints: string[]
  notes?: string | null
}

export interface UserResponse {
  user_id: string
  profile: UserProfile
  created_at: string
  updated_at: string
}

export interface MetricBounds {
  center: number
  lower: number
  upper: number
}

export interface BaselineResponse {
  user_id: string
  version: string
  cognitive_load: MetricBounds
  attention: MetricBounds
  fatigue: MetricBounds
  sample_count: number
  reliability: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MetricGap {
  current: number
  baseline: number | null
  deviation: number | null
  relative_deviation: number | null
  lower_bound?: number | null
  upper_bound?: number | null
  in_normal_range?: boolean | null
  status: string
  trend: string
  persistent: boolean
  persistence_count?: number
}

export interface StateReport {
  state_report_id: string
  user_id: string
  session_id: string
  timestamp: string
  state_level: StateLevel
  baseline: {
    source: string
    version: string | null
    reliability: number | null
  }
  cognitive_gap: Record<string, MetricGap>
  context_summary: Record<string, unknown>
  analysis_confidence: number
  requires_response: boolean
  additional_observation_required: boolean
  warnings: string[]
  possible_contributing_factors?: string[]
  narrative_observation?: string | null
  emotion_context?: { label?: string | null; intensity?: number | null; confidence?: number | null } | null
  memory_context?: MemoryContext | null
}

export interface MemoryCard {
  card_id: string
  memory_type: string
  key: string
  value: unknown
  backstory: string
  confidence: number
  evidence: string[]
  valid_from: string | null
  valid_to: string | null
  superseded_by?: string | null
}

export interface ProactiveAlert {
  rule: string
  severity: 'high' | 'medium' | 'low'
  message: string
  evidence: string[]
}

export interface MemoryContext {
  working_memory: {
    activated_cards: MemoryCard[]
    similar_episodes: Array<{ session_id: string; state_level: string; score: number; signals: Record<string, number> }>
  }
  proactive_alerts: ProactiveAlert[]
  long_term_card_count: number
  knowledge_updates?: Array<{ key: string; decision: string; card_id: string | null }>
}

export interface MemoryOverview {
  user_id: string
  layers: Record<string, number>
  current_cards: MemoryCard[]
  card_history: MemoryCard[]
  episode_importance: Array<{ session_id: string; archived: boolean; score: number; age_days: number; frequency: number; recency: number; emotion: number; uniqueness: number }>
}

export interface MemoryEvent {
  event_id: string
  event_type: string
  session_id: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface EpisodeResponse {
  id: number
  user_id: string
  session_id: string
  state_level: string
  state_report: StateReport
  created_at: string
}

export interface SummaryResponse {
  user_id: string
  summary: Record<string, unknown>
  recent_episode_count: number
  updated_at: string | null
}

export interface AnalyzeInput {
  user_id: string
  session_id: string
  timestamp: string
  cognitive_metrics: {
    cognitive_load: number
    attention: number
    fatigue: number
  }
  context?: {
    content_id?: string
    content_type?: string
    difficulty?: number
    visual_complexity?: number
    audio_stimulation?: number
    elapsed_time_min?: number
  }
  data_quality: {
    cognitive_confidence: number
    completeness: number
  }
}
