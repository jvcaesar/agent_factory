"""Provider selection.

Provides two entry points:

* ``get_client(...)`` — build a client directly from provider + overrides.
* ``client_for_role(role, provider_override=None)`` — build a client for a
  specific role, honoring per-role provider/model overrides and the tier-based
  model resolution in :mod:`agent_factory.llm.models`.

Providers: ``openai`` (default), ``ollama`` (local Gemma/Qwen), ``fake``
(offline tests). ``AGENT_FACTORY_PROVIDER`` sets the global default.
"""

from __future__ import annotations

import os
from typing import Optional

from ..config import Role
from .base import LLMClient, LLMError
from .fake import FakeLLM
from .models import resolve_role
from .ollama_client import OllamaLLM
from .openai_client import OpenAILLM


def get_client(
    provider: Optional[str] = None,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    responses: Optional[list[str]] = None,
) -> LLMClient:
    """Return a configured LLM client.

    ``provider`` defaults to ``AGENT_FACTORY_PROVIDER`` (or ``openai``). For
    ``fake``, ``responses`` scripts the deterministic outputs.
    """
    name = (provider or os.environ.get("AGENT_FACTORY_PROVIDER", "openai")).strip().lower()
    if name in ("fake", "test", "echo"):
        return FakeLLM(responses=responses, model=model)
    if name == "openai":
        return OpenAILLM(api_key=api_key, base_url=base_url, model=model)
    if name == "ollama":
        return OllamaLLM(base_url=base_url, model=model)
    raise LLMError(f"unknown provider {name!r} (expected openai | ollama | fake)")


def client_for_role(
    role: Role,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> LLMClient:
    """Build a client configured for a specific role.

    Applies per-role provider/model overrides (from ``Role.provider`` /
    ``Role.model`` or the tier-based env resolution), so different agents can
    run on different LLMs. ``provider_override`` (CLI ``--provider``) wins.
    """
    provider, model = resolve_role(
        role,
        provider_override=provider_override,
        model_override=model_override,
    )
    return get_client(provider, model=model)
