"""StateReport 입력 검증 노드."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from app.agents.xr_control.state import AgentState
from app.schemas.state_report import StateReport


def validate_state_report(state: AgentState) -> Dict[str, Any]:
    raw = state.get("raw_state_report") or {}
    try:
        validated = StateReport.model_validate(raw)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(x) for x in e.get('loc', []))}: {e.get('msg')}" for e in exc.errors()]
        return {
            "validation_ok": False,
            "validation_errors": errors,
            "user_id": str(raw.get("user_id", "")),
            "session_id": str(raw.get("session_id", "")),
            "state_report_id": str(raw.get("state_report_id", "")),
        }

    return {
        "validation_ok": True,
        "validation_errors": [],
        "state_report": validated.model_dump(mode="json"),
        "user_id": validated.user_id,
        "session_id": validated.session_id,
        "state_report_id": validated.state_report_id,
    }
