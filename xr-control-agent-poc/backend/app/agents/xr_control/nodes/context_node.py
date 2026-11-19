"""정책/행동/콘텐츠/Memory 컨텍스트 결합 노드 (순수 함수, DB 접근은 러너가 수행)."""

from __future__ import annotations

from typing import Any, Dict, List

from app.agents.xr_control.state import AgentState


def apply_context(
    state: AgentState,
    *,
    profile: Dict[str, Any],
    policies: List[Dict[str, Any]],
    actions_catalog: List[Dict[str, Any]],
    contents: List[Dict[str, Any]],
    xr_state: Dict[str, Any],
    recent_episodes: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "profile": profile,
        "policies": policies,
        "actions_catalog": actions_catalog,
        "contents": contents,
        "xr_state": xr_state,
        "recent_episodes": recent_episodes,
        "summary": summary,
    }


def build_llm_context(state: AgentState) -> Dict[str, Any]:
    """Planner(Qwen/Fallback)에 전달할 컨텍스트 딕셔너리 구성."""
    return {
        "state_report": state.get("state_report"),
        "profile": state.get("profile") or {},
        "policies": state.get("policies") or [],
        "actions": state.get("actions_catalog") or [],
        "contents": state.get("contents") or [],
        "xr_state": state.get("xr_state") or {},
        "summary": state.get("summary") or {},
        "memory": state.get("memory_context") or {},
    }
