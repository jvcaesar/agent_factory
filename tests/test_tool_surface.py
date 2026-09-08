"""Tests for the honest tool-surface reporting (RC-05).

Guards the contract between the runtime catalog, the ``agent_factory tools``
command, and the README tool-surface table: every stub id must be reported as
a stub, real tools must expose their actions, and the two categories must not
overlap.
"""

from __future__ import annotations

import contextlib
import io
import unittest
from argparse import Namespace

from _helpers import SRC  # noqa: F401  (ensures the src tree is importable)

from agent_factory.cli import cmd_tools
from agent_factory.runtime.tools import CATALOG, tool_surface

EXPECTED_REAL = {"files", "web", "memory", "channel"}
EXPECTED_STUBS = {
    "notion", "gmail", "calendar", "slack", "stripe", "supabase",
    "github", "sheets", "docs", "crm", "cms", "payments", "analytics",
}


class TestToolSurface(unittest.TestCase):
    def test_real_tools_reported_with_actions(self):
        surface = tool_surface()
        real = {tid for tid, info in surface.items() if info["real"]}
        self.assertEqual(real, EXPECTED_REAL)
        self.assertTrue(surface["memory"]["actions"])  # type: ignore[operator]
        self.assertIn("memory_read", surface["memory"]["actions"])  # type: ignore[operator]
        self.assertIn("channel_post", surface["channel"]["actions"])  # type: ignore[operator]

    def test_stubs_reported_and_disjoint_from_real(self):
        surface = tool_surface()
        stubs = {tid for tid, info in surface.items() if not info["real"]}
        self.assertEqual(stubs, EXPECTED_STUBS)
        self.assertEqual(len(surface), len(EXPECTED_REAL) + len(EXPECTED_STUBS))

    def test_every_catalog_entry_is_accounted_for(self):
        """No silent catalog drift: all CATALOG ids must appear in the surface."""
        surface = tool_surface()
        for tid in CATALOG:
            self.assertIn(tid, surface)

    def test_cmd_tools_output(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_tools(Namespace())
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("4 real, 13 stub", out)
        self.assertIn("REAL", out)
        self.assertIn("STUB", out)
        for tid in sorted(EXPECTED_REAL | EXPECTED_STUBS):
            self.assertIn(tid, out)


if __name__ == "__main__":
    unittest.main()
