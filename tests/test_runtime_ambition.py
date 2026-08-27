"""Tests for M2 — the ambition loop and the context store (all offline)."""

import json
import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.config import Org, Role
from agent_factory.llm.fake import FakeLLM
from agent_factory.runtime.ambition import parse_proposals, propose_actions, run_ambition_loop
from agent_factory.runtime.state import Store

# A proactive lead with a worker beneath it; the worker has a read-only grant
# (so the execute step can actually run without stubs/approval).
LEAD = Role(
    id="lead_exec",
    display_name="Org Lead",
    title="Org Lead",
    charter="Route and initiate work.",
    sop="",
    proactivity_level=5,
    tool_grants=[],
    subagents=["worker_research_1"],
)

WORKER = Role(
    id="worker_research_1",
    display_name="Research Worker",
    title="Research Worker",
    charter="Synthesize info.",
    sop="",
    proactivity_level=1,
    tool_grants=[],
)

PASSIVE = Role(
    id="passive",
    display_name="Reactive",
    title="Reactive",
    charter="Only does assigned work.",
    sop="",
    proactivity_level=2,
    tool_grants=[],
)


def make_org(role=LEAD, extra=None):
    roles = [role, WORKER] if role is LEAD else [role, WORKER]
    if extra:
        roles.extend(extra)
    return Org(
        name="Acme",
        founder="Ada",
        north_star="Ship great things",
        quarterly_goals=["Launch v1 to 100 customers"],
        roles=roles,
    )


PROPOSAL_JSON = {
    "type": "proposals",
    "proposals": [
        {"title": "Draft launch brief", "action": "Write the launch brief for v1.", "rationale": "Advances launch.", "risk": "low", "priority": 1},
        {"title": "Research competitors", "action": "Summarize competitor positioning.", "rationale": "Informs positioning.", "risk": "medium", "priority": 2},
    ],
}


class TestParseProposals(unittest.TestCase):
    def test_parses_list_sorted_by_priority(self):
        ps = parse_proposals(json.dumps(PROPOSAL_JSON))
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].title, "Draft launch brief")
        self.assertEqual(ps[0].risk, "low")
        self.assertEqual(ps[0].priority, 1)

    def test_plain_text_returns_empty(self):
        self.assertEqual(parse_proposals("just some text"), [])

    def test_bad_risk_defaults_to_medium(self):
        ps = parse_proposals(json.dumps({
            "type": "proposals",
            "proposals": [{"title": "X", "action": "Do X", "risk": "catastrophic", "priority": 3}],
        }))
        self.assertEqual(ps[0].risk, "medium")

    def test_empty_proposals_list(self):
        self.assertEqual(parse_proposals(json.dumps({"type": "proposals", "proposals": []})), [])

    def test_max_candidates_is_enforced(self):
        self.assertEqual(len(parse_proposals(json.dumps(PROPOSAL_JSON), max_candidates=1)), 1)

    def test_invalid_priority_defaults(self):
        ps = parse_proposals(json.dumps({
            "type": "proposals",
            "proposals": [{"title": "X", "action": "Do X", "priority": "urgent"}],
        }))
        self.assertEqual(ps[0].priority, 5)


class TestProposeActions(unittest.TestCase):
    def test_proactive_role_proposes(self):
        llm = FakeLLM(responses=[json.dumps(PROPOSAL_JSON)])
        store = Store(":memory:")
        org = make_org()
        proposals = propose_actions(org, LEAD, llm, store.context_blob())
        self.assertEqual(len(proposals), 2)
        store.close()

    def test_passive_role_proposes_nothing(self):
        llm = FakeLLM(responses=[json.dumps(PROPOSAL_JSON)])
        store = Store(":memory:")
        org = make_org(PASSIVE)
        proposals = propose_actions(org, PASSIVE, llm, store.context_blob())
        self.assertEqual(proposals, [])
        store.close()
