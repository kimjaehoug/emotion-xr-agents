"""XR Episodic / Summary Memory 및 idempotency 리포지토리."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import ProcessedStateReport, XrEpisodicMemory, XrSummaryMemory


class ProcessedReportRepository:
    """state_report_id 중복 처리 방지."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, state_report_id: str) -> Optional[ProcessedStateReport]:
        return (
            self.db.query(ProcessedStateReport)
            .filter(ProcessedStateReport.state_report_id == state_report_id)
            .first()
        )

    def save(
        self, *, state_report_id: str, user_id: str, session_id: str, result_json: Dict[str, Any]
    ) -> ProcessedStateReport:
        existing = self.get(state_report_id)
        if existing is not None:
            return existing
        row = ProcessedStateReport(
            state_report_id=state_report_id,
            user_id=user_id,
            session_id=session_id,
            result_json=result_json,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row


class XrEpisodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, episode: XrEpisodicMemory) -> XrEpisodicMemory:
        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)
        return episode

    def list_recent(self, user_id: str, limit: int = 20) -> List[XrEpisodicMemory]:
        return (
            self.db.query(XrEpisodicMemory)
            .filter(XrEpisodicMemory.user_id == user_id)
            .order_by(XrEpisodicMemory.created_at.desc())
            .limit(limit)
            .all()
        )

    def count(self, user_id: str) -> int:
        return (
            self.db.query(XrEpisodicMemory).filter(XrEpisodicMemory.user_id == user_id).count()
        )


class XrSummaryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: str) -> Optional[XrSummaryMemory]:
        return (
            self.db.query(XrSummaryMemory).filter(XrSummaryMemory.user_id == user_id).first()
        )

    def upsert(
        self, user_id: str, summary_json: Dict[str, Any], recent_episode_count: int
    ) -> XrSummaryMemory:
        row = self.get(user_id)
        if row is None:
            row = XrSummaryMemory(
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
