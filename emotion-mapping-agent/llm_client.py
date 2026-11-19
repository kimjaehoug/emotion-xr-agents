"""OpenAI 호환 LLM 클라이언트."""

from __future__ import annotations

from typing import Any

import httpx
from openai import APITimeoutError, OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT
from json_repair import parse_llm_json


class LLMClient:
    def __init__(self) -> None:
        timeout = httpx.Timeout(
            connect=30.0,
            read=LLM_TIMEOUT,
            write=30.0,
            pool=30.0,
        )
        self.client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            timeout=timeout,
            max_retries=1,
        )
        self._model: str | None = LLM_MODEL or None

    def _resolve_model(self) -> str:
        if self._model:
            return self._model
        models = self.client.models.list()
        if not models.data:
            raise RuntimeError("LLM 서버에서 사용 가능한 모델을 찾을 수 없습니다.")

        active = [m for m in models.data if getattr(m, "active", True)]
        chosen = active[0] if active else models.data[0]
        self._model = chosen.id
        return self._model

    def _complete(self, messages: list[dict[str, str]], temperature: float) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self._resolve_model(),
                messages=messages,
                temperature=temperature,
                max_tokens=1600,
            )
        except APITimeoutError as exc:
            raise TimeoutError(
                f"LLM 응답 대기 시간 초과 ({int(LLM_TIMEOUT)}초). "
                "잠시 후 다시 시도하거나 .env의 LLM_TIMEOUT을 더 늘려주세요."
            ) from exc
        return response.choices[0].message.content or ""

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt + "\n유효한 JSON 객체만 출력. 코드블록/주석 금지."},
            {"role": "user", "content": user_prompt},
        ]
        content = self._complete(messages, temperature)
        try:
            return parse_llm_json(content)
        except ValueError:
            # 한 번만 재요청: 방금 출력을 올바른 JSON으로 고치기
            repair_messages = messages + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "위 출력을 유효한 JSON 객체로만 다시 출력하세요. 설명 없이 JSON만.",
                },
            ]
            repaired = self._complete(repair_messages, 0.0)
            return parse_llm_json(repaired)
