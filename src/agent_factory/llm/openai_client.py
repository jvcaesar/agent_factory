"""OpenAI provider adapter.

Handles both API generations:
  * legacy module-level API (``openai.ChatCompletion.create``) — openai <1.0
  * modern client API (``openai.OpenAI().chat.completions.create``) — openai >=1.0

Detects which is available at construction time. The legacy API is the default
in this environment (openai 0.28.x). ``base_url`` may be set via
``OPENAI_BASE_URL`` for compatible endpoints (OpenRouter, proxies, etc.).
"""

from __future__ import annotations

import os
from typing import Optional

from .base import ChatMessage, LLMClient, LLMError, LLMResult


class OpenAILLM(LLMClient):
    name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("OpenAI provider requires OPENAI_API_KEY (or api_key=).")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self._modern = False
        self._client = None
        self._init_openai()

    @property
    def default_model(self) -> str:
        return self.model

    def _init_openai(self) -> None:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("OpenAI provider requires the 'openai' package.") from exc

        if hasattr(openai, "OpenAI"):
            # modern (>=1.0) client
            try:
                kwargs = {"api_key": self.api_key, "timeout": self.timeout}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = openai.OpenAI(**kwargs)
                self._modern = True
                return
            except Exception:
                self._modern = False  # fall through to legacy

        # legacy module-level API
        openai.api_key = self.api_key
        if self.base_url:
            openai.api_base = self.base_url
        self._modern = False

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResult:
        chosen = model or self.model
        payload = [{"role": m.role, "content": m.content} for m in messages]
        try:
            if self._modern:
                resp = self._client.chat.completions.create(
                    model=chosen,
                    messages=payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.choices[0].message.content or ""
                raw = resp.model_dump() if hasattr(resp, "model_dump") else None
            else:
                import openai

                resp = openai.ChatCompletion.create(
                    model=chosen,
                    messages=payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp["choices"][0]["message"]["content"] or ""
                raw = dict(resp)
        except Exception as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        usage = None
        if raw and isinstance(raw, dict):
            if "usage" in raw:
                usage = raw.get("usage")
            elif "usage" in str(raw):
                usage = None
        return LLMResult(text=text, model=chosen, raw=raw, usage=usage)
