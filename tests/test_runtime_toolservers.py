"""Tests for M6 — the wider tool surface: risk-aware permissions, the
store-backed memory/channel adapters, and MCP-style local tool servers.

All offline: nothing here reaches the network or an API key.
"""

import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.config import ApprovalPolicy, Org, Role, ToolAccess, ToolGrant
from agent_factory.runtime.state import Store
from agent_factory.runtime.tools import (
    CATALOG,
    RISK_ORDER,
    Tool,
    approval_needed,
    lookup,
    tools_for_role,
)
from agent_factory.runtime.toolservers import (
    REGISTERED_SERVERS,
    ServerTool,
    register_tool_server,
    server_tools,
)


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


def make_org(role):
    return Org(name="Acme", founder="Ada", north_star="Ship things", roles=[role])


class FakeToolServer:
    """A local MCP-style server with an easy read and a dangerous op."""

    def __init__(self):
        self.calls = []

    def tool_descriptors(self):
        return [
            ServerTool(name="ping", description="Ping the server", risk="low"),
            ServerTool(name="destroy", description="Destructive op", requires_approval=True, risk="high"),
        ]

    def execute_tool(self, name, inputs):
        self.calls.append((name, dict(inputs or {})))
        if name == "ping":
            return "pong"
        return f"executed:{name}"


class TestRiskApprovalPolicy(unittest.TestCase):
    def test_grant_gate_is_absolute(self):
        web = CATALOG["web"]["read"]
        self.assertTrue(
            approval_needed(grant_approval=True, access=ToolAccess.READ, tool=web)
        )

    def test_approval_first_gates_even_low_risk_reads(self):
        web = CATALOG["web"]["read"]
        self.assertEqual(web.risk, "low")
        org = make_org(role_with([]))
        role = role_with([])
        role.approval_policy = ApprovalPolicy.APPROVAL_FIRST
        self.assertTrue(
            approval_needed(grant_approval=False, access=ToolAccess.READ, tool=web, role=role, org=org)
        )

    def test_autonomous_medium_write_is_free_but_high_risk_is_gated(self):
        org = make_org(role_with([]))
        org.risk_tier = ApprovalPolicy.AUTONOMOUS
        role = role_with([])
        role.approval_policy = ApprovalPolicy.AUTONOMOUS

        medium = Tool(name="channel_post", description="x", func=lambda _i: "", risk="medium")
        self.assertFalse(
            approval_needed(grant_approval=False, access=ToolAccess.WRITE, tool=medium, role=role, org=org)
        )
        high = medium.with_risk("high")
        self.assertTrue(
            approval_needed(grant_approval=False, access=ToolAccess.WRITE, tool=high, role=role, org=org)
        )

    def test_review_external_gates_writes_and_high_risk_reads(self):
        org = make_org(role_with([]))
        org.risk_tier = ApprovalPolicy.REVIEW_EXTERNAL
        low = Tool(name="web_fetch", description="x", func=lambda _i: "", risk="low")
        self.assertFalse(
            approval_needed(grant_approval=False, access=ToolAccess.READ, tool=low, org=org)
        )
        high = low.with_risk("high")
        self.assertTrue(
            approval_needed(grant_approval=False, access=ToolAccess.READ, tool=high, org=org)
        )
        self.assertTrue(
            approval_needed(grant_approval=False, access=ToolAccess.WRITE, tool=low, org=org)
        )

    def test_risk_order_consistent(self):
        self.assertTrue(RISK_ORDER["low"] < RISK_ORDER["medium"] < RISK_ORDER["high"])


