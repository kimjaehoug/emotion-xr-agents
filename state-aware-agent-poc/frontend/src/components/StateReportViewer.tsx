import type { EpisodeResponse, StateReport } from '../types'
import {
  baselineSourceKo,
  gapStatusKo,
  metricKo,
  trendDisplayKo,
} from '../labels'
import { MetricTrendCharts } from './MetricTrendCharts'
import { StateBadge } from './StateBadge'
import { RULE_KO, SEVERITY_KO, cardTitle } from '../memoryLabels'

const METRICS = ['cognitive_load', 'attention', 'fatigue'] as const

export function StateReportViewer({
  report,
  episodes = [],
}: {
  report: StateReport | null
  episodes?: EpisodeResponse[]
}) {
  if (!report) {
    return (
      <div className="rounded-lg border border-[var(--line)] bg-white p-5 text-sm text-[var(--muted)]">
        상태 분석을 실행하면 결과가 여기에 표시됩니다.
      </div>
    )
  }

  return (
    <div className="space-y-4 rounded-lg border border-[var(--line)] bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">상태 리포트</h3>
          <p className="font-mono text-xs text-[var(--muted)]">{report.state_report_id}</p>
        </div>
        <StateBadge level={report.state_level} />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Meta label="분석 신뢰도" value={report.analysis_confidence.toFixed(3)} />
        <Meta
          label="기준선"
          value={`${baselineSourceKo(report.baseline.source)} / ${report.baseline.version ?? '-'}`}
        />
        <Meta label="응답 필요" value={report.requires_response ? '예' : '아니오'} />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-[var(--line)] text-[var(--muted)]">
            <tr>
              <th className="py-2 pr-2 font-medium">지표</th>
              <th className="py-2 pr-2 font-medium">현재</th>
              <th className="py-2 pr-2 font-medium">기준</th>
              <th className="py-2 pr-2 font-medium">편차</th>
              <th className="py-2 pr-2 font-medium">상태</th>
              <th className="py-2 pr-2 font-medium">추세</th>
              <th className="py-2 font-medium">지속</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map((m) => {
              const g = report.cognitive_gap[m]
              if (!g) return null
              return (
                <tr key={m} className="border-b border-[var(--line)]/60">
                  <td className="py-2 pr-2 text-xs">
                    {metricKo(m)}
                    <span className="ml-1 font-mono text-[10px] text-[var(--muted)]">({m})</span>
                  </td>
                  <td className="py-2 pr-2">{g.current?.toFixed(3)}</td>
                  <td className="py-2 pr-2">{g.baseline?.toFixed(3) ?? '-'}</td>
                  <td className="py-2 pr-2">{g.deviation?.toFixed(3) ?? '-'}</td>
                  <td className="py-2 pr-2">{gapStatusKo(g.status)}</td>
                  <td className="py-2 pr-2">{trendDisplayKo(g.trend, g.status)}</td>
                  <td className="py-2">{g.persistent ? '예' : '아니오'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <MetricTrendCharts report={report} episodes={episodes} />

      {report.warnings?.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="mb-1 font-semibold">경고</p>
          <ul className="list-disc pl-5">
            {report.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {(report.memory_context?.proactive_alerts?.length ?? 0) > 0 && (
        <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">
          <p className="mb-1 font-semibold">선제 알림 (누적 메모리 점검 결과)</p>
          <ul className="list-disc pl-5">
            {report.memory_context!.proactive_alerts.map((a, i) => (
              <li key={`${a.rule}-${i}`}>
                <span className="text-xs font-semibold">
                  [{SEVERITY_KO[a.severity] ?? a.severity}] {RULE_KO[a.rule] ?? a.rule}
                </span>{' '}
                {a.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.memory_context && (
        <div className="rounded border border-[var(--line)] bg-white p-3 text-sm">
          <p className="mb-1 font-semibold">이번 분석에서 참조한 메모리</p>
          <p className="text-xs text-[var(--muted)]">
            참조한 개인 특성 {report.memory_context.working_memory.activated_cards.length}건 · 유사 세션{' '}
            {report.memory_context.working_memory.similar_episodes
              .map((e) => `${e.session_id}(관련도 ${e.score.toFixed(2)})`)
              .join(', ') || '없음'}
          </p>
          <ul className="mt-1 list-disc pl-5 text-xs">
            {report.memory_context.working_memory.activated_cards.map((c) => (
              <li key={c.card_id}>
                <span className="font-semibold">{cardTitle(c.key)}</span> — {c.backstory}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.narrative_observation && (
        <div className="rounded border border-teal-200 bg-teal-50 p-3 text-sm text-teal-950">
          <p className="mb-1 font-semibold">서술 관찰 (Qwen)</p>
          <p>{report.narrative_observation}</p>
        </div>
      )}

      <details className="rounded border border-[var(--line)] bg-slate-50 p-3">
        <summary className="cursor-pointer text-sm font-medium">원본 JSON</summary>
        <pre className="mt-2 overflow-x-auto font-mono text-xs leading-relaxed">
          {JSON.stringify(report, null, 2)}
        </pre>
      </details>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--line)] bg-slate-50 px-3 py-2">
      <p className="text-xs text-[var(--muted)]">{label}</p>
      <p className="font-mono text-sm font-medium">{value}</p>
    </div>
  )
}
