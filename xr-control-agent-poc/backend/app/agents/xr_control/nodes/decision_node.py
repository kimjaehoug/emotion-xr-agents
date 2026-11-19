"""Qwen 호출 필요 여부를 결정하는 비즈니스 규칙 노드.

- NORMAL + requires_response=false → Qwen 호출 없이 KEEP_CURRENT_STATE/NO_ACTION.
- UNKNOWN → Qwen 호출 없이 CONTINUE_OBSERVATION (자동 XR 제어 금지).
- analysis_confidence < 임계값 → Qwen 호출 없이 관찰 지속.
"""

from __future__ import annotations

from typing import Any, Dict

from app.agents.xr_control.state import AgentState


def decide_shortcut(state: AgentState, *, min_observation_confidence: float) -> Dict[str, Any]:
    report = state.get("state_report") or {}
    state_level = report.get("state_level", "UNKNOWN")
    confidence = float(report.get("analysis_confidence") or 0.0)
    requires_response = bool(report.get("requires_response"))

    if state_level == "UNKNOWN":
        return {"need_llm": False, "shortcut_reason": "UNKNOWN 상태는 자동 XR 제어 없이 관찰만 수행합니다."}

    if confidence < min_observation_confidence:
        return {
            "need_llm": False,
            "shortcut_reason": (
                f"분석 신뢰도({confidence:.2f})가 관찰 임계값({min_observation_confidence:.2f}) "
                "미만이라 관찰을 지속합니다."
            ),
        }

    if state_level == "NORMAL" and not requires_response:
        return {
            "need_llm": False,
            "shortcut_reason": "정상 상태이며 응답이 필요하지 않아 현재 상태를 유지합니다.",
        }

    return {"need_llm": True, "shortcut_reason": None}
