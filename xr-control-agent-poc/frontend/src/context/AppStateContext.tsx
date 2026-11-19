import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { ActionPlan, ExecuteResponse, ExecutionResponse, HealthResponse } from "../api/types";
import { SAMPLE_STATE_REPORT_JSON } from "../data/sampleStateReport";

interface PlanHistoryEntry {
  plan: ActionPlan;
  requestedAt: string;
}

interface AppStateValue {
  stateReportText: string;
  setStateReportText: (value: string) => void;

  lastPlan: ActionPlan | null;
  planHistory: PlanHistoryEntry[];
  recordPlan: (plan: ActionPlan) => void;

  lastExecute: ExecuteResponse | null;
  executionHistory: ExecutionResponse[];
  recordExecute: (execute: ExecuteResponse) => void;

  health: HealthResponse | null;
  setHealth: (health: HealthResponse | null) => void;
}

const AppStateContext = createContext<AppStateValue | undefined>(undefined);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [stateReportText, setStateReportText] = useState(SAMPLE_STATE_REPORT_JSON);
  const [planHistory, setPlanHistory] = useState<PlanHistoryEntry[]>([]);
  const [executionHistory, setExecutionHistory] = useState<ExecutionResponse[]>([]);
  const [lastExecute, setLastExecute] = useState<ExecuteResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const recordPlan = (plan: ActionPlan) => {
    setPlanHistory((prev) => [{ plan, requestedAt: new Date().toISOString() }, ...prev].slice(0, 10));
  };

  const recordExecute = (execute: ExecuteResponse) => {
    setLastExecute(execute);
    setExecutionHistory((prev) => [...execute.executions, ...prev].slice(0, 20));
  };

  const value = useMemo<AppStateValue>(
    () => ({
      stateReportText,
      setStateReportText,
      lastPlan: planHistory[0]?.plan ?? null,
      planHistory,
      recordPlan,
      lastExecute,
      executionHistory,
      recordExecute,
      health,
      setHealth,
    }),
    [stateReportText, planHistory, lastExecute, executionHistory, health],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState는 AppStateProvider 내부에서만 사용할 수 있습니다.");
  return ctx;
}
