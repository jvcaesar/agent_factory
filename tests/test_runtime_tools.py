"""Tests for the runtime tool framework: grants, approval flags, stubs."""

import os
import pathlib
import tempfile
import unittest
from unittest import mock

from _helpers import SRC  # noqa: F401

from agent_factory.config import ApprovalPolicy, Org, Role, ToolAccess, ToolGrant
from agent_factory.runtime.tools import _web_fetch, lookup, tools_for_role


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

    def test_org_policy_enforces_write_approval(self):
        r = role_with([ToolGrant(tool="files", access=ToolAccess.WRITE)])
        org = Org(name="Acme", founder="Ada", north_star="Ship things", roles=[r])
        org.risk_tier = ApprovalPolicy.REVIEW_EXTERNAL
        write = lookup(tools_for_role(r, pathlib.Path.cwd(), org=org), "files_write")
        self.assertTrue(write.requires_approval)

    def test_approval_first_enforces_read_approval(self):
        r = role_with([
            ToolGrant(tool="web", access=ToolAccess.READ),
        ])
        r.approval_policy = ApprovalPolicy.APPROVAL_FIRST
        web = lookup(tools_for_role(r, org=Org(name="Acme", founder="Ada", north_star="Ship things", roles=[r])), "web_fetch")
        self.assertTrue(web.requires_approval)

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

    def test_file_read_requires_workspace_root(self):
        r = role_with([ToolGrant(tool="files", access=ToolAccess.READ)])
        result = lookup(tools_for_role(r), "files_read").execute({"path": "note.txt"})
        self.assertIn("workspace root", result)

    def test_file_paths_are_confined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            outside = root.parent / "outside-agent-factory-test.txt"
            outside.write_text("secret", encoding="utf-8")
            try:
                r = role_with([ToolGrant(tool="files", access=ToolAccess.READ)])
                tool = lookup(tools_for_role(r, root), "files_read")
                self.assertIn("outside the agent workspace", tool.execute({"path": "../outside-agent-factory-test.txt"}))
                self.assertIn("must be relative", tool.execute({"path": str(outside)}))
            finally:
                outside.unlink(missing_ok=True)

    def test_file_write_stays_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            r = role_with([ToolGrant(tool="files", access=ToolAccess.WRITE)])
            tool = lookup(tools_for_role(r, root), "files_write")
            result = tool.execute({"path": "outputs/result.txt", "content": "ok"})
            self.assertIn("WROTE", result)
            self.assertEqual((root / "outputs" / "result.txt").read_text(encoding="utf-8"), "ok")

    @mock.patch.dict(os.environ, {"AGENT_FACTORY_WEB_ALLOWED_HOSTS": "example.com"}, clear=False)
    @mock.patch("agent_factory.runtime.tools.socket.getaddrinfo")
    @mock.patch("requests.Session")
    def test_web_fetch_allows_public_response(self, session_class, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 443))]
        response = mock.Mock(
            is_redirect=False,
            is_permanent_redirect=False,
            headers={},
            encoding="utf-8",
            iter_content=lambda chunk_size: [b"hello"],
        )
        session_class.return_value.get.return_value = response
        self.assertEqual(_web_fetch({"url": "https://example.com"}), "hello")
        session_class.return_value.get.assert_called_once_with(
            "https://example.com", timeout=(10, 30), allow_redirects=False, stream=True
        )

    @mock.patch.dict(os.environ, {"AGENT_FACTORY_WEB_ALLOWED_HOSTS": "example.com"}, clear=False)
    def test_web_fetch_rejects_unlisted_host(self):
        self.assertIn("allowlist", _web_fetch({"url": "https://example.net"}))

    def test_web_fetch_rejects_unsafe_urls(self):
        self.assertIn("only permits http and https", _web_fetch({"url": "file:///etc/passwd"}))
        self.assertIn("public address", _web_fetch({"url": "http://127.0.0.1"}))
        self.assertIn("public address", _web_fetch({"url": "http://169.254.169.254"}))
        self.assertIn("cannot include credentials", _web_fetch({"url": "https://user:pass@example.com"}))

    @mock.patch.dict(os.environ, {"AGENT_FACTORY_WEB_ALLOWED_HOSTS": "example.com"}, clear=False)
    @mock.patch("agent_factory.runtime.tools.socket.getaddrinfo")
    @mock.patch("requests.Session")
    def test_web_fetch_rejects_redirect_to_private_address(self, session_class, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 443))]
        response = mock.Mock(
            is_redirect=True,
            is_permanent_redirect=False,
            headers={"Location": "http://127.0.0.1/admin"},
        )
        session_class.return_value.get.return_value = response
        self.assertIn("public address", _web_fetch({"url": "https://example.com"}))
        response.close.assert_called_once()

    @mock.patch.dict(os.environ, {"AGENT_FACTORY_WEB_ALLOWED_HOSTS": "example.com"}, clear=False)
    @mock.patch("agent_factory.runtime.tools.socket.getaddrinfo")
    @mock.patch("requests.Session")
    def test_web_fetch_bounds_response_size(self, session_class, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 443))]
        response = mock.Mock(
            is_redirect=False,
            is_permanent_redirect=False,
            headers={},
            encoding="utf-8",
            iter_content=lambda chunk_size: [b"x" * (1024 * 1024 + 1)],
        )
        session_class.return_value.get.return_value = response
        result = _web_fetch({"url": "https://example.com"})
        self.assertTrue(result.endswith("...\n[truncated]"))
        self.assertEqual(len(result.split("...\n[truncated]")[0]), 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
