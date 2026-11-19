"""Episodic / Summary Memory 리포지토리."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import EpisodicMemory, SummaryMemory


class EpisodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, episode: EpisodicMemory) -> EpisodicMemory:
        existing = (
            self.db.query(EpisodicMemory)
            .filter(
                EpisodicMemory.user_id == episode.user_id,
                EpisodicMemory.session_id == episode.session_id,
            )
            .first()
        )
        if existing:
            existing.input_json = episode.input_json
            existing.gap_json = episode.gap_json
            existing.state_level = episode.state_level
            existing.state_report_json = episode.state_report_json
            existing.created_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)
        return episode

    def list_recent(self, user_id: str, limit: int = 20) -> List[EpisodicMemory]:
        return (
            self.db.query(EpisodicMemory)
            .filter(EpisodicMemory.user_id == user_id)
            .order_by(EpisodicMemory.created_at.desc())
            .limit(limit)
            .all()
        )

    def count(self, user_id: str) -> int:
        return (
            self.db.query(EpisodicMemory)
            .filter(EpisodicMemory.user_id == user_id)
            .count()
        )


class SummaryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: str) -> Optional[SummaryMemory]:
        return (
            self.db.query(SummaryMemory)
            .filter(SummaryMemory.user_id == user_id)
            .first()
        )

    def upsert(
        self,
        user_id: str,
        summary_json: Dict[str, Any],
        recent_episode_count: int,
    ) -> SummaryMemory:
        row = self.get(user_id)
        if row is None:
            row = SummaryMemory(
                user_id=user_id,
                summary_json=summary_json,
                recent_episode_count=recent_episode_count,
            )
            self.db.add(row)
        else:
            row.summary_json = summary_json
            row.recent_episode_count = recent_episode_count
            row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row
