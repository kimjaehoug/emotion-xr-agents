"""FastAPI 라우터. XR Control AI Agent PoC."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.llm.prompt_builder import build_system_prompt
from app.llm.protocol import LLMConnectionError
from app.llm.qwen_client import QwenLocalLLMClient
from app.llm.response_parser import parse_json_response
from app.memory.service import XrMemoryV2
from app.repositories.catalog_repo import ActionCatalogRepository, ContentRepository, PolicyRepository
from app.repositories.memory_repo import XrEpisodeRepository, XrSummaryRepository
from app.repositories.plan_repo import ExecutionRepository
from app.repositories.user_repo import UserRepository
from app.schemas import (
    ActionCatalogCreate,
    ActionCatalogResponse,
    ConfirmationDecisionRequest,
    ContentCreate,
    ContentResponse,
    ExecuteRequest,
    ExecuteResponse,
    ExecutionResponse,
    FeedbackRequest,
    FeedbackResponse,
    LLMHealthResponse,
    PlanResponse,
    PolicyCreate,
    PolicyResponse,
    SeedResponse,
    TestLLMRequest,
    TestLLMResponse,
    UserCreate,
    UserResponse,
    XrEpisodeResponse,
    XrSummaryResponse,
)
from app.services.plan_service import (
    ConfirmationNotFoundError,
    ExecutionNotFoundError,
    PlanNotFoundError,
    PlanService,
)
from app.services.seed_service import seed_demo_data

router = APIRouter(prefix="/api/v1")


# ----------------------------------------------------------------------
# XR Control Agent — Plan / Execute / Confirmation / Feedback
# ----------------------------------------------------------------------
@router.post("/xr-agent/plan", response_model=PlanResponse)
def create_plan(state_report: Dict[str, Any], db: Session = Depends(get_db)) -> Any:
    service = PlanService(db)
    try:
        return service.create_plan(state_report)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        # UNIQUE 등 DB 충돌도 500 대신 명확한 메시지로
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"계획 생성 실패: {exc}",
        ) from exc


@router.post("/xr-agent/execute", response_model=ExecuteResponse)
def execute_plan(body: ExecuteRequest, db: Session = Depends(get_db)) -> Any:
    service = PlanService(db)
    try:
        return service.execute_plan(body.plan_id)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/xr-agent/warmup-llm")
def warmup_llm() -> Any:
    """qwen3.5:9b 모델을 미리 로드한다."""
    get_settings.cache_clear()
    client = QwenLocalLLMClient()
    return client.warm_up()


@router.get("/xr-agent/health/llm", response_model=LLMHealthResponse)
def llm_health() -> Any:
    from app.llm.health import check_llm_health

    get_settings.cache_clear()
    result = check_llm_health()
    return LLMHealthResponse(
        reachable=bool(result.get("reachable")),
        base_url=str(result.get("base_url")),
        model=str(result.get("model")),
        detail=str(result.get("detail")),
    )


@router.post("/xr-agent/confirmations/{confirmation_id}")
def resolve_confirmation(
    confirmation_id: str, body: ConfirmationDecisionRequest, db: Session = Depends(get_db)
) -> Any:
    service = PlanService(db)
    try:
        confirmation, execution = service.resolve_confirmation(confirmation_id, body.decision)
    except ConfirmationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"confirmation": confirmation, "execution": execution}


@router.post("/xr-agent/feedback", response_model=FeedbackResponse)
def submit_feedback(body: FeedbackRequest, db: Session = Depends(get_db)) -> Any:
    service = PlanService(db)
    try:
        execution, profile_updated = service.submit_feedback(
            body.execution_id, body.effect, body.comment
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FeedbackResponse(
        execution_id=execution["execution_id"], effect=body.effect, profile_updated=profile_updated
    )


@router.get("/xr-agent/executions/{execution_id}", response_model=ExecutionResponse)
def get_execution(execution_id: str, db: Session = Depends(get_db)) -> Any:
    repo = ExecutionRepository(db)
    execution = repo.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"execution_id '{execution_id}'를 찾을 수 없습니다.")
    return PlanService.execution_to_response(execution)


@router.post("/xr-agent/test-llm", response_model=TestLLMResponse)
def test_llm(body: TestLLMRequest) -> Any:
    settings = get_settings()
    client = QwenLocalLLMClient(settings)
    system_prompt = body.system_prompt or build_system_prompt()
    try:
        raw_output = client.generate_plan(system_prompt=system_prompt, user_prompt=body.user_prompt)
    except LLMConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"로컬 LLM 호출 실패: {exc}") from exc

    parsed, parse_error = parse_json_response(raw_output)
    return TestLLMResponse(raw_output=raw_output, parsed=parsed, parse_error=parse_error)


@router.get("/xr-agent/users/{user_id}/xr-episodes", response_model=List[XrEpisodeResponse])
def list_xr_episodes(user_id: str, limit: int = 20, db: Session = Depends(get_db)) -> Any:
    repo = XrEpisodeRepository(db)
    episodes = repo.list_recent(user_id, limit=limit)
    return [
        XrEpisodeResponse(
            id=e.id,
            user_id=e.user_id,
            session_id=e.session_id,
            state_report_id=e.state_report_id,
            state_level=e.state_level,
            route=e.route,
            planner_source=e.planner_source,
            plan=e.plan_json,
            created_at=e.created_at,
        )
        for e in episodes
    ]


@router.get("/xr-agent/users/{user_id}/xr-summary", response_model=XrSummaryResponse)
def get_xr_summary(user_id: str, db: Session = Depends(get_db)) -> Any:
    repo = XrSummaryRepository(db)
    row = repo.get(user_id)
    if row is None:
        return XrSummaryResponse(user_id=user_id, summary={}, recent_episode_count=0, updated_at=None)
    return XrSummaryResponse(
        user_id=row.user_id,
        summary=row.summary_json,
        recent_episode_count=row.recent_episode_count,
        updated_at=row.updated_at,
    )


# ----------------------------------------------------------------------
# Memory v2
# ----------------------------------------------------------------------
@router.get("/xr-agent/users/{user_id}/memory")
def xr_memory_overview(user_id: str, db: Session = Depends(get_db)) -> Any:
    return XrMemoryV2(db).overview(user_id)


@router.get("/xr-agent/users/{user_id}/memory/events")
def xr_memory_events(user_id: str, limit: int = 50, db: Session = Depends(get_db)) -> Any:
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "session_id": e.session_id,
            "payload": e.payload_json,
            "created_at": e.created_at,
        }
        for e in XrMemoryV2(db).events.list(user_id, limit=limit)
    ]


# ----------------------------------------------------------------------
# 사용자 (Profile Memory)
# ----------------------------------------------------------------------
@router.get("/users", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    return [
        UserResponse(
            user_id=u.user_id, profile=u.profile_json, created_at=u.created_at, updated_at=u.updated_at
        )
        for u in repo.list_all()
    ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    try:
        user = repo.create(body.user_id, body.profile.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserResponse(
        user_id=user.user_id, profile=user.profile_json, created_at=user.created_at, updated_at=user.updated_at
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)) -> Any:
    repo = UserRepository(db)
    user = repo.get_by_user_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"사용자 '{user_id}'를 찾을 수 없습니다.")
    return UserResponse(
        user_id=user.user_id, profile=user.profile_json, created_at=user.created_at, updated_at=user.updated_at
    )


# ----------------------------------------------------------------------
# 정책 / 행동 / 콘텐츠 카탈로그
# ----------------------------------------------------------------------
@router.get("/xr-agent/policies", response_model=List[PolicyResponse])
def list_policies(db: Session = Depends(get_db)) -> Any:
    repo = PolicyRepository(db)
    return [
        PolicyResponse(
            id=p.id,
            policy_key=p.policy_key,
            state_level=p.state_level,
            min_confidence=p.min_confidence,
            allowed_routes=p.allowed_routes_json,
            description=p.description,
            is_active=p.is_active,
            created_at=p.created_at,
        )
        for p in repo.list_all()
    ]


@router.post("/xr-agent/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(body: PolicyCreate, db: Session = Depends(get_db)) -> Any:
    repo = PolicyRepository(db)
    if repo.get_by_key(body.policy_key) is not None:
        raise HTTPException(status_code=400, detail=f"policy_key '{body.policy_key}'가 이미 존재합니다.")
    p = repo.create(
        policy_key=body.policy_key,
        state_level=body.state_level,
        min_confidence=body.min_confidence,
        allowed_routes_json=body.allowed_routes,
        description=body.description,
        is_active=body.is_active,
    )
    return PolicyResponse(
        id=p.id,
        policy_key=p.policy_key,
        state_level=p.state_level,
        min_confidence=p.min_confidence,
        allowed_routes=p.allowed_routes_json,
        description=p.description,
        is_active=p.is_active,
        created_at=p.created_at,
    )


@router.get("/xr-agent/actions", response_model=List[ActionCatalogResponse])
def list_actions(db: Session = Depends(get_db)) -> Any:
    repo = ActionCatalogRepository(db)
    return [
        ActionCatalogResponse(
            id=a.id,
            action_type=a.action_type,
            xr_parameter=a.xr_parameter,
            category=a.category,
            max_delta=a.max_delta,
            requires_confirmation=a.requires_confirmation,
            description=a.description,
            is_active=a.is_active,
            created_at=a.created_at,
        )
        for a in repo.list_all()
    ]


@router.post("/xr-agent/actions", response_model=ActionCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_action(body: ActionCatalogCreate, db: Session = Depends(get_db)) -> Any:
    repo = ActionCatalogRepository(db)
    a = repo.create(
        action_type=body.action_type,
        xr_parameter=body.xr_parameter,
        category=body.category,
        max_delta=body.max_delta,
        requires_confirmation=body.requires_confirmation,
        description=body.description,
        is_active=body.is_active,
    )
    return ActionCatalogResponse(
        id=a.id,
        action_type=a.action_type,
        xr_parameter=a.xr_parameter,
        category=a.category,
        max_delta=a.max_delta,
        requires_confirmation=a.requires_confirmation,
        description=a.description,
        is_active=a.is_active,
        created_at=a.created_at,
    )


@router.get("/xr-agent/contents", response_model=List[ContentResponse])
def list_contents(db: Session = Depends(get_db)) -> Any:
    repo = ContentRepository(db)
    return [
        ContentResponse(
            id=c.id,
            content_id=c.content_id,
            title=c.title,
            content_type=c.content_type,
            category=c.category,
            difficulty=c.difficulty,
            visual_complexity=c.visual_complexity,
            audio_stimulation=c.audio_stimulation,
            interaction_density=c.interaction_density,
            tags=c.tags_json,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in repo.list_all()
    ]


@router.post("/xr-agent/contents", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def create_content(body: ContentCreate, db: Session = Depends(get_db)) -> Any:
    repo = ContentRepository(db)
    if repo.get_by_content_id(body.content_id) is not None:
        raise HTTPException(status_code=400, detail=f"content_id '{body.content_id}'가 이미 존재합니다.")
    c = repo.create(
        content_id=body.content_id,
        title=body.title,
        content_type=body.content_type,
        category=body.category,
        difficulty=body.difficulty,
        visual_complexity=body.visual_complexity,
        audio_stimulation=body.audio_stimulation,
        interaction_density=body.interaction_density,
        tags_json=body.tags,
        is_active=body.is_active,
    )
    return ContentResponse(
        id=c.id,
        content_id=c.content_id,
        title=c.title,
        content_type=c.content_type,
        category=c.category,
        difficulty=c.difficulty,
        visual_complexity=c.visual_complexity,
        audio_stimulation=c.audio_stimulation,
        interaction_density=c.interaction_density,
        tags=c.tags_json,
        is_active=c.is_active,
        created_at=c.created_at,
    )


# ----------------------------------------------------------------------
# Mock 데이터 시드
# ----------------------------------------------------------------------
@router.get("/xr-agent/users/{user_id}/sessions/{session_id}/xr-state")
def get_mock_xr_state(
    user_id: str,
    session_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Mock XR 환경 상태 조회."""
    from app.services.mock_xr_runtime import MockXrRuntime

    runtime = MockXrRuntime(db)
    state = runtime.get_state(user_id, session_id)
    return {"user_id": user_id, "session_id": session_id, "state": state}


@router.post("/mock/seed", response_model=SeedResponse)
def mock_seed(db: Session = Depends(get_db)) -> Any:
    result = seed_demo_data(db)
    return SeedResponse(**result)
