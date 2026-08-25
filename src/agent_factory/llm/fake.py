"""Deterministic, offline LLM for tests and headless runs.

The fake is scriptable: give it a list of response texts and it returns them in
order; once exhausted it falls back to echoing the last message. This lets the
test suite drive exact agent-loop behavior (final answers, tool calls, blocked
approvals) with no network and no API keys.
"""

from __future__ import annotations

from typing import Optional

from .base import ChatMessage, LLMClient, LLMResult


class FakeLLM(LLMClient):
    name = "fake"

    def __init__(self, responses: Optional[list[str]] = None, model: str = "fake-model"):
        self.responses = list(responses or [])
        self.model_name = model
        self.calls = 0

    @property
    def default_model(self) -> str:
        return self.model_name

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResult:
        self.calls += 1
        if self.responses:
            text = self.responses.pop(0)
        else:
            text = messages[-1].content
        return LLMResult(text=text, model=self.model_name)
