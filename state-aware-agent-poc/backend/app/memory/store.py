"""Memory v2 저장소.

- MemoryEventStore: 원시 증거. append만 제공한다(수정·삭제 메서드 없음).
- MemoryCardStore: 지식 카드. 새 카드 추가와 유효기간 닫기만 제공한다(내용 덮어쓰기 없음).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.memory.core import as_aware, sanitize_obj, utcnow
from app.models import EpisodeArchive, MemoryCard, MemoryEvent


class MemoryEventStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(
        self,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
        commit: bool = True,
    ) -> MemoryEvent:
        event = MemoryEvent(
            event_id=f"EV-{uuid4().hex[:12].upper()}",
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            payload_json=sanitize_obj(payload),
        )
        self.db.add(event)
        if commit:
            self.db.commit()
        return event

    def list(
        self, user_id: str, *, event_type: Optional[str] = None, limit: int = 200
    ) -> List[MemoryEvent]:
        q = self.db.query(MemoryEvent).filter(MemoryEvent.user_id == user_id)
        if event_type:
            q = q.filter(MemoryEvent.event_type == event_type)
        return q.order_by(MemoryEvent.id.desc()).limit(limit).all()

    def access_counts(self, user_id: str) -> Dict[str, int]:
        """memory_accessed 이벤트에서 참조된 id별 접근 횟수 (중요도의 '접근 빈도' 요소)."""
        counts: Dict[str, int] = {}
        for ev in self.list(user_id, event_type="memory_accessed", limit=5000):
            for ref in (ev.payload_json or {}).get("refs", []):
                counts[ref] = counts.get(ref, 0) + 1
        return counts


class MemoryCardStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        *,
        user_id: str,
        memory_type: str,
        key: str,
        value: Any,
        backstory: str,
        evidence: List[str],
        confidence: float,
        source: str = "rule_extractor",
        commit: bool = True,
    ) -> MemoryCard:
        card = MemoryCard(
            card_id=f"MC-{uuid4().hex[:10].upper()}",
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            value_json=value,
            backstory=backstory,
            evidence_json=list(evidence),
            confidence=round(float(confidence), 4),
            source=source,
            valid_from=utcnow(),
        )
        self.db.add(card)
        if commit:
            self.db.commit()
        return card

    def close(self, card: MemoryCard, *, superseded_by: Optional[str] = None, commit: bool = True) -> None:
        card.valid_to = utcnow()
        card.superseded_by = superseded_by
        if commit:
            self.db.commit()

    def list(self, user_id: str, *, include_history: bool = True) -> List[MemoryCard]:
        q = self.db.query(MemoryCard).filter(MemoryCard.user_id == user_id)
        if not include_history:
            q = q.filter(MemoryCard.valid_to.is_(None))
        return q.order_by(MemoryCard.id).all()

    @staticmethod
    def to_dict(card: MemoryCard) -> Dict[str, Any]:
        return {
            "card_id": card.card_id,
            "memory_type": card.memory_type,
            "key": card.key,
            "value": card.value_json,
            "backstory": card.backstory,
            "evidence": card.evidence_json or [],
            "confidence": card.confidence,
            "source": card.source,
            "valid_from": as_aware(card.valid_from),
            "valid_to": as_aware(card.valid_to),
            "superseded_by": card.superseded_by,
        }


class EpisodeArchiveStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def archived_sessions(self, user_id: str) -> Dict[str, EpisodeArchive]:
        rows = self.db.query(EpisodeArchive).filter(EpisodeArchive.user_id == user_id).all()
        return {r.session_id: r for r in rows}

    def archive(
        self,
        *,
        user_id: str,
        session_id: str,
        cluster_card_id: Optional[str],
        importance: Dict[str, Any],
        archived_at: Optional[datetime] = None,
    ) -> EpisodeArchive:
        row = EpisodeArchive(
            user_id=user_id,
            session_id=session_id,
            cluster_card_id=cluster_card_id,
            importance_json=importance,
            archived_at=archived_at or utcnow(),
        )
        self.db.add(row)
        return row
