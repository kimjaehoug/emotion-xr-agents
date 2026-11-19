"""save_memory 헬퍼."""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents.nodes.generate_report import build_summary_payload
from app.models import EpisodicMemory
from app.repositories.memory_repo import EpisodeRepository, SummaryRepository


def save_episode(db: Session, report: Dict[str, Any], input_json: Dict[str, Any]) -> EpisodicMemory:
    repo = EpisodeRepository(db)
    episode = EpisodicMemory(
        user_id=report["user_id"],
        session_id=report["session_id"],
        input_json=input_json,
        gap_json=report.get("cognitive_gap"),
        state_level=report["state_level"],
        state_report_json=report,
    )
    return repo.save(episode)


def update_summary_memory(
    db: Session,
    user_id: str,
    recent_episodes: List[Dict[str, Any]],
    latest_report: Dict[str, Any],
) -> None:
    summary_repo = SummaryRepository(db)
    episode_repo = EpisodeRepository(db)
    summary = build_summary_payload(
        user_id=user_id,
        recent_episodes=recent_episodes,
        latest_report=latest_report,
    )
    summary_repo.upsert(
        user_id=user_id,
        summary_json=summary,
        recent_episode_count=episode_repo.count(user_id),
    )
