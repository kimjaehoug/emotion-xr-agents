import type {
  AnalyzeInput,
  BaselineResponse,
  EpisodeResponse,
  MemoryEvent,
  MemoryOverview,
  StateReport,
  SummaryResponse,
  UserResponse,
} from '../types'

const BASE = ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try {
      const j = JSON.parse(text)
      detail = j.detail ? JSON.stringify(j.detail) : text
    } catch {
      /* keep text */
    }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  listUsers: () => request<UserResponse[]>('/api/v1/users'),
  getUser: (userId: string) => request<UserResponse>(`/api/v1/users/${userId}`),
  seed: () => request<{ message: string }>('/api/v1/mock/seed', { method: 'POST' }),
  getBaseline: (userId: string) =>
    request<BaselineResponse>(`/api/v1/users/${userId}/baseline`),
  listObservations: (userId: string) =>
    request<
      Array<{
        id: number
        session_id: string
        cognitive_load: number
        attention: number
        fatigue: number
        confidence: number
        completeness: number
        is_normal_confirmed: boolean
      }>
    >(`/api/v1/users/${userId}/baseline-observations`),
  addObservation: (
    userId: string,
    body: {
      session_id: string
      cognitive_load: number
      attention: number
      fatigue: number
      confidence: number
      completeness: number
      is_normal_confirmed: boolean
    },
  ) =>
    request(`/api/v1/users/${userId}/baseline-observations`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  buildBaseline: (userId: string) =>
    request<BaselineResponse>(`/api/v1/users/${userId}/baseline/build`, {
      method: 'POST',
    }),
  listEpisodes: (userId: string, limit = 10) =>
    request<EpisodeResponse[]>(`/api/v1/users/${userId}/episodes?limit=${limit}`),
  getSummary: (userId: string) =>
    request<SummaryResponse>(`/api/v1/users/${userId}/summary`),
  analyze: (payload: AnalyzeInput) =>
    request<StateReport>('/api/v1/state/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getMemory: (userId: string) => request<MemoryOverview>(`/api/v1/users/${userId}/memory`),
  listMemoryEvents: (userId: string, limit = 30) =>
    request<MemoryEvent[]>(`/api/v1/users/${userId}/memory/events?limit=${limit}`),
  consolidateMemory: (userId: string, minAgeDays: number, threshold: number) =>
    request<{ archived_sessions: string[]; cluster_cards: unknown[] }>(
      `/api/v1/users/${userId}/memory/consolidate?min_age_days=${minAgeDays}&threshold=${threshold}`,
      { method: 'POST' },
    ),
  health: () =>
    request<{
      status: string
      ollama_reachable: boolean
      ollama_model: string
      ollama_num_ctx: number
    }>('/health'),
}
