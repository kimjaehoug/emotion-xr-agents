"""ActionPlan / PlanAction Pydantic 스키마.

Qwen(또는 Fallback Planner)이 산출하는 원시 JSON은 이 스키마로 파싱/검증된다.
검증에 실패하면 `app.validators.schema_validator`가 오류 목록을 반환하고
`app.planners.fallback_planner`가 규칙 기반 대안을 생성한다.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.enums import ActionType, PlanGoal, PlanRoute, PlannerSource, XrParameter


class PlanAction(BaseModel):
    """계획에 포함된 개별 행동."""

    action_type: ActionType
    xr_parameter: Optional[XrParameter] = None
    target_content_id: Optional[str] = None
    delta: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="XR 파라미터 변화량 제안치. 실제 적용 시 xr_max_parameter_delta로 clamp된다.",
    )
    final_value: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="clamp 적용 후 최종 파라미터 값(검증/런타임에서 계산).",
    )
    requires_confirmation: bool = False
    rationale: str = ""
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class ActionPlan(BaseModel):
    """XR Control Agent의 최종 산출물."""

    plan_id: str
    state_report_id: str
    user_id: str
    session_id: str
    goal: PlanGoal
    route: PlanRoute
    planner_source: PlannerSource
    actions: List[PlanAction] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)
    narrative: Optional[str] = None
    content_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed: bool = False
    idempotent_replay: bool = False
    memory_context: Optional[Dict[str, Any]] = None


class RawPlanOutput(BaseModel):
    """LLM(Qwen)이 직접 산출해야 하는 JSON 스키마.

    `plan_id` / `state_report_id` / `user_id` / `session_id` / `created_at`는
    서버가 주입하므로 LLM 출력에는 포함되지 않는다.
    """

    goal: PlanGoal
    route: PlanRoute
    actions: List[PlanAction] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    narrative: Optional[str] = None
