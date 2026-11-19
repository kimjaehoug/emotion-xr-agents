"""콘텐츠 추천 행동 검증."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.core.enums import ActionType
from app.schemas.action_plan import PlanAction


def validate_content_actions(
    *,
    actions: List[PlanAction],
    contents: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> Tuple[List[PlanAction], List[str]]:
    """RECOMMEND_CONTENT 행동의 target_content_id 유효성 및 금지 카테고리를 검사한다."""
    errors: List[str] = []
    valid: List[PlanAction] = []
    forbidden = set(profile.get("forbidden_categories") or [])
    content_map = {c.get("content_id"): c for c in contents}

    for idx, action in enumerate(actions):
        if action.action_type != ActionType.RECOMMEND_CONTENT:
            valid.append(action)
            continue

        content = content_map.get(action.target_content_id)
        if content is None:
            errors.append(
                f"actions[{idx}]: target_content_id '{action.target_content_id}'가 "
                "콘텐츠 카탈로그에 없습니다."
            )
            continue

        category = content.get("category")
        if category and category in forbidden:
            errors.append(
                f"actions[{idx}]: 콘텐츠 카테고리 '{category}'는 사용자 금지 목록에 있습니다."
            )
            continue

        valid.append(action)

    return valid, errors
