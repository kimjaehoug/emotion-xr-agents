"""로컬 LLM 클라이언트 프로토콜.

`QwenLocalLLMClient`(실제 httpx 구현)와 `MockLocalLLMClient`(테스트용)가
동일한 인터페이스를 구현하도록 강제한다.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class LocalLLMClientProtocol(Protocol):
    """OpenAI 호환 로컬 LLM(Qwen 등) 클라이언트 인터페이스."""

    def generate_plan(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """LLM에 계획 생성을 요청하고 원시 텍스트(JSON 기대)를 반환한다.

        연결 실패/타임아웃 시 `LLMConnectionError`를 발생시켜야 한다.
        """
        ...

    def health_check(self) -> bool:
        """LLM 서버 접근 가능 여부를 반환한다."""
        ...


class LLMConnectionError(Exception):
    """LLM 서버 연결/타임아웃 실패."""


class LLMResponseError(Exception):
    """LLM이 응답했지만 사용 불가능한 형식(빈 응답 등)일 때."""
