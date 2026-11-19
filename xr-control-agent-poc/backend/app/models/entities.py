"""DB ORM 모델."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Profile Memory. auto_control_allowed / forbidden_categories / sensitivities / rejected_actions."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ResponsePolicy(Base):
    """상태 수준별 허용 라우트 / 최소 신뢰도 정책."""

    __tablename__ = "response_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    state_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    min_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    allowed_routes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActionCatalogEntry(Base):
    """허용 행동 카탈로그. Qwen 출력의 action_type/xr_parameter를 검증하는 기준."""

    __tablename__ = "action_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    xr_parameter: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    max_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Content(Base):
    """추천 가능 콘텐츠 카탈로그."""

    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    visual_complexity: Mapped[float] = mapped_column(Float, default=0.5)
    audio_stimulation: Mapped[float] = mapped_column(Float, default=0.5)
    interaction_density: Mapped[float] = mapped_column(Float, default=0.5)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MockXrState(Base):
    """세션별 모의 XR 파라미터 현재값."""

    __tablename__ = "mock_xr_states"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_mock_xr_user_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    visual_complexity: Mapped[float] = mapped_column(Float, default=0.5)
    audio_stimulation: Mapped[float] = mapped_column(Float, default=0.5)
    interaction_density: Mapped[float] = mapped_column(Float, default=0.5)
    information_density: Mapped[float] = mapped_column(Float, default=0.5)
    motion_intensity: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProcessedStateReport(Base):
    """state_report_id 재실행 방지용 idempotency 기록."""

    __tablename__ = "processed_state_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_report_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class XrEpisodicMemory(Base):
    """XR Agent Episodic Memory. 세션별 계획 결과 기록."""

    __tablename__ = "xr_episodic_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state_report_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state_level: Mapped[str] = mapped_column(String(32), nullable=False)
    route: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_source: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class XrSummaryMemory(Base):
    """XR Agent Summary Memory. 사용자별 장기 누적 요약."""

    __tablename__ = "xr_summary_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recent_episode_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ActionPlanRecord(Base):
    """검증 완료된 ActionPlan 저장 테이블."""

    __tablename__ = "action_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    state_report_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    goal: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    actions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_candidates_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Confirmation(Base):
    """사용자 확인이 필요한 행동 대기열."""

    __tablename__ = "confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    confirmation_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Execution(Base):
    """실제로 적용된(또는 시도된) 행동 기록."""

    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confirmation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    feedback_effect: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ----------------------------------------------------------------------
# Memory v2 (책 3장: 원시 증거 → 지식 → 서비스 3계층)
# ----------------------------------------------------------------------
class MemoryEvent(Base):
    """원시 증거 계층. 추가 전용(append-only) 궤적 — 수정/삭제 API를 두지 않는다."""

    __tablename__ = "memory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoryCard(Base):
    """지식 계층. 고급 JSON 카드(의미/절차 메모리). ADD-only, 변경 시 valid_to로 이전 카드를 닫는다."""

    __tablename__ = "memory_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    backstory: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="rule_extractor")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
