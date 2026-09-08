"""OpenAI provider adapter (modern SDK, ``openai >= 1.0``).

Uses ``openai.OpenAI().chat.completions.create``. ``base_url`` may be set via
``OPENAI_BASE_URL``/constructor for compatible endpoints (OpenRouter, proxies,
etc.). For corporate TLS-intercepting proxies set ``OPENAI_VERIFY_SSL=0``
(unverified ``httpx.Client``); prefer ``REQUESTS_CA_BUNDLE=<corp CA>``.
"""

from __future__ import annotations

import os

from ..config.env import env_get
from .base import ChatMessage, LLMClient, LLMError, LLMResult


def _ssl_verify_disabled() -> bool:
    """True when OPENAI_VERIFY_SSL is explicitly disabled (0/false/off/no).

    For corporate TLS-intercepting proxies. Prefer ``REQUESTS_CA_BUNDLE``
    pointing at your company's root CA when possible — disabling verification
    is a trust downgrade.
    """
    value = (env_get("OPENAI_VERIFY_SSL") or "").lower()
    return value in ("0", "false", "off", "no")


class OpenAILLM(LLMClient):
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("OpenAI provider requires OPENAI_API_KEY (or api_key=).")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self._client = None
        self._init_openai()

    @property
    def default_model(self) -> str:
        return self.model

    def _init_openai(self) -> None:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("OpenAI provider requires the 'openai' package (>=1.0).") from exc

        kwargs = {"api_key": self.api_key, "timeout": self.timeout}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if _ssl_verify_disabled():
            import httpx

            kwargs["http_client"] = httpx.Client(verify=False, timeout=self.timeout)
        self._client = openai.OpenAI(**kwargs)

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResult:
        chosen = model or self.model
        payload = [{"role": m.role, "content": m.content} for m in messages]
        try:
            resp = self._client.chat.completions.create(
                model=chosen,
                messages=payload,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = resp.choices[0].message.content or ""
            raw = resp.model_dump() if hasattr(resp, "model_dump") else None
        except Exception as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        usage = raw.get("usage") if isinstance(raw, dict) else None
        return LLMResult(text=text, model=chosen, raw=raw, usage=usage)
