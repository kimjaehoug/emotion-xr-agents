import { useState } from "react";
import { Card } from "../components/common/Card";
import { EmptyState } from "../components/common/EmptyState";
import { JsonBlock } from "../components/common/JsonBlock";
import { Badge, PlannerSourceBadge } from "../components/common/Badge";
import { Button } from "../components/common/Button";
import { useAppState } from "../context/AppStateContext";

export function ActionPlanViewerTab() {
  const { lastPlan, planHistory } = useAppState();
  const [showRaw, setShowRaw] = useState(false);

  if (!lastPlan) {
    return (
      <Card title="Action Plan 뷰어">
        <EmptyState>
          아직 생성된 계획이 없습니다. "State Report 시뮬레이터" 탭에서 Plan을 먼저 생성하세요.
        </EmptyState>
      </Card>
    );
  }

  const isFallback = lastPlan.planner_source === "rule_based_fallback";

  return (
    <div className="flex flex-col gap-6">
      <Card
        title={`최근 계획: ${lastPlan.plan_id}`}
        description={`state_report_id: ${lastPlan.state_report_id}`}
        actions={
          <Button variant="ghost" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? "요약 보기" : "원본 JSON 보기"}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="teal">{lastPlan.goal}</Badge>
          <Badge tone="slate">{lastPlan.route}</Badge>
          <PlannerSourceBadge source={lastPlan.planner_source} />
          <Badge tone="neutral">신뢰도 {lastPlan.confidence.toFixed(2)}</Badge>
          <Badge tone={lastPlan.executed ? "emerald" : "neutral"}>
            {lastPlan.executed ? "실행됨" : "실행 대기"}
          </Badge>
          {lastPlan.idempotent_replay && <Badge tone="amber">idempotent replay</Badge>}
        </div>

        {isFallback && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            이 계획은 Qwen LLM이 아닌 <span className="mono">rule_based_fallback</span> 플래너가 생성했습니다.
            (LLM 미도달, 낮은 신뢰도, 또는 NORMAL/UNKNOWN 단축 경로일 수 있습니다.)
          </div>
        )}

        {lastPlan.narrative && <p className="mt-3 text-sm text-slate-600">{lastPlan.narrative}</p>}
      </Card>

      {showRaw ? (
        <Card title="원본 응답 (JSON)">
          <JsonBlock value={lastPlan} maxHeight="32rem" />
        </Card>
      ) : (
        <>
          <Card
            title="검증(Validation) / 경고"
            description="ActionPlan.warnings — 안전 규칙 및 정책 검증 과정에서 수집된 경고"
          >
            {lastPlan.warnings.length === 0 ? (
              <p className="text-sm text-emerald-600">경고 없음 — 검증을 통과했습니다.</p>
            ) : (
              <ul className="list-inside list-disc space-y-1 text-sm text-amber-700">
                {lastPlan.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            )}
          </Card>

          <Card title={`액션 목록 (${lastPlan.actions.length}건)`}>
            {lastPlan.actions.length === 0 ? (
              <EmptyState>이 계획에는 실행할 액션이 없습니다.</EmptyState>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                      <th className="py-2 pr-3">action_type</th>
                      <th className="py-2 pr-3">xr_parameter</th>
                      <th className="py-2 pr-3">delta → final</th>
                      <th className="py-2 pr-3">확인 필요</th>
                      <th className="py-2 pr-3">신뢰도</th>
                      <th className="py-2 pr-3">근거(rationale)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {lastPlan.actions.map((action, idx) => (
                      <tr key={idx}>
                        <td className="py-2 pr-3 font-medium text-slate-700">{action.action_type}</td>
                        <td className="mono py-2 pr-3 text-xs text-slate-500">
                          {action.xr_parameter ?? action.target_content_id ?? "—"}
                        </td>
                        <td className="mono py-2 pr-3 text-xs text-slate-500">
                          {action.delta ?? "—"} → {action.final_value ?? "—"}
                        </td>
                        <td className="py-2 pr-3">
                          <Badge tone={action.requires_confirmation ? "amber" : "neutral"}>
                            {action.requires_confirmation ? "필요" : "불필요"}
                          </Badge>
                        </td>
                        <td className="py-2 pr-3 text-xs text-slate-500">
                          {action.confidence?.toFixed(2) ?? "—"}
                        </td>
                        <td className="max-w-xs py-2 pr-3 text-xs text-slate-600">{action.rationale}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {lastPlan.content_candidates.length > 0 && (
            <Card title={`콘텐츠 후보 (${lastPlan.content_candidates.length}건)`}>
              <JsonBlock value={lastPlan.content_candidates} maxHeight="16rem" />
            </Card>
          )}
        </>
      )}

      {planHistory.length > 1 && (
        <Card title="이전 계획 기록" description="이 세션에서 생성된 계획들 (최신 10건)">
          <ul className="divide-y divide-slate-100 text-sm">
            {planHistory.map((entry) => (
              <li key={entry.plan.plan_id} className="flex items-center justify-between gap-3 py-2">
                <span className="mono text-xs text-slate-500">{entry.plan.plan_id}</span>
                <span className="text-slate-700">
                  {entry.plan.goal} · {entry.plan.route}
                </span>
                <PlannerSourceBadge source={entry.plan.planner_source} />
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
