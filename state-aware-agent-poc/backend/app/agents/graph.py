"""LangGraph 오케스트레이션.

노드:
1. validate_input
2. load_profile_memory
3. load_baseline_memory
4. load_recent_episodes
5. compute_cognitive_gap
6. analyze_trend
7. classify_state
8. generate_state_report
9. save_episode
10. update_summary_memory

분기: error_response | unknown_report | low_confidence_report | complete_report
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.nodes.generate_report import (
    analyze_trend,
    build_summary_payload,
    classify_state,
    compute_cognitive_gap,
    generate_state_report,
)
from app.agents.nodes.load_memory import (
    load_baseline_memory,
    load_profile_memory,
    load_recent_episodes,
)
from app.agents.nodes.validate_input import validate_input
from app.agents.state import AgentState
from app.models import EpisodicMemory
from app.repositories.memory_repo import EpisodeRepository, SummaryRepository
from app.repositories.user_repo import UserRepository
from app.memory.service import StateMemoryService
from app.services.baseline_service import BaselineService


def _route_after_validate(state: AgentState) -> Literal["error_response", "load_profile"]:
    if not state.get("validation_ok"):
        return "error_response"
    return "load_profile"


def build_graph() -> Any:
    """컴파일된 LangGraph 반환. DB 의존 노드는 런타임 클로저로 바인딩한다."""

    graph = StateGraph(AgentState)

    # 순수 노드
    graph.add_node("validate_input", validate_input)
    graph.add_node("compute_cognitive_gap", compute_cognitive_gap)
    graph.add_node("analyze_trend", analyze_trend)
    graph.add_node("classify_state", classify_state)
    graph.add_node("generate_state_report", generate_state_report)

    # 플레이스홀더 — 실제 DB 바인딩은 run_agent에서 수행
    # 여기서는 그래프 구조만 정의하고, run_agent가 순차 실행 + 조건부 분기를 담당할 수도 있음.
    # LangGraph 정식 연결을 위해 래퍼 노드를 둔다.

    def passthrough_profile(state: AgentState) -> Dict[str, Any]:
        return {}

    def passthrough_baseline(state: AgentState) -> Dict[str, Any]:
        return {}

    def passthrough_episodes(state: AgentState) -> Dict[str, Any]:
        return {}

    def passthrough_save(state: AgentState) -> Dict[str, Any]:
        return {}

    def passthrough_summary(state: AgentState) -> Dict[str, Any]:
        return {}

    def error_response_node(state: AgentState) -> Dict[str, Any]:
        updated = dict(state)
        updated["route"] = "error_response"
        return generate_state_report(updated)  # type: ignore[arg-type]

    graph.add_node("load_profile_memory", passthrough_profile)
    graph.add_node("load_baseline_memory", passthrough_baseline)
    graph.add_node("load_recent_episodes", passthrough_episodes)
    graph.add_node("save_episode", passthrough_save)
    graph.add_node("update_summary_memory", passthrough_summary)
    graph.add_node("error_response", error_response_node)

    graph.set_entry_point("validate_input")
    graph.add_conditional_edges(
        "validate_input",
        _route_after_validate,
        {
            "error_response": "error_response",
            "load_profile": "load_profile_memory",
        },
    )
    graph.add_edge("load_profile_memory", "load_baseline_memory")
    graph.add_edge("load_baseline_memory", "load_recent_episodes")
    graph.add_edge("load_recent_episodes", "compute_cognitive_gap")
    graph.add_edge("compute_cognitive_gap", "analyze_trend")
    graph.add_edge("analyze_trend", "classify_state")
    graph.add_edge("classify_state", "generate_state_report")
    graph.add_edge("generate_state_report", "save_episode")
    graph.add_edge("save_episode", "update_summary_memory")
    graph.add_edge("update_summary_memory", END)
    graph.add_edge("error_response", END)

    return graph.compile()


class StateAgentRunner:
    """DB 세션을 주입하여 LangGraph 파이프라인을 실행한다."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.baseline_service = BaselineService(db)
        self.episode_repo = EpisodeRepository(db)
        self.summary_repo = SummaryRepository(db)
        self.memory = StateMemoryService(db)

    def run(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        state: AgentState = {
            "raw_input": raw_input,
            "warnings": [],
            "recent_episodes": [],
            "cognitive_gaps": {},
            "validation_ok": False,
            "validation_errors": [],
            "route": "complete_report",
            "baseline_source": "none",
        }

        # 1. validate
        state.update(validate_input(state))
        if not state.get("validation_ok"):
            state.update(generate_state_report({**state, "route": "error_response"}))
            return state["state_report"]  # type: ignore[return-value]

        user_id = state["user_id"]

        # 2. profile
        user = self.user_repo.get_by_user_id(user_id)
        profile = user.profile_json if user else None
        state.update(load_profile_memory(state, profile=profile))
        if user is None:
            warnings = list(state.get("warnings") or [])
            warnings.append(f"사용자 '{user_id}' 프로필이 없습니다. 분석을 계속합니다.")
            state["warnings"] = warnings

        # 3. baseline
        baseline, source = self.baseline_service.baseline_dict_for_agent(user_id)
        state.update(load_baseline_memory(state, baseline=baseline, baseline_source=source))

        # 4. episodes
        episodes = self.episode_repo.list_recent(user_id, limit=20)
        ep_dicts = [
            {
                "session_id": e.session_id,
                "state_level": e.state_level,
                "gap_json": e.gap_json,
                "state_report_json": e.state_report_json,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in episodes
        ]
        state.update(load_recent_episodes(state, episodes=ep_dicts))

        # 5-8 analysis chain
        state.update(compute_cognitive_gap(state))
        state.update(analyze_trend(state))
        state.update(classify_state(state))
        state.update(generate_state_report(state))

        report = state["state_report"]
        assert report is not None

        # 9. save episode (오류 경로가 아니면)
        if state.get("route") != "error_response":
            # Memory v2: 작업 메모리 활성화 + 능동 경고를 리포트에 첨부 (후속 XR Agent가 소비)
            report["memory_context"] = self.memory.build_working_memory(report, baseline=state.get("baseline"))

            episode = EpisodicMemory(
                user_id=report["user_id"],
                session_id=report["session_id"],
                input_json=state.get("validated_input") or raw_input,
                gap_json=report.get("cognitive_gap"),
                state_level=report["state_level"],
                state_report_json=report,
            )
            self.episode_repo.save(episode)

            # 10. summary
            summary = build_summary_payload(
                user_id=report["user_id"],
                recent_episodes=ep_dicts,
                latest_report=report,
            )
            self.summary_repo.upsert(
                user_id=report["user_id"],
                summary_json=summary,
                recent_episode_count=self.episode_repo.count(report["user_id"]),
            )

            # Memory v2: 원시 증거 append → 지식 카드 갱신
            self.memory.record_analysis(state.get("validated_input") or raw_input, report)
            report["memory_context"]["knowledge_updates"] = self.memory.update_knowledge(report["user_id"])

        return report


# 그래프 객체 (구조 검증 / 시각화용)
compiled_graph = build_graph()