class TestRunAmbitionLoop(unittest.TestCase):
    def _fake_for_loop(self):
        # LLM call 1: propose. Calls 2..: the worker's run_agent loop (final).
        return FakeLLM(
            responses=[
                json.dumps(PROPOSAL_JSON),
                '{"type":"final","output":"launch brief written"}',
                '{"type":"final","output":"competitors summarized"}',
            ]
        )

    def test_executes_accepted_proposals_and_learns(self):
        store = Store(":memory:")
        org = make_org()
        llm = self._fake_for_loop()
        proposals, executed = run_ambition_loop(org, LEAD, llm, store, max_actions=2, max_risk="medium")
        self.assertEqual(len(executed), 2)
        # Each executed proposal recorded back into context (the 'learn' step).
        keys = {r["key"] for r in store.list_context()}
        self.assertTrue(any("ambition/" in k for k in keys))
        # Jobs recorded done.
        self.assertTrue(all(store.get(j)["status"] == "done" for _, _, j in executed))
        store.close()

    def test_high_risk_proposal_skipped(self):
        store = Store(":memory:")
        org = make_org()
        high_risk = {
            "type": "proposals",
            "proposals": [
                {"title": "Auto-send email", "action": "Send emails to customers.", "rationale": "Growth.", "risk": "high", "priority": 1}
            ],
        }
        llm = FakeLLM(responses=[json.dumps(high_risk)])
        proposals, executed = run_ambition_loop(org, LEAD, llm, store, max_actions=2, max_risk="low")
        self.assertEqual(len(proposals), 1)
        self.assertEqual(len(executed), 0)
        # The skip is recorded in context.
        self.assertTrue(any("skipped" in (r["key"] or "") for r in store.list_context()))
        store.close()

    def test_budget_limits_executed_actions(self):
        store = Store(":memory:")
        org = make_org()
        llm = FakeLLM(
            responses=[
                json.dumps(PROPOSAL_JSON),
                '{"type":"final","output":"only first done"}',
            ]
        )
        proposals, executed = run_ambition_loop(org, LEAD, llm, store, max_actions=1, max_risk="medium")
        self.assertEqual(len(executed), 1)
        store.close()

    def test_dispatches_proposals_round_robin(self):
        worker_two = Role(
            id="worker_research_2", display_name="Research Worker 2",
            title="Research Worker", charter="Synthesize info.", sop="",
            proactivity_level=1, tool_grants=[],
        )
        lead = LEAD.model_copy(update={"subagents": [WORKER.id, worker_two.id]})
        org = make_org(lead, extra=[worker_two])
        store = Store(":memory:")
        llm = FakeLLM(responses=[
            json.dumps(PROPOSAL_JSON),
            '{"type":"final","output":"first"}',
            '{"type":"final","output":"second"}',
        ])
        _, executed = run_ambition_loop(org, lead, llm, store, max_actions=2)
        self.assertEqual([job[1].output for job in executed], ["first", "second"])
        self.assertEqual([store.get(job[2])["role"] for job in executed], [WORKER.id, worker_two.id])
        store.close()


class TestContextStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_upsert_and_get(self):
        self.store.upsert_context("diary/2026-08-21", "Talked with a client about reskilling.", "diary")
        row = self.store.get_context("diary/2026-08-21")
        self.assertIsNotNone(row)
        self.assertIn("reskilling", row["content"])

    def test_upsert_overwrites_same_key(self):
        self.store.upsert_context("k", "one", "diary")
        self.store.upsert_context("k", "two", "diary")
        rows = self.store.list_context()
        self.assertEqual(len(rows), 1)
        self.assertIn("two", rows[0]["content"])

    def test_search(self):
        self.store.upsert_context("a", "client wants new workflows", "diary")
        self.store.upsert_context("b", "unrelated note", "diary")
        rows = self.store.search_context("workflows")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "a")

    def test_context_blob_includes_entries(self):
        self.store.upsert_context("k", "some content", "diary")
        blob = self.store.context_blob()
        self.assertIn("some content", blob)


if __name__ == "__main__":
    unittest.main()

