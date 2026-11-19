"""XR Episodic / Summary Memory 서비스."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import XrEpisodicMemory
from app.repositories.memory_repo import XrEpisodeRepository, XrSummaryRepository


class XrMemoryService:
    def __init__(self, db: Session) -> None:
        self.episode_repo = XrEpisodeRepository(db)
        self.summary_repo = XrSummaryRepository(db)

    def load_recent(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        episodes = self.episode_repo.list_recent(user_id, limit=limit)
        return [
            {
                "session_id": e.session_id,
                "state_report_id": e.state_report_id,
                "state_level": e.state_level,
                "route": e.route,
                "planner_source": e.planner_source,
                "plan": e.plan_json,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in episodes
        ]

    def load_summary_dict(self, user_id: str) -> Dict[str, Any]:
        row = self.summary_repo.get(user_id)
        return row.summary_json if row else {}

    def save_episode(
        self,
        *,
        user_id: str,
        session_id: str,
        state_report_id: str,
        state_level: str,
        route: str,
        planner_source: str,
        plan_json: Dict[str, Any],
    ) -> XrEpisodicMemory:
        episode = XrEpisodicMemory(
            user_id=user_id,
            session_id=session_id,
            state_report_id=state_report_id,
            state_level=state_level,
            route=route,
            planner_source=planner_source,
            plan_json=plan_json,
        )
        return self.episode_repo.save(episode)

    def upsert_summary(self, user_id: str, recent_episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        route_counts: Dict[str, int] = {}
        planner_counts: Dict[str, int] = {}
        level_counts: Dict[str, int] = {}
        for ep in recent_episodes[:20]:
            route_counts[ep.get("route", "")] = route_counts.get(ep.get("route", ""), 0) + 1
            planner_counts[ep.get("planner_source", "")] = (
                planner_counts.get(ep.get("planner_source", ""), 0) + 1
            )
            level_counts[ep.get("state_level", "")] = level_counts.get(ep.get("state_level", ""), 0) + 1

        summary = {
            "user_id": user_id,
            "route_counts": route_counts,
            "planner_source_counts": planner_counts,
            "state_level_counts": level_counts,
            "dominant_recent_route": max(route_counts, key=route_counts.get) if route_counts else None,
            "recent_sessions": [
                {"session_id": ep.get("session_id"), "route": ep.get("route")}
                for ep in recent_episodes[:10]
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.summary_repo.upsert(user_id, summary, recent_episode_count=len(recent_episodes))
        return summary
