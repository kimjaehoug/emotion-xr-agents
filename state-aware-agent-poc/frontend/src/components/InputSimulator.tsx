import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { StateReport } from '../types'

interface Props {
  userId: string
  onAnalyzed: (report: StateReport) => void
}

export function InputSimulator({ userId, onAnalyzed }: Props) {
  const [cognitiveLoad, setCognitiveLoad] = useState(0.72)
  const [attention, setAttention] = useState(0.58)
  const [fatigue, setFatigue] = useState(0.68)
  const [confidence, setConfidence] = useState(0.9)
  const [completeness, setCompleteness] = useState(0.95)
  const [difficulty, setDifficulty] = useState(0.8)
  const [visualComplexity, setVisualComplexity] = useState(0.75)
  const [audioStimulation, setAudioStimulation] = useState(0.6)
  const [elapsed, setElapsed] = useState(25)
  const [contentId, setContentId] = useState('C102')
  const [contentType, setContentType] = useState('education')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sessionId = useMemo(() => `S-${Date.now().toString(36).toUpperCase()}`, [])

  async function handleAnalyze() {
    setLoading(true)
    setError(null)
    try {
      const report = await api.analyze({
        user_id: userId,
        session_id: `${sessionId}-${Math.floor(Math.random() * 1000)}`,
        timestamp: new Date().toISOString(),
        cognitive_metrics: {
          cognitive_load: cognitiveLoad,
          attention,
          fatigue,
        },
        context: {
          content_id: contentId,
          content_type: contentType,
          difficulty,
          visual_complexity: visualComplexity,
          audio_stimulation: audioStimulation,
          elapsed_time_min: elapsed,
        },
        data_quality: {
          cognitive_confidence: confidence,
          completeness,
        },
      })
      onAnalyzed(report)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-[var(--line)] bg-white p-5">
      <h3 className="mb-1 text-lg font-semibold">입력 시뮬레이터</h3>
      <p className="mb-4 text-sm text-[var(--muted)]">
        인지평가 정량값과 콘텐츠 조건을 조절한 뒤 상태를 분석합니다.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <Slider label="인지 부하" hint="cognitive_load" value={cognitiveLoad} onChange={setCognitiveLoad} />
        <Slider label="주의 집중" hint="attention" value={attention} onChange={setAttention} />
        <Slider label="피로" hint="fatigue" value={fatigue} onChange={setFatigue} />
        <Slider
          label="인지 신뢰도"
          hint="cognitive_confidence"
          value={confidence}
          onChange={setConfidence}
        />
        <Slider label="데이터 완전성" hint="completeness" value={completeness} onChange={setCompleteness} />
        <Slider label="콘텐츠 난이도" hint="difficulty" value={difficulty} onChange={setDifficulty} />
        <Slider
          label="시각 복잡도"
          hint="visual_complexity"
          value={visualComplexity}
          onChange={setVisualComplexity}
        />
        <Slider
          label="청각 자극"
          hint="audio_stimulation"
          value={audioStimulation}
          onChange={setAudioStimulation}
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          <span className="mb-1 block text-[var(--muted)]">콘텐츠 ID</span>
          <input
            className="w-full rounded border border-[var(--line)] px-2 py-1.5"
            value={contentId}
            onChange={(e) => setContentId(e.target.value)}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[var(--muted)]">콘텐츠 유형</span>
          <input
            className="w-full rounded border border-[var(--line)] px-2 py-1.5"
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[var(--muted)]">경과 시간 (분)</span>
          <input
            type="number"
            className="w-full rounded border border-[var(--line)] px-2 py-1.5"
            value={elapsed}
            onChange={(e) => setElapsed(Number(e.target.value))}
          />
        </label>
      </div>

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      <button
        type="button"
        onClick={handleAnalyze}
        disabled={loading || !userId}
        className="mt-4 rounded bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {loading ? '분석 중…' : '상태 분석'}
      </button>
    </div>
  )
}

function Slider({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint?: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <label className="block text-sm">
      <div className="mb-1 flex justify-between gap-2">
        <span className="text-[var(--muted)]">
          {label}
          {hint && <span className="ml-1 font-mono text-[10px] opacity-60">({hint})</span>}
        </span>
        <span className="font-mono text-xs">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--accent)]"
      />
    </label>
  )
}
