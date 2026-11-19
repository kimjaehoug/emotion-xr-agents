import { useState } from "react";
import { ApiError, createPlan, executePlan } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { ErrorNotice } from "../components/common/ErrorNotice";
import { JsonBlock } from "../components/common/JsonBlock";
import { EmptyState } from "../components/common/EmptyState";
import { Badge, PlannerSourceBadge } from "../components/common/Badge";
import { useAppState } from "../context/AppStateContext";
import { SAMPLE_STATE_REPORT_JSON } from "../data/sampleStateReport";
import type { ActionPlan, ExecuteResponse } from "../api/types";

export function StateReportSimulatorTab() {
  const { stateReportText, setStateReportText, recordPlan, recordExecute } = useAppState();
  const [planResult, setPlanResult] = useState<ActionPlan | null>(null);
  const [executeResult, setExecuteResult] = useState<ExecuteResponse | null>(null);
  const [planning, setPlanning] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);
  const [jsonError, setJsonError] = useState<string | null>(null);

  const handlePlan = async () => {
    setError(null);
    setJsonError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(stateReportText);
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "JSON 파싱 오류");
      return;
    }

    setPlanning(true);
    try {
      const plan = await createPlan(parsed);
      setPlanResult(plan);
      setExecuteResult(null);
      recordPlan(plan);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "계획 생성 실패", detail: apiErr.detail });
    } finally {
      setPlanning(false);
    }
  };

  const handleExecute = async () => {
    if (!planResult) return;
    setError(null);
    setExecuting(true);
    try {
      const result = await executePlan(planResult.plan_id);
      setExecuteResult(result);
      recordExecute(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "계획 실행 실패", detail: apiErr.detail });
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="State Report 입력"
        description="상태 인지 Agent가 전달하는 StateReport JSON을 편집한 뒤 계획을 생성하세요."
        actions={
          <Button variant="ghost" onClick={() => setStateReportText(SAMPLE_STATE_REPORT_JSON)}>
            샘플 다시 불러오기
          </Button>
        }
      >
        <textarea
          value={stateReportText}
          onChange={(e) => setStateReportText(e.target.value)}
          spellCheck={false}
          className="mono h-96 w-full resize-y rounded-md border border-slate-300 bg-slate-50 p-3 text-xs leading-relaxed text-slate-800 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
        />
        {jsonError && <p className="mt-2 text-xs text-rose-600">JSON 오류: {jsonError}</p>}

        <div className="mt-4 flex items-center gap-3">
          <Button variant="primary" onClick={() => void handlePlan()} loading={planning}>
            Plan 생성
          </Button>
          <Button
            variant="secondary"
            onClick={() => void handleExecute()}
            loading={executing}
            disabled={!planResult}
          >
            Execute 실행
          </Button>
          {planResult && <span className="mono text-xs text-slate-400">plan_id: {planResult.plan_id}</span>}
        </div>
      </Card>

      {error && <ErrorNotice message={error.message} detail={error.detail} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Plan 응답" description="POST /api/v1/xr-agent/plan">
          {planResult ? (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="teal">{planResult.goal}</Badge>
                <Badge tone="slate">{planResult.route}</Badge>
                <PlannerSourceBadge source={planResult.planner_source} />
                <Badge tone="neutral">신뢰도 {planResult.confidence.toFixed(2)}</Badge>
              </div>
              <JsonBlock value={planResult} />
            </div>
          ) : (
            <EmptyState>아직 계획이 없습니다. 위에서 "Plan 생성"을 실행하세요.</EmptyState>
          )}
        </Card>

        <Card title="Execute 응답" description="POST /api/v1/xr-agent/execute">
          {executeResult ? (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={executeResult.already_executed ? "amber" : "emerald"}>
                  {executeResult.already_executed ? "이미 실행됨" : "실행 완료"}
                </Badge>
                <Badge tone="neutral">확인 대기 {executeResult.confirmations.length}건</Badge>
                <Badge tone="neutral">실행됨 {executeResult.executions.length}건</Badge>
              </div>
              <JsonBlock value={executeResult} />
            </div>
          ) : (
            <EmptyState>아직 실행 결과가 없습니다.</EmptyState>
          )}
        </Card>
      </div>
    </div>
  );
}
