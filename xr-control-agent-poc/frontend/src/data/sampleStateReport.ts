// ACTION_REQUIRED + 높은 시각 복잡도 샘플 (상태 인지 Agent → XR Agent 입력)

export function buildSampleStateReport() {
  const stamp = Date.now().toString(36).toUpperCase();
  return {
    state_report_id: `SR-${stamp}`,
    user_id: "U001",
    session_id: `S-${stamp}`,
    timestamp: new Date().toISOString(),
    state_level: "ACTION_REQUIRED",
    baseline: {
      source: "personal",
      version: "v1",
      reliability: 0.84,
    },
    cognitive_gap: {
      cognitive_load: {
        status: "above_baseline",
        deviation: 0.24,
        trend: "increasing",
        persistent: true,
        current: 0.72,
        baseline: 0.48,
      },
      attention: {
        status: "below_baseline",
        deviation: -0.13,
        trend: "decreasing",
        persistent: false,
        current: 0.58,
        baseline: 0.71,
      },
      fatigue: {
        status: "above_baseline",
        deviation: 0.31,
        trend: "increasing",
        persistent: true,
        current: 0.68,
        baseline: 0.37,
      },
    },
    emotion_context: {
      label: "frustration",
      intensity: 0.67,
      confidence: 0.81,
    },
    context_summary: {
      content_id: "C102",
      content_type: "education",
      difficulty: 0.8,
      visual_complexity: 0.75,
      audio_stimulation: 0.6,
      interaction_density: 0.7,
      elapsed_time_min: 25,
    },
    candidate_causes: [
      {
        type: "content",
        factor: "high_visual_complexity",
        confidence: 0.74,
      },
    ],
    analysis_confidence: 0.84,
    requires_response: true,
    additional_observation_required: false,
    warnings: [],
    possible_contributing_factors: [
      "high_visual_complexity",
      "extended_session_duration",
    ],
    narrative_observation:
      "인지 부하·피로가 기준을 지속 상회하고 주의는 하락한 상태입니다. 시각 복잡도가 높은 콘텐츠 조건과 함께 관찰됩니다.",
  };
}

export function sampleStateReportJson(): string {
  return JSON.stringify(buildSampleStateReport(), null, 2);
}

/** @deprecated 고정 ID 샘플 — 새 코드는 sampleStateReportJson() 사용 */
export const SAMPLE_STATE_REPORT_JSON = sampleStateReportJson();
