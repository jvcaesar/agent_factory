"""Opt-in smoke tests for the *real* LLM provider adapters (RC-04).

Every test here skips unless ``AGENT_FACTORY_LIVE_TESTS=1`` is set, so the
default suite (`python -m unittest discover -s tests`) stays 100% offline —
no API keys, no network, no local Ollama server.

Run them explicitly with prerequisites in place:

    # OpenAI (needs OPENAI_API_KEY; honors OPENAI_BASE_URL / OPENAI_MODEL)
    AGENT_FACTORY_LIVE_TESTS=1 python -m unittest discover -s tests/integration -v

    # Ollama (needs a server on OLLAMA_BASE_URL, default http://localhost:11434/v1)
    AGENT_FACTORY_LIVE_TESTS=1 OLLAMA_MODEL=<pulled-model> python -m unittest discover -s tests/integration -v

Each provider test records a clear skip reason when its prerequisite is
missing (flag unset / SDK missing / key absent / server unreachable /
model not pulled), per the 1.0 release checklist (RC-04).
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest

# Self-contained path setup (not ``_helpers``): unittest discovery can start
# from ``tests`` *or* ``tests/integration``, and only the start dir itself is
# put on sys.path — so a sibling import would break under the latter.
_SRC = pathlib.Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent_factory.llm.base import ChatMessage, LLMError, LLMResult  # noqa: E402

LIVE = os.environ.get("AGENT_FACTORY_LIVE_TESTS") == "1"

_TRIVIAL_PROMPT = [ChatMessage(role="user", content="Reply with exactly: OK")]


def _skip(reason: str) -> None:
    raise unittest.SkipTest(reason)


def _openai_sdk_available() -> bool:
    try:
        import openai  # noqa: F401

        return True
    except ImportError:
        return False


@unittest.skipUnless(LIVE, "set AGENT_FACTORY_LIVE_TESTS=1 to enable live provider tests")
class TestOpenAILive(unittest.TestCase):
    """Smoke-test the OpenAI adapter against the real API."""

    def _client(self):
        from agent_factory.llm.openai_client import OpenAILLM

        if not os.environ.get("OPENAI_API_KEY"):
            _skip("OPENAI_API_KEY not set — skipped")
        if not _openai_sdk_available():
            _skip("'openai' package not installed (pip install 'agent_factory[openai]') — skipped")
        return OpenAILLM(timeout=30)

    def test_complete_returns_nonempty_text(self):
        client = self._client()
        result = client.complete(_TRIVIAL_PROMPT, temperature=0.1, max_tokens=20)
        self.assertIsInstance(result, LLMResult)
        self.assertTrue((result.text or "").strip(), "expected non-empty completion text")
        self.assertEqual(result.model, client.default_model)
        self.assertIsInstance(result.raw, dict)

    def test_error_wrapped_as_llmerror(self):
        client = self._client()
        # A deliberately invalid model name must surface as LLMError, not a
        # raw SDK exception leaking out of the adapter.
        with self.assertRaises(LLMError):
            client.complete(_TRIVIAL_PROMPT, model="__no_such_model_for_smoke_test__", max_tokens=5)


@unittest.skipUnless(LIVE, "set AGENT_FACTORY_LIVE_TESTS=1 to enable live provider tests")
class TestOllamaLive(unittest.TestCase):
    """Smoke-test the Ollama adapter against a local server (if reachable)."""

    def _client(self):
        import requests

        from agent_factory.llm.ollama_client import OllamaLLM

        client = OllamaLLM(timeout=120)  # local 7–12B models: allow load+gen time
        try:
            resp = requests.get(f"{client.base_url}/models", timeout=3)
            resp.raise_for_status()
            models = resp.json()
        except Exception as exc:
            _skip(f"Ollama server unreachable at {client.base_url} ({exc.__class__.__name__}) — skipped")
        ids = [m.get("id", "") for m in models.get("data", [])]
        # Ollama resolves model ids strictly: a bare name (``gemma4``) is NOT
        # accepted — the tagged id (``gemma4:12b``) is required. Live testing
        # found that ``POST /v1/chat/completions`` 404s ("model not found")
        # for a bare name, so resolve to the concrete id here the same way a
        # real user would via ``OLLAMA_MODEL``.
        resolved = client.model if client.model in ids else next(
            (i for i in ids if i.split(":", 1)[0] == client.model), None
        )
        if not resolved:
            _skip(f"model '{client.model}' not pulled on {client.base_url} (available: {ids or 'none'}) — skipped")
        self.resolved_model = resolved
        return client

    def test_complete_returns_nonempty_text(self):
        client = self._client()
        result = client.complete(
            _TRIVIAL_PROMPT, model=self.resolved_model, temperature=0.1, max_tokens=40
        )
        self.assertIsInstance(result, LLMResult)
        # Reasoning models may reply from the ``reasoning`` fallback, but the
        # adapter must never hand back a blank response.
        self.assertTrue((result.text or "").strip(), "expected non-empty completion text")
        self.assertEqual(result.model, self.resolved_model)
        self.assertIsInstance(result.raw, dict)


if __name__ == "__main__":
    unittest.main()
