"""M6 — local MCP-style tool servers.

A :class:`ToolServer` is any object that can *describe* its tools and *execute*
them by name — effectively a tiny local MCP server. :func:`server_tools` adapts
one into the runtime's :class:`~agent_factory.runtime.tools.Tool` objects, so a
third-party or local tool surface can be grafted onto the existing grant +
approval system without editing the catalog.

Register a server under a tool id:

    register_tool_server("notion_lite", my_local_server)

A role holding ``ToolGrant(tool="notion_lite", access=WRITE)`` then sees every
tool the server advertises, gateable by the same permission rules as built-ins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .tools import Tool


@dataclass(frozen=True)
class ServerTool:
    """A tool a server advertises. Mirrors the fields of ``runtime.Tool``."""

    name: str
    description: str
    requires_approval: bool = False
    risk: str = "medium"


@runtime_checkable
class ToolServer(Protocol):
    """The local MCP-style contract: describe your tools, execute by name."""

    def tool_descriptors(self) -> list[ServerTool]: ...

    def execute_tool(self, name: str, inputs: dict) -> str: ...


def server_tools(server: ToolServer, *, tool_prefix: str) -> list[Tool]:
    """Wrap every descriptor a server advertises as an independent Tool.

    Each tool is named ``{tool_prefix}_{server_name}`` so grants resolve to
    fully qualified, collision-free tool names (``server_tools`` reuses the
    row-level grant of the server in ``tools_for_role``).
    """
    wrapped: list[Tool] = []
    for descriptor in server.tool_descriptors():
        name = f"{tool_prefix}_{descriptor.name}"
        wrapped.append(
            Tool(
                name=name,
                description=descriptor.description,
                func=lambda inputs, _n=descriptor.name: server.execute_tool(_n, inputs or {}),
                requires_approval=descriptor.requires_approval,
                risk=descriptor.risk,
            )
        )
    return wrapped


# Servers registered under a plain tool id (e.g. "notion") that roles can grant.
REGISTERED_SERVERS: dict[str, ToolServer] = {}


def register_tool_server(tool_id: str, server: ToolServer) -> None:
    """Register a server so ``tools_for_role`` can expose its tools to grants."""
    REGISTERED_SERVERS[tool_id] = server


def get_registered_server(tool_id: str) -> ToolServer | None:
    return REGISTERED_SERVERS.get(tool_id)
