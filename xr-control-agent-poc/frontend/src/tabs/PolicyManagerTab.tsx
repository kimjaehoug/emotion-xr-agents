import { useCallback, useEffect, useState } from "react";
import { ApiError, listPolicies } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge, StateLevelBadge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorNotice } from "../components/common/ErrorNotice";
import type { PolicyResponse } from "../api/types";

export function PolicyManagerTab() {
  const [policies, setPolicies] = useState<PolicyResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listPolicies();
      setPolicies(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "정책 목록 조회 실패", detail: apiErr.detail });
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
        title="정책(Policy) 관리"
        description="GET /api/v1/xr-agent/policies — state_level별 자동 제어 허용 정책"
        actions={
          <Button variant="ghost" onClick={() => void load()} loading={loading}>
            새로고침
          </Button>
        }
      >
        {error && <ErrorNotice message={error.message} detail={error.detail} />}

        {policies.length === 0 && !loading && !error ? (
          <EmptyState>등록된 정책이 없습니다. 대시보드에서 Mock 데이터를 시드해보세요.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                  <th className="py-2 pr-3">policy_key</th>
                  <th className="py-2 pr-3">state_level</th>
                  <th className="py-2 pr-3">min_confidence</th>
                  <th className="py-2 pr-3">allowed_routes</th>
                  <th className="py-2 pr-3">설명</th>
                  <th className="py-2 pr-3">활성</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {policies.map((policy) => (
                  <tr key={policy.id}>
                    <td className="mono py-2 pr-3 text-xs text-slate-700">{policy.policy_key}</td>
                    <td className="py-2 pr-3">
                      <StateLevelBadge level={policy.state_level} />
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-500">{policy.min_confidence.toFixed(2)}</td>
                    <td className="py-2 pr-3">
                      <div className="flex flex-wrap gap-1">
                        {policy.allowed_routes.map((route) => (
                          <Badge key={route} tone="slate">
                            {route}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="max-w-xs py-2 pr-3 text-xs text-slate-600">{policy.description ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={policy.is_active ? "emerald" : "neutral"}>
                        {policy.is_active ? "활성" : "비활성"}
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
