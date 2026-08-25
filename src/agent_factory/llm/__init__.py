"""LLM layer: a provider-agnostic client interface plus concrete adapters.

Providers are selected via the ``AGENT_FACTORY_PROVIDER`` env var (or the
``provider`` argument): ``openai`` (default), ``ollama`` (local Gemma/Qwen),
or ``fake`` (deterministic offline testing). The runtime only ever talks to
:class:`~agent_factory.llm.base.LLMClient`, so swapping providers never touches
agent code.
"""

from .base import ChatMessage, LLMClient, LLMError, LLMResult
from .factory import get_client
from .fake import FakeLLM

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResult",
    "ChatMessage",
    "FakeLLM",
    "get_client",
]
