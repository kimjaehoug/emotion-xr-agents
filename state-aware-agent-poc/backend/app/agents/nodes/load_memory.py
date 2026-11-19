"""Memory 로드 노드."""

from typing import Any, Dict, List

from app.agents.state import AgentState
from app.core.config import get_settings


def load_profile_memory(state: AgentState, *, profile: Dict[str, Any] | None) -> Dict[str, Any]:
    return {"profile": profile}


def load_baseline_memory(
    state: AgentState,
    *,
    baseline: Dict[str, Any] | None,
    baseline_source: str,
) -> Dict[str, Any]:
    warnings = list(state.get("warnings") or [])
    route = state.get("route") or "complete_report"

    if baseline is None or baseline_source == "none":
        warnings.append("Baseline이 없어 UNKNOWN 경로로 전환합니다.")
        route = "unknown_report"
    elif baseline_source == "group_default":
        warnings.append("group_default_baseline을 사용합니다.")

    return {
        "baseline": baseline,
        "baseline_source": baseline_source,
        "warnings": warnings,
        "route": route,
    }


def load_recent_episodes(
    state: AgentState,
    *,
    episodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    settings = get_settings()
    return {"recent_episodes": episodes[: settings.recent_episode_window * 2]}
