import { useMemo, useState } from "react";
import { ApiError, getExecution, listXrEpisodes } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorNotice } from "../components/common/ErrorNotice";
import { JsonBlock } from "../components/common/JsonBlock";
import { useAppState } from "../context/AppStateContext";
import type { ExecutionResponse, XrEpisodeResponse } from "../api/types";

const XR_PARAMETERS = [
  "visual_complexity",
  "audio_stimulation",
  "interaction_density",
  "information_density",
  "motion_intensity",
] as const;

function reconstructXrState(episodes: XrEpisodeResponse[]): Record<string, number> {
  // 백엔드는 모의 XR 런타임 상태를 직접 조회하는 GET 엔드포인트를 제공하지 않는다.
  // 대신 xr-episodes의 plan.actions(UPDATE_XR_PARAMETER, final_value)를 시간순으로 replay하여
  // 최신 상태를 근사 재구성한다. created_at 내림차순(최신 우선)으로 채워 넣는다.
  const state: Record<string, number> = {};
  for (const episode of episodes) {
    const actions = (episode.plan?.actions as Record<string, unknown>[] | undefined) ?? [];
    for (const action of actions) {
      if (action.action_type !== "UPDATE_XR_PARAMETER") continue;
      const param = action.xr_parameter as string | undefined;
      const finalValue = action.final_value as number | null | undefined;
      if (param && finalValue != null && !(param in state)) {
        state[param] = finalValue;
      }
    }
  }
  return state;
}

export function MockXrRuntimeTab() {
  const { lastPlan } = useAppState();
  const [userId, setUserId] = useState(lastPlan?.user_id ?? "");
  const [episodes, setEpisodes] = useState<XrEpisodeResponse[]>([]);
  const [loadingEpisodes, setLoadingEpisodes] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);

  const [executionId, setExecutionId] = useState("");
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [loadingExecution, setLoadingExecution] = useState(false);
  const [executionError, setExecutionError] = useState<{ message: string; detail?: string } | null>(null);

  const reconstructed = useMemo(() => reconstructXrState(episodes), [episodes]);

  const handleRefresh = async () => {
    if (!userId.trim()) return;
    setLoadingEpisodes(true);
    setError(null);
    try {
      const result = await listXrEpisodes(userId.trim(), 20);
      setEpisodes(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "에피소드 조회 실패", detail: apiErr.detail });
    } finally {
      setLoadingEpisodes(false);
    }
  };

  const handleLookupExecution = async () => {
    if (!executionId.trim()) return;
    setLoadingExecution(true);
    setExecutionError(null);
    try {
      const result = await getExecution(executionId.trim());
      setExecution(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setExecutionError({ message: apiErr.message ?? "실행 결과 조회 실패", detail: apiErr.detail });
    } finally {
      setLoadingExecution(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-md border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
        참고: 백엔드는 모의 XR 런타임 상태를 직접 조회하는 GET 엔드포인트를 제공하지 않습니다. 이 탭은
        사용자의 최근 XR 에피소드(<span className="mono">GET /xr-agent/users/{"{user_id}"}/xr-episodes</span>)에
        기록된 계획의 <span className="mono">UPDATE_XR_PARAMETER</span> 액션을 재생(replay)하여 파라미터
        상태를 근사 재구성합니다. 정확한 스냅샷이 필요하면 아래에서 특정 실행(Execution)의 결과를 직접 조회할
        수 있습니다.
      </div>

      <Card
        title="사용자별 XR 상태 재구성"
        description="GET /api/v1/xr-agent/users/{user_id}/xr-episodes 기반"
        actions={
          <Button variant="primary" onClick={() => void handleRefresh()} loading={loadingEpisodes}>
            새로고침
          </Button>
        }
      >
        <div className="mb-4 flex items-center gap-2">
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="user_id (예: user-demo-01)"
            className="mono w-72 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </div>

        {error && <ErrorNotice message={error.message} detail={error.detail} />}

        {episodes.length === 0 && !loadingEpisodes && !error ? (
          <EmptyState>사용자 ID를 입력하고 새로고침을 눌러 XR 상태를 재구성하세요.</EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                재구성된 파라미터 (추정)
              </p>
              <div className="space-y-2">
                {XR_PARAMETERS.map((param) => (
                  <div key={param} className="flex items-center justify-between text-sm">
                    <span className="mono text-xs text-slate-500">{param}</span>
                    <Badge tone={param in reconstructed ? "teal" : "neutral"}>
                      {param in reconstructed ? reconstructed[param].toFixed(2) : "기록 없음 (기본값 0.50 추정)"}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                최근 에피소드 ({episodes.length}건)
              </p>
              <ul className="max-h-64 space-y-1 overflow-y-auto text-xs">
                {episodes.map((ep) => (
                  <li key={ep.id} className="flex items-center justify-between gap-2 rounded bg-slate-50 px-2 py-1">
                    <span className="mono text-slate-500">{ep.state_report_id}</span>
                    <span className="text-slate-600">{ep.route}</span>
                    <Badge tone="slate">{ep.state_level}</Badge>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Card>

      <Card
        title="실행(Execution) 단위 스냅샷 조회"
        description="GET /api/v1/xr-agent/executions/{execution_id} — result.xr_state에 정확한 적용 시점 상태가 담깁니다"
        actions={
          <Button variant="primary" onClick={() => void handleLookupExecution()} loading={loadingExecution}>
            조회
          </Button>
        }
      >
        <div className="mb-4 flex items-center gap-2">
          <input
            value={executionId}
            onChange={(e) => setExecutionId(e.target.value)}
            placeholder="execution_id (예: EXE-XXXXXXXXXX)"
            className="mono w-72 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </div>

        {executionError && <ErrorNotice message={executionError.message} detail={executionError.detail} />}

        {execution ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={execution.status === "SUCCESS" ? "emerald" : "rose"}>{execution.status}</Badge>
              <Badge tone="slate">{execution.action.action_type}</Badge>
              <span className="mono text-xs text-slate-400">{execution.plan_id}</span>
            </div>
            <JsonBlock value={execution.result} maxHeight="14rem" />
          </div>
        ) : (
          !executionError && <EmptyState>execution_id를 입력하면 해당 시점의 XR 상태를 확인할 수 있습니다.</EmptyState>
        )}
      </Card>
    </div>
  );
}
