"""FastAPI 라우터."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.memory.service import StateMemoryService
from app.repositories.memory_repo import EpisodeRepository, SummaryRepository
from app.repositories.user_repo import UserRepository
from app.schemas import (
    BaselineObservationCreate,
    BaselineResponse,
    CognitiveInput,
    EpisodeResponse,
    SeedResponse,
    StateReport,
    SummaryResponse,
    UserCreate,
    UserResponse,
)
from app.services.analyze_service import AnalyzeService
from app.services.baseline_service import BaselineService
from app.services.seed_service import seed_demo_data

router = APIRouter(prefix="/api/v1")


@router.post("/state/analyze", response_model=StateReport)
def analyze_state(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Any:
    """인지평가 입력 → State Report."""
    # 스키마 사전 검증 (422)
    try:
        CognitiveInput.model_validate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    service = AnalyzeService(db)
    report = service.analyze(payload)
    return report


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    try:
        user = repo.create(body.user_id, body.profile.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserResponse(
        user_id=user.user_id,
        profile=user.profile_json,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/users", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    users = repo.list_all()
    return [
        UserResponse(
            user_id=u.user_id,
            profile=u.profile_json,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    user = repo.get_by_user_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"사용자 '{user_id}'를 찾을 수 없습니다.")
    return UserResponse(
        user_id=user.user_id,
        profile=user.profile_json,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/users/{user_id}/baseline-observations", status_code=status.HTTP_201_CREATED)
def add_baseline_observation(
    user_id: str,
    body: BaselineObservationCreate,
    db: Session = Depends(get_db),
) -> Any:
    repo = UserRepository(db)
    if repo.get_by_user_id(user_id) is None:
        raise HTTPException(status_code=404, detail=f"사용자 '{user_id}'를 찾을 수 없습니다.")
    service = BaselineService(db)
    try:
        obs = service.add_observation(user_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": obs.id,
        "user_id": obs.user_id,
        "session_id": obs.session_id,
        "cognitive_load": obs.cognitive_load,
        "attention": obs.attention,
        "fatigue": obs.fatigue,
        "confidence": obs.confidence,
        "completeness": obs.completeness,
        "is_normal_confirmed": obs.is_normal_confirmed,
        "created_at": obs.created_at,
    }


@router.post("/users/{user_id}/baseline/build", response_model=BaselineResponse)
def build_baseline(user_id: str, db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    if repo.get_by_user_id(user_id) is None:
        raise HTTPException(status_code=404, detail=f"사용자 '{user_id}'를 찾을 수 없습니다.")
    service = BaselineService(db)
    try:
        baseline = service.build_baseline(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.to_response(baseline)


@router.get("/users/{user_id}/baseline", response_model=BaselineResponse)
def get_baseline(user_id: str, db: Session = Depends(get_db)) -> Any:
    service = BaselineService(db)
    baseline = service.get_active(user_id)
    if baseline is None:
        raise HTTPException(
            status_code=404,
            detail=f"사용자 '{user_id}'의 활성 Baseline이 없습니다.",
        )
    return service.to_response(baseline)


@router.get("/users/{user_id}/baseline-observations")
def list_baseline_observations(user_id: str, db: Session = Depends(get_db)) -> Any:
    service = BaselineService(db)
    obs = service.repo.list_observations(user_id)
    return [
        {
            "id": o.id,
            "session_id": o.session_id,
            "cognitive_load": o.cognitive_load,
            "attention": o.attention,
            "fatigue": o.fatigue,
            "confidence": o.confidence,
            "completeness": o.completeness,
            "is_normal_confirmed": o.is_normal_confirmed,
            "created_at": o.created_at,
        }
        for o in obs
    ]


@router.get("/users/{user_id}/episodes", response_model=List[EpisodeResponse])
def list_episodes(user_id: str, limit: int = 20, db: Session = Depends(get_db)) -> Any:
    repo = EpisodeRepository(db)
    episodes = repo.list_recent(user_id, limit=limit)
    return [
        EpisodeResponse(
            id=e.id,
            user_id=e.user_id,
            session_id=e.session_id,
            state_level=e.state_level,
            state_report=e.state_report_json,
            created_at=e.created_at,
        )
        for e in episodes
    ]


@router.get("/users/{user_id}/summary", response_model=SummaryResponse)
def get_summary(user_id: str, db: Session = Depends(get_db)) -> Any:
    repo = SummaryRepository(db)
    row = repo.get(user_id)
    if row is None:
        return SummaryResponse(
            user_id=user_id,
            summary={},
            recent_episode_count=0,
            updated_at=None,
        )
    return SummaryResponse(
        user_id=row.user_id,
        summary=row.summary_json,
        recent_episode_count=row.recent_episode_count,
        updated_at=row.updated_at,
    )


# ----------------------------------------------------------------------
# Memory v2
# ----------------------------------------------------------------------
@router.get("/users/{user_id}/memory")
def memory_overview(user_id: str, db: Session = Depends(get_db)) -> Any:
    return StateMemoryService(db).overview(user_id)


@router.get("/users/{user_id}/memory/events")
def memory_events(user_id: str, limit: int = 50, db: Session = Depends(get_db)) -> Any:
    rows = StateMemoryService(db).events.list(user_id, limit=limit)
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "session_id": e.session_id,
            "payload": e.payload_json,
            "created_at": e.created_at,
        }
        for e in rows
    ]


@router.post("/users/{user_id}/memory/consolidate")
def memory_consolidate(
    user_id: str, min_age_days: float = 14.0, threshold: float = 0.35, db: Session = Depends(get_db)
) -> Any:
    return StateMemoryService(db).consolidate(user_id, min_age_days=min_age_days, threshold=threshold)


@router.post("/mock/seed", response_model=SeedResponse)
def mock_seed(db: Session = Depends(get_db)) -> Any:
    result = seed_demo_data(db)
    return SeedResponse(**result)
