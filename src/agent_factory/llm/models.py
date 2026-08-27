"""Per-role model/provider resolution.

Each role selects its LLM via a precedence chain (highest wins):

1. ``Role.provider`` / ``Role.model`` — explicit per-role override in the org YAML.
2. Model from ``model_tier`` for the provider:
   ``OPENAI_MODEL_FAST/SMART/BIG`` or ``OLLAMA_MODEL_FAST/SMART/BIG``.
3. The provider's general model env (``OPENAI_MODEL`` / ``OLLAMA_MODEL``).
4. A built-in default for the tier.

This lets you run different agents on different models (e.g. cheap workers on
``gpt-4o-mini``, a big reasoning lead on ``gpt-4o``, local research on Ollama),
entirely configured through the ``.env`` file and the role YAML.
"""

from __future__ import annotations

import os
from typing import Optional

from ..config import ModelTier, Role
from ..config.env import env_get

KNOWN_PROVIDERS = ("openai", "ollama", "fake")

# env var name per (provider, tier) for a concrete model override
_TIER_ENV = {
    "openai": {"fast": "OPENAI_MODEL_FAST", "smart": "OPENAI_MODEL_SMART", "big": "OPENAI_MODEL_BIG"},
    "ollama": {"fast": "OLLAMA_MODEL_FAST", "smart": "OLLAMA_MODEL_SMART", "big": "OLLAMA_MODEL_BIG"},
}

# Provider-agnostic overrides (documented in ``.env.example``). These win over
# built-in defaults but lose to the provider-specific vars above, so a user can
# still pin one provider's tier while leaving the rest on the shared default.
_GENERIC_TIER_ENV = {"fast": ("MODEL_fast", "MODEL_FAST"), "smart": ("MODEL_smart", "MODEL_SMART"), "big": ("MODEL_big", "MODEL_BIG")}
_GENERIC_FALLBACK_ENV = ("MODEL_default", "MODEL_DEFAULT")

_GENERAL_ENV = {"openai": "OPENAI_MODEL", "ollama": "OLLAMA_MODEL"}

# Built-in defaults per (provider, tier) — used only if no env var is set.
_DEFAULTS = {
    "openai": {"fast": "gpt-4o-mini", "smart": "gpt-4o", "big": "gpt-4o"},
    "ollama": {"fast": "qwen2.5:0.5b", "smart": "gemma4", "big": "gemma4"},
}

def model_for_tier(provider: str, tier: ModelTier) -> Optional[str]:
    """Resolve a concrete model name for a provider + model tier from env.

    Priority: provider tier env > provider general env > generic
    ``MODEL_<tier>`` > ``MODEL_default`` > built-in default.
    """
    name = provider.lower()
    tier_key = tier.value if isinstance(tier, ModelTier) else str(tier)

    tier_var = _TIER_ENV.get(name, {}).get(tier_key)
    if tier_var:
        value = env_get(tier_var)
        if value:
            return value

    general_var = _GENERAL_ENV.get(name)
    if general_var:
        value = env_get(general_var)
        if value:
            return value

    generic = _GENERIC_TIER_ENV.get(tier_key)
    if generic:
        value = env_get(*generic)
        if value:
            return value

    value = env_get(*_GENERIC_FALLBACK_ENV)
    if value:
        return value

    return _DEFAULTS.get(name, {}).get(tier_key)


def resolve_default_provider() -> str:
    """Global provider: env AGENT_FACTORY_PROVIDER or 'openai'."""
    p = os.environ.get("AGENT_FACTORY_PROVIDER", "openai").strip().lower()
    return p if p in KNOWN_PROVIDERS else "openai"


def split_provider_model(value: str) -> tuple[Optional[str], str]:
    """Split an optional ``provider/model`` prefix: ``openai/gpt-4o`` -> (``openai``, ``gpt-4o``).

    Bare values pass through unchanged as ``(None, value)``. Unknown prefixes
    are treated as part of the model name.
    """
    value = value.strip()
    if "/" in value:
        head, _, rest = value.partition("/")
        candidate = head.strip().lower()
        if candidate in KNOWN_PROVIDERS and rest.strip():
            return candidate, rest.strip()
    return None, value


def resolve_role(
    role: Role,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Return (provider, model_name) for a role.

    Precedence for the provider: ``provider_override`` (CLI ``--provider``) >
    prefix on the per-role env var > prefix on ``Role.model`` > ``Role.provider``
    > global provider env. Model precedence: per-role env ``MODEL_<role_id>`` >
    ``Role.model`` > tier chain (``model_for_tier``).
    ``model_override`` has highest model precedence. A known provider prefix on
    it selects the provider unless ``provider_override`` is supplied; conflicting
    explicit prefixes are rejected.
    """
    provider: Optional[str] = provider_override
    model: Optional[str] = None

    if model_override:
        model_provider, model = split_provider_model(model_override)
        if provider_override and model_provider and model_provider != provider_override.lower():
            raise ValueError(
                f"--provider {provider_override!r} conflicts with "
                f"--model {model_override!r}"
            )
        if provider is None and model_provider:
            provider = model_provider

    # 1. Per-role env override: MODEL_<role_id>=ollama/gemma4:12b or gpt-4o-mini
    role_env = env_get(f"MODEL_{role.id}")
    if not model and role_env:
        env_provider, parsed = split_provider_model(role_env)
        model = parsed
        if provider is None and env_provider:
            provider = env_provider

    # 2. Role YAML model (a provider/ prefix is honored here too)
    if not model and role.model:
        yaml_provider, parsed = split_provider_model(role.model)
        model = parsed
        if provider is None and yaml_provider:
            provider = yaml_provider

    # 3. Tier-based resolution from the environment
    if not model:
        base = provider or role.provider or resolve_default_provider()
        base = base.strip().lower()
        if base == "fake":
            return "fake", None
        model = model_for_tier(base, role.model_tier.value)
        if model:
            # A tier value may itself carry an explicit provider/ prefix that
            # overrides the resolved provider (e.g. MODEL_fast=openai/gpt-4o-mini
            # while AGENT_FACTORY_PROVIDER=ollama).
            tier_provider, parsed = split_provider_model(model)
            if tier_provider:
                model = parsed
                if provider is None:
                    provider = tier_provider

    if provider is None:
        provider = role.provider or resolve_default_provider()
    return provider.strip().lower(), model