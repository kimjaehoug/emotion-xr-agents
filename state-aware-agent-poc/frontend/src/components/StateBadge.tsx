import type { StateLevel } from '../types'
import { stateLevelKo } from '../labels'

const styles: Record<StateLevel, string> = {
  NORMAL: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  WATCH: 'bg-amber-100 text-amber-900 border-amber-300',
  ACTION_REQUIRED: 'bg-red-100 text-red-800 border-red-300',
  UNKNOWN: 'bg-slate-100 text-slate-700 border-slate-300',
}

export function StateBadge({ level }: { level: string }) {
  const key = (level as StateLevel) in styles ? (level as StateLevel) : 'UNKNOWN'
  return (
    <span
      className={`inline-flex items-center rounded border px-2.5 py-1 text-xs font-semibold tracking-wide ${styles[key]}`}
      title={level}
    >
      {stateLevelKo(level)}
    </span>
  )
}
