"""Base LLM client interface and shared data types.

The runtime treats providers uniformly through this interface. Only the
concrete adapters know about vendor specifics (API shape, transport, auth).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """Raised when an LLM provider cannot be reached or misconfigured."""


@dataclass
class ChatMessage:
    """A single chat message. ``role`` is one of system/user/assistant/tool."""

    role: str
    content: str


@dataclass
class LLMResult:
    """A completed model response."""

    text: str
    model: str | None = None
    raw: dict | None = None
    usage: dict | None = None

    def __post_init__(self) -> None:
        if isinstance(self.raw, dict) and self.usage is None:
            self.usage = self.raw.get("usage")


class LLMClient(ABC):
    """Provider-agnostic LLM interface consumed by the agent loop."""

    name: str = "base"

    @property
    def default_model(self) -> str:
        return "default"

    @abstractmethod
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResult:
        """Send messages and return a completion. Raises :class:`LLMError` on failure."""

    def complete_many(self, messages: list[dict], **kwargs) -> LLMResult:
        """Convenience wrapper accepting raw dict messages (role/content)."""
        return self.complete([ChatMessage(**m) for m in messages], **kwargs)
