"""Qwen LLM 기반 Planner."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from app.llm.prompt_builder import build_system_prompt, build_user_prompt
from app.llm.protocol import LocalLLMClientProtocol
from app.schemas.action_plan import RawPlanOutput


class QwenPlanner:
    """로컬 Qwen(OpenAI 호환) 클라이언트를 사용해 원시 계획 텍스트를 생성한다."""

    def __init__(self, client: LocalLLMClientProtocol) -> None:
        self.client = client

    def build_prompts(self, context: Dict[str, Any]) -> Tuple[str, str]:
        return build_system_prompt(), build_user_prompt(context)

    def plan(self, context: Dict[str, Any]) -> Tuple[str, str, str]:
        """(raw_output, system_prompt, user_prompt) 반환.

        연결 실패 시 `LLMConnectionError`가 그대로 전파되며, 상위(그래프 노드)에서
        `FallbackPlanner`로 전환한다.
        """
        system_prompt, user_prompt = self.build_prompts(context)
        schema = RawPlanOutput.model_json_schema()
        raw_output = self.client.generate_plan(
            system_prompt=system_prompt, user_prompt=user_prompt, json_schema=schema
        )
        return raw_output, system_prompt, user_prompt
