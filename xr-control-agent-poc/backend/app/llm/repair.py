"""검증 실패 시 LLM 재요청(자체 복구) 훅."""

from __future__ import annotations

import logging
from typing import List, Optional

from app.llm.prompt_builder import build_repair_prompt
from app.llm.protocol import LLMConnectionError, LocalLLMClientProtocol

logger = logging.getLogger(__name__)


def attempt_repair(
    client: LocalLLMClientProtocol,
    *,
    system_prompt: str,
    user_prompt: str,
    raw_output: str,
    errors: List[str],
    json_schema: Optional[dict] = None,
) -> Optional[str]:
    """1회 복구 요청. 연결 실패 시 None을 반환하여 상위에서 fallback 처리하도록 한다."""
    repair_prompt = build_repair_prompt(user_prompt=user_prompt, raw_output=raw_output, errors=errors)
    try:
        return client.generate_plan(
            system_prompt=system_prompt, user_prompt=repair_prompt, json_schema=json_schema
        )
    except LLMConnectionError as exc:
        logger.warning("복구 요청도 연결 실패: %s", exc)
        return None
