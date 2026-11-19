"""환경 변수 기반 설정."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
TAXONOMY_PATH = BASE_DIR / "taxonomies" / "emotions.json"

# 프로젝트 .env를 우선 적용 (셸에 남은 이전 값보다 우선)
load_dotenv(BASE_DIR / ".env", override=True)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
# auto: LLM 사용, 실패 시 오프라인 규칙으로 fallback / offline: LLM 호출 없이 규칙 + 메모리만 사용
LLM_MODE = os.getenv("LLM_MODE", "auto").strip().lower()
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", str(BASE_DIR / "data" / "emotion_memory.db"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
