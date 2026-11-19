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
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class BaselineObservation(Base):
    __tablename__ = "baseline_observations"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_obs_user_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cognitive_load: Mapped[float] = mapped_column(Float, nullable=False)
    attention: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, nullable=False)
    is_normal_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    cognitive_load_center: Mapped[float] = mapped_column(Float, nullable=False)
    cognitive_load_lower: Mapped[float] = mapped_column(Float, nullable=False)
    cognitive_load_upper: Mapped[float] = mapped_column(Float, nullable=False)
    attention_center: Mapped[float] = mapped_column(Float, nullable=False)
    attention_lower: Mapped[float] = mapped_column(Float, nullable=False)
    attention_upper: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue_center: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue_lower: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue_upper: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reliability: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EpisodicMemory(Base):
    __tablename__ = "episodic_memories"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_ep_user_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    gap_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    state_level: Mapped[str] = mapped_column(String(32), nullable=False)
    state_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SummaryMemory(Base):
    __tablename__ = "summary_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recent_episode_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


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


class EpisodeArchive(Base):
    """압축(3.1.7)으로 보조 저장소로 옮긴 일화. 원본 EpisodicMemory 행은 보존한다."""

    __tablename__ = "episode_archives"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_arch_user_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cluster_card_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    importance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
