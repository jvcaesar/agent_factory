"""Ollama provider adapter for local models (Gemma, Qwen, etc.).

Ollama exposes an OpenAI-compatible HTTP endpoint at ``/v1/chat/completions``,
so this adapter uses ``requests`` and speaks that schema directly — no extra
SDK and no cloud dependency. Point ``base_url`` at the local Ollama server,
``http://localhost:11434/v1`` by default.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import ChatMessage, LLMClient, LLMError, LLMResult


class OllamaLLM(LLMClient):
    name = "ollama"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: str = "gemma4",
        timeout: int = 180,
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "gemma4")
        self.timeout = timeout

    @property
    def default_model(self) -> str:
        return self.model

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResult:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise LLMError("Ollama provider requires the 'requests' package.") from exc

        chosen = model or self.model
        payload = {
            "model": chosen,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            raise LLMError(f"Ollama request failed ({self.base_url}): {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected Ollama response shape: {data!r}") from exc

        return LLMResult(text=text, model=chosen, raw=data)
