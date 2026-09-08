"""Tests for M4 — insights store, observer/watchdog, and mission-control stats."""

import json
import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.config import Org, Role
from agent_factory.llm.fake import FakeLLM
from agent_factory.runtime.insights import (
    build_daily_brief,
    observe,
    parse_observations,
)
from agent_factory.runtime.state import Store

OBSERVER = Role(
    id="observer",
    title="Observer",
    display_name="Observer",
    charter="Scan the workforce for friction and blockers.",
    sop="",
    proactivity_level=4,
)

OBSERVE_JSON = {
    "type": "observations",
    "observations": [
        {
            "level": "warning",
            "kind": "access_gap",
            "title": "Research worker lacks web tool",
            "detail": "worker_research_1 wants web_fetch but has no grant.",
            "suggestion": "Grant worker_research_1 web read.",
        },
        {
            "level": "critical",
            "kind": "blocker",
            "title": "Old job is stuck running",
            "detail": "job #3 has been running for a long time.",
            "suggestion": "Mark it failed and requeue.",
        },
    ],
}


def make_org(role=OBSERVER):
    return Org(
        name="Acme",
        founder="Ada",
        north_star="Ship great things",
        quarterly_goals=["Launch v1"],
        roles=[role],
    )


class TestParseObservations(unittest.TestCase):
    def test_parses_list(self):
        obs = parse_observations(json.dumps(OBSERVE_JSON))
        self.assertEqual(len(obs), 2)
        self.assertEqual(obs[0].level, "warning")
        self.assertEqual(obs[0].kind, "access_gap")
        self.assertEqual(obs[1].kind, "blocker")

    def test_plain_text_returns_empty(self):
        self.assertEqual(parse_observations("just some text"), [])

    def test_bad_level_and_kind_default(self):
        obs = parse_observations(json.dumps({
            "type": "observations",
            "observations": [{"level": "panic", "kind": "wizard", "title": "X", "detail": "d", "suggestion": "s"}],
        }))
        self.assertEqual(obs[0].level, "info")
        self.assertEqual(obs[0].kind, "friction")

    def test_max_count(self):
        obs = parse_observations(json.dumps(OBSERVE_JSON), max_count=1)
        self.assertEqual(len(obs), 1)


class TestObserve(unittest.TestCase):
    def test_observe_persists_insights(self):
        store = Store(":memory:")
        llm = FakeLLM(responses=[json.dumps(OBSERVE_JSON)])
        org = make_org()
        findings = observe(org, OBSERVER, store, llm)
        self.assertEqual(len(findings), 2)
        rows = store.list_insights(status="open")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["role"], "observer")
        store.close()

    def test_observe_keeps_similar_titles_with_different_details(self):
        store = Store(":memory:")
        payload = {
            "type": "observations",
            "observations": [
                {
                    "level": "warning",
                    "kind": "blocker",
                    "title": "Review is stuck",
                    "detail": "job #3 is blocked by approval.",
                    "suggestion": "Ask the human to approve.",
                },
                {
                    "level": "warning",
                    "kind": "blocker",
                    "title": "Review is stuck",
                    "detail": "job #4 is blocked by missing tool access.",
                    "suggestion": "Grant read access to the reviewer.",
                },
            ],
        }
        llm = FakeLLM(responses=[json.dumps(payload)])
        findings = observe(make_org(), OBSERVER, store, llm)
        self.assertEqual(len(findings), 2)
        self.assertEqual(len(store.list_insights(status="open")), 2)
        store.close()


class TestInsightStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_add_and_status_update(self):
        iid = self.store.add_insight("Acme", "observer", level="warning",
                                     kind="friction", title="Too many retries",
                                     detail="d", suggestion="s")
        self.store.update_insight_status(iid, "accepted")
        row = self.store.list_insights(status="accepted")
        self.assertEqual(len(row), 1)

    def test_stats_counts(self):
        self.store.enqueue("Acme", "w", "t")
        self.store.add_insight("Acme", "observer", title="t1")
        self.store.add_insight("Acme", "observer", title="t2")
        stats = self.store.stats()
        self.assertEqual(stats["jobs"], 1)
        self.assertEqual(stats["open_insights"], 2)

    def test_invalid_status_raises(self):
        self.store.add_insight("Acme", "observer", title="t1")
        with self.assertRaises(ValueError):
            self.store.update_insight_status(1, "archived")


class TestDailyBrief(unittest.TestCase):
    def test_brief_returns_llm_text(self):
        store = Store(":memory:")
        store.add_insight("Acme", "observer", level="warning", kind="blocker",
                          title="Stuck job", suggestion="Requeue it")
        llm = FakeLLM(responses=["WHAT: requeue job 3\nWHO: lead\nFIRST STEP: mark failed"])
        org = make_org()
        brief = build_daily_brief(org, OBSERVER, store, llm)
        self.assertIn("requeue job 3", brief)
        store.close()


if __name__ == "__main__":
    unittest.main()
