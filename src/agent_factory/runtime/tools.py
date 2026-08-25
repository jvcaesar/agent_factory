"""Runtime tool framework.

Tools are the actions an agent can take on the world. Each role only sees the
tools it is *granted* (from its ``tool_grants``), and ``requires_approval``
tools are gated behind a human approval callback.

M1 ships a minimal set of real tools (``files``, ``web``) plus generic stubs
for the rest, so the *framework* (grants, approval, tool-calling loop) is real
even where third-party integrations are not yet wired.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

from ..config import Role, ToolAccess

# A tool function takes a dict of inputs and returns a text result.
ToolFunc = Callable[[dict], str]
ApprovalFn = Callable[["Tool"], bool]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    func: ToolFunc
    requires_approval: bool = False

    def with_approval(self, value: bool = True) -> "Tool":
        return replace(self, requires_approval=value)

    def execute(self, inputs: Optional[dict] = None) -> str:
        return self.func(inputs or {})


# ---------------------------------------------------------------------------
# Real (minimal) built-in tools.
# ---------------------------------------------------------------------------

def _files_read(inputs: dict) -> str:
    path = inputs.get("path", "")
    if not path:
        return "ERROR: 'path' is required for files_read"
    try:
        Path(path).read_text(encoding="utf-8")
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR reading {path}: {exc}"
    return text[:8000] + ("...\n[truncated]" if len(text) > 8000 else "")


def _files_write(inputs: dict) -> str:
    path = inputs.get("path", "")
    content = inputs.get("content", "")
    if not path:
        return "ERROR: 'path' is required for files_write"
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"ERROR writing {path}: {exc}"
    return f"WROTE {len(content)} chars to {path}"


def _web_fetch(inputs: dict) -> str:
    url = inputs.get("url", "")
    if not url:
        return "ERROR: 'url' is required for web_fetch"
    try:
        import requests
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except Exception as exc:
        return f"ERROR fetching {url}: {exc}"
    return r.text[:8000] + ("...\n[truncated]" if len(r.text) > 8000 else "")


# ---------------------------------------------------------------------------
# Catalog: tool id -> read/write Tool instances (or a stub fallback).
# ---------------------------------------------------------------------------

CATALOG: dict[str, dict[str, Tool]] = {
    "files": {
        "read": Tool("files_read", "Read a local file. Input: {path}.", _files_read),
        "write": Tool(
            "files_write",
            "Write content to a local file. Input: {path, content}.",
            _files_write,
            requires_approval=True,
        ),
    },
    "web": {
        "read": Tool("web_fetch", "Fetch the text body of a URL. Input: {url}.", _web_fetch),
    },
}

# Tool ids that exist in the schema but have no real adapter in M1 -> stub.
_STUBBED = {
    "notion", "gmail", "calendar", "slack", "stripe", "supabase",
    "github", "sheets", "docs", "crm", "cms", "payments", "analytics",
}


def _stub_tool(tool_id: str) -> Tool:
    return Tool(
        name=f"{tool_id}_stub",
        description=f"{tool_id} integration (STUB — not wired in M1 runtime).",
        func=lambda _inputs, _tid=tool_id: (
            f"STUB: the '{_tid}' integration is not implemented in the M1 runtime. "
            "This tool is declared in the role grants but has no live adapter yet."
        ),
        requires_approval=False,
    )


def tools_for_role(role: Role) -> list[Tool]:
    """Resolve a role's ``tool_grants`` into executable Tools (respecting access)."""
    tools: dict[str, Tool] = {}
    for g in role.tool_grants:
        spec = CATALOG.get(g.tool)
        if spec is None:
            tools[g.tool] = _stub_tool(g.tool).with_approval(g.requires_approval)
            continue
        if g.access == ToolAccess.WRITE and "write" in spec:
            chosen = spec["write"]
        elif "read" in spec:
            chosen = spec["read"]
        else:
            continue  # write requested but no write impl
        # A schema-level approval gate overrides the tool default.
        if g.requires_approval and not chosen.requires_approval:
            chosen = chosen.with_approval(True)
        tools[chosen.name] = chosen
    return list(tools.values())


def lookup(tools: list[Tool], name: str) -> Optional[Tool]:
    for t in tools:
        if t.name == name:
            return t
    return None
