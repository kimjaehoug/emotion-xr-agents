"""입력 검증 노드."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import ValidationError

from app.agents.state import AgentState
from app.core.config import get_settings
from app.schemas import CognitiveInput


def validate_input(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    raw = state.get("raw_input") or {}
    errors: List[str] = []
    warnings: List[str] = list(state.get("warnings") or [])

    try:
        validated = CognitiveInput.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            errors.append(f"{loc}: {err.get('msg')}")
        return {
            "validation_ok": False,
            "validation_errors": errors,
            "route": "error_response",
            "error": "입력 스키마 검증 실패",
            "warnings": warnings,
            "user_id": str(raw.get("user_id", "")),
            "session_id": str(raw.get("session_id", "")),
        }

    # 시간 정합성: 미래 과도한 타임스탬프 경고
    ts = validated.timestamp
    if ts.tzinfo is None:
        warnings.append("timestamp에 timezone이 없습니다. UTC로 해석합니다.")

    now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.utcnow()
    if ts > now and (ts - now).total_seconds() > 3600:
        warnings.append("timestamp가 현재보다 1시간 이상 미래입니다.")

    dq = validated.data_quality
    route = "complete_report"
    if dq.cognitive_confidence < settings.min_confidence or dq.completeness < settings.min_completeness:
        route = "low_confidence_report"
        warnings.append("데이터 품질이 낮아 저신뢰 경로로 처리합니다.")

    return {
        "validation_ok": True,
        "validation_errors": [],
        "validated_input": validated.model_dump(mode="json"),
        "route": route,
        "warnings": warnings,
        "user_id": validated.user_id,
        "session_id": validated.session_id,
        "error": None,
    }
