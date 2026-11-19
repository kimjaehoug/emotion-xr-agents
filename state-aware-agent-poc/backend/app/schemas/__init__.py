"""Pydantic 입력/출력 스키마."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CognitiveMetrics(BaseModel):
    cognitive_load: float = Field(..., ge=0.0, le=1.0)
    attention: float = Field(..., ge=0.0, le=1.0)
    fatigue: float = Field(..., ge=0.0, le=1.0)


class ContextData(BaseModel):
    content_id: Optional[str] = None
    content_type: Optional[str] = None
    difficulty: Optional[float] = Field(None, ge=0.0, le=1.0)
    visual_complexity: Optional[float] = Field(None, ge=0.0, le=1.0)
    audio_stimulation: Optional[float] = Field(None, ge=0.0, le=1.0)
    elapsed_time_min: Optional[float] = Field(None, ge=0.0)


class EmotionContextInput(BaseModel):
    """감정 매핑 Agent 출력 연계 (선택)."""

    label: Optional[str] = None
    intensity: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class DataQuality(BaseModel):
    cognitive_confidence: float = Field(..., ge=0.0, le=1.0)
    completeness: float = Field(..., ge=0.0, le=1.0)


class CognitiveInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    timestamp: datetime
    cognitive_metrics: CognitiveMetrics
    context: Optional[ContextData] = None
    data_quality: DataQuality
    emotion_context: Optional[EmotionContextInput] = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Any:
        if isinstance(v, str):
            # ISO 8601 허용 (Z 포함)
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class UserProfile(BaseModel):
    preferred_content_types: List[str] = Field(default_factory=list)
    sensory_sensitivity: Dict[str, float] = Field(default_factory=dict)
    xr_experience_level: Literal["none", "beginner", "intermediate", "advanced"] = "none"
    accessibility_constraints: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class UserCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    profile: UserProfile = Field(default_factory=UserProfile)


class UserResponse(BaseModel):
    user_id: str
    profile: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BaselineObservationCreate(BaseModel):
    session_id: str = Field(..., min_length=1)
    cognitive_load: float = Field(..., ge=0.0, le=1.0)
    attention: float = Field(..., ge=0.0, le=1.0)
    fatigue: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(0.9, ge=0.0, le=1.0)
    completeness: float = Field(0.9, ge=0.0, le=1.0)
    is_normal_confirmed: bool = True


class MetricBounds(BaseModel):
    center: float
    lower: float
    upper: float


class BaselineResponse(BaseModel):
    user_id: str
    version: str
    cognitive_load: MetricBounds
    attention: MetricBounds
    fatigue: MetricBounds
    sample_count: int
    reliability: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MetricGapDetail(BaseModel):
    current: float
    baseline: Optional[float]
    deviation: Optional[float]
    relative_deviation: Optional[float]
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    in_normal_range: Optional[bool] = None
    status: Literal["above_baseline", "below_baseline", "within_range", "unknown"]
    trend: Literal["increasing", "decreasing", "stable", "insufficient_data"]
    persistent: bool
    persistence_count: int = 0


class BaselineInfo(BaseModel):
    source: Literal["personal", "group_default", "none"]
    version: Optional[str]
    reliability: Optional[float]


class ContextSummary(BaseModel):
    content_id: Optional[str] = None
    content_type: Optional[str] = None
    difficulty: Optional[float] = None
    visual_complexity: Optional[float] = None
    audio_stimulation: Optional[float] = None
    elapsed_time_min: Optional[float] = None


class StateReport(BaseModel):
    state_report_id: str
    user_id: str
    session_id: str
    timestamp: datetime
    state_level: Literal["NORMAL", "WATCH", "ACTION_REQUIRED", "UNKNOWN"]
    baseline: BaselineInfo
    cognitive_gap: Dict[str, MetricGapDetail]
    context_summary: ContextSummary
    analysis_confidence: float
    requires_response: bool
    additional_observation_required: bool
    warnings: List[str] = Field(default_factory=list)
    possible_contributing_factors: List[str] = Field(default_factory=list)
    narrative_observation: Optional[str] = None
    emotion_context: Optional[Dict[str, Any]] = None
    memory_context: Optional[Dict[str, Any]] = None


class EpisodeResponse(BaseModel):
    id: int
    user_id: str
    session_id: str
    state_level: str
    state_report: Dict[str, Any]
    created_at: datetime


class SummaryResponse(BaseModel):
    user_id: str
    summary: Dict[str, Any]
    recent_episode_count: int
    updated_at: Optional[datetime] = None


class SeedResponse(BaseModel):
    message: str
    users_created: List[str]
    baselines_created: List[str]
    episodes_created: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
