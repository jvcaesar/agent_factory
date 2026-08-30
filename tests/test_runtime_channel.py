"""Tests for M6 — the shared human<->agent channel (Loop Alley) and its worker.

Everything runs offline with FakeLLM: a human posts into the shared channel,
the channel worker resolves an answering role, runs the normal agent loop, and
posts the reply back into the same channel. Also covers the CLI surface.
"""

import contextlib
import io
import json
import pathlib
import tempfile
import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.cli import main
from agent_factory.config import Org, Role
from agent_factory.llm.fake import FakeLLM
from agent_factory.runtime.channel import (
    default_lead,
    list_channel,
    post_to_channel,
    run_channel_worker,
)
from agent_factory.runtime.state import Store

LEAD = Role(
    id="lead_exec",
    display_name="Org Lead",
    title="Org Lead",
    charter="Route and answer channel questions.",
    sop="",
    proactivity_level=5,
    tool_grants=[],
)

WORKER = Role(
    id="worker_research_1",
    display_name="Research Worker",
    title="Research Worker",
    charter="Answer research questions.",
    sop="",
    proactivity_level=2,
    reports_to="lead_exec",
    tool_grants=[],
)


def make_org():
    return Org(
        name="Acme",
        founder="Ada",
        north_star="Ship great things",
        quarterly_goals=["Launch v1"],
        roles=[LEAD, WORKER],
    )


def final(text):
    return json.dumps({"type": "final", "output": text})


class TestMessageStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_post_and_list(self):
        mid = self.store.post_message("general", "human", "Ada", "Did Greg respond?")
        self.assertTrue(mid >= 1)
        rows = self.store.list_messages(channel="general")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["author_role"], "human")
        self.assertEqual(rows[0]["status"], "pending")

    def test_claim_next_is_atomic(self):
        m1 = self.store.post_message("general", "human", "Ada", "one")
        m2 = self.store.post_message("general", "human", "Bob", "two")
        self.assertEqual(self.store.claim_next_in_channel("general")["id"], m1)
        self.assertEqual(self.store.claim_next_in_channel("general")["id"], m2)
        self.assertIsNone(self.store.claim_next_in_channel("general"))

    def test_claim_message_only_pending(self):
        m1 = self.store.post_message("general", "human", "Ada", "x")
        self.assertTrue(self.store.claim_message(m1))
        self.assertFalse(self.store.claim_message(m1))

    def test_complete_and_stats_pending_count(self):
        m1 = self.store.post_message("general", "human", "Ada", "x")
        self.assertEqual(self.store.stats()["pending_messages"], 1)
        self.store.complete_message(m1)
        self.assertEqual(self.store.stats()["pending_messages"], 0)
        self.assertEqual(self.store.list_messages(channel="general")[0]["status"], "done")

    def test_channel_blob_flattens_thread(self):
        self.store.post_message("general", "human", "Ada", "hello workforce")
        blob = self.store.channel_blob("general")
        self.assertIn("hello workforce", blob)

    def test_other_channel_is_isolated(self):
        self.store.post_message("general", "human", "Ada", "general msg")
        self.store.post_message("incidents", "human", "Bob", "crisis")
        self.assertEqual(len(self.store.list_messages(channel="general")), 1)
        self.assertEqual(len(list_channel(self.store, "general")), 1)


