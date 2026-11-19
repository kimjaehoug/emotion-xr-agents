"""모의 XR 런타임. 실제 XR 디바이스 대신 DB에 파라미터 상태를 저장/적용한다."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import MockXrState
from app.repositories.xr_state_repo import MockXrStateRepository

PARAMETER_FIELDS = (
    "visual_complexity",
    "audio_stimulation",
    "interaction_density",
    "information_density",
    "motion_intensity",
)


def _state_to_dict(state: MockXrState) -> Dict[str, float]:
    return {field: getattr(state, field) for field in PARAMETER_FIELDS}


class MockXrRuntime:
    def __init__(self, db: Session) -> None:
        self.repo = MockXrStateRepository(db)

    def get_state(self, user_id: str, session_id: str) -> Dict[str, float]:
        state = self.repo.get_or_create(user_id, session_id)
        return _state_to_dict(state)

    def apply_parameter(
        self, user_id: str, session_id: str, parameter: str, final_value: float
    ) -> Dict[str, Any]:
        if parameter not in PARAMETER_FIELDS:
            raise ValueError(f"알 수 없는 XR 파라미터: {parameter}")
        clamped = max(0.0, min(1.0, float(final_value)))
        state = self.repo.update_parameter(user_id, session_id, parameter, clamped)
        return _state_to_dict(state)
