"""LangGraph Agent 상태 정의."""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # 입력
    raw_input: Dict[str, Any]
    validated_input: Optional[Dict[str, Any]]

    # 검증 / 분기
    validation_ok: bool
    validation_errors: List[str]
    route: str  # complete_report | unknown_report | low_confidence_report | error_response

    # Memory
    profile: Optional[Dict[str, Any]]
    baseline: Optional[Dict[str, Any]]
    baseline_source: str  # personal | group_default | none
    recent_episodes: List[Dict[str, Any]]

    # 분석
    cognitive_gaps: Dict[str, Dict[str, Any]]
    trend_analysis: Dict[str, Any]
    classification: Dict[str, Any]

    # 출력
    state_report: Optional[Dict[str, Any]]
    warnings: List[str]
    error: Optional[str]

    # DB 세션은 서비스 레이어에서 주입 (직렬화 불가 객체는 graph 외부 관리)
    user_id: str
    session_id: str
