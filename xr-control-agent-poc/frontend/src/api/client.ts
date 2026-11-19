// XR Control Agent 백엔드 API 클라이언트.
// vite.config.ts의 dev proxy(/api, /health -> http://127.0.0.1:8001)를 통해 호출한다.
import type {
  ActionCatalogResponse,
  ActionPlan,
  ConfirmationDecisionRequest,
  ConfirmationResponse,
  ContentResponse,
  ExecuteResponse,
  ExecutionResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  LLMHealthResponse,
  PolicyResponse,
  SeedResponse,
  TestLLMRequest,
  TestLLMResponse,
  UserResponse,
  XrEpisodeResponse,
  XrSummaryResponse,
  XrMemoryOverview,
} from "./types";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (err) {
    throw new ApiError(
      `네트워크 오류: 백엔드(${path})에 연결할 수 없습니다.`,
      0,
      err instanceof Error ? err.message : String(err),
    );
  }

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      detail = await res.text().catch(() => undefined);
    }
    throw new ApiError(`요청 실패 (${res.status})`, res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ----------------------------------------------------------------------
// 헬스체크
// ----------------------------------------------------------------------
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getLlmHealth(): Promise<LLMHealthResponse> {
  return request<LLMHealthResponse>(`${API_BASE}/xr-agent/health/llm`);
}

export function testLlm(body: TestLLMRequest): Promise<TestLLMResponse> {
  return request<TestLLMResponse>(`${API_BASE}/xr-agent/test-llm`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ----------------------------------------------------------------------
// Plan / Execute / Confirmation / Feedback
// ----------------------------------------------------------------------
export function createPlan(stateReport: Record<string, unknown>): Promise<ActionPlan> {
  return request<ActionPlan>(`${API_BASE}/xr-agent/plan`, {
    method: "POST",
    body: JSON.stringify(stateReport),
  });
}

export function executePlan(planId: string): Promise<ExecuteResponse> {
  return request<ExecuteResponse>(`${API_BASE}/xr-agent/execute`, {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
  });
}

export function resolveConfirmation(
  confirmationId: string,
  decision: ConfirmationDecisionRequest["decision"],
): Promise<{ confirmation: ConfirmationResponse; execution: ExecutionResponse | null }> {
  return request(`${API_BASE}/xr-agent/confirmations/${confirmationId}`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

export function submitFeedback(body: FeedbackRequest): Promise<FeedbackResponse> {
  return request<FeedbackResponse>(`${API_BASE}/xr-agent/feedback`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getExecution(executionId: string): Promise<ExecutionResponse> {
  return request<ExecutionResponse>(`${API_BASE}/xr-agent/executions/${executionId}`);
}

// ----------------------------------------------------------------------
// Memory (Episode / Summary)
// ----------------------------------------------------------------------
export function listXrEpisodes(userId: string, limit = 20): Promise<XrEpisodeResponse[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return request<XrEpisodeResponse[]>(
    `${API_BASE}/xr-agent/users/${encodeURIComponent(userId)}/xr-episodes?${params.toString()}`,
  );
}

export function getXrMemory(userId: string): Promise<XrMemoryOverview> {
  return request<XrMemoryOverview>(`${API_BASE}/xr-agent/users/${encodeURIComponent(userId)}/memory`);
}

export function getXrSummary(userId: string): Promise<XrSummaryResponse> {
  return request<XrSummaryResponse>(
    `${API_BASE}/xr-agent/users/${encodeURIComponent(userId)}/xr-summary`,
  );
}

// ----------------------------------------------------------------------
// Users
// ----------------------------------------------------------------------
export function listUsers(): Promise<UserResponse[]> {
  return request<UserResponse[]>(`${API_BASE}/users`);
}

export function getUser(userId: string): Promise<UserResponse> {
  return request<UserResponse>(`${API_BASE}/users/${encodeURIComponent(userId)}`);
}

// ----------------------------------------------------------------------
// 정책 / 행동 / 콘텐츠 카탈로그
// ----------------------------------------------------------------------
export function listPolicies(): Promise<PolicyResponse[]> {
  return request<PolicyResponse[]>(`${API_BASE}/xr-agent/policies`);
}

export function listActions(): Promise<ActionCatalogResponse[]> {
  return request<ActionCatalogResponse[]>(`${API_BASE}/xr-agent/actions`);
}

export function listContents(): Promise<ContentResponse[]> {
  return request<ContentResponse[]>(`${API_BASE}/xr-agent/contents`);
}

// ----------------------------------------------------------------------
// Mock 데이터 시드
// ----------------------------------------------------------------------
export function seedMockData(): Promise<SeedResponse> {
  return request<SeedResponse>(`${API_BASE}/mock/seed`, { method: "POST" });
}
