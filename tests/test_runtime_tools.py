"""Tests for the runtime tool framework: grants, approval flags, stubs."""

import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.config import Role, ToolAccess, ToolGrant
from agent_factory.runtime.tools import lookup, tools_for_role


def role_with(grants):
    return Role(
        id="tester",
        display_name="Tester",
        title="Tester",
        charter="test role",
        sop="",
        proactivity_level=2,
        tool_grants=grants,
    )


class TestToolsForRole(unittest.TestCase):
    def test_read_grant_exposes_read_only(self):
        r = role_with([ToolGrant(tool="files", access=ToolAccess.READ)])
        names = {t.name for t in tools_for_role(r)}
        self.assertIn("files_read", names)
        self.assertNotIn("files_write", names)

    def test_write_grant_exposes_write_and_marks_approval_if_gated(self):
        r = role_with([ToolGrant(tool="files", access=ToolAccess.WRITE, requires_approval=True)])
        tools = tools_for_role(r)
        write = lookup(tools, "files_write")
        self.assertIsNotNone(write)
        self.assertTrue(write.requires_approval)

    def test_write_grant_without_approval_still_warns_by_default(self):
        # files_write is approval-required at the tool level regardless.
        r = role_with([ToolGrant(tool="files", access=ToolAccess.WRITE, requires_approval=False)])
        write = lookup(tools_for_role(r), "files_write")
        self.assertTrue(write.requires_approval)

    def test_unknown_tool_becomes_stub(self):
        r = role_with([ToolGrant(tool="notion", access=ToolAccess.READ)])
        tools = tools_for_role(r)
        self.assertEqual(len(tools), 1)
        self.assertIn("stub", tools[0].name)

    def test_stub_executes_without_error(self):
        r = role_with([ToolGrant(tool="github", access=ToolAccess.READ)])
        tool = tools_for_role(r)[0]
        out = tool.execute({})
        self.assertIn("STUB", out)

    def test_duplicate_grants_dedupe(self):
        r = role_with([ToolGrant(tool="files", access=ToolAccess.READ), ToolGrant(tool="files", access=ToolAccess.READ)])
        self.assertEqual(len(tools_for_role(r)), 1)


if __name__ == "__main__":
    unittest.main()
