import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import type { EpisodeResponse } from '../types'

export function TrendChart({ episodes }: { episodes: EpisodeResponse[] }) {
  const data = [...episodes]
    .reverse()
    .map((ep) => {
      const gap = ep.state_report?.cognitive_gap || {}
      return {
        session: ep.session_id,
        load: gap.cognitive_load?.current ?? null,
        attention: gap.attention?.current ?? null,
        fatigue: gap.fatigue?.current ?? null,
        level: ep.state_level,
      }
    })

  if (data.length === 0) {
    return <p className="text-sm text-[var(--muted)]">세션 데이터가 없습니다.</p>
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="session" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="load" name="인지 부하" stroke="#0f766e" strokeWidth={2} dot />
          <Line type="monotone" dataKey="attention" name="주의 집중" stroke="#1d4ed8" strokeWidth={2} dot />
          <Line type="monotone" dataKey="fatigue" name="피로" stroke="#b45309" strokeWidth={2} dot />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
