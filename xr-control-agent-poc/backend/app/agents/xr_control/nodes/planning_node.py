"""Qwen 호출 → 파싱 → 검증 → 복구/Fallback 파이프라인 노드."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agents.xr_control.nodes.context_node import build_llm_context
from app.agents.xr_control.state import AgentState
from app.core.config import Settings
from app.core.enums import PlannerSource
from app.llm.protocol import LLMConnectionError, LocalLLMClientProtocol
from app.llm.repair import attempt_repair
from app.llm.response_parser import parse_json_response
from app.planners.fallback_planner import FallbackPlanner
from app.planners.qwen_planner import QwenPlanner
from app.schemas.action_plan import RawPlanOutput
from app.validators.action_validator import validate_actions
from app.validators.content_validator import validate_content_actions
from app.validators.policy_validator import validate_policy
from app.validators.safety_validator import apply_safety_rules
from app.validators.schema_validator import validate_schema

logger = logging.getLogger(__name__)


def _validate_candidate(
    candidate: RawPlanOutput,
    *,
    state_level: str,
    confidence: float,
    policies: List[Dict[str, Any]],
    catalog: List[Dict[str, Any]],
    contents: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> List[str]:
    errors = validate_policy(
        state_level=state_level,
        confidence=confidence,
        route=candidate.route.value,
        policies=policies,
    )
    valid_actions, action_errors = validate_actions(
        actions=candidate.actions, catalog=catalog, profile=profile
    )
    errors.extend(action_errors)
    valid_actions, content_errors = validate_content_actions(
        actions=valid_actions, contents=contents, profile=profile
    )
    errors.extend(content_errors)
    candidate.actions = valid_actions
    return errors


def _parse_and_validate(
    raw_text: str,
    *,
    state_level: str,
    confidence: float,
    policies: List[Dict[str, Any]],
    catalog: List[Dict[str, Any]],
    contents: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> tuple[Optional[RawPlanOutput], List[str]]:
    parsed_dict, parse_error = parse_json_response(raw_text)
    if parse_error:
        return None, [parse_error]

    candidate, schema_errors = validate_schema(parsed_dict)  # type: ignore[arg-type]
    if candidate is None:
        return None, schema_errors

    errors = _validate_candidate(
        candidate,
        state_level=state_level,
        confidence=confidence,
        policies=policies,
        catalog=catalog,
        contents=contents,
        profile=profile,
    )
    return candidate, errors


def run_planning(
    state: AgentState,
    *,
    llm_client: LocalLLMClientProtocol,
    settings: Settings,
) -> Dict[str, Any]:
    context = build_llm_context(state)
    report = state.get("state_report") or {}
    state_level = report.get("state_level", "UNKNOWN")
    confidence = float(report.get("analysis_confidence") or 0.0)
    policies = state.get("policies") or []
    catalog = state.get("actions_catalog") or []
    contents = state.get("contents") or []
    profile = state.get("profile") or {}

    warnings: List[str] = list(state.get("plan_warnings") or [])
    planner_source = PlannerSource.QWEN.value
    plan: Optional[RawPlanOutput] = None

    qwen_planner = QwenPlanner(llm_client)
    try:
        raw_text, system_prompt, user_prompt = qwen_planner.plan(context)
        candidate, errors = _parse_and_validate(
            raw_text,
            state_level=state_level,
            confidence=confidence,
            policies=policies,
            catalog=catalog,
            contents=contents,
            profile=profile,
        )

        if errors and settings.llm_repair_max_attempts > 0:
            repaired_text = attempt_repair(
                llm_client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_output=raw_text,
                errors=errors,
                json_schema=RawPlanOutput.model_json_schema(),
            )
            if repaired_text:
                repaired_candidate, repaired_errors = _parse_and_validate(
                    repaired_text,
                    state_level=state_level,
                    confidence=confidence,
                    policies=policies,
                    catalog=catalog,
                    contents=contents,
                    profile=profile,
                )
                if not repaired_errors and repaired_candidate is not None:
                    candidate, errors = repaired_candidate, []
                else:
                    errors = repaired_errors or errors
                    warnings.append("LLM 복구(repair) 시도가 검증을 통과하지 못했습니다.")

        if errors or candidate is None:
            warnings.append(f"Qwen 출력 검증 실패로 Fallback Planner를 사용합니다: {errors}")
            plan = FallbackPlanner().plan(context)
            planner_source = PlannerSource.FALLBACK.value
        else:
            plan = candidate
            planner_source = PlannerSource.QWEN.value

    except LLMConnectionError as exc:
        warnings.append(f"로컬 LLM 연결 실패로 Fallback Planner를 사용합니다: {exc}")
        plan = FallbackPlanner().plan(context)
        planner_source = PlannerSource.FALLBACK.value

    assert plan is not None
    safety_warnings = apply_safety_rules(
        actions=plan.actions,
        profile=profile,
        xr_state=state.get("xr_state") or {},
        settings=settings,
    )
    warnings.extend(safety_warnings)

    return {
        "raw_plan_output": plan.model_dump(mode="json"),
        "planner_source": planner_source,
        "plan_warnings": warnings,
        "plan_errors": [],
    }
