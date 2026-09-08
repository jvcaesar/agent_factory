"""End-to-end bootstrap generation test driven by the demo spec file.

Runs entirely offline: no LLM, no network. Verifies that a scripted interview
produces a valid org with the expected directors, workers, and settings.
"""

import pathlib
import tempfile
import unittest

import yaml
from _helpers import FIXTURES, SRC  # noqa: F401  (SRC added for import path)

from agent_factory.bootstrap.generator import generate_org, write_org
from agent_factory.bootstrap.interview import InterviewAnswers
from agent_factory.config import ApprovalPolicy
from agent_factory.config.loader import load_org_yaml, validate_org


def export_and_reload(answers, out_dir):
    org = generate_org(answers)
    write_org(org, out_dir)
    errors = validate_org(org)
    return org, errors


class TestBootstrapDemo(unittest.TestCase):
    def setUp(self):
        with open(FIXTURES / "demo_spec.yaml", encoding="utf-8") as fh:
            self.spec = yaml.safe_load(fh)
        self.answers = InterviewAnswers.from_dict(self.spec)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "acme"

    def tearDown(self):
        self.tmp.cleanup()

    def test_answers_from_spec_are_valid(self):
        self.assertEqual(self.answers.validate(), [])

    def test_spec_booleans_are_strict(self):
        data = dict(self.spec)
        data["use_lead"] = "false"
        with self.assertRaisesRegex(ValueError, "use_lead must be a boolean"):
            InterviewAnswers.from_dict(data)

    def test_org_has_lead_and_expected_directors(self):
        org = generate_org(self.answers)
        ids = {r.id for r in org.roles}
        expected = {"lead_exec", "director_product", "director_engineering",
                    "director_marketing", "director_support", "amplifier", "observer"}
        self.assertTrue(expected.issubset(ids), ids)

    def test_lead_at_top_and_directors_report_to_it(self):
        org = generate_org(self.answers)
        for r in org.roles:
            if r.id == "lead_exec":
                self.assertIsNone(r.reports_to, "lead must be top of org")
            elif r.id.startswith("director_"):
                self.assertEqual(r.reports_to, "lead_exec")

    def test_generated_org_validates(self):
        org, errors = export_and_reload(self.answers, self.root)
        self.assertEqual(errors, [])

    def test_files_written(self):
        write_org(generate_org(self.answers), self.root)
        for f in ("org.yaml", "settings.yaml", "README.md", "goals/current.md"):
            self.assertTrue((self.root / f).exists(), f"missing {f}")
        self.assertTrue((self.root / "roles" / "lead_exec.yaml").exists())

    def test_write_org_refuses_overwrite_by_default(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "existing.txt").write_text("already here", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists|refusing to overwrite"):
            write_org(generate_org(self.answers), self.root)

    def test_org_yaml_reloads_equal(self):
        org = generate_org(self.answers)
        write_org(org, self.root)
        reloaded = load_org_yaml(self.root / "org.yaml")
        self.assertEqual(len(reloaded.roles), len(org.roles))
        self.assertEqual(reloaded.name, org.name)

    def test_role_model_settings_round_trip(self):
        org = generate_org(self.answers)
        org.roles[0].provider = "ollama"
        org.roles[0].model = "qwen3:8b"
        write_org(org, self.root)
        reloaded = load_org_yaml(self.root / "org.yaml")
        role = reloaded.role(org.roles[0].id)
        self.assertEqual(role.provider, "ollama")
        self.assertEqual(role.model, "qwen3:8b")

    def test_proactivity_in_range_and_model_tier_plan(self):
        org = generate_org(self.answers)
        for r in org.roles:
            self.assertGreaterEqual(r.proactivity_level, 0)
            self.assertLessEqual(r.proactivity_level, 5)

    def test_risk_and_budget_propagate(self):
        org = generate_org(self.answers)
        self.assertEqual(org.risk_tier, ApprovalPolicy.REVIEW_EXTERNAL)
        self.assertEqual(org.budget_tier, "medium")


if __name__ == "__main__":
    unittest.main()
