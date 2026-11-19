import type {
  BaselineResponse,
  EpisodeResponse,
  SummaryResponse,
  UserResponse,
} from '../types'
import { StateBadge } from './StateBadge'
import { METRIC_KO } from '../memoryLabels'

interface Props {
  user: UserResponse | null
  baseline: BaselineResponse | null
  episodes: EpisodeResponse[]
  summary: SummaryResponse | null
}

export function MemoryViewer({ user, baseline, episodes, summary }: Props) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="1. 사용자 프로필">
        {user ? (
          <pre className="overflow-x-auto font-mono text-xs">{JSON.stringify(user.profile, null, 2)}</pre>
        ) : (
          <Empty />
        )}
      </Panel>

      <Panel title="2. 개인 기준선 (Baseline)">
        {baseline ? (
          <div className="space-y-2 text-sm">
            <p>
              버전 <span className="font-mono">{baseline.version}</span> · 측정 횟수{' '}
              <span className="font-mono">{baseline.sample_count}</span> · 신뢰도{' '}
              <span className="font-mono">{baseline.reliability.toFixed(3)}</span>
            </p>
            {(['cognitive_load', 'attention', 'fatigue'] as const).map((m) => (
              <p key={m} className="font-mono text-xs">
                {METRIC_KO[m]}: 기준 {baseline[m].center.toFixed(2)} (정상 범위 {baseline[m].lower.toFixed(2)} ~{' '}
                {baseline[m].upper.toFixed(2)})
              </p>
            ))}
          </div>
        ) : (
          <Empty text="아직 개인 기준선이 없습니다" />
        )}
      </Panel>

      <Panel title="3. 세션 이력">
        {episodes.length === 0 ? (
          <Empty />
        ) : (
          <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
            {episodes.map((ep) => (
              <li
                key={ep.id}
                className="flex items-center justify-between gap-2 border-b border-[var(--line)] pb-2"
              >
                <span className="font-mono text-xs">{ep.session_id}</span>
                <StateBadge level={ep.state_level} />
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="4. 세션 요약">
        {summary && Object.keys(summary.summary || {}).length > 0 ? (
          <pre className="max-h-64 overflow-auto font-mono text-xs">
            {JSON.stringify(summary.summary, null, 2)}
          </pre>
        ) : (
          <Empty />
        )}
      </Panel>
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

function Empty({ text = '데이터 없음' }: { text?: string }) {
  return <p className="text-sm text-[var(--muted)]">{text}</p>
}
