import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { metricKo, trendDisplayKo } from '../labels'
import type { EpisodeResponse, MetricGap, StateReport } from '../types'

const METRICS = ['cognitive_load', 'attention', 'fatigue'] as const
type MetricKey = (typeof METRICS)[number]

const COLORS: Record<MetricKey, string> = {
  cognitive_load: '#0f766e',
  attention: '#1d4ed8',
  fatigue: '#b45309',
}

interface Props {
  report: StateReport
  episodes: EpisodeResponse[]
}

export function MetricTrendCharts({ report, episodes }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-2">
        <h4 className="text-sm font-semibold text-[var(--muted)]">지표별 추세</h4>
        <p className="text-xs text-[var(--muted)]">최근 세션 + 현재 분석 · 점선=기준선</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {METRICS.map((metric) => (
          <MetricChart
            key={metric}
            metric={metric}
            gap={report.cognitive_gap[metric]}
            report={report}
            episodes={episodes}
          />
        ))}
      </div>
    </div>
  )
}

function MetricChart({
  metric,
  gap,
  report,
  episodes,
}: {
  metric: MetricKey
  gap?: MetricGap
  report: StateReport
  episodes: EpisodeResponse[]
}) {
  const data = buildSeries(metric, report, episodes)
  const color = COLORS[metric]
  const baseline = gap?.baseline ?? null
  const lower = gap?.lower_bound ?? null
  const upper = gap?.upper_bound ?? null

  return (
    <div className="rounded border border-[var(--line)] bg-slate-50/80 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{metricKo(metric)}</p>
        {gap && (
          <span className="text-xs text-[var(--muted)]">
            {trendDisplayKo(gap.trend, gap.status)}
            {gap.persistent ? ' · 지속' : ''}
          </span>
        )}
      </div>
      <div className="h-44 w-full">
        {data.length === 0 ? (
          <p className="flex h-full items-center justify-center text-xs text-[var(--muted)]">
            추세 데이터 없음
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} width={36} />
              <Tooltip
                formatter={(value) =>
                  typeof value === 'number' ? value.toFixed(3) : String(value ?? '-')
                }
                labelFormatter={(label) => `세션 ${label}`}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {lower != null && upper != null && (
                <ReferenceArea y1={lower} y2={upper} fill={color} fillOpacity={0.08} />
              )}
              {baseline != null && (
                <ReferenceLine
                  y={baseline}
                  stroke={color}
                  strokeDasharray="4 4"
                  strokeOpacity={0.7}
                />
              )}
              <Line
                type="monotone"
                dataKey="value"
                name="현재값"
                stroke={color}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {gap && (
        <p className="mt-1 font-mono text-[11px] text-[var(--muted)]">
          현재 {gap.current?.toFixed(2) ?? '-'}
          {baseline != null && ` / 기준 ${baseline.toFixed(2)}`}
          {lower != null && upper != null && ` · 범위 [${lower.toFixed(2)}, ${upper.toFixed(2)}]`}
        </p>
      )}
    </div>
  )
}

function buildSeries(
  metric: MetricKey,
  report: StateReport,
  episodes: EpisodeResponse[],
): Array<{ label: string; value: number | null; isCurrent: boolean }> {
  // episodes: newest first → reverse to chronological
  const chronological = [...episodes].reverse()
  const points: Array<{ label: string; value: number | null; isCurrent: boolean }> = []
  const seen = new Set<string>()

  for (const ep of chronological) {
    if (ep.session_id === report.session_id) continue
    const g = ep.state_report?.cognitive_gap?.[metric]
    const value = g?.current ?? null
    if (value == null) continue
    if (seen.has(ep.session_id)) continue
    seen.add(ep.session_id)
    points.push({
      label: shortSession(ep.session_id),
      value,
      isCurrent: false,
    })
  }

  // keep last 9 historical + current
  const trimmed = points.slice(-9)
  const current = report.cognitive_gap[metric]?.current
  trimmed.push({
    label: shortSession(report.session_id) || '현재',
    value: current ?? null,
    isCurrent: true,
  })

  return trimmed
}

function shortSession(sessionId: string): string {
  if (sessionId.length <= 10) return sessionId
  return `…${sessionId.slice(-8)}`
}
