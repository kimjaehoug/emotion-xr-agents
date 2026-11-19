import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { MemoryEvent, MemoryOverview } from '../types'
import { EVENT_KO, LAYER_KO, MEMORY_TYPE_KO, cardTitle } from '../memoryLabels'

interface Props {
  userId: string
  refreshKey: number
}

/** 메모리 현황: 분석 이력 로그 → 개인 특성 메모리 → 메모리 정리. */
export function MemoryV2Panel({ userId, refreshKey }: Props) {
  const [overview, setOverview] = useState<MemoryOverview | null>(null)
  const [events, setEvents] = useState<MemoryEvent[]>([])
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    if (!userId) return
    const [o, e] = await Promise.all([api.getMemory(userId), api.listMemoryEvents(userId, 30)])
    setOverview(o)
    setEvents(e)
  }, [userId])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const consolidate = async () => {
    const r = await api.consolidateMemory(userId, 0, 0.35)
    setMsg(`메모리 정리 완료: 이력 ${r.archived_sessions.length}건을 요약 ${r.cluster_cards.length}건으로 보관`)
    await load()
  }

  if (!overview) return null
  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-5">
        {Object.entries(overview.layers).map(([k, v]) => (
          <div key={k} className="rounded-lg border border-[var(--line)] bg-white p-3 text-center">
            <p className="text-xs text-[var(--muted)]">{LAYER_KO[k] ?? k}</p>
            <p className="font-mono text-lg">{v}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="5. 개인 특성 메모리">
          {overview.current_cards.length === 0 ? (
            <Empty />
          ) : (
            <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">
              {overview.current_cards.map((c) => (
                <li key={c.card_id} className="border-b border-[var(--line)] pb-2">
                  <p className="text-sm font-semibold">
                    {cardTitle(c.key)}{' '}
                    <span className="text-xs font-normal text-[var(--muted)]">
                      [{MEMORY_TYPE_KO[c.memory_type] ?? c.memory_type}] 신뢰도 {Math.round(c.confidence * 100)}%
                    </span>
                  </p>
                  <p className="text-xs">{c.backstory}</p>
                  <p className="text-xs text-[var(--muted)]">근거 세션: {c.evidence.join(', ')}</p>
                </li>
              ))}
            </ul>
          )}
          {overview.card_history.length > 0 && (
            <p className="mt-2 text-xs text-[var(--muted)]">
              변경 이력 {overview.card_history.length}건 — 삭제하지 않고 보관
            </p>
          )}
        </Panel>

        <Panel title="6. 세션 이력 중요도 (낮은 이력은 요약 보관)">
          <div className="mb-2 flex items-center gap-2">
            <button
              className="rounded bg-[var(--ink)] px-3 py-1 text-xs text-white"
              onClick={() => void consolidate()}
            >
              메모리 정리
            </button>
            <span className="text-xs text-[var(--muted)]">{msg}</span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[var(--muted)]">
                <th rowSpan={2} className="align-bottom">세션</th>
                <th rowSpan={2} className="align-bottom text-[var(--ink)]">중요도</th>
                <th colSpan={4} className="border-l border-[var(--line)] bg-slate-50 pl-2 font-normal">
                  산출 근거 (메타데이터)
                </th>
              </tr>
              <tr className="text-left text-[11px] font-normal text-[var(--muted)]">
                <th className="border-l border-[var(--line)] bg-slate-50 pl-2 font-normal">참조 빈도</th>
                <th className="bg-slate-50 font-normal">최근성</th>
                <th className="bg-slate-50 font-normal">감정 강도</th>
                <th className="bg-slate-50 font-normal">고유도</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {overview.episode_importance.slice(0, 12).map((e) => (
                <tr key={e.session_id} className={e.archived ? 'text-[var(--muted)]' : ''}>
                  <td className={e.archived ? 'line-through' : ''}>{e.session_id}</td>
                  <td className="pr-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{e.score.toFixed(2)}</span>
                      <span className="h-1.5 w-12 rounded bg-slate-200">
                        <span
                          className={`block h-1.5 rounded ${e.archived ? 'bg-slate-400' : 'bg-[var(--ink)]'}`}
                          style={{ width: `${Math.min(1, Math.max(0, e.score)) * 100}%` }}
                        />
                      </span>
                    </div>
                  </td>
                  <td className="border-l border-[var(--line)] bg-slate-50 pl-2 text-[11px] text-[var(--muted)]">
                    {e.frequency.toFixed(2)}
                  </td>
                  <td className="bg-slate-50 text-[11px] text-[var(--muted)]">{e.recency.toFixed(2)}</td>
                  <td className="bg-slate-50 text-[11px] text-[var(--muted)]">{e.emotion.toFixed(2)}</td>
                  <td className="bg-slate-50 text-[11px] text-[var(--muted)]">{e.uniqueness.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-[var(--muted)]">
            중요도는 산출 근거 4개 항목을 가중합한 점수이며, 취소선은 요약 보관된 세션입니다.
          </p>
        </Panel>

        <Panel title="7. 분석 이력 로그 (수정·삭제 없이 누적)">
          <ul className="max-h-64 space-y-1 overflow-y-auto font-mono text-xs">
            {events.map((e) => (
              <li key={e.event_id}>
                {e.created_at.slice(11, 19)} {EVENT_KO[e.event_type] ?? e.event_type} {e.session_id ?? ''}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--line)] bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold tracking-wide text-[var(--muted)]">{title}</h3>
      {children}
    </div>
  )
}

function Empty() {
  return <p className="text-sm text-[var(--muted)]">데이터 없음</p>
}
