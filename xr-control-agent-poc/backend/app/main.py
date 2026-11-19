"""FastAPI 애플리케이션 엔트리포인트.

실행: `uvicorn app.main:app --reload --port 8001` (기본 포트 8001; 8080이 사용
중이거나 미기동일 수 있어 로컬 개발은 Ollama(11434) 기반 8001 포트를 사용한다.)
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import init_db
from app.llm.health import check_llm_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("data").mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="XR Control AI Agent PoC — 상태 인지 Agent의 StateReport를 받아 "
        "XR 파라미터/콘텐츠 조정 계획을 세우고 실행하는 연구용 백엔드.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        llm_status = check_llm_health(settings)
        return {
            "status": "ok",
            "app": settings.app_name,
            "database_url": settings.database_url,
            "local_llm": llm_status,
        }

    return app


app = create_app()
