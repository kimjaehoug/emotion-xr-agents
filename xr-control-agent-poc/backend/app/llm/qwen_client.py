"""로컬 Qwen 클라이언트.

우선순위:
1) Ollama 네이티브 `/api/chat` (think=false, format=json) — 11434일 때
2) OpenAI-compatible `/v1/chat/completions` — llama-server 등

16GB RAM 환경: num_ctx=4096, 짧은 max_tokens, 재시도 최소화.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings
from app.llm.protocol import LLMConnectionError, LLMResponseError

logger = logging.getLogger(__name__)


class QwenLocalLLMClient:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @property
    def _is_ollama(self) -> bool:
        host = urlparse(self.settings.local_llm_base_url).netloc
        return "11434" in host or self.settings.local_llm_base_url.rstrip("/").endswith("/v1") and "11434" in self.settings.local_llm_base_url

    @property
    def _ollama_chat_url(self) -> str:
        # http://127.0.0.1:11434/v1 → http://127.0.0.1:11434/api/chat
        parsed = urlparse(self.settings.local_llm_base_url)
        return f"{parsed.scheme}://{parsed.netloc}/api/chat"

    @property
    def _openai_chat_url(self) -> str:
        return f"{self.settings.local_llm_base_url.rstrip('/')}/chat/completions"

    @property
    def _models_url(self) -> str:
        if self._is_ollama:
            parsed = urlparse(self.settings.local_llm_base_url)
            return f"{parsed.scheme}://{parsed.netloc}/api/tags"
        return f"{self.settings.local_llm_base_url.rstrip('/')}/models"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.local_llm_api_key}"}

    def generate_plan(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        settings = self.settings
        # timeout 시 긴 재시도는 오히려 500/대기 유발 → 기본 1회(+옵션 1회)
        max_attempts = max(settings.local_llm_max_retries, 0) + 1
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            started = time.perf_counter()
            try:
                if self._is_ollama:
                    content = self._call_ollama_native(system_prompt, user_prompt)
                else:
                    content = self._call_openai_compatible(
                        system_prompt, user_prompt, json_schema
                    )
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "로컬 LLM 응답 성공 model=%s latency_ms=%s attempt=%s",
                    settings.local_llm_model,
                    latency_ms,
                    attempt + 1,
                )
                if not content:
                    raise LLMResponseError("LLM 응답에 content가 없습니다.")
                return content
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "로컬 LLM 타임아웃/연결 실패(시도 %s/%s): %s",
                    attempt + 1,
                    max_attempts,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "로컬 LLM HTTP 오류(시도 %s/%s): %s %s",
                    attempt + 1,
                    max_attempts,
                    exc.response.status_code,
                    exc.response.text[:300],
                )
            except LLMResponseError as exc:
                last_error = exc
                logger.warning("로컬 LLM 응답 오류: %s", exc)

        raise LLMConnectionError(
            f"로컬 LLM 호출이 {max_attempts}회 모두 실패했습니다: {last_error}"
        )

    def _call_ollama_native(self, system_prompt: str, user_prompt: str) -> str:
        """Ollama /api/chat — think 비활성 + JSON format."""
        settings = self.settings
        payload: Dict[str, Any] = {
            "model": settings.local_llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": settings.local_llm_temperature,
                "num_ctx": 4096,
                "num_predict": min(settings.local_llm_max_tokens, 512),
            },
        }
        timeout = httpx.Timeout(
            connect=10.0,
            read=float(settings.local_llm_timeout_sec),
            write=30.0,
            pool=10.0,
        )
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(self._ollama_chat_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        message = data.get("message") or {}
        text = (message.get("content") or "").strip()
        # thinking 잔여 제거
        for marker in ("</think>", "</thinking>"):
            if marker in text:
                text = text.split(marker)[-1].strip()
        return text

    def _call_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]],
    ) -> str:
        settings = self.settings
        payload: Dict[str, Any] = {
            "model": settings.local_llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.local_llm_temperature,
            "max_tokens": min(settings.local_llm_max_tokens, 512),
            "think": False,
        }
        use_schema = json_schema is not None and settings.local_llm_json_schema_enabled
        if use_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "xr_action_plan",
                    "schema": json_schema,
                    "strict": True,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        timeout = httpx.Timeout(
            connect=10.0,
            read=float(settings.local_llm_timeout_sec),
            write=30.0,
            pool=10.0,
        )
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                self._openai_chat_url, json=payload, headers=self._headers()
            )
            if resp.status_code == 400 and "response_format" in payload:
                # schema/json_object 미지원 → 일반 호출
                payload.pop("response_format", None)
                resp = client.post(
                    self._openai_chat_url, json=payload, headers=self._headers()
                )
            resp.raise_for_status()
            data = resp.json()
        return self._extract_content(data)

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        for marker in ("</think>", "</thinking>"):
            if marker in text:
                text = text.split(marker)[-1].strip()
        return text

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(self._models_url, headers=self._headers())
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def warm_up(self) -> Dict[str, Any]:
        """짧은 호출로 모델 로드. 실패해도 예외를 밖으로 던지지 않는다."""
        started = time.perf_counter()
        try:
            text = self.generate_plan(
                system_prompt="Reply with JSON only.",
                user_prompt='{"ping":true} 에 대해 {"ok":true} 만 출력하라.',
                json_schema=None,
            )
            return {
                "ok": True,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "preview": text[:80],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "error": str(exc),
            }
