import { useCallback, useEffect, useState } from "react";
import { ApiError, listActions } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorNotice } from "../components/common/ErrorNotice";
import type { ActionCatalogResponse } from "../api/types";

export function ActionCatalogTab() {
  const [actions, setActions] = useState<ActionCatalogResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listActions();
      setActions(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "행동 카탈로그 조회 실패", detail: apiErr.detail });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="행동(Action) 카탈로그"
        description="GET /api/v1/xr-agent/actions — 계획에서 사용 가능한 행동 유형"
        actions={
          <Button variant="ghost" onClick={() => void load()} loading={loading}>
            새로고침
          </Button>
        }
      >
        {error && <ErrorNotice message={error.message} detail={error.detail} />}

        {actions.length === 0 && !loading && !error ? (
          <EmptyState>등록된 행동이 없습니다. 대시보드에서 Mock 데이터를 시드해보세요.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                  <th className="py-2 pr-3">action_type</th>
                  <th className="py-2 pr-3">xr_parameter</th>
                  <th className="py-2 pr-3">category</th>
                  <th className="py-2 pr-3">max_delta</th>
                  <th className="py-2 pr-3">확인 필요</th>
                  <th className="py-2 pr-3">설명</th>
                  <th className="py-2 pr-3">활성</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {actions.map((action) => (
                  <tr key={action.id}>
                    <td className="mono py-2 pr-3 text-xs font-medium text-slate-700">{action.action_type}</td>
                    <td className="mono py-2 pr-3 text-xs text-slate-500">{action.xr_parameter ?? "—"}</td>
                    <td className="py-2 pr-3 text-xs text-slate-500">{action.category ?? "—"}</td>
                    <td className="py-2 pr-3 text-xs text-slate-500">
                      {action.max_delta != null ? action.max_delta.toFixed(2) : "—"}
                    </td>
                    <td className="py-2 pr-3">
                      <Badge tone={action.requires_confirmation ? "amber" : "neutral"}>
                        {action.requires_confirmation ? "필요" : "불필요"}
                      </Badge>
                    </td>
                    <td className="max-w-xs py-2 pr-3 text-xs text-slate-600">{action.description ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={action.is_active ? "emerald" : "neutral"}>
                        {action.is_active ? "활성" : "비활성"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
