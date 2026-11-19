import { useCallback, useEffect, useState } from "react";
import { ApiError, listContents } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorNotice } from "../components/common/ErrorNotice";
import type { ContentResponse } from "../api/types";

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 shrink-0 text-slate-500">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-slate-100">
        <div
          className="h-1.5 rounded-full bg-teal-500"
          style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-slate-500">{value.toFixed(2)}</span>
    </div>
  );
}

export function ContentCatalogTab() {
  const [contents, setContents] = useState<ContentResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listContents();
      setContents(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "콘텐츠 카탈로그 조회 실패", detail: apiErr.detail });
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
        title="콘텐츠(Content) 카탈로그"
        description="GET /api/v1/xr-agent/contents — 콘텐츠 추천에 사용되는 카탈로그"
        actions={
          <Button variant="ghost" onClick={() => void load()} loading={loading}>
            새로고침
          </Button>
        }
      >
        {error && <ErrorNotice message={error.message} detail={error.detail} />}

        {contents.length === 0 && !loading && !error ? (
          <EmptyState>등록된 콘텐츠가 없습니다. 대시보드에서 Mock 데이터를 시드해보세요.</EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {contents.map((content) => (
              <div key={content.id} className="rounded-md border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{content.title}</p>
                    <p className="mono text-xs text-slate-400">{content.content_id}</p>
                  </div>
                  <Badge tone={content.is_active ? "emerald" : "neutral"}>
                    {content.is_active ? "활성" : "비활성"}
                  </Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  <Badge tone="teal">{content.content_type}</Badge>
                  {content.category && <Badge tone="slate">{content.category}</Badge>}
                </div>
                <div className="mt-3 space-y-1.5">
                  <MetricBar label="난이도" value={content.difficulty} />
                  <MetricBar label="시각 복잡도" value={content.visual_complexity} />
                  <MetricBar label="청각 자극" value={content.audio_stimulation} />
                  <MetricBar label="상호작용 밀도" value={content.interaction_density} />
                </div>
                {content.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {content.tags.map((tag) => (
                      <span key={tag} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
