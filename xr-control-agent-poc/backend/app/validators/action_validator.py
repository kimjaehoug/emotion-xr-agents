"""행동 카탈로그(action_catalog) 검증."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.schemas.action_plan import PlanAction


def _action_signature(action: PlanAction) -> str:
    param = action.xr_parameter.value if action.xr_parameter else ""
    return f"{action.action_type.value}:{param}"


def validate_actions(
    *,
    actions: List[PlanAction],
    catalog: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> Tuple[List[PlanAction], List[str]]:
    """카탈로그에 없는 조합, 사용자가 거부한 행동을 제거한다."""
    errors: List[str] = []
    valid_actions: List[PlanAction] = []
    rejected = set(profile.get("rejected_actions") or [])

    for idx, action in enumerate(actions):
        entry = next(
            (
                c
                for c in catalog
                if c.get("action_type") == action.action_type.value
                and (
                    action.xr_parameter is None
                    or c.get("xr_parameter") in (None, action.xr_parameter.value)
                )
            ),
            None,
        )
        if entry is None:
            errors.append(
                f"actions[{idx}]: action_type='{action.action_type.value}', "
                f"xr_parameter='{action.xr_parameter}' 조합이 행동 카탈로그에 없습니다."
            )
            continue

        signature = _action_signature(action)
        if signature in rejected:
            errors.append(f"actions[{idx}]: 사용자가 이전에 거부한 행동입니다 ({signature}).")
            continue

        if entry.get("requires_confirmation"):
            action.requires_confirmation = True

        valid_actions.append(action)

    return valid_actions, errors
