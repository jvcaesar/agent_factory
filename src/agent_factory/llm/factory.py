"""Provider selection.

Chooses an :class:`LLMClient` from a provider name. The provider can be passed
explicitly or read from ``AGENT_FACTORY_PROVIDER`` (default ``openai``).
"""

from __future__ import annotations

import os
from typing import Optional

from .base import LLMError
from .fake import FakeLLM
from .ollama_client import OllamaLLM
from .openai_client import OpenAILLM


def get_client(provider: Optional[str] = None, **kwargs) -> object:
    """Return a configured LLM client for ``provider`` (or the env default)."""
    name = (provider or os.environ.get("AGENT_FACTORY_PROVIDER", "openai")).strip().lower()
    if name in ("fake", "test", "echo"):
        return FakeLLM(**{k: v for k, v in kwargs.items() if k in ("responses", "model")})
    if name == "openai":
        return OpenAILLM(**kwargs.get("openai", {}) if isinstance(kwargs.get("openai"), dict) else kwargs)
    if name == "ollama":
        return OllamaLLM(
            base_url=kwargs.get("base_url"),
            model=kwargs.get("model"),
        )
    raise LLMError(f"unknown provider {name!r} (expected openai | ollama | fake)")
