import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import { BaselineBuilder } from './components/BaselineBuilder'
import { InputSimulator } from './components/InputSimulator'
import { MemoryViewer } from './components/MemoryViewer'
import { MemoryV2Panel } from './components/MemoryV2Panel'
import { StateBadge } from './components/StateBadge'
import { StateReportViewer } from './components/StateReportViewer'
import { TrendChart } from './components/TrendChart'
import type {
  BaselineResponse,
  EpisodeResponse,
  StateReport,
  SummaryResponse,
  UserResponse,
} from './types'

type Tab = 'dashboard' | 'analyze' | 'memory' | 'baseline'

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [users, setUsers] = useState<UserResponse[]>([])
  const [userId, setUserId] = useState('')
  const [user, setUser] = useState<UserResponse | null>(null)
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null)
  const [episodes, setEpisodes] = useState<EpisodeResponse[]>([])
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [obsCount, setObsCount] = useState(0)
  const [report, setReport] = useState<StateReport | null>(null)
  const [health, setHealth] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshUserData = useCallback(async (id: string) => {
    if (!id) return
    setError(null)
    try {
      const u = await api.getUser(id)
      setUser(u)
    } catch {
      setUser(null)
    }
    try {
      setBaseline(await api.getBaseline(id))
    } catch {
      setBaseline(null)
    }
    try {
      setEpisodes(await api.listEpisodes(id, 10))
    } catch {
      setEpisodes([])
    }
    try {
      setSummary(await api.getSummary(id))
    } catch {
      setSummary(null)
    }
    try {
      const obs = await api.listObservations(id)
      setObsCount(obs.filter((o) => o.is_normal_confirmed).length)
    } catch {
      setObsCount(0)
    }
  }, [])

  const loadUsers = useCallback(async () => {
    try {
      const list = await api.listUsers()
      setUsers(list)
      if (!userId && list.length > 0) {
        setUserId(list[0].user_id)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [userId])

  useEffect(() => {
    void loadUsers()
    void api
      .health()
      .then((h) =>
        setHealth(
          `API OK · Ollama ${h.ollama_reachable ? '연결됨' : '미연결'} (${h.ollama_model}, ctx=${h.ollama_num_ctx})`,
        ),
      )
      .catch(() => setHealth('API 연결 실패 — 백엔드 실행 여부를 확인하세요'))
  }, [loadUsers])

  useEffect(() => {
    if (userId) void refreshUserData(userId)
  }, [userId, refreshUserData])

  async function handleSeed() {
    setBusy(true)
    setError(null)
    try {
      await api.seed()
      await loadUsers()
      setUserId('U001')
      await refreshUserData('U001')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const latestLevel = episodes[0]?.state_level ?? 'UNKNOWN'

  return (
    <div className="mx-auto min-h-screen max-w-6xl px-4 py-6 sm:px-6">
      <header className="mb-6 border-b border-[var(--line)] pb-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
              Research PoC
            </p>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              State-Aware AI Agent
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              사용자 인지 상태 변화 분석
            </p>
          </div>
          <div className="text-right text-xs text-[var(--muted)]">
            <p>{health}</p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="text-sm">
            <span className="mr-2 text-[var(--muted)]">사용자</span>
            <select
              className="rounded border border-[var(--line)] bg-white px-2 py-1.5"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            >
              {users.length === 0 && <option value="">없음</option>}
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.user_id}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={handleSeed}
            className="rounded border border-[var(--line)] bg-white px-3 py-1.5 text-sm font-medium"
          >
            데모 데이터 생성
          </button>
          <nav className="ml-auto flex flex-wrap gap-1">
            {(
              [
                ['dashboard', '대시보드'],
                ['analyze', '상태 분석'],
                ['memory', '메모리'],
                ['baseline', '기준선'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`rounded px-3 py-1.5 text-sm font-medium ${
                  tab === id
                    ? 'bg-[var(--accent)] text-white'
                    : 'bg-white text-[var(--ink)] border border-[var(--line)]'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      {tab === 'dashboard' && (
        <section className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Card title="기준선 상태">
              {baseline ? (
                <>
                  <p className="font-mono text-lg font-semibold">{baseline.version}</p>
                  <p className="text-sm text-[var(--muted)]">
                    샘플 {baseline.sample_count}개 · 신뢰도 {baseline.reliability.toFixed(2)}
                  </p>
                </>
              ) : (
                <p className="text-sm text-[var(--muted)]">미설정 (미확인 경로)</p>
              )}
            </Card>
            <Card title="최근 상태 수준">
              <StateBadge level={latestLevel} />
              <p className="mt-2 text-xs text-[var(--muted)]">
                {episodes[0]?.session_id ?? '세션 없음'}
              </p>
            </Card>
            <Card title="에피소드 수">
              <p className="font-mono text-lg font-semibold">
                {summary?.recent_episode_count ?? episodes.length}
              </p>
            </Card>
          </div>
          <div className="rounded-lg border border-[var(--line)] bg-white p-5">
            <h3 className="mb-3 text-sm font-semibold text-[var(--muted)]">최근 10개 세션 추세</h3>
            <TrendChart episodes={episodes} />
          </div>
        </section>
      )}

      {tab === 'analyze' && (
        <section className="space-y-4">
          <InputSimulator
            userId={userId}
            onAnalyzed={(r) => {
              setReport(r)
              void refreshUserData(userId)
            }}
          />
          <StateReportViewer report={report} episodes={episodes} />
        </section>
      )}

      {tab === 'memory' && (
        <div className="space-y-4">
          <MemoryViewer user={user} baseline={baseline} episodes={episodes} summary={summary} />
          <MemoryV2Panel userId={userId} refreshKey={episodes.length} />
        </div>
      )}

      {tab === 'baseline' && (
        <BaselineBuilder
          userId={userId}
          baseline={baseline}
          observationCount={obsCount}
          onUpdated={() => void refreshUserData(userId)}
        />
      )}
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--line)] bg-white p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {title}
      </p>
      {children}
    </div>
  )
}
