"""FastAPI 앱."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import LLM_BASE_URL, LLM_MODE, LLM_MODEL, TAXONOMY_PATH
from pipeline import EmotionPipeline

app = FastAPI(
    title="Emotion Mapping Agent",
    description="다중 감정 분류 → 7대 기본감정 매핑 LLM 에이전트",
    version="1.2.0",
)

pipeline = EmotionPipeline()
STATIC_DIR = Path(__file__).resolve().parent / "static"


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="감정 분석할 문장")
    mapping_memory: str | None = Field(
        None,
        max_length=8000,
        description="7대 감정 매핑 기준 (에이전트 메모리)",
    )
    user_id: str = Field("default", min_length=1, max_length=64, description="메모리 소유자 (상태 인지 Agent와 동일 ID 권장)")


class AnalyzeResponse(BaseModel):
    input: str
    mapping_memory: str
    classification: dict
    mapping: dict
    verification: dict
    final_emotion: str
    steps: list
    elapsed_ms: int
    mode: str
    fallback_reason: str | None = None
    rulebook_version: int
    case_id: str
    memory: dict
    emotion_context: dict


class CorrectionRequest(BaseModel):
    case_id: str = Field(..., min_length=1)
    correct_emotion: str = Field(..., min_length=1)
    note: str | None = Field(None, max_length=500)


class RulebookProposal(BaseModel):
    content: str = Field(..., min_length=10, max_length=20000)
    note: str = Field("", max_length=500)


@app.get("/")
async def index() -> Response:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    memory = pipeline.memory.active_rulebook()["content"]
    safe = (
        memory.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    html = html.replace(
        '<textarea id="memoryText" placeholder="매핑 기준을 불러오는 중..."></textarea>',
        f'<textarea id="memoryText" placeholder="7대 감정 매핑 기준을 입력하세요...">{safe}</textarea>',
        1,
    )
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "llm_base_url": LLM_BASE_URL,
        "llm_model": LLM_MODEL or "auto-detect",
        "llm_mode": LLM_MODE,
        "active_rulebook_version": pipeline.memory.active_rulebook()["version"],
    }


@app.get("/api/mapping-memory")
async def mapping_memory() -> dict:
    rb = pipeline.memory.active_rulebook()
    return {"content": rb["content"], "version": rb["version"]}


@app.get("/api/emotions")
async def emotions() -> dict:
    import json

    with TAXONOMY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="문장을 입력해주세요.")
    try:
        memory = req.mapping_memory.strip() if req.mapping_memory else None
        result = pipeline.run(text, mapping_memory=memory, user_id=req.user_id)
        return AnalyzeResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM 처리 실패: {exc}") from exc


# ----------------------------------------------------------------------
# Agent Memory (책 3장: 사례 메모리 · 교정 · 압축 · 규칙집 PR)
# ----------------------------------------------------------------------
@app.get("/api/memory/{user_id}")
async def memory_overview(user_id: str) -> dict:
    return pipeline.memory.overview(user_id)


@app.get("/api/memory/{user_id}/events")
async def memory_events(user_id: str, limit: int = 50) -> list:
    return pipeline.memory.store.list_events(user_id, limit=limit)


@app.post("/api/memory/correction")
async def memory_correction(req: CorrectionRequest) -> dict:
    try:
        return pipeline.memory.correct(req.case_id, req.correct_emotion, req.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/memory/{user_id}/consolidate")
async def memory_consolidate(user_id: str) -> dict:
    return pipeline.memory.consolidate(user_id)


@app.get("/api/rulebook")
async def rulebook_versions() -> list:
    return [{k: v for k, v in r.items() if k != "content"} for r in pipeline.memory.store.rulebook_versions()]


@app.get("/api/rulebook/{version}")
async def rulebook_get(version: int) -> dict:
    rb = pipeline.memory.store.get_rulebook(version)
    if rb is None:
        raise HTTPException(status_code=404, detail="버전 없음")
    return rb


@app.post("/api/rulebook/propose")
async def rulebook_propose(req: RulebookProposal) -> dict:
    return pipeline.memory.propose_rulebook(req.content, req.note)


@app.post("/api/rulebook/{version}/approve")
async def rulebook_approve(version: int) -> dict:
    try:
        return pipeline.memory.approve_rulebook(version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rulebook/{version}/rollback")
async def rulebook_rollback(version: int) -> dict:
    try:
        return pipeline.memory.rollback_rulebook(version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
