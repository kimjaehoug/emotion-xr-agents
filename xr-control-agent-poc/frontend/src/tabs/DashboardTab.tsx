import { useCallback, useEffect, useState } from "react";
import { ApiError, getHealth, seedMockData } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge, PlannerSourceBadge } from "../components/common/Badge";
import { ErrorNotice } from "../components/common/ErrorNotice";
import { EmptyState } from "../components/common/EmptyState";
import { useAppState } from "../context/AppStateContext";
import type { SeedResponse } from "../api/types";

export function DashboardTab() {
  const { health, setHealth, planHistory, executionHistory } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);
  const [seedResult, setSeedResult] = useState<SeedResponse | null>(null);
  const [seeding, setSeeding] = useState(false);

  const loadHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getHealth();
      setHealth(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "헬스체크 조회 실패", detail: apiErr.detail });
    } finally {
      setLoading(false);
    }
  }, [setHealth]);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  const handleSeed = async () => {
    setSeeding(true);
    setError(null);
    try {
      const result = await seedMockData();
      setSeedResult(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "시드 데이터 생성 실패", detail: apiErr.detail });
    } finally {
      setSeeding(false);
    }
  };

  const llm = health?.local_llm;

  return (
    <div className="flex flex-col gap-6">
      {error && <ErrorNotice message={error.message} detail={error.detail} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card
          title="백엔드 상태"
          description="/health"
          actions={
            <Button variant="ghost" onClick={() => void loadHealth()} loading={loading}>
              새로고침
            </Button>
          }
        >
          {health ? (
            <div className="space-y-2 text-sm text-slate-700">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">상태</span>
                <Badge tone={health.status === "ok" ? "emerald" : "rose"}>{health.status}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">앱 이름</span>
                <span>{health.app}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="shrink-0 text-slate-500">DB URL</span>
                <span className="mono truncate text-xs text-slate-500" title={health.database_url}>
                  {health.database_url}
                </span>
              </div>
            </div>
          ) : (
            <EmptyState>{loading ? "로딩 중..." : "상태 정보를 불러오지 못했습니다."}</EmptyState>
          )}
        </Card>

        <Card title="로컬 LLM 상태" description="/api/v1/xr-agent/health/llm (health에 포함)">
          {llm ? (
            <div className="space-y-2 text-sm text-slate-700">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">연결 가능</span>
                <Badge tone={llm.reachable ? "emerald" : "rose"}>{llm.reachable ? "정상" : "불가"}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">모델</span>
                <span className="mono text-xs">{llm.model}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="shrink-0 text-slate-500">base_url</span>
                <span className="mono truncate text-xs" title={llm.base_url}>
                  {llm.base_url}
                </span>
              </div>
              {llm.detail && <p className="text-xs text-slate-400">{llm.detail}</p>}
            </div>
          ) : (
            <EmptyState>{loading ? "로딩 중..." : "LLM 상태 정보가 없습니다."}</EmptyState>
          )}
        </Card>

        <Card
          title="Mock 데이터 시드"
          description="POST /api/v1/mock/seed"
          actions={
            <Button variant="primary" onClick={() => void handleSeed()} loading={seeding}>
              시드 실행
            </Button>
          }
        >
          {seedResult ? (
            <div className="space-y-1 text-sm text-slate-700">
              <p>{seedResult.message}</p>
              <ul className="text-xs text-slate-500">
                <li>사용자 생성: {seedResult.users_created.length}명</li>
                <li>정책 생성: {seedResult.policies_created}건</li>
                <li>행동 생성: {seedResult.actions_created}건</li>
                <li>콘텐츠 생성: {seedResult.contents_created}건</li>
              </ul>
            </div>
          ) : (
            <EmptyState>초기 데모 데이터를 생성하려면 버튼을 클릭하세요.</EmptyState>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="최근 계획(Plan) 요약" description="이 세션에서 생성된 최근 계획">
          {planHistory.length === 0 ? (
            <EmptyState>
              아직 생성된 계획이 없습니다. "State Report 시뮬레이터" 탭에서 계획을 생성해보세요.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {planHistory.slice(0, 5).map((entry) => (
                <li key={entry.plan.plan_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="mono truncate text-xs text-slate-500">{entry.plan.plan_id}</p>
                    <p className="text-slate-700">
                      {entry.plan.goal} · {entry.plan.route}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <PlannerSourceBadge source={entry.plan.planner_source} />
                    <Badge tone="slate">conf {entry.plan.confidence.toFixed(2)}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="최근 실행(Execution) 요약" description="이 세션에서 실행된 최근 액션">
          {executionHistory.length === 0 ? (
            <EmptyState>
              아직 실행된 액션이 없습니다. 계획 생성 후 "Execute"를 실행해보세요.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {executionHistory.slice(0, 5).map((exe) => (
                <li key={exe.execution_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="mono truncate text-xs text-slate-500">{exe.execution_id}</p>
                    <p className="text-slate-700">{exe.action.action_type}</p>
                  </div>
                  <Badge tone={exe.status === "SUCCESS" ? "emerald" : "rose"}>{exe.status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
