import { useState } from 'react'
import { api } from '../api/client'
import type { BaselineResponse } from '../types'

interface Props {
  userId: string
  baseline: BaselineResponse | null
  observationCount: number
  onUpdated: () => void
}

export function BaselineBuilder({ userId, baseline, observationCount, onUpdated }: Props) {
  const [cl, setCl] = useState(0.45)
  const [att, setAtt] = useState(0.7)
  const [fat, setFat] = useState(0.35)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function addSample() {
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      await api.addObservation(userId, {
        session_id: `OBS-${Date.now()}`,
        cognitive_load: cl,
        attention: att,
        fatigue: fat,
        confidence: 0.9,
        completeness: 0.95,
        is_normal_confirmed: true,
      })
      setMsg('정상 샘플이 추가되었습니다.')
      onUpdated()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function build() {
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      const bl = await api.buildBaseline(userId)
      setMsg(`Baseline ${bl.version} 생성 완료 (samples=${bl.sample_count})`)
      onUpdated()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-[var(--line)] bg-white p-5">
      <h3 className="mb-2 text-lg font-semibold">Baseline Builder</h3>
      <p className="mb-4 text-sm text-[var(--muted)]">
        정상 확인 샘플 수: <span className="font-mono font-semibold text-[var(--ink)]">{observationCount}</span>{' '}
        (최소 3개 권장)
      </p>

      <div className="grid gap-3 sm:grid-cols-3">
        <Num label="cognitive_load" value={cl} onChange={setCl} />
        <Num label="attention" value={att} onChange={setAtt} />
        <Num label="fatigue" value={fat} onChange={setFat} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || !userId}
          onClick={addSample}
          className="rounded border border-[var(--line)] bg-slate-50 px-3 py-2 text-sm font-medium disabled:opacity-50"
        >
          정상 샘플 추가
        </button>
        <button
          type="button"
          disabled={busy || !userId}
          onClick={build}
          className="rounded bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          Baseline 생성
        </button>
      </div>

      {msg && <p className="mt-3 text-sm text-teal-800">{msg}</p>}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      {baseline && (
        <div className="mt-4 rounded border border-[var(--line)] bg-slate-50 p-3 text-sm">
          <p className="mb-2 font-medium">
            현재 Baseline <span className="font-mono">{baseline.version}</span>
          </p>
          {(['cognitive_load', 'attention', 'fatigue'] as const).map((m) => (
            <p key={m} className="font-mono text-xs">
              {m}: center={baseline[m].center.toFixed(3)} range=[{baseline[m].lower.toFixed(3)},{' '}
              {baseline[m].upper.toFixed(3)}]
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function Num({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block font-mono text-xs text-[var(--muted)]">{label}</span>
      <input
        type="number"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded border border-[var(--line)] px-2 py-1.5"
      />
    </label>
  )
}
