"""API 요청/응답 Pydantic 스키마."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.action_plan import ActionPlan, PlanAction


class UserProfile(BaseModel):
    """Profile Memory. 사용자별 자동 제어 허용 여부 / 제약을 담는다."""

    auto_control_allowed: bool = True
    forbidden_categories: List[str] = Field(default_factory=list)
    sensitivities: Dict[str, float] = Field(default_factory=dict)
    rejected_actions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class UserCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    profile: UserProfile = Field(default_factory=UserProfile)


class UserResponse(BaseModel):
    user_id: str
    profile: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PolicyCreate(BaseModel):
    policy_key: str
    state_level: Literal["NORMAL", "WATCH", "ACTION_REQUIRED", "UNKNOWN"]
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    allowed_routes: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    is_active: bool = True


class PolicyResponse(BaseModel):
    id: int
    policy_key: str
    state_level: str
    min_confidence: float
    allowed_routes: List[str]
    description: Optional[str] = None
    is_active: bool
    created_at: datetime


class ActionCatalogCreate(BaseModel):
    action_type: str
    xr_parameter: Optional[str] = None
    category: Optional[str] = None
    max_delta: Optional[float] = Field(None, ge=0.0, le=1.0)
    requires_confirmation: bool = False
    description: Optional[str] = None
    is_active: bool = True


class ActionCatalogResponse(BaseModel):
    id: int
    action_type: str
    xr_parameter: Optional[str] = None
    category: Optional[str] = None
    max_delta: Optional[float] = None
    requires_confirmation: bool
    description: Optional[str] = None
    is_active: bool
    created_at: datetime


class ContentCreate(BaseModel):
    content_id: str
    title: str
    content_type: str
    category: Optional[str] = None
    difficulty: float = Field(0.5, ge=0.0, le=1.0)
    visual_complexity: float = Field(0.5, ge=0.0, le=1.0)
    audio_stimulation: float = Field(0.5, ge=0.0, le=1.0)
    interaction_density: float = Field(0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True


class ContentResponse(BaseModel):
    id: int
    content_id: str
    title: str
    content_type: str
    category: Optional[str] = None
    difficulty: float
    visual_complexity: float
    audio_stimulation: float
    interaction_density: float
    tags: List[str]
    is_active: bool
    created_at: datetime


class PlanResponse(ActionPlan):
    """POST /plan 응답. ActionPlan 필드를 그대로 노출한다."""


class ExecuteRequest(BaseModel):
    plan_id: str = Field(..., min_length=1)


class ConfirmationResponse(BaseModel):
    confirmation_id: str
    plan_id: str
    user_id: str
    session_id: str
    action_index: int
    action: Dict[str, Any]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None


class ExecutionResponse(BaseModel):
    execution_id: str
    plan_id: str
    confirmation_id: Optional[str] = None
    user_id: str
    session_id: str
    action: Dict[str, Any]
    status: str
    result: Dict[str, Any]
    feedback_effect: Optional[str] = None
    created_at: datetime


class ExecuteResponse(BaseModel):
    plan_id: str
    already_executed: bool = False
    confirmations: List[ConfirmationResponse] = Field(default_factory=list)
    executions: List[ExecutionResponse] = Field(default_factory=list)


class ConfirmationDecisionRequest(BaseModel):
    decision: Literal["ACCEPTED", "REJECTED"]


class FeedbackRequest(BaseModel):
    execution_id: str = Field(..., min_length=1)
    effect: Literal["positive", "neutral", "negative"]
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    execution_id: str
    effect: str
    profile_updated: bool = False


class XrEpisodeResponse(BaseModel):
    id: int
    user_id: str
    session_id: str
    state_report_id: str
    state_level: str
    route: str
    planner_source: str
    plan: Dict[str, Any]
    created_at: datetime


class XrSummaryResponse(BaseModel):
    user_id: str
    summary: Dict[str, Any]
    recent_episode_count: int
    updated_at: Optional[datetime] = None


class SeedResponse(BaseModel):
    message: str
    users_created: List[str]
    policies_created: int
    actions_created: int
    contents_created: int


class LLMHealthResponse(BaseModel):
    reachable: bool
    base_url: str
    model: str
    detail: Optional[str] = None


class TestLLMRequest(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt: str = Field(..., min_length=1)


class TestLLMResponse(BaseModel):
    raw_output: str
    parsed: Optional[Dict[str, Any]] = None
    parse_error: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


__all__ = [
    "UserProfile",
    "UserCreate",
    "UserResponse",
    "PolicyCreate",
    "PolicyResponse",
    "ActionCatalogCreate",
    "ActionCatalogResponse",
    "ContentCreate",
    "ContentResponse",
    "PlanResponse",
    "ExecuteRequest",
    "ExecuteResponse",
    "ConfirmationResponse",
    "ConfirmationDecisionRequest",
    "ExecutionResponse",
    "FeedbackRequest",
    "FeedbackResponse",
    "XrEpisodeResponse",
    "XrSummaryResponse",
    "SeedResponse",
    "LLMHealthResponse",
    "TestLLMRequest",
    "TestLLMResponse",
    "ErrorResponse",
    "ActionPlan",
    "PlanAction",
]
