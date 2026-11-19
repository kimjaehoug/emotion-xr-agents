"""데모용 정책/행동/콘텐츠/사용자 시드 서비스."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.enums import ActionType, PlanRoute, XrParameter
from app.repositories.catalog_repo import ActionCatalogRepository, ContentRepository, PolicyRepository
from app.repositories.user_repo import UserRepository

DEMO_USER_ID = "U001"


def seed_demo_data(db: Session) -> Dict[str, Any]:
    user_repo = UserRepository(db)
    policy_repo = PolicyRepository(db)
    action_repo = ActionCatalogRepository(db)
    content_repo = ContentRepository(db)

    users_created: List[str] = []
    policies_created = 0
    actions_created = 0
    contents_created = 0

    # 데모 사용자
    if user_repo.get_by_user_id(DEMO_USER_ID) is None:
        user_repo.create(
            DEMO_USER_ID,
            {
                "auto_control_allowed": True,
                "forbidden_categories": [],
                "sensitivities": {"visual_complexity": 0.1},
                "rejected_actions": [],
                "notes": "데모 사용자",
            },
        )
        users_created.append(DEMO_USER_ID)

    if user_repo.get_by_user_id("U002") is None:
        user_repo.create(
            "U002",
            {
                "auto_control_allowed": False,
                "forbidden_categories": ["horror"],
                "sensitivities": {"audio_stimulation": 0.3},
                "rejected_actions": [],
                "notes": "자동 제어 비허용 사용자(모든 XR 조정에 확인 필요)",
            },
        )
        users_created.append("U002")

    # 응답 정책
    policy_specs = [
        {
            "policy_key": "policy_normal",
            "state_level": "NORMAL",
            "min_confidence": 0.5,
            "allowed_routes_json": [PlanRoute.NO_ACTION.value, PlanRoute.OBSERVATION.value],
            "description": "정상 상태: 조치 없음 또는 관찰만 허용.",
        },
        {
            "policy_key": "policy_watch",
            "state_level": "WATCH",
            "min_confidence": 0.6,
            "allowed_routes_json": [
                PlanRoute.XR_OPTIMIZATION.value,
                PlanRoute.CONTENT_RECOMMENDATION.value,
                PlanRoute.OBSERVATION.value,
            ],
            "description": "주의 상태: XR 파라미터 조정 또는 콘텐츠 추천 허용.",
        },
        {
            "policy_key": "policy_action_required",
            "state_level": "ACTION_REQUIRED",
            "min_confidence": 0.6,
            "allowed_routes_json": [
                PlanRoute.BREAK_SUGGESTION.value,
                PlanRoute.XR_OPTIMIZATION.value,
                PlanRoute.CONTENT_RECOMMENDATION.value,
            ],
            "description": "조치 필요 상태: 휴식 제안 우선, XR 조정/콘텐츠 추천도 허용.",
        },
        {
            "policy_key": "policy_unknown",
            "state_level": "UNKNOWN",
            "min_confidence": 0.0,
            "allowed_routes_json": [PlanRoute.OBSERVATION.value],
            "description": "미확인 상태: 관찰만 허용, 자동 XR 제어 금지.",
        },
    ]
    for spec in policy_specs:
        if policy_repo.get_by_key(spec["policy_key"]) is None:
            policy_repo.create(**spec)
            policies_created += 1

    # 행동 카탈로그
    action_specs = [
        {
            "action_type": ActionType.OBSERVE.value,
            "xr_parameter": None,
            "category": None,
            "max_delta": None,
            "requires_confirmation": False,
            "description": "관찰만 지속.",
        },
        {
            "action_type": ActionType.KEEP_CURRENT_STATE.value,
            "xr_parameter": None,
            "category": None,
            "max_delta": None,
            "requires_confirmation": False,
            "description": "현재 상태 유지.",
        },
        {
            "action_type": ActionType.UPDATE_XR_PARAMETER.value,
            "xr_parameter": XrParameter.VISUAL_COMPLEXITY.value,
            "category": None,
            "max_delta": 0.20,
            "requires_confirmation": False,
            "description": "시각 복잡도 조정.",
        },
        {
            "action_type": ActionType.UPDATE_XR_PARAMETER.value,
            "xr_parameter": XrParameter.AUDIO_STIMULATION.value,
            "category": None,
            "max_delta": 0.20,
            "requires_confirmation": False,
            "description": "청각 자극 조정.",
        },
        {
            "action_type": ActionType.UPDATE_XR_PARAMETER.value,
            "xr_parameter": XrParameter.INTERACTION_DENSITY.value,
            "category": None,
            "max_delta": 0.20,
            "requires_confirmation": True,
            "description": "상호작용 밀도 조정(확인 필요).",
        },
        {
            "action_type": ActionType.UPDATE_XR_PARAMETER.value,
            "xr_parameter": XrParameter.INFORMATION_DENSITY.value,
            "category": None,
            "max_delta": 0.20,
            "requires_confirmation": False,
            "description": "정보 밀도 조정.",
        },
        {
            "action_type": ActionType.UPDATE_XR_PARAMETER.value,
            "xr_parameter": XrParameter.MOTION_INTENSITY.value,
            "category": None,
            "max_delta": 0.20,
            "requires_confirmation": True,
            "description": "모션 강도 조정(확인 필요, 멀미 위험).",
        },
        {
            "action_type": ActionType.RECOMMEND_CONTENT.value,
            "xr_parameter": None,
            "category": "content",
            "max_delta": None,
            "requires_confirmation": False,
            "description": "콘텐츠 추천.",
        },
        {
            "action_type": ActionType.SUGGEST_BREAK.value,
            "xr_parameter": None,
            "category": None,
            "max_delta": None,
            "requires_confirmation": True,
            "description": "휴식 제안(확인 필요).",
        },
    ]
    for spec in action_specs:
        existing = action_repo.find(spec["action_type"], spec.get("xr_parameter"))
        if existing is None:
            action_repo.create(**spec)
            actions_created += 1

    # 콘텐츠 카탈로그
    content_specs = [
        {
            "content_id": "C001",
            "title": "고요한 숲 산책",
            "content_type": "relaxation",
            "category": "nature",
            "difficulty": 0.2,
            "visual_complexity": 0.2,
            "audio_stimulation": 0.2,
            "interaction_density": 0.1,
            "tags_json": ["calm", "low_stimulation"],
        },
        {
            "content_id": "C002",
            "title": "우주 탐사 교육",
            "content_type": "education",
            "category": "science",
            "difficulty": 0.6,
            "visual_complexity": 0.6,
            "audio_stimulation": 0.4,
            "interaction_density": 0.5,
            "tags_json": ["education", "space"],
        },
        {
            "content_id": "C003",
            "title": "리듬 액션 트레이닝",
            "content_type": "training",
            "category": "action",
            "difficulty": 0.8,
            "visual_complexity": 0.85,
            "audio_stimulation": 0.8,
            "interaction_density": 0.9,
            "tags_json": ["high_stimulation", "action"],
        },
        {
            "content_id": "C004",
            "title": "호흡 명상 가이드",
            "content_type": "wellness",
            "category": "meditation",
            "difficulty": 0.1,
            "visual_complexity": 0.15,
            "audio_stimulation": 0.15,
            "interaction_density": 0.05,
            "tags_json": ["calm", "breathing"],
        },
        {
            "content_id": "C005",
            "title": "공포 체험관",
            "content_type": "entertainment",
            "category": "horror",
            "difficulty": 0.7,
            "visual_complexity": 0.75,
            "audio_stimulation": 0.85,
            "interaction_density": 0.6,
            "tags_json": ["high_stimulation", "horror"],
        },
    ]
    for spec in content_specs:
        if content_repo.get_by_content_id(spec["content_id"]) is None:
            content_repo.create(**spec)
            contents_created += 1

    return {
        "message": "XR Control Agent 데모 데이터 시드 완료",
        "users_created": users_created,
        "policies_created": policies_created,
        "actions_created": actions_created,
        "contents_created": contents_created,
    }
