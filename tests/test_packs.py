"""Tests for M5 — role packs."""

import contextlib
import io
import pathlib
import tempfile
import unittest

import yaml

from _helpers import SRC  # noqa: F401

from agent_factory.bootstrap.archetypes import ADDONS, ALL_WORKERS, DIRECTORS
from agent_factory.bootstrap.generator import generate_org
from agent_factory.bootstrap.interview import InterviewAnswers
from agent_factory.cli import main
from agent_factory.config.loader import load_org_yaml, validate_org
from agent_factory.packs import (
    PACKS,
    build_answers,
    get_pack,
    list_packs,
    overridden_archetypes,
)

EXAMPLES = pathlib.Path(SRC).parent / "examples" / "packs"


class TestPackRegistry(unittest.TestCase):
    def test_expected_packs_present(self):
        self.assertTrue({"business_ops", "engineering", "research"} <= set(PACKS))

    def test_list_packs_sorted_by_id(self):
        ids = [p.id for p in list_packs()]
        self.assertEqual(ids, sorted(ids))

    def test_get_unknown_pack_raises(self):
        with self.assertRaises(KeyError):
            get_pack("nope")

    def test_overrides_reference_known_archetypes(self):
        known = set(DIRECTORS) | set(ALL_WORKERS) | set(ADDONS)
        for arch in DIRECTORS.values():
            known.add(arch.id)
        for arch in ALL_WORKERS.values():
            known.add(arch.id)
        for arch in ADDONS.values():
            known.add(arch.id)
        for pack in list_packs():
            for archetype_id in pack.archetype_overrides:
                self.assertIn(archetype_id, known,
                              f"{pack.id} overrides unknown archetype {archetype_id}")

    def test_override_changes_charter(self):
        pack = get_pack("engineering")
        directors, workers, _ = overridden_archetypes(pack)
        self.assertNotEqual(
            directors["engineering"].charter,
            DIRECTORS["engineering"].charter,
        )
        self.assertIn("self-review", workers["worker_code"].charter)


class TestBuildAnswers(unittest.TestCase):
    def test_pack_spec_is_valid(self):
        for pack in list_packs():
            answers = build_answers(pack)
            self.assertEqual(answers.validate(), [], pack.id)

    def test_cli_overrides_applied(self):
        pack = get_pack("business_ops")
        answers = build_answers(pack, org_name="StarOps", founder="Ada",
                                north_star="Be the ops engine")
        self.assertEqual(answers.org_name, "StarOps")
        self.assertEqual(answers.founder, "Ada")
        self.assertEqual(answers.north_star, "Be the ops engine")

    def test_missing_fields_have_defaults(self):
        pack = get_pack("research")
        answers = build_answers(pack)
        self.assertTrue(answers.org_name)
        self.assertTrue(answers.north_star)
        self.assertTrue(answers.founder)
class TestPackGeneration(unittest.TestCase):
    def test_engineering_pack_generates_valid_org_with_overrides(self):
        pack = get_pack("engineering")
        answers = build_answers(pack)
        directors, workers, addons = overridden_archetypes(pack)
        org = generate_org(answers, directors=directors, workers=workers, addons=addons)
        self.assertEqual(validate_org(org), [])
        ids = {r.id for r in org.roles}
        self.assertIn("director_engineering", ids)
        self.assertIn("worker_code_1", ids)
        self.assertIn("amplifier", ids)
        self.assertIn("observer", ids)
        self.assertIn("delivery and architecture", org.role("director_engineering").charter)

    def test_pack_charters_differ_from_defaults(self):
        pack = get_pack("research")
        answers = build_answers(pack)
        plain = generate_org(answers)
        directors, workers, addons = overridden_archetypes(pack)
        packed = generate_org(answers, directors=directors, workers=workers, addons=addons)
        self.assertNotEqual(
            plain.role("director_research").charter,
            packed.role("director_research").charter,
        )


class TestExampleSpecs(unittest.TestCase):
    def test_example_specs_generate_valid_orgs(self):
        self.assertTrue(EXAMPLES.exists(), f"missing {EXAMPLES}")
        for path in EXAMPLES.glob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            answers = InterviewAnswers.from_dict(data)
            self.assertEqual(answers.validate(), [], path.name)
            org = generate_org(answers)
            self.assertEqual(validate_org(org), [], path.name)


class TestCliPacks(unittest.TestCase):
    def _run(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_packs_lists(self):
        code, out = self._run("packs")
        self.assertEqual(code, 0, out)
        self.assertIn("business_ops", out)
        self.assertIn("engineering", out)
        self.assertIn("research", out)

    def test_packs_show_spec(self):
        code, out = self._run("packs", "--show", "engineering")
        self.assertEqual(code, 0, out)
        self.assertIn("north_star", out)

    def test_bootstrap_pack_writes_org(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = pathlib.Path(tmp) / "eng"
            code, out = self._run("bootstrap", "--pack", "engineering", "--out", str(out_dir))
            self.assertEqual(code, 0, out)
            self.assertIn("pack: engineering", out)
            org = load_org_yaml(out_dir / "org.yaml")
            self.assertEqual(validate_org(org), [])
            self.assertIn("worker_code_1", {r.id for r in org.roles})

    def test_bootstrap_pack_with_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = pathlib.Path(tmp) / "ops"
            code, out = self._run(
                "bootstrap", "--pack", "business_ops",
                "--name", "StarOps", "--north-star", "Be the ops engine",
                "--out", str(out_dir),
            )
            self.assertEqual(code, 0, out)
            org = load_org_yaml(out_dir / "org.yaml")
            self.assertEqual(org.name, "StarOps")
            self.assertEqual(org.north_star, "Be the ops engine")

    def test_bootstrap_pack_conflicts_with_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = self._run(
                "bootstrap", "--pack", "engineering",
                "--spec", str(EXAMPLES / "engineering.yaml"),
                "--out", str(pathlib.Path(tmp) / "x"),
            )
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()