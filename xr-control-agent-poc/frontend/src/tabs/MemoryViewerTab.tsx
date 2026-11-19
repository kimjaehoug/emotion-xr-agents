import { useState } from "react";
import { ApiError, getXrMemory, getXrSummary, listXrEpisodes } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge, PlannerSourceBadge, StateLevelBadge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorNotice } from "../components/common/ErrorNotice";
import { JsonBlock } from "../components/common/JsonBlock";
import { useAppState } from "../context/AppStateContext";
import type { XrEpisodeResponse, XrMemoryOverview, XrSummaryResponse } from "../api/types";

const LEVEL_KO: Record<string, string> = {
  NORMAL: "정상",
  WATCH: "주의",
  ACTION_REQUIRED: "조치 필요",
  UNKNOWN: "판단 보류",
};
const PARAM_KO: Record<string, string> = {
  visual_complexity: "시각 복잡도",
  audio_stimulation: "청각 자극",
  interaction_density: "상호작용 빈도",
  information_density: "정보량",
  motion_intensity: "움직임 강도",
};
const ACTION_KO: Record<string, string> = {
  SUGGEST_BREAK: "휴식 제안",
  RECOMMEND_CONTENT: "콘텐츠 추천",
  OBSERVE: "지켜보기",
  KEEP_CURRENT_STATE: "현재 상태 유지",
};

/** "UPDATE_XR_PARAMETER:visual_complexity" → "시각 복잡도 조절" */
function actionKo(signature: string): string {
  const [action, param] = signature.split(":");
  if (action === "UPDATE_XR_PARAMETER") return `${PARAM_KO[param] ?? param} 조절`;
  return ACTION_KO[action] ?? action;
}

/** 기억 카드 key를 읽기 쉬운 제목으로 바꾼다. */
function cardTitle(key: string): string {
  if (key.startsWith("procedure.")) {
    const [, level, ...rest] = key.split(".");
    return `${LEVEL_KO[level] ?? level} · ${actionKo(rest.join("."))}`;
  }
  if (key.startsWith("preference.avoid.")) return `회피 대상: ${actionKo(key.slice("preference.avoid.".length))}`;
  return key;
}

export function MemoryViewerTab() {
  const { lastPlan } = useAppState();
  const [userId, setUserId] = useState(lastPlan?.user_id ?? "");
  const [episodes, setEpisodes] = useState<XrEpisodeResponse[]>([]);
  const [summary, setSummary] = useState<XrSummaryResponse | null>(null);
  const [memory, setMemory] = useState<XrMemoryOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; detail?: string } | null>(null);

  const handleLoad = async () => {
    if (!userId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const [episodeResult, summaryResult, memoryResult] = await Promise.all([
        listXrEpisodes(userId.trim(), 20),
        getXrSummary(userId.trim()),
        getXrMemory(userId.trim()),
      ]);
      setEpisodes(episodeResult);
      setSummary(summaryResult);
      setMemory(memoryResult);
    } catch (err) {
      const apiErr = err as ApiError;
      setError({ message: apiErr.message ?? "메모리 조회 실패", detail: apiErr.detail });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="사용자 메모리 조회"
        description="GET /api/v1/xr-agent/users/{user_id}/xr-episodes, xr-summary"
        actions={
          <Button variant="primary" onClick={() => void handleLoad()} loading={loading}>
            조회
          </Button>
        }
      >
        <div className="flex items-center gap-2">
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="user_id (예: user-demo-01)"
            className="mono w-72 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </div>
      </Card>

      {error && <ErrorNotice message={error.message} detail={error.detail} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="요약 메모리 (Summary)" description="XrSummaryMemory">
          {summary ? (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Badge tone="teal">최근 에피소드 {summary.recent_episode_count}건</Badge>
                {summary.updated_at && (
                  <span className="text-xs text-slate-400">
                    갱신: {new Date(summary.updated_at).toLocaleString("ko-KR")}
                  </span>
                )}
              </div>
              <JsonBlock value={summary.summary} maxHeight="20rem" />
            </div>
          ) : (
            <EmptyState>사용자 ID를 입력하고 조회하세요.</EmptyState>
          )}
        </Card>

        <Card title={`에피소드 메모리 (${episodes.length}건)`} description="XrEpisodicMemory">
          {episodes.length === 0 ? (
            <EmptyState>표시할 에피소드가 없습니다.</EmptyState>
          ) : (
            <ul className="max-h-96 space-y-2 overflow-y-auto">
              {episodes.map((ep) => (
                <li key={ep.id} className="rounded-md border border-slate-100 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="mono text-xs text-slate-400">{ep.state_report_id}</span>
                    <StateLevelBadge level={ep.state_level} />
                    <Badge tone="slate">{ep.route}</Badge>
                    <PlannerSourceBadge source={ep.planner_source} />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    {new Date(ep.created_at).toLocaleString("ko-KR")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    {memory && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card
            title="XR 조절 효과 이력 (사용자 반응 통계)"
            description="조절 후 사용자 반응(긍정·부정·거절)을 누적 · 다음 조절 계획에 반영"
          >
            {memory.current_cards.filter((c) => c.memory_type === "procedural").length === 0 ? (
              <EmptyState>XR 조절 실행 후 사용자 반응을 입력하면 누적됩니다.</EmptyState>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th>인지 상태 · 조절 방법</th>
                    <th>긍정</th>
                    <th>부정</th>
                    <th>거절</th>
                    <th>효과 점수</th>
                  </tr>
                </thead>
                <tbody>
                  {memory.current_cards
                    .filter((c) => c.memory_type === "procedural")
                    .map((c) => {
                      const v = (c.value ?? {}) as Record<string, number>;
                      return (
                        <tr key={c.card_id} className="border-t border-slate-100">
                          <td className="py-1">{cardTitle(c.key)}</td>
                          <td>{v.positive}</td>
                          <td>{v.negative}</td>
                          <td>{v.rejected}</td>
                          <td className={v.effectiveness < 0 ? "text-rose-600" : "text-teal-700"}>
                            {v.effectiveness?.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            )}
          </Card>
          <Card
            title="회피 대상 조절 · 변경 이력"
            description={`분석 이력 로그 ${memory.layers.raw_events}건 · 현재 메모리 ${memory.layers.current_cards}건 · 변경 이력 포함 ${memory.layers.card_history}건`}
          >
            <ul className="max-h-80 space-y-2 overflow-y-auto text-xs">
              {memory.current_cards
                .filter((c) => c.memory_type !== "procedural")
                .map((c) => (
                  <li key={c.card_id} className="rounded-md border border-rose-100 bg-rose-50 p-2">
                    <span className="font-semibold">{cardTitle(c.key)}</span> — {c.backstory}
                  </li>
                ))}
              {memory.card_history.map((c) => (
                <li key={c.card_id} className="rounded-md border border-slate-100 p-2 text-slate-400">
                  <span className="font-semibold">{cardTitle(c.key)}</span> (변경 이력 · {c.superseded_by ? "새 통계로 갱신" : "만료"}) {c.backstory}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
