"""상태 인지 Agent StateReport 스키마 (재구현).

`shared/state_report.py`와 동일한 계약을 유지한다. 두 서비스(상태 인지 Agent,
XR Control Agent)가 별도 배포 단위로 존재할 수 있으므로 얇은 의존성 대신
동일 스펙을 이 파일에 복제하여 import 경로 문제를 피한다.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MetricGapLite(BaseModel):
    status: Literal["above_baseline", "below_baseline", "within_range", "unknown"]
    deviation: Optional[float] = None
    relative_deviation: Optional[float] = None
    trend: Literal["increasing", "decreasing", "stable", "insufficient_data"] = "insufficient_data"
    persistent: bool = False
    current: Optional[float] = None
    baseline: Optional[float] = None


class BaselineInfo(BaseModel):
    source: Literal["personal", "group_default", "none"] = "none"
    version: Optional[str] = None
    reliability: Optional[float] = None


class EmotionContext(BaseModel):
    label: Optional[str] = None
    intensity: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class CandidateCause(BaseModel):
    type: str
    factor: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class ContextSummary(BaseModel):
    content_id: Optional[str] = None
    content_type: Optional[str] = None
    difficulty: Optional[float] = Field(None, ge=0.0, le=1.0)
    visual_complexity: Optional[float] = Field(None, ge=0.0, le=1.0)
    audio_stimulation: Optional[float] = Field(None, ge=0.0, le=1.0)
    interaction_density: Optional[float] = Field(None, ge=0.0, le=1.0)
    elapsed_time_min: Optional[float] = Field(None, ge=0.0)


class StateReport(BaseModel):
    """상태 인지 Agent 출력 / XR Control Agent 입력."""

    state_report_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    timestamp: datetime
    state_level: Literal["NORMAL", "WATCH", "ACTION_REQUIRED", "UNKNOWN"]
    baseline: BaselineInfo = Field(default_factory=BaselineInfo)
    cognitive_gap: Dict[str, MetricGapLite] = Field(default_factory=dict)
    emotion_context: Optional[EmotionContext] = None
    context_summary: ContextSummary = Field(default_factory=ContextSummary)
    candidate_causes: List[CandidateCause] = Field(default_factory=list)
    analysis_confidence: float = Field(..., ge=0.0, le=1.0)
    requires_response: bool = False
    additional_observation_required: bool = False
    warnings: List[str] = Field(default_factory=list)
    possible_contributing_factors: List[str] = Field(default_factory=list)
    narrative_observation: Optional[str] = None
    # Memory v2: 상태 인지 Agent의 작업 메모리·능동 경고 (선택)
    memory_context: Optional[Dict[str, Any]] = None
