"""FastAPI 애플리케이션 엔트리포인트."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import init_db
from app.services.llm_service import OllamaLLMService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 작업 디렉터리 기준 data 폴더
    Path("data").mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="상태 인지 AI Agent PoC — 연구용. 의료 진단용이 아닙니다.",
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
        llm = OllamaLLMService(settings)
        return {
            "status": "ok",
            "app": settings.app_name,
            "ollama_enabled": settings.ollama_enabled,
            "ollama_reachable": llm.health_check(),
            "ollama_model": settings.ollama_model,
            "ollama_num_ctx": settings.ollama_num_ctx,
        }

    return app


app = create_app()
