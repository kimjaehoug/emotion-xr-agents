"""규칙 기반 Fallback Planner.

Qwen 연결 실패, 파싱/검증 실패(복구 실패 포함), 또는 비즈니스 규칙상
LLM 호출이 불필요한 경우(NORMAL/UNKNOWN/저신뢰도)에 사용된다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.enums import ActionType, PlanGoal, PlanRoute, XrParameter
from app.memory.service import PARAM_KO
from app.schemas.action_plan import PlanAction, RawPlanOutput

DEFAULT_XR_DELTA = -0.10


class FallbackPlanner:
    """결정적(deterministic) 규칙으로 안전한 기본 계획을 생성한다."""

    def plan(self, context: Dict[str, Any]) -> RawPlanOutput:
        state_report = context.get("state_report") or {}
        state_level = state_report.get("state_level", "UNKNOWN")
        confidence = float(state_report.get("analysis_confidence") or 0.0)
        requires_response = bool(state_report.get("requires_response"))
        min_observation_confidence = context.get("min_observation_confidence", 0.60)
        catalog = context.get("actions") or []

        if state_level == "UNKNOWN" or confidence < min_observation_confidence:
            return self._observation_plan(
                "상태가 UNKNOWN이거나 분석 신뢰도가 낮아 관찰을 지속합니다."
                if state_level == "UNKNOWN"
                else f"분석 신뢰도({confidence:.2f})가 기준보다 낮아 관찰을 지속합니다."
            )

        if state_level == "NORMAL" and not requires_response:
            return RawPlanOutput(
                goal=PlanGoal.MAINTAIN_CURRENT_STATE,
                route=PlanRoute.NO_ACTION,
                actions=[
                    PlanAction(
                        action_type=ActionType.KEEP_CURRENT_STATE,
                        rationale="상태가 정상이며 응답이 필요하지 않아 현재 상태를 유지합니다.",
                        confidence=confidence,
                    )
                ],
                confidence=confidence,
                narrative="정상 상태가 유지되고 있어 별도 조치를 취하지 않습니다.",
            )

        if state_level == "WATCH":
            xr_entry, memory_note = self._choose_xr_entry(catalog, context.get("memory") or {})
            if xr_entry is not None:
                return RawPlanOutput(
                    goal=PlanGoal.REDUCE_COGNITIVE_BURDEN,
                    route=PlanRoute.XR_OPTIMIZATION,
                    actions=[
                        PlanAction(
                            action_type=ActionType.UPDATE_XR_PARAMETER,
                            xr_parameter=XrParameter(xr_entry["xr_parameter"]),
                            delta=DEFAULT_XR_DELTA,
                            requires_confirmation=bool(xr_entry.get("requires_confirmation")),
                            rationale=f"주의(WATCH) 상태로 '{PARAM_KO.get(xr_entry['xr_parameter'], xr_entry['xr_parameter'])}' 값을 소폭 낮춥니다.{memory_note}",
                            confidence=confidence,
                        )
                    ],
                    confidence=confidence,
                    narrative=f"인지 부하 완화를 위해 '{PARAM_KO.get(xr_entry['xr_parameter'], xr_entry['xr_parameter'])}' 값을 낮추는 조절을 제안합니다.",
                )
            return self._observation_plan("WATCH 상태이나 사용 가능한(회피 학습되지 않은) XR 조정 행동이 없습니다.")

        if state_level == "ACTION_REQUIRED":
            break_entry = self._find_action(catalog, ActionType.SUGGEST_BREAK.value)
            return RawPlanOutput(
                goal=PlanGoal.SUPPORT_ATTENTION_RECOVERY,
                route=PlanRoute.BREAK_SUGGESTION,
                actions=[
                    PlanAction(
                        action_type=ActionType.SUGGEST_BREAK,
                        requires_confirmation=True if break_entry is None else bool(
                            break_entry.get("requires_confirmation", True)
                        ),
                        rationale="조치 필요 상태가 지속되어 휴식을 제안합니다.",
                        confidence=confidence,
                    )
                ],
                confidence=confidence,
                narrative="누적된 인지 부하/피로 신호로 짧은 휴식을 제안합니다.",
            )

        return self._observation_plan(f"알 수 없는 상태수준('{state_level}')으로 관찰을 지속합니다.")

    def _choose_xr_entry(
        self, catalog: List[Dict[str, Any]], memory: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """기본은 visual_complexity. 절차 메모리에서 효과가 확인된 파라미터를 우선하고, 회피 학습된 것은 제외한다."""
        avoid = set(memory.get("avoid_signatures") or [])
        prefix = f"{ActionType.UPDATE_XR_PARAMETER.value}:"
        candidates = [
            e for e in catalog
            if e.get("action_type") == ActionType.UPDATE_XR_PARAMETER.value
            and e.get("xr_parameter")
            and f"{prefix}{e['xr_parameter']}" not in avoid
        ]
        if not candidates:
            return None, ""
        for proc in memory.get("procedures") or []:
            value = proc.get("value") or {}
            sig = str(proc.get("key", "")).split(".", 2)[-1]
            if value.get("effectiveness", 0) > 0 and sig.startswith(prefix):
                for e in candidates:
                    if f"{prefix}{e['xr_parameter']}" == sig:
                        return e, f" (조절 효과 이력: 효과 점수 {value['effectiveness']:+.2f}, {value.get('n')}회)"
        for e in candidates:
            if e["xr_parameter"] == XrParameter.VISUAL_COMPLEXITY.value:
                return e, ""
        return candidates[0], " (기본 조절에 부정 반응이 누적되어 대체 조절 선택)"

    @staticmethod
    def _observation_plan(rationale: str) -> RawPlanOutput:
        return RawPlanOutput(
            goal=PlanGoal.CONTINUE_OBSERVATION,
            route=PlanRoute.OBSERVATION,
            actions=[
                PlanAction(
                    action_type=ActionType.OBSERVE,
                    rationale=rationale,
                    confidence=0.5,
                )
            ],
            confidence=0.5,
            narrative=rationale,
        )

    @staticmethod
    def _find_action(
        catalog: List[Dict[str, Any]], action_type: str, xr_parameter: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        for entry in catalog:
            if entry.get("action_type") != action_type:
                continue
            if xr_parameter is not None and entry.get("xr_parameter") != xr_parameter:
                continue
            return entry
        return None
