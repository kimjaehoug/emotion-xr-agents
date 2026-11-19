"""안전 규칙: delta clamp, final_value 계산, 자동 제어 권한 강제."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import Settings, get_settings
from app.core.enums import ActionType
from app.schemas.action_plan import PlanAction

DEFAULT_PARAMETER_VALUE = 0.5


def apply_safety_rules(
    *,
    actions: List[PlanAction],
    profile: Dict[str, Any],
    xr_state: Dict[str, Any],
    settings: Settings | None = None,
) -> List[str]:
    """delta를 `xr_max_parameter_delta`로 clamp하고 final_value를 계산한다.

    `auto_control_allowed`가 False인 사용자는 XR 파라미터 변경에 항상
    확인(confirmation)이 필요하도록 강제한다.
    """
    settings = settings or get_settings()
    warnings: List[str] = []
    auto_allowed = bool(profile.get("auto_control_allowed", True))
    max_delta = settings.xr_max_parameter_delta

    for action in actions:
        if action.action_type != ActionType.UPDATE_XR_PARAMETER or action.xr_parameter is None:
            continue

        raw_delta = action.delta if action.delta is not None else 0.0
        clamped_delta = max(-max_delta, min(max_delta, raw_delta))
        if clamped_delta != raw_delta:
            warnings.append(
                f"'{action.xr_parameter.value}' delta({raw_delta:.3f})가 허용 범위(±{max_delta})를 "
                f"초과하여 {clamped_delta:.3f}로 조정되었습니다."
            )
        action.delta = round(clamped_delta, 4)

        current_value = float(xr_state.get(action.xr_parameter.value, DEFAULT_PARAMETER_VALUE))
        final_value = max(0.0, min(1.0, current_value + clamped_delta))
        action.final_value = round(final_value, 4)

        if not auto_allowed and not action.requires_confirmation:
            action.requires_confirmation = True
            warnings.append(
                f"'{action.xr_parameter.value}' 자동 제어가 허용되지 않아 사용자 확인이 필요합니다."
            )

    return warnings
