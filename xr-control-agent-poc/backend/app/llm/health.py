"""로컬 LLM 헬스체크 유틸."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.core.config import Settings, get_settings


def check_llm_health(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """`GET /models` 호출로 로컬 LLM 서버 접근 가능 여부를 확인한다."""
    settings = settings or get_settings()
    url = f"{settings.local_llm_base_url.rstrip('/')}/models"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {settings.local_llm_api_key}"})
        return {
            "reachable": resp.status_code == 200,
            "base_url": settings.local_llm_base_url,
            "model": settings.local_llm_model,
            "detail": f"HTTP {resp.status_code}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "reachable": False,
            "base_url": settings.local_llm_base_url,
            "model": settings.local_llm_model,
            "detail": str(exc),
        }
