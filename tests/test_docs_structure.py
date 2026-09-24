"""Tests for documentation structure and phase-handoff conventions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import build_docs, check_docs


class TestPhaseRecords(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.implementation = self.root / "docs" / "releases" / "v2.0" / "implementation"
        self.implementation.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_record(self, folder: str, headings=check_docs.PHASE_HEADINGS):
        phase_dir = self.implementation / folder
        phase_dir.mkdir()
        body = "# Phase record\n\n" + "\n\n".join(headings) + "\n"
        (phase_dir / "README.md").write_text(body, encoding="utf-8")

    def test_accepts_valid_dated_phase_record(self):
        self.write_record("2026-09-24-phase-0-baseline")
        self.assertEqual(check_docs.check_phase_records(self.root), [])

    def test_rejects_malformed_phase_date(self):
        self.write_record("2026-13-40-phase-0-baseline")
        errors = check_docs.check_phase_records(self.root)
        self.assertTrue(any("invalid phase start date" in error for error in errors), errors)

    def test_rejects_duplicate_release_phase(self):
        self.write_record("2026-09-24-phase-1-backend")
        self.write_record("2026-09-25-phase-1-backend-retry")
        errors = check_docs.check_phase_records(self.root)
        self.assertTrue(any("duplicate Phase 1" in error for error in errors), errors)

    def test_requires_handoff_sections(self):
        headings = tuple(
            heading for heading in check_docs.PHASE_HEADINGS if heading != "## Handoff"
        )
        self.write_record("2026-09-24-phase-0-baseline", headings)
        errors = check_docs.check_phase_records(self.root)
        self.assertTrue(any("missing heading ## Handoff" in error for error in errors), errors)


class TestDocumentationRepository(unittest.TestCase):
    def test_repository_documentation_is_valid(self):
        self.assertEqual(check_docs.validate(), [])

    def test_generated_document_manifest_is_explicit(self):
        pairs = list(build_docs.targets())
        self.assertEqual(
            [(source.name, output.name) for source, output in pairs],
            [("PRODUCT.md", "PRODUCT.html"), ("USER_GUIDE.md", "USER_GUIDE.html")],
        )
        for source, output in pairs:
            self.assertTrue(source.is_file())
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
