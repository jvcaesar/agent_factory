"""Unit tests for the config schema and loader validation rules."""

import pathlib
import tempfile
import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.bootstrap.generator import generate_org
from agent_factory.bootstrap.interview import InterviewAnswers
from agent_factory.config import ApprovalPolicy, ModelTier, Role, ToolAccess, ToolGrant
from agent_factory.config.loader import validate_org


def answers(**over):
    base = dict(
        org_name="TestCo",
        founder="Tester",
        north_star="Do great things",
        quarterly_goals=["Target A"],
        human_team_size=1,
        domains=["product"],
        tools={"notion", "files", "docs"},
        risk_tier=ApprovalPolicy.REVIEW_EXTERNAL,
        budget_tier="medium",
        add_amplifier=False,
        add_observer=False,
        use_lead=True,
    )
    base.update(over)
    return InterviewAnswers(**base)


class TestValidateOrg(unittest.TestCase):
    def test_unknown_reference_detected(self):
        org = generate_org(answers())
        # Point a role at a nonexistent id.
        org.roles[0].reports_to = "ghost"
        errors = validate_org(org)
        self.assertTrue(any("ghost" in e for e in errors), errors)

    def test_cycle_detected(self):
        org = generate_org(answers(domains=["product"]))
        lead = org.role("lead_exec")
        prod = org.role("director_product")
        # Create a two-node cycle: lead <-> director.
        lead.reports_to = "director_product"
        prod.reports_to = "lead_exec"
        errors = validate_org(org)
        self.assertTrue(any("cycle" in e.lower() for e in errors), errors)

    def test_duplicate_ids_detected(self):
        org = generate_org(answers())
        org.roles.append(org.role("lead_exec"))
        errors = validate_org(org)
        self.assertTrue(any("duplicate" in e for e in errors), errors)

    def test_proactivity_out_of_range(self):
        org = generate_org(answers())
        org.roles[0].proactivity_level = 9
        errors = validate_org(org)
        self.assertTrue(any("proactivity_level" in e for e in errors), errors)

    def test_valid_org_passes(self):
        org = generate_org(answers())
        self.assertEqual(validate_org(org), [])

    def test_schema_rejects_bad_id(self):
        with self.assertRaises(ValueError):
            Role(
                id="Bad ID",
                display_name="x",
                title="x",
                charter="charter",
                sop="sop.md",
                proactivity_level=2,
            )

    def test_small_budget_downgrades_big_director(self):
        # With a small budget, an AI-ops director (BIG) must drop to SMART.
        org = generate_org(answers(domains=["ai_ops"], budget_tier="small"))
        ai = org.role("director_ai_ops")
        self.assertEqual(ai.model_tier, ModelTier.SMART)

    def test_worker_model_tier_is_fast(self):
        org = generate_org(answers(domains=["product"], budget_tier="medium"))
        product = org.role("director_product")
        # Research and write workers are high-volume -> cheap tier.
        for wid in ("worker_research_1", "worker_write_1"):
            self.assertIn(wid, product.subagents)
            self.assertEqual(org.role(wid).model_tier, ModelTier.FAST)


if __name__ == "__main__":
    unittest.main()