class TestChannelWorker(unittest.TestCase):
    def test_answers_pending_message_and_posts_reply(self):
        store = Store(":memory:")
        org = make_org()
        mid = post_to_channel(store, "general", "Did the client respond?")
        llm = FakeLLM(responses=[final("Not yet — I will chase them.")])
        answered = run_channel_worker(org, store, llm, channel="general")

        self.assertEqual(len(answered), 1)
        message, outcome, job_id = answered[0]
        self.assertEqual(message["id"], mid)
        self.assertEqual(outcome.output, "Not yet — I will chase them.")

        # The reply is posted back into the channel by the answering role.
        rows = store.list_messages(channel="general")
        self.assertEqual(len(rows), 2)
        reply = rows[0]
        self.assertEqual(reply["author_role"], "lead_exec")
        self.assertEqual(reply["reply_to"], mid)

        # Original marked done and the reply job is on the ledger.
        original = next(m for m in rows if m["id"] == mid)
        self.assertEqual(original["status"], "done")
        self.assertEqual(store.get(job_id)["role"], "lead_exec")
        self.assertEqual(store.stats()["jobs"], 1)
        store.close()

    def test_requested_role_answers(self):
        store = Store(":memory:")
        org = make_org()
        post_to_channel(store, "general", "Pull the metrics.", requested_role="worker_research_1")
        llm = FakeLLM(responses=[final("here are the metrics")])
        answered = run_channel_worker(org, store, llm, channel="general")
        self.assertEqual(len(answered), 1)
        self.assertEqual(store.get(answered[0][2])["role"], "worker_research_1")
        store.close()

    def test_role_resolver_can_override(self):
        store = Store(":memory:")
        org = make_org()
        post_to_channel(store, "general", "Who owns this work?")
        llm = FakeLLM(responses=[final("the worker does")])
        answered = run_channel_worker(
            org, store, llm, channel="general",
            role_resolver=lambda _m: org.role("worker_research_1"),
        )
        self.assertEqual(store.get(answered[0][2])["role"], "worker_research_1")
        store.close()

    def test_unknown_requested_role_falls_back_to_lead(self):
        store = Store(":memory:")
        org = make_org()
        post_to_channel(store, "general", "Who is on call?", requested_role="ghost_role")
        llm = FakeLLM(responses=[final("the lead is on call")])
        answered = run_channel_worker(org, store, llm, channel="general")
        self.assertEqual(len(answered), 1)
        self.assertEqual(store.get(answered[0][2])["role"], "lead_exec")
        store.close()

    def test_no_pending_messages_returns_empty(self):
        store = Store(":memory:")
        answered = run_channel_worker(make_org(), store, FakeLLM(responses=["x"]), channel="incidents")
        self.assertEqual(answered, [])
        store.close()

    def test_max_messages_limits_batch(self):
        store = Store(":memory:")
        org = make_org()
        for i in range(3):
            post_to_channel(store, "general", f"question {i}")
        llm = FakeLLM(responses=[final(f"answer {i}") for i in range(2)])
        answered = run_channel_worker(org, store, llm, channel="general", max_messages=2)
        self.assertEqual(len(answered), 2)
        self.assertEqual(len(store.pending_messages(channel="general")), 1)
        store.close()

    def test_default_lead_is_top_of_org(self):
        self.assertEqual(default_lead(make_org()).id, "lead_exec")


class TestCliChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "acme"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def _bootstrap(self):
        code, out = self._run("bootstrap", "--pack", "engineering", "--out", str(self.root))
        self.assertEqual(code, 0, out)

    def test_channel_post(self):
        self._bootstrap()
        code, out = self._run(
            "channel", "post", "--org", str(self.root),
            "--channel", "general", "--text", "hello workforce",
        )
        self.assertEqual(code, 0, out)
        self.assertIn("posted message #1", out)

    def test_channel_post_then_worker_then_list(self):
        self._bootstrap()
        code, _ = self._run(
            "channel", "post", "--org", str(self.root),
            "--text", "What is the north star?", "--role", "lead_exec",
        )
        self.assertEqual(code, 0)
        code, out = self._run(
            "channel", "worker", "--org", str(self.root), "--provider", "fake"
        )
        self.assertEqual(code, 0, out)
        self.assertIn("answered 1 message(s)", out)
        code, out = self._run("channel", "list", "--org", str(self.root))
        self.assertEqual(code, 0, out)
        self.assertIn("north star", out)

    def test_channel_list_with_empty_store(self):
        self._bootstrap()
        code, out = self._run("channel", "list", "--org", str(self.root))
        self.assertEqual(code, 0, out)
        self.assertIn("no messages yet", out)


if __name__ == "__main__":
    unittest.main()