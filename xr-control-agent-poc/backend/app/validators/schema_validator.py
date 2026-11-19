"""LLM 출력 JSON 스키마 검증."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.schemas.action_plan import RawPlanOutput


def validate_schema(raw: Dict[str, Any]) -> Tuple[Optional[RawPlanOutput], List[str]]:
    """딕셔너리를 `RawPlanOutput`으로 검증한다. 실패 시 (None, 오류목록)."""
    try:
        parsed = RawPlanOutput.model_validate(raw)
        return parsed, []
    except ValidationError as exc:
        errors: List[str] = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            errors.append(f"{loc or '(root)'}: {err.get('msg')}")
        return None, errors
