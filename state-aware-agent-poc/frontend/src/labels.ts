/** UI 표시용 한국어 라벨 (API JSON 값은 영문 유지) */

import type { StateLevel } from './types'

export const STATE_LEVEL_KO: Record<StateLevel, string> = {
  NORMAL: '정상',
  WATCH: '주의',
  ACTION_REQUIRED: '조치 필요',
  UNKNOWN: '미확인',
}

export const METRIC_KO: Record<string, string> = {
  cognitive_load: '인지 부하',
  attention: '주의 집중',
  fatigue: '피로',
}

export const GAP_STATUS_KO: Record<string, string> = {
  above_baseline: '기준 초과',
  below_baseline: '기준 미만',
  within_range: '정상 범위',
  unknown: '미확인',
}

export const TREND_KO: Record<string, string> = {
  increasing: '상승',
  decreasing: '하락',
  stable: '변화 없음',
  insufficient_data: '데이터 부족',
}

/** 기준선 이탈이 이어지며 값만 횡보할 때 오해를 줄이기 위한 표시 */
export function trendDisplayKo(trend: string, status?: string): string {
  const outOfRange = status === 'above_baseline' || status === 'below_baseline'
  if (trend === 'stable' && outOfRange) {
    return '이탈 유지'
  }
  return TREND_KO[trend] ?? trend
}

export const BASELINE_SOURCE_KO: Record<string, string> = {
  personal: '개인',
  group_default: '그룹 기본',
  none: '없음',
}

export function stateLevelKo(level: string): string {
  return STATE_LEVEL_KO[level as StateLevel] ?? level
}

export function metricKo(key: string): string {
  return METRIC_KO[key] ?? key
}

export function gapStatusKo(status: string): string {
  return GAP_STATUS_KO[status] ?? status
}

export function trendKo(trend: string): string {
  return TREND_KO[trend] ?? trend
}

export function baselineSourceKo(source: string): string {
  return BASELINE_SOURCE_KO[source] ?? source
}
