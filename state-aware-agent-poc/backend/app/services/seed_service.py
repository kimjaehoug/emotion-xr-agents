"""데모용 mock seed."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import EpisodicMemory
from app.repositories.memory_repo import EpisodeRepository, SummaryRepository
from app.repositories.user_repo import UserRepository
from app.schemas import BaselineObservationCreate, UserProfile
from app.services.baseline_service import BaselineService


def seed_demo_data(db: Session) -> Dict[str, Any]:
    user_repo = UserRepository(db)
    baseline_service = BaselineService(db)
    episode_repo = EpisodeRepository(db)
    summary_repo = SummaryRepository(db)

    users_created: List[str] = []
    baselines_created: List[str] = []
    episodes_created = 0

    # U001: Baseline 있는 사용자
    if user_repo.get_by_user_id("U001") is None:
        user_repo.create(
            "U001",
            UserProfile(
                preferred_content_types=["education", "training"],
                sensory_sensitivity={"visual": 0.4, "audio": 0.3},
                xr_experience_level="intermediate",
                accessibility_constraints=[],
                notes="데모 사용자 (Baseline 보유)",
            ).model_dump(),
        )
        users_created.append("U001")

    # 정상 샘플 5개
    normal_samples = [
        (0.45, 0.72, 0.32),
        (0.48, 0.70, 0.35),
        (0.42, 0.74, 0.30),
        (0.50, 0.68, 0.38),
        (0.46, 0.71, 0.33),
    ]
    existing_obs = baseline_service.observation_count("U001")
    if existing_obs < 3:
        for i, (cl, att, fat) in enumerate(normal_samples, start=1):
            try:
                baseline_service.add_observation(
                    "U001",
                    BaselineObservationCreate(
                        session_id=f"BASE-U001-{i}",
                        cognitive_load=cl,
                        attention=att,
                        fatigue=fat,
                        confidence=0.92,
                        completeness=0.95,
                        is_normal_confirmed=True,
                    ),
                )
            except ValueError:
                pass
        if baseline_service.get_active("U001") is None:
            bl = baseline_service.build_baseline("U001")
            baselines_created.append(f"U001:{bl.version}")

    # U002: Baseline 없는 신규 사용자
    if user_repo.get_by_user_id("U002") is None:
        user_repo.create(
            "U002",
            UserProfile(
                preferred_content_types=["education"],
                sensory_sensitivity={"visual": 0.6, "audio": 0.5},
                xr_experience_level="beginner",
                accessibility_constraints=["high_contrast"],
                notes="Baseline 미보유 사용자",
            ).model_dump(),
        )
        users_created.append("U002")

    # 과거 에피소드 (추세용)
    if episode_repo.count("U001") == 0:
        base_ts = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
        history = [
            ("S-HIST-1", 0.48, 0.70, 0.34, "NORMAL"),
            ("S-HIST-2", 0.52, 0.68, 0.40, "NORMAL"),
            ("S-HIST-3", 0.60, 0.62, 0.48, "WATCH"),
            ("S-HIST-4", 0.68, 0.58, 0.58, "WATCH"),
            ("S-HIST-5", 0.72, 0.55, 0.65, "ACTION_REQUIRED"),
        ]
        bl = baseline_service.get_active("U001")
        for i, (sid, cl, att, fat, level) in enumerate(history):
            ts = (base_ts + timedelta(hours=i)).isoformat()
            report = {
                "state_report_id": f"SR-SEED-{i+1}",
                "user_id": "U001",
                "session_id": sid,
                "timestamp": ts,
                "state_level": level,
                "baseline": {
                    "source": "personal",
                    "version": bl.version if bl else "v1",
                    "reliability": bl.reliability if bl else 0.7,
                },
                "cognitive_gap": {
                    "cognitive_load": {
                        "current": cl,
                        "baseline": bl.cognitive_load_center if bl else 0.45,
                        "deviation": round(cl - (bl.cognitive_load_center if bl else 0.45), 4),
                        "relative_deviation": 0.0,
                        "status": "above_baseline" if level != "NORMAL" else "within_range",
                        "trend": "increasing",
                        "persistent": level == "ACTION_REQUIRED",
                        "persistence_count": 2 if level == "ACTION_REQUIRED" else 0,
                    },
                    "attention": {
                        "current": att,
                        "baseline": bl.attention_center if bl else 0.7,
                        "deviation": round(att - (bl.attention_center if bl else 0.7), 4),
                        "relative_deviation": 0.0,
                        "status": "below_baseline" if level != "NORMAL" else "within_range",
                        "trend": "decreasing",
                        "persistent": False,
                        "persistence_count": 0,
                    },
                    "fatigue": {
                        "current": fat,
                        "baseline": bl.fatigue_center if bl else 0.35,
                        "deviation": round(fat - (bl.fatigue_center if bl else 0.35), 4),
                        "relative_deviation": 0.0,
                        "status": "above_baseline" if level != "NORMAL" else "within_range",
                        "trend": "increasing",
                        "persistent": level == "ACTION_REQUIRED",
                        "persistence_count": 2 if level == "ACTION_REQUIRED" else 0,
                    },
                },
                "context_summary": {
                    "content_id": f"C{100+i}",
                    "difficulty": 0.5 + i * 0.05,
                    "visual_complexity": 0.5,
                    "elapsed_time_min": 10 + i * 5,
                },
                "analysis_confidence": 0.85,
                "requires_response": level == "ACTION_REQUIRED",
                "additional_observation_required": level == "WATCH",
                "warnings": [],
            }
            episode_repo.save(
                EpisodicMemory(
                    user_id="U001",
                    session_id=sid,
                    input_json={
                        "user_id": "U001",
                        "session_id": sid,
                        "timestamp": ts,
                        "cognitive_metrics": {
                            "cognitive_load": cl,
                            "attention": att,
                            "fatigue": fat,
                        },
                        "data_quality": {
                            "cognitive_confidence": 0.9,
                            "completeness": 0.95,
                        },
                    },
                    gap_json=report["cognitive_gap"],
                    state_level=level,
                    state_report_json=report,
                )
            )
            episodes_created += 1

        summary_repo.upsert(
            "U001",
            {
                "user_id": "U001",
                "long_term_state_summary": {
                    "state_level_counts": {
                        "NORMAL": 2,
                        "WATCH": 2,
                        "ACTION_REQUIRED": 1,
                    },
                    "dominant_recent_level": "WATCH",
                },
                "recurring_patterns": [
                    "최근 세션에서 'cognitive_load' 지표 이탈이 반복 관찰됨."
                ],
                "frequently_deviating_metrics": [
                    {"metric": "cognitive_load", "count": 3},
                    {"metric": "fatigue", "count": 3},
                ],
                "recent_sessions": [
                    {"session_id": h[0], "state_level": h[4]} for h in history
                ],
                "baseline_update_candidate": {
                    "eligible": False,
                    "note": "seed 데이터",
                },
            },
            recent_episode_count=episodes_created,
        )

    return {
        "message": "데모 데이터 시드 완료",
        "users_created": users_created,
        "baselines_created": baselines_created,
        "episodes_created": episodes_created,
    }
