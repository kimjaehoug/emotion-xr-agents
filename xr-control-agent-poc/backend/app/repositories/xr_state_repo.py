"""모의 XR 파라미터 상태 리포지토리."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import MockXrState

DEFAULT_PARAMETER_VALUE = 0.5


class MockXrStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: str, session_id: str) -> Optional[MockXrState]:
        return (
            self.db.query(MockXrState)
            .filter(MockXrState.user_id == user_id, MockXrState.session_id == session_id)
            .first()
        )

    def get_or_create(self, user_id: str, session_id: str) -> MockXrState:
        state = self.get(user_id, session_id)
        if state is not None:
            return state
        state = MockXrState(
            user_id=user_id,
            session_id=session_id,
            visual_complexity=DEFAULT_PARAMETER_VALUE,
            audio_stimulation=DEFAULT_PARAMETER_VALUE,
            interaction_density=DEFAULT_PARAMETER_VALUE,
            information_density=DEFAULT_PARAMETER_VALUE,
            motion_intensity=DEFAULT_PARAMETER_VALUE,
        )
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        return state

    def update_parameter(self, user_id: str, session_id: str, parameter: str, value: float) -> MockXrState:
        state = self.get_or_create(user_id, session_id)
        setattr(state, parameter, value)
        state.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(state)
        return state