class TestMemoryAndChannelTools(unittest.TestCase):
    def test_memory_read_write_search_round_trip(self):
        store = Store(":memory:")
        role = role_with([ToolGrant(tool="memory", access=ToolAccess.WRITE)])
        tools = tools_for_role(role, store=store)
        self.assertIn("memory_write", {t.name for t in tools})
        out = lookup(tools, "memory_write").execute({"key": "client/alice", "content": "wants a demo first"})
        self.assertIn("WROTE", out)
        self.assertIn("demo", store.get_context("client/alice")["content"])

        read_role = role_with([ToolGrant(tool="memory", access=ToolAccess.READ)])
        read_tools = tools_for_role(read_role, store=store)
        names = {t.name for t in read_tools}
        self.assertIn("memory_read", names)
        self.assertIn("memory_search", names)
        self.assertIn("demo", lookup(read_tools, "memory_read").execute({"key": "client/alice"}))
        self.assertIn("client/alice", lookup(read_tools, "memory_search").execute({"term": "demo"}))
        store.close()

    def test_memory_tools_require_store(self):
        role = role_with([ToolGrant(tool="memory", access=ToolAccess.READ)])
        tools = tools_for_role(role)
        out = lookup(tools, "memory_read").execute({"key": "x"})
        self.assertIn("requires the org job store", out)

    def test_channel_tools_read_post(self):
        store = Store(":memory:")
        role = role_with([ToolGrant(tool="channel", access=ToolAccess.WRITE)])
        tools = tools_for_role(role, store=store)
        post = lookup(tools, "channel_post")
        self.assertIn("POSTED", post.execute({"channel": "general", "content": "hi there"}))

        read_role = role_with([ToolGrant(tool="channel", access=ToolAccess.READ)])
        read_tools = tools_for_role(read_role, store=store)
        self.assertIn("hi there", lookup(read_tools, "channel_list").execute({"channel": "general"}))
        store.close()

    def test_channel_post_approval_under_review_external(self):
        org = make_org(role_with([]))
        org.risk_tier = ApprovalPolicy.REVIEW_EXTERNAL
        role = role_with([ToolGrant(tool="channel", access=ToolAccess.WRITE)])
        store = Store(":memory:")
        try:
            tools = tools_for_role(role, org=org, store=store)
            self.assertTrue(lookup(tools, "channel_post").requires_approval)
        finally:
            store.close()

    def test_channel_post_autonomous_medium_is_free(self):
        org = make_org(role_with([]))
        org.risk_tier = ApprovalPolicy.AUTONOMOUS
        role = role_with([ToolGrant(tool="channel", access=ToolAccess.WRITE)])
        store = Store(":memory:")
        tools = tools_for_role(role, org=org, store=store)
        self.assertFalse(lookup(tools, "channel_post").requires_approval)
        store.close()


class TestMcpStyleToolServers(unittest.TestCase):
    def tearDown(self):
        REGISTERED_SERVERS.pop("status", None)
        REGISTERED_SERVERS.pop("ops_internal", None)

    def test_server_tools_wrap_and_prefix(self):
        server = FakeToolServer()
        tools = server_tools(server, tool_prefix="status")
        names = sorted(t.name for t in tools)
        self.assertIn("status_ping", names)
        self.assertIn("status_destroy", names)
        ping = lookup(tools, "status_ping")
        self.assertEqual(ping.execute({}), "pong")
        self.assertEqual(server.calls, [("ping", {})])

    def test_registered_server_resolves_through_grants(self):
        server = FakeToolServer()
        register_tool_server("status", server)
        role = role_with([ToolGrant(tool="status", access=ToolAccess.READ)])
        tools = tools_for_role(role)
        names = {t.name for t in tools}
        self.assertIn("status_ping", names)
        self.assertIn("status_destroy", names)
        # Server-level approval is preserved: destroy stays gated.
        self.assertFalse(lookup(tools, "status_ping").requires_approval)
        self.assertTrue(lookup(tools, "status_destroy").requires_approval)

    def test_servers_parameter_overrides_registry(self):
        role = role_with([ToolGrant(tool="ops_internal", access=ToolAccess.READ)])
        tools = tools_for_role(role, servers={"ops_internal": FakeToolServer()})
        self.assertIn("ops_internal_ping", {t.name for t in tools})

    def test_approval_first_gates_server_tools(self):
        server = FakeToolServer()
        register_tool_server("status", server)
        role = role_with([ToolGrant(tool="status", access=ToolAccess.READ)])
        role.approval_policy = ApprovalPolicy.APPROVAL_FIRST
        org = make_org(role)
        tools = tools_for_role(role, org=org)
        self.assertTrue(lookup(tools, "status_ping").requires_approval)


if __name__ == "__main__":
    unittest.main()
