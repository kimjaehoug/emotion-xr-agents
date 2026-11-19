"""XR Control Agent LangGraph 오케스트레이션.

플로우:
1. validate_state_report      — StateReport 스키마 검증
2. load_context (DB)          — Profile/정책/행동/콘텐츠/모의 XR 상태/Memory 로드
3. apply_context               — 컨텍스트 결합
4. decide_shortcut             — Qwen 호출 필요 여부 판단
5. run_planning 또는 Fallback  — Qwen 호출→파싱→검증→복구, 실패 시 규칙 기반 대안
6. postprocess                 — 라우트별 콘텐츠 랭킹, ActionPlan 조립
7. save (DB)                   — action_plans / processed_state_reports / xr_episodic_memories / xr_summary_memories

LangGraph는 구조 검증/시각화용으로 컴파일하며, 실제 실행은 DB 세션이 필요하므로
`XrAgentRunner`가 노드를 순차 호출하는 방식(StateAgentRunner 패턴)을 사용한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.xr_control.nodes.context_node import apply_context, build_llm_context
from app.agents.xr_control.nodes.decision_node import decide_shortcut
from app.agents.xr_control.nodes.planning_node import run_planning
from app.agents.xr_control.nodes.validate_node import validate_state_report
from app.agents.xr_control.state import AgentState
from app.core.config import Settings, get_settings
from app.core.enums import PlannerSource
from app.llm.protocol import LocalLLMClientProtocol
from app.llm.qwen_client import QwenLocalLLMClient
from app.models import ActionPlanRecord
from app.planners.fallback_planner import FallbackPlanner
from app.repositories.catalog_repo import ActionCatalogRepository, ContentRepository, PolicyRepository
from app.repositories.memory_repo import ProcessedReportRepository
from app.repositories.plan_repo import ActionPlanRepository
from app.repositories.user_repo import UserRepository
from app.services.content_ranker import rank_contents
from app.memory.service import XrMemoryV2, apply_memory_guards
from app.services.memory_service import XrMemoryService
from app.services.mock_xr_runtime import MockXrRuntime

logger = logging.getLogger(__name__)

DEFAULT_PROFILE: Dict[str, Any] = {
    "auto_control_allowed": True,
    "forbidden_categories": [],
    "sensitivities": {},
    "rejected_actions": [],
}


def _route_after_validate(state: AgentState) -> Literal["error", "load_context"]:
    return "load_context" if state.get("validation_ok") else "error"


def _route_after_decision(state: AgentState) -> Literal["plan_with_llm", "plan_fallback"]:
    return "plan_with_llm" if state.get("need_llm") else "plan_fallback"


def build_graph() -> Any:
    """구조 검증/시각화용 컴파일된 LangGraph. 실제 실행은 `XrAgentRunner`가 담당한다."""

    graph = StateGraph(AgentState)

    graph.add_node("validate_state_report", validate_state_report)

    def _passthrough(_: AgentState) -> Dict[str, Any]:
        return {}

    graph.add_node("load_context", _passthrough)
    graph.add_node("decide_shortcut", decide_shortcut)
    graph.add_node("plan_with_llm", _passthrough)
    graph.add_node("plan_fallback", _passthrough)
    graph.add_node("postprocess_and_save", _passthrough)
    graph.add_node("error", _passthrough)

    graph.set_entry_point("validate_state_report")
    graph.add_conditional_edges(
        "validate_state_report",
        _route_after_validate,
        {"error": "error", "load_context": "load_context"},
    )
    graph.add_edge("load_context", "decide_shortcut")
    graph.add_conditional_edges(
        "decide_shortcut",
        _route_after_decision,
        {"plan_with_llm": "plan_with_llm", "plan_fallback": "plan_fallback"},
    )
    graph.add_edge("plan_with_llm", "postprocess_and_save")
    graph.add_edge("plan_fallback", "postprocess_and_save")
    graph.add_edge("postprocess_and_save", END)
    graph.add_edge("error", END)

    return graph.compile()


class XrAgentRunner:
    """DB 세션 + LLM 클라이언트를 주입하여 XR Control Agent 파이프라인을 실행한다."""

    def __init__(
        self,
        db: Session,
        *,
        llm_client: Optional[LocalLLMClientProtocol] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.llm_client = llm_client or QwenLocalLLMClient(self.settings)

        self.user_repo = UserRepository(db)
        self.policy_repo = PolicyRepository(db)
        self.action_repo = ActionCatalogRepository(db)
        self.content_repo = ContentRepository(db)
        self.processed_repo = ProcessedReportRepository(db)
        self.plan_repo = ActionPlanRepository(db)
        self.xr_runtime = MockXrRuntime(db)
        self.memory_service = XrMemoryService(db)
        self.memory_v2 = XrMemoryV2(db)

    def run(self, raw_state_report: Dict[str, Any]) -> Dict[str, Any]:
        # 0. idempotency: 이미 처리된 state_report_id는 재실행하지 않고 이전 결과를 반환한다.
        state_report_id = str(raw_state_report.get("state_report_id") or "")
        if state_report_id:
            existing_processed = self.processed_repo.get(state_report_id)
            if existing_processed is not None:
                result = dict(existing_processed.result_json)
                result["idempotent_replay"] = True
                return result
            # processed 없이 plan만 남은 경우(이전 저장 중단)에도 재실행 충돌 방지
            existing_plan = self.plan_repo.get_by_state_report_id(state_report_id)
            if existing_plan is not None:
                result = {
                    "plan_id": existing_plan.plan_id,
                    "state_report_id": existing_plan.state_report_id,
                    "user_id": existing_plan.user_id,
                    "session_id": existing_plan.session_id,
                    "goal": existing_plan.goal,
                    "route": existing_plan.route,
                    "planner_source": existing_plan.planner_source,
                    "actions": existing_plan.actions_json or [],
                    "confidence": existing_plan.confidence,
                    "warnings": existing_plan.warnings_json or [],
                    "narrative": existing_plan.narrative,
                    "content_candidates": existing_plan.content_candidates_json or [],
                    "created_at": (
                        existing_plan.created_at.isoformat()
                        if existing_plan.created_at
                        else None
                    ),
                    "executed": existing_plan.executed_at is not None,
                    "idempotent_replay": True,
                }
                return result

        state: AgentState = {
            "raw_state_report": raw_state_report,
            "plan_warnings": [],
            "plan_errors": [],
        }

        # 1. validate
        state.update(validate_state_report(state))
        if not state.get("validation_ok"):
            errors = state.get("validation_errors") or ["알 수 없는 검증 오류"]
            raise ValueError("StateReport 검증 실패: " + "; ".join(errors))

        user_id = state["user_id"]
        session_id = state["session_id"]

        # 2. load context (DB)
        user = self.user_repo.get_or_create(user_id, dict(DEFAULT_PROFILE))
        policies = [self._policy_to_dict(p) for p in self.policy_repo.list_active()]
        actions_catalog = [self._action_to_dict(a) for a in self.action_repo.list_active()]
        contents = [self._content_to_dict(c) for c in self.content_repo.list_active()]
        xr_state = self.xr_runtime.get_state(user_id, session_id)
        recent_episodes = self.memory_service.load_recent(user_id, limit=20)
        summary = self.memory_service.load_summary_dict(user_id)

        state.update(
            apply_context(
                state,
                profile=user.profile_json or dict(DEFAULT_PROFILE),
                policies=policies,
                actions_catalog=actions_catalog,
                contents=contents,
                xr_state=xr_state,
                recent_episodes=recent_episodes,
                summary=summary,
            )
        )

        # 2-1. Memory v2: 절차 메모리·회피 학습·능동 경고를 작업 메모리로 활성화
        state["memory_context"] = self.memory_v2.build_working_memory(state["state_report"], recent_episodes)

        # 3. 단축 경로 판단 (NORMAL/UNKNOWN/저신뢰도)
        state.update(
            decide_shortcut(state, min_observation_confidence=self.settings.xr_observation_min_confidence)
        )

        # 4. Planning
        if state.get("need_llm"):
            state.update(run_planning(state, llm_client=self.llm_client, settings=self.settings))
        else:
            context = build_llm_context(state)
            plan = FallbackPlanner().plan(context)
            from app.validators.safety_validator import apply_safety_rules

            warnings = list(state.get("plan_warnings") or [])
            reason = state.get("shortcut_reason")
            if reason:
                warnings.append(reason)
            warnings.extend(
                apply_safety_rules(
                    actions=plan.actions,
                    profile=state.get("profile") or {},
                    xr_state=state.get("xr_state") or {},
                    settings=self.settings,
                )
            )
            state.update(
                {
                    "raw_plan_output": plan.model_dump(mode="json"),
                    "planner_source": PlannerSource.FALLBACK.value,
                    "plan_warnings": warnings,
                }
            )

        # 4-1. 메모리 가드 (LLM/Fallback 공통 후처리)
        raw_actions = (state.get("raw_plan_output") or {}).get("actions") or []
        state["plan_warnings"] = list(state.get("plan_warnings") or []) + apply_memory_guards(
            raw_actions, state["memory_context"]
        )

        # 5. postprocess: 콘텐츠 랭킹 + ActionPlan 조립
        action_plan = self._build_action_plan(state)

        # 6. save
        self._save(state, action_plan)

        return action_plan

    # ------------------------------------------------------------------
    # 컨텍스트 직렬화 헬퍼
    # ------------------------------------------------------------------
    @staticmethod
    def _policy_to_dict(policy: Any) -> Dict[str, Any]:
        return {
            "policy_key": policy.policy_key,
            "state_level": policy.state_level,
            "min_confidence": policy.min_confidence,
            "allowed_routes": policy.allowed_routes_json,
        }

    @staticmethod
    def _action_to_dict(action: Any) -> Dict[str, Any]:
        return {
            "action_type": action.action_type,
            "xr_parameter": action.xr_parameter,
            "category": action.category,
            "max_delta": action.max_delta,
            "requires_confirmation": action.requires_confirmation,
        }

    @staticmethod
    def _content_to_dict(content: Any) -> Dict[str, Any]:
        return {
            "content_id": content.content_id,
            "title": content.title,
            "content_type": content.content_type,
            "category": content.category,
            "difficulty": content.difficulty,
            "visual_complexity": content.visual_complexity,
            "audio_stimulation": content.audio_stimulation,
            "interaction_density": content.interaction_density,
            "tags": content.tags_json,
        }

    # ------------------------------------------------------------------
    # ActionPlan 조립
    # ------------------------------------------------------------------
    def _build_action_plan(self, state: AgentState) -> Dict[str, Any]:
        raw_plan = state.get("raw_plan_output") or {}
        route = raw_plan.get("route", "OBSERVATION")

        content_candidates: List[Dict[str, Any]] = []
        if route == "CONTENT_RECOMMENDATION":
            content_candidates = rank_contents(
                contents=state.get("contents") or [],
                profile=state.get("profile") or {},
                top_k=self.settings.content_recommendation_top_k,
            )

        return {
            "plan_id": f"PLAN-{uuid4().hex[:10].upper()}",
            "state_report_id": state["state_report_id"],
            "user_id": state["user_id"],
            "session_id": state["session_id"],
            "goal": raw_plan.get("goal"),
            "route": route,
            "planner_source": state.get("planner_source", PlannerSource.FALLBACK.value),
            "actions": raw_plan.get("actions", []),
            "confidence": raw_plan.get("confidence", 0.0),
            "warnings": state.get("plan_warnings") or [],
            "narrative": raw_plan.get("narrative"),
            "content_candidates": content_candidates,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "executed": False,
            "idempotent_replay": False,
            "memory_context": state.get("memory_context"),
        }

    # ------------------------------------------------------------------
    # 저장
    # ------------------------------------------------------------------
    def _save(self, state: AgentState, action_plan: Dict[str, Any]) -> None:
        record = ActionPlanRecord(
            plan_id=action_plan["plan_id"],
            state_report_id=action_plan["state_report_id"],
            user_id=action_plan["user_id"],
            session_id=action_plan["session_id"],
            goal=str(action_plan.get("goal")),
            route=str(action_plan.get("route")),
            planner_source=str(action_plan.get("planner_source")),
            confidence=float(action_plan.get("confidence") or 0.0),
            actions_json=action_plan.get("actions", []),
            warnings_json=action_plan.get("warnings", []),
            narrative=action_plan.get("narrative"),
            content_candidates_json=action_plan.get("content_candidates", []),
        )
        self.plan_repo.save(record)

        self.processed_repo.save(
            state_report_id=action_plan["state_report_id"],
            user_id=action_plan["user_id"],
            session_id=action_plan["session_id"],
            result_json=action_plan,
        )

        self.memory_service.save_episode(
            user_id=action_plan["user_id"],
            session_id=action_plan["session_id"],
            state_report_id=action_plan["state_report_id"],
            state_level=(state.get("state_report") or {}).get("state_level", "UNKNOWN"),
            route=str(action_plan.get("route")),
            planner_source=str(action_plan.get("planner_source")),
            plan_json=action_plan,
        )
        recent = self.memory_service.load_recent(action_plan["user_id"], limit=20)
        self.memory_service.upsert_summary(action_plan["user_id"], recent)
        self.memory_v2.record_plan(state.get("state_report") or {}, action_plan)


# 그래프 객체 (구조 검증/시각화용)
compiled_graph = build_graph()
