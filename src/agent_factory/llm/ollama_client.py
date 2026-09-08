"""Ollama provider adapter for local models (Gemma, Qwen, etc.).

Ollama exposes an OpenAI-compatible HTTP endpoint at ``/v1/chat/completions``,
so this adapter uses ``requests`` and speaks that schema directly — no extra
SDK and no cloud dependency. Point ``base_url`` at the local Ollama server,
``http://localhost:11434/v1`` by default.

**Model tag resolution:** Ollama rejects *bare* model names — ``gemma4`` gets
``404 Not Found``; only the tagged id (``gemma4:12b``) is valid. To spare
users that gotcha, this adapter lazily resolves a bare name to its tagged id
via ``GET /v1/models`` on first use (cached per client instance). Tagged
names pass through untouched, and if the server can't be listed the
configured name is used as-is (so offline/mocked setups keep working).
"""

from __future__ import annotations

import contextlib
import os

from .base import ChatMessage, LLMClient, LLMError, LLMResult


class OllamaLLM(LLMClient):
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str = "gemma4",
        timeout: int = 180,
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "gemma4")
        self.timeout = timeout
        # bare-name -> tagged-id cache (populated lazily, one lookup max)
        self._resolved_tags: dict[str, str] = {}

    @property
    def default_model(self) -> str:
        return self.model

    def _resolve_model_tag(self, chosen: str, requests) -> str:
        """Map a bare model name to its tagged id (``gemma4`` → ``gemma4:12b``).

        Tagged names are returned untouched. Resolution hits ``GET /v1/models``
        at most once per bare name; on any listing failure the name is kept
        as-is rather than failing the request.
        """
        if ":" in chosen:
            return chosen
        if chosen in self._resolved_tags:
            return self._resolved_tags[chosen]
        tagged = chosen
        with contextlib.suppress(Exception):
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            resp.raise_for_status()
            ids = [m.get("id", "") for m in resp.json().get("data", [])]
            match = chosen if chosen in ids else next((i for i in ids if i.split(":", 1)[0] == chosen), None)
            if match:
                tagged = match
        self._resolved_tags[chosen] = tagged
        return tagged

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResult:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise LLMError("Ollama provider requires the 'requests' package.") from exc

        chosen = self._resolve_model_tag(model or self.model, requests)
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
            message = data["choices"][0]["message"]
            text = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected Ollama response shape: {data!r}") from exc

        # Reasoning models (e.g. deepseek-r1, gemma with thinking enabled) put
        # their chain-of-thought in a separate ``reasoning`` field and may leave
        # ``content`` empty when the token budget is exhausted mid-reasoning.
        # Fall back to the reasoning trace rather than returning a blank reply,
        # and surface a warning so callers know this happened.
        self.used_reasoning_fallback = False
        if not (text or "").strip():
            reasoning = ""
            with contextlib.suppress(KeyError, IndexError, TypeError):
                reasoning = (data["choices"][0]["message"].get("reasoning") or "").strip()
            if reasoning:
                self.used_reasoning_fallback = True
                text = reasoning

        return LLMResult(text=text, model=chosen, raw=data)
