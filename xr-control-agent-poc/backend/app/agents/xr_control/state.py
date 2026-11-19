"""XR Control Agent LangGraph 상태 정의."""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # 입력
    raw_state_report: Dict[str, Any]
    state_report: Optional[Dict[str, Any]]

    # 검증 / 식별자
    validation_ok: bool
    validation_errors: List[str]
    user_id: str
    session_id: str
    state_report_id: str

    # Memory / 카탈로그 컨텍스트
    profile: Dict[str, Any]
    policies: List[Dict[str, Any]]
    actions_catalog: List[Dict[str, Any]]
    contents: List[Dict[str, Any]]
    xr_state: Dict[str, Any]
    recent_episodes: List[Dict[str, Any]]
    summary: Dict[str, Any]
    memory_context: Dict[str, Any]

    # 의사결정
    need_llm: bool
    shortcut_reason: Optional[str]

    # Planner 산출물
    raw_plan_output: Optional[Dict[str, Any]]
    planner_source: str
    plan_warnings: List[str]
    plan_errors: List[str]

    # 최종 산출
    action_plan: Optional[Dict[str, Any]]
    idempotent_replay: bool
