"""테스트/개발용 Mock LLM 클라이언트."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.llm.protocol import LLMConnectionError


class MockLocalLLMClient:
    """`LocalLLMClientProtocol` 구현체. 미리 지정된 응답을 순서대로 반환한다."""

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        *,
        raise_connection_error: bool = False,
        response_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        self._responses = list(responses or [])
        self._raise_connection_error = raise_connection_error
        self._response_factory = response_factory
        self.calls: List[Dict[str, Any]] = []

    def generate_plan(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt, "json_schema": json_schema}
        )
        if self._raise_connection_error:
            raise LLMConnectionError("Mock: 연결 실패")
        if self._response_factory is not None:
            return self._response_factory()
        if self._responses:
            return self._responses.pop(0)
        return "{}"

    def health_check(self) -> bool:
        return not self._raise_connection_error
