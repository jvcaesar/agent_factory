"""Offline unit tests for the Ollama adapter's model-tag resolution (RC-04 fix).

Live testing (2026-09-08) showed real Ollama servers reject *bare* model
names (``gemma4`` → ``404 Not Found``); only tagged ids (``gemma4:12b``) work.
These tests mock ``requests`` so the resolution logic is verified without a
server or network.
"""

from __future__ import annotations

import unittest
from unittest import mock

from _helpers import SRC  # noqa: F401  (ensures the src tree is importable)

from agent_factory.llm.base import ChatMessage, LLMError
from agent_factory.llm.ollama_client import OllamaLLM

_MSGS = [ChatMessage(role="user", content="hi")]

_FAKE_LISTING = {
    "data": [{"id": "llama3:latest"}, {"id": "gemma3:12b"}, {"id": "gemma4:12b"}]
}

_FAKE_COMPLETION = {"choices": [{"message": {"content": "OK"}}]}


def _client(**kwargs) -> OllamaLLM:
    defaults = {"base_url": "http://x:11434/v1", "model": "gemma4"}
    defaults.update(kwargs)
    return OllamaLLM(**defaults)


class TestModelTagResolution(unittest.TestCase):
    def test_bare_name_resolves_to_tagged_id(self):
        client = _client()
        with mock.patch("requests.get", return_value=mock.Mock(**{
            "raise_for_status.return_value": None,
            "json.return_value": _FAKE_LISTING,
        })) as mget, mock.patch(
            "requests.post",
            return_value=mock.Mock(**{
                "raise_for_status.return_value": None,
                "json.return_value": _FAKE_COMPLETION,
            }),
        ) as mpost:
            result = client.complete(_MSGS)
        mget.assert_called_once()  # listing attempted
        sent = mpost.call_args.kwargs["json"]["model"]
        self.assertEqual(sent, "gemma4:12b")
        self.assertEqual(result.model, "gemma4:12b")

    def test_tagged_name_passes_through_untouched(self):
        client = _client(model="llama3:latest")
        with mock.patch("requests.get") as mget, mock.patch(
            "requests.post",
            return_value=mock.Mock(**{
                "raise_for_status.return_value": None,
                "json.return_value": _FAKE_COMPLETION,
            }),
        ) as mpost:
            client.complete(_MSGS)
        mget.assert_not_called()  # no listing needed for tagged names
        self.assertEqual(mpost.call_args.kwargs["json"]["model"], "llama3:latest")

    def test_resolution_cached_across_calls(self):
        client = _client()
        listing = mock.Mock(**{
            "raise_for_status.return_value": None,
            "json.return_value": _FAKE_LISTING,
        })
        post = mock.Mock(**{
            "raise_for_status.return_value": None,
            "json.return_value": _FAKE_COMPLETION,
        })
        with mock.patch("requests.get", return_value=listing) as mget, mock.patch(
            "requests.post", return_value=post
        ):
            client.complete(_MSGS)
            client.complete(_MSGS)
        self.assertEqual(mget.call_count, 1)  # cached after first lookup
        self.assertEqual(client._resolved_tags, {"gemma4": "gemma4:12b"})

    def test_unresolvable_name_kept_as_is(self):
        client = _client(model="nonexistent")
        with mock.patch("requests.get", return_value=mock.Mock(**{
            "raise_for_status.return_value": None,
            "json.return_value": _FAKE_LISTING,
        })), mock.patch(
            "requests.post",
            return_value=mock.Mock(**{
                "raise_for_status.return_value": None,
                "json.return_value": _FAKE_COMPLETION,
            }),
        ) as mpost:
            client.complete(_MSGS)
        # No matching tag: configured name is sent rather than failing early.
        self.assertEqual(mpost.call_args.kwargs["json"]["model"], "nonexistent")

    def test_listing_failure_falls_back_to_configured_name(self):
        client = _client()
        with mock.patch("requests.get", side_effect=ConnectionError("no server")), mock.patch(
            "requests.post",
            return_value=mock.Mock(**{
                "raise_for_status.return_value": None,
                "json.return_value": _FAKE_COMPLETION,
            }),
        ) as mpost:
            result = client.complete(_MSGS)
        self.assertEqual(mpost.call_args.kwargs["json"]["model"], "gemma4")
        self.assertEqual(result.text, "OK")

    def test_request_failure_wrapped_as_llmerror(self):
        client = _client()
        with (
            mock.patch("requests.get", return_value=mock.Mock(**{
                "raise_for_status.return_value": None,
                "json.return_value": _FAKE_LISTING,
            })),
            mock.patch("requests.post", side_effect=Exception("boom")),
            self.assertRaises(LLMError),
        ):
            client.complete(_MSGS)

    def test_reasoning_fallback_preserved(self):
        """Blank content + non-empty ``reasoning`` still returns the trace."""
        client = _client(model="gemma4:12b")
        reasoning_resp = {
            "choices": [{"message": {"content": "", "reasoning": "chain of thought"}}]
        }
        with mock.patch(
            "requests.post",
            return_value=mock.Mock(**{
                "raise_for_status.return_value": None,
                "json.return_value": reasoning_resp,
            }),
        ):
            result = client.complete(_MSGS)
        self.assertEqual(result.text, "chain of thought")
        self.assertTrue(client.used_reasoning_fallback)


if __name__ == "__main__":
    unittest.main()
