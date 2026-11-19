"""Baseline Memory 리포지토리."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Baseline, BaselineObservation


class BaselineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_observation(self, obs: BaselineObservation) -> BaselineObservation:
        existing = (
            self.db.query(BaselineObservation)
            .filter(
                BaselineObservation.user_id == obs.user_id,
                BaselineObservation.session_id == obs.session_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"세션 '{obs.session_id}'의 관측값이 이미 등록되어 있습니다."
            )
        self.db.add(obs)
        self.db.commit()
        self.db.refresh(obs)
        return obs

    def list_observations(
        self,
        user_id: str,
        *,
        normal_only: bool = False,
        quality_min: float = 0.0,
    ) -> List[BaselineObservation]:
        q = self.db.query(BaselineObservation).filter(
            BaselineObservation.user_id == user_id
        )
        if normal_only:
            q = q.filter(BaselineObservation.is_normal_confirmed.is_(True))
        if quality_min > 0:
            q = q.filter(
                BaselineObservation.confidence >= quality_min,
                BaselineObservation.completeness >= quality_min,
            )
        return q.order_by(BaselineObservation.created_at).all()

    def get_active_baseline(self, user_id: str) -> Optional[Baseline]:
        return (
            self.db.query(Baseline)
            .filter(Baseline.user_id == user_id, Baseline.is_active.is_(True))
            .order_by(Baseline.created_at.desc())
            .first()
        )

    def deactivate_all(self, user_id: str) -> None:
        baselines = (
            self.db.query(Baseline)
            .filter(Baseline.user_id == user_id, Baseline.is_active.is_(True))
            .all()
        )
        for b in baselines:
            b.is_active = False
        self.db.commit()

    def save_baseline(self, baseline: Baseline) -> Baseline:
        self.db.add(baseline)
        self.db.commit()
        self.db.refresh(baseline)
        return baseline

    def next_version(self, user_id: str) -> str:
        count = self.db.query(Baseline).filter(Baseline.user_id == user_id).count()
        return f"v{count + 1}"
