// 메모리 화면용 쉬운 한국어 이름 (서버의 key/rule/event 코드를 사람이 읽기 쉽게 바꾼다)
export const METRIC_KO: Record<string, string> = {
  cognitive_load: '인지 부하',
  attention: '집중도',
  fatigue: '피로도',
}

export const LAYER_KO: Record<string, string> = {
  raw_events: '분석 이력 로그',
  episodic: '세션 이력',
  archived_episodes: '요약 보관 이력',
  current_cards: '개인 특성 메모리',
  card_history: '변경 이력',
}

export const MEMORY_TYPE_KO: Record<string, string> = {
  semantic: '개인 특성',
  procedural: '보정·조절 효과',
  episodic: '이력 요약',
}

export const RULE_KO: Record<string, string> = {
  persistent_deviation: '인지 지표 지속 이탈',
  early_drift: '악화 추세',
  baseline_low_reliability: '기준선 신뢰도 부족',
  known_trigger_active: '인지 부하 유발 조건',
  emotion_metric_mismatch: '감정·인지 지표 불일치',
}

export const SEVERITY_KO: Record<string, string> = { high: '높음', medium: '보통', low: '낮음' }

export const EVENT_KO: Record<string, string> = {
  state_analyzed: '인지 상태 분석',
  card_added: '개인 특성 추가',
  card_superseded: '개인 특성 변경',
  card_reinforced: '개인 특성 재확인',
  card_expired: '개인 특성 만료',
  memory_accessed: '메모리 참조',
  consolidated: '메모리 정리',
}

export function cardTitle(key: string): string {
  const [kind, a, b] = key.split('.')
  if (kind === 'trait' && a === 'state') return "'조치 필요' 반복"
  if (kind === 'trait' && a === 'emotion') return '주된 감정'
  if (kind === 'trait') return `${METRIC_KO[a] ?? a} 반복 이탈`
  if (kind === 'trigger' && a === 'visual_complexity') return '인지 부하 유발 조건: 시각 복잡도'
  if (kind === 'trigger' && a === 'content_type') return `인지 부하 유발 조건: '${b}' 콘텐츠`
  if (kind === 'cluster') return '유사 이력 요약'
  return key
}
