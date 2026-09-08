"""Runtime tool framework.

Tools are the actions an agent can take on the world. Each role only sees the
tools it is *granted* (from its ``tool_grants``), and approval-gated tools are
blocked until a human approves.

M1 shipped a minimal set of real tools (``files``, ``web``) plus generic stubs
for third-party integrations. M6 widens the surface:

* **``memory`` / ``channel`` local adapters** — company-memory read/search/write
  over the ``Store`` context table, and read/post over the shared human->agent
  channel. Both are *local* tools that need no external service.
* **MCP-style tool servers** — ``toolservers.register_tool_server`` attaches any
  local server (description + execute-by-name) to the grant system.
* **Risk-aware permissions** — every ``Tool`` carries a ``risk`` (low/medium/
  high); ``approval_needed`` turns access + role/org policy + risk into a single
  defensible approval decision.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin, urlparse

from ..config import ApprovalPolicy, Org, Role, ToolAccess
from .state import Store

# A tool function takes a dict of inputs and returns a text result.
ToolFunc = Callable[[dict], str]
ApprovalFn = Callable[["Tool"], bool]

_MAX_WEB_RESPONSE_BYTES = 1024 * 1024
_MAX_WEB_REDIRECTS = 5
_ALLOWED_WEB_SCHEMES = {"http", "https"}
_WEB_ALLOWLIST_ENV_VARS = (
    "AGENT_FACTORY_WEB_ALLOWED_HOSTS",
    "WEB_FETCH_ALLOWED_HOSTS",
    "WEB_ALLOWLIST",
)
_BLOCKED_WEB_IPS = {
    "100.100.100.200",  # Alibaba Cloud metadata
    "169.254.169.254",  # common cloud metadata endpoint
    "169.254.170.2",    # AWS ECS metadata
}

RISK_ORDER = {"low": 1, "medium": 2, "high": 3}


def approval_needed(
    *,
    grant_approval: bool,
    access: ToolAccess,
    tool: Tool,
    role: Role | None = None,
    org: Org | None = None,
) -> bool:
    """The single permission rule: does this tool call need a human approval?

    Order of precedence (first match wins):

    1. the schema-level grant gate (``ToolGrant.requires_approval``) is absolute;
    2. ``APPROVAL_FIRST`` (role *or* org) gates every tool call;
    3. ``REVIEW_EXTERNAL`` gates write access and high-risk reads;
    4. otherwise (autonomous) high-risk tools are still gated — defense in depth,
       so a self-driving org cannot silently run shell-level or destructive tools.
    """
    if grant_approval:
        return True
    org_policy = org.risk_tier if org is not None else ApprovalPolicy.AUTONOMOUS
    role_policy = role.approval_policy if role is not None else org_policy
    if ApprovalPolicy.APPROVAL_FIRST in (role_policy, org_policy):
        return True
    risk = RISK_ORDER.get(tool.risk, RISK_ORDER["medium"])
    if ApprovalPolicy.REVIEW_EXTERNAL in (role_policy, org_policy):
        if access == ToolAccess.WRITE:
            return True
        return risk >= RISK_ORDER["high"]
    # Autonomous role + org: only high-risk actions need sign-off.
    return risk >= RISK_ORDER["high"]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    func: ToolFunc
    requires_approval: bool = False
    risk: str = "medium"  # risk tier: low | medium | high

    def with_approval(self, value: bool = True) -> Tool:
        return replace(self, requires_approval=value)

    def with_risk(self, value: str) -> Tool:
        return replace(self, risk=value)

    def execute(self, inputs: dict | None = None) -> str:
        return self.func(inputs or {})


# ---------------------------------------------------------------------------
# Real (minimal) built-in tools.
# ---------------------------------------------------------------------------

def _confined_path(raw_path: object, root: Path | None) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "ERROR: 'path' is required"
    if root is None:
        return None, "ERROR: file tools require an agent workspace root"

    workspace = Path(root).resolve()
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return None, "ERROR: path must be relative to the agent workspace"

    resolved = (workspace / candidate).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError:
        return None, "ERROR: path is outside the agent workspace"
    return resolved, None


def _files_read(inputs: dict, root: Path | None) -> str:
    path = inputs.get("path", "")
    target, error = _confined_path(path, root)
    if error:
        return error
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR reading file: {exc}"
    return text[:8000] + ("...\n[truncated]" if len(text) > 8000 else "")


def _files_write(inputs: dict, root: Path | None) -> str:
    path = inputs.get("path", "")
    content = inputs.get("content", "")
    target, error = _confined_path(path, root)
    if error:
        return error
    if not isinstance(content, str):
        return "ERROR: 'content' must be a string"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"ERROR writing file: {exc}"
    return f"WROTE {len(content)} chars to {target.relative_to(Path(root).resolve())}"


def _web_allowed_hosts() -> set[str]:
    for key in _WEB_ALLOWLIST_ENV_VARS:
        value = os.environ.get(key)
        if value is None:
            continue
        hosts = set()
        for raw in value.split(","):
            host = raw.strip().lower().strip(".")
            if host:
                hosts.add(host)
        return hosts
    return set()


def _is_host_allowed(host: str, allowed_hosts: set[str]) -> bool:
    host = host.rstrip(".").lower()
    if not host:
        return False
    for allowed in allowed_hosts:
        allowed = allowed.rstrip(".").lower()
        if not allowed:
            continue
        # "*" is an explicit opt-in to disable the domain allowlist; the
        # scheme/port/private-IP/metadata checks in _validate_web_url still apply.
        if allowed == "*":
            return True
        if host == allowed or host.endswith(f".{allowed}"):
            return True
    return False


def _validate_web_url(url: object) -> tuple[str | None, str | None]:
    if not isinstance(url, str) or not url.strip():
        return None, "ERROR: 'url' is required for web_fetch"

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in _ALLOWED_WEB_SCHEMES:
        return None, "ERROR: web_fetch only permits http and https URLs"
    if not parsed.hostname:
        return None, "ERROR: web_fetch URL must include a hostname"
    if parsed.username is not None or parsed.password is not None:
        return None, "ERROR: web_fetch URLs cannot include credentials"
    try:
        port = parsed.port
    except ValueError:
        return None, "ERROR: web_fetch URL has an invalid port"
    if port is not None and port not in (80, 443):
        return None, "ERROR: web_fetch only permits ports 80 and 443"

    host = parsed.hostname.rstrip(".").lower()
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ]
        except (OSError, ValueError):
            return None, "ERROR: web_fetch could not resolve the hostname"

    if not addresses or any(
        str(address) in _BLOCKED_WEB_IPS or not address.is_global
        for address in addresses
    ):
        return None, "ERROR: web_fetch destination is not a public address"

    allowed_hosts = _web_allowed_hosts()
    if not allowed_hosts or not _is_host_allowed(host, allowed_hosts):
        return None, "ERROR: web_fetch host is not in the configured allowlist"
    return url.strip(), None


def _web_fetch(inputs: dict) -> str:
    url = inputs.get("url", "")
    current_url, error = _validate_web_url(url)
    if error:
        return error

    try:
        import requests
        session = requests.Session()
        session.trust_env = False
        try:
            for _ in range(_MAX_WEB_REDIRECTS + 1):
                response = session.get(
                    current_url,
                    timeout=(10, 30),
                    allow_redirects=False,
                    stream=True,
                )
                try:
                    if response.is_redirect or response.is_permanent_redirect:
                        location = response.headers.get("Location")
                        if not location:
                            return "ERROR: web_fetch redirect did not provide a destination"
                        current_url, error = _validate_web_url(urljoin(current_url, location))
                        if error:
                            return error
                        continue

                    response.raise_for_status()
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > _MAX_WEB_RESPONSE_BYTES:
                        return "ERROR: web_fetch response exceeds the size limit"

                    chunks: list[bytes] = []
                    total = 0
                    truncated = False
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        remaining = _MAX_WEB_RESPONSE_BYTES - total
                        if len(chunk) > remaining:
                            chunks.append(chunk[:remaining])
                            truncated = True
                            break
                        chunks.append(chunk)
                        total += len(chunk)
                    body = b"".join(chunks)
                    encoding = response.encoding or "utf-8"
                    text = body.decode(encoding, errors="replace")
                    return text + ("...\n[truncated]" if truncated else "")
                finally:
                    response.close()
            return "ERROR: web_fetch exceeded the redirect limit"
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - the tool returns a stable error
        return f"ERROR fetching web resource: {exc.__class__.__name__}"


# ---------------------------------------------------------------------------
# Catalog: tool id -> read/write Tool instances (or a stub fallback).
# ---------------------------------------------------------------------------

CATALOG: dict[str, dict[str, Tool | list[Tool]]] = {
    "web": {
        "read": Tool(
            "web_fetch",
            "Fetch the text body of a URL. Input: {url}.",
            _web_fetch,
            risk="low",
        ),
    },
}


def _file_tools(root: Path | None) -> dict[str, Tool]:
    return {
        "read": Tool(
            "files_read",
            "Read a local file relative to the agent workspace. Input: {path}.",
            lambda inputs: _files_read(inputs, root),
            risk="low",
        ),
        "write": Tool(
            "files_write",
            "Write content to a local file relative to the agent workspace. Input: {path, content}.",
            lambda inputs: _files_write(inputs, root),
            requires_approval=True,
            risk="high",
        ),
    }


# ---------------------------------------------------------------------------
# M6 local adapters backed by the durable Store (the other extension point).
#   memory  — read/search/write over the company context store ("memory")
#   channel — read/post over the shared human<->agent channel
# Both need a Store instance, so they are built per-resolution like files.
# ---------------------------------------------------------------------------

def _store_missing(what: str) -> str:
    return (
        f"ERROR: the {what!r} tool requires the org job store, which is only "
        "available while the role runs inside a job/worker loop."
    )


def _memory_read(inputs: dict, store: Store | None) -> str:
    if store is None:
        return _store_missing("memory")
    key = inputs.get("key", "")
    if not isinstance(key, str) or not key.strip():
        return "ERROR: 'key' is required for memory_read"
    row = store.get_context(key.strip())
    if row is None:
        return f"memory_read: no entry for key {key!r}"
    return f"[{row['key']}] (source: {row['source'] or '--'})\n{row['content']}"


def _memory_search(inputs: dict, store: Store | None) -> str:
    if store is None:
        return _store_missing("memory")
    term = inputs.get("term", "")
    if not isinstance(term, str) or not term.strip():
        return "ERROR: 'term' is required for memory_search"
    rows = store.search_context(term.strip(), limit=20)
    if not rows:
        return "memory_search: no matches"
    return "\n".join(f"[{r['key']}] {r['content'][:800]}" for r in rows)


def _memory_write(inputs: dict, store: Store | None) -> str:
    if store is None:
        return _store_missing("memory")
    key = inputs.get("key", "")
    content = inputs.get("content", "")
    if not isinstance(key, str) or not key.strip():
        return "ERROR: 'key' is required for memory_write"
    if not isinstance(content, str):
        return "ERROR: 'content' must be a string"
    store.upsert_context(key.strip(), content, source="memory")
    return f"WROTE memory key {key!r} ({len(content)} chars)"


def _channel_list(inputs: dict, store: Store | None) -> str:
    if store is None:
        return _store_missing("channel")
    channel = str(inputs.get("channel", "general") or "general")
    try:
        limit = int(inputs.get("limit", 20) or 20)
    except (TypeError, ValueError):
        return "ERROR: 'limit' must be an integer"
    messages = store.list_messages(channel=channel, limit=limit)
    if not messages:
        return f"channel {channel!r}: no messages yet"
    lines = []
    for m in reversed(messages):
        reply = "->" if m["reply_to"] else "*"
        lines.append(f"{reply} [{m['author_role']}:{m['author']}] {m['content'][:400]}")
    return "\n".join(lines)


def _channel_post(inputs: dict, store: Store | None) -> str:
    if store is None:
        return _store_missing("channel")
    channel = str(inputs.get("channel", "general") or "general")
    content = inputs.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return "ERROR: 'content' is required for channel_post"
    reply_to = inputs.get("reply_to")
    if reply_to is not None:
        try:
            reply_to = int(reply_to)
        except (TypeError, ValueError):
            return "ERROR: 'reply_to' must be a message id"
    mid = store.post_message(
        channel, "agent", "agent", content, requested_role=None, reply_to=reply_to, status="done"
    )
    return f"POSTED message #{mid} to channel {channel!r}"


def _store_tools(store: Store | None) -> dict[str, dict[str, Tool | list[Tool]]]:
    """Build the Store-backed ``memory``/``channel`` tool sets for a resolution."""
    memory_read = Tool(
        "memory_read",
        "Read the current value of one company-memory key from the durable context store. Input: {key}.",
        lambda inputs: _memory_read(inputs, store),
        risk="low",
    )
    memory_search = Tool(
        "memory_search",
        "Search company memory by term and return matching context entries. Input: {term}.",
        lambda inputs: _memory_search(inputs, store),
        risk="low",
    )
    memory_write = Tool(
        "memory_write",
        "Write (or update) one key in company memory so the workforce stays queryable. Input: {key, content}.",
        lambda inputs: _memory_write(inputs, store),
        risk="medium",
    )
    channel_list = Tool(
        "channel_list",
        "List recent messages in a shared human<->agent channel. Input: {channel, limit}.",
        lambda inputs: _channel_list(inputs, store),
        risk="low",
    )
    channel_post = Tool(
        "channel_post",
        "Post a message into a shared human<->agent channel. Input: {channel, content, reply_to}.",
        lambda inputs: _channel_post(inputs, store),
        risk="medium",
    )
    return {
        "memory": {"read": [memory_read, memory_search], "write": [memory_write]},
        "channel": {"read": [channel_list], "write": [channel_post]},
    }


# Keep the static catalog authoritative: memory/channel are registered here
# (bound to no store) so grants resolve even outside a job loop; tools_for_role
# substitutes the live store spec when one is in scope.
CATALOG["memory"] = _store_tools(None)["memory"]
CATALOG["channel"] = _store_tools(None)["channel"]


# Tool ids that exist in the schema but still have no live adapter -> stub.
_STUBBED = {
    "notion", "gmail", "calendar", "slack", "stripe", "supabase",
    "github", "sheets", "docs", "crm", "cms", "payments", "analytics",
}


def tool_surface() -> dict[str, dict[str, object]]:
    """Public snapshot of the declared tool surface, keyed by tool id.

    Returns ``{tool_id: {"real": bool, "actions": [tool names]}}`` where
    ``real=True`` entries have a live adapter in this runtime and ``real=False``
    entries are stubs: declared in role grants but returning a placeholder
    when invoked. Used by the ``agent_factory tools`` command and kept in sync
    with the README tool-surface table so docs never overclaim.
    """
    surface: dict[str, dict[str, object]] = {}
    for tid, entry in CATALOG.items():
        if tid in _STUBBED:
            continue
        actions: list[str] = []
        for kind in ("read", "write"):
            spec = entry.get(kind)
            if spec is None:
                continue
            for tool in (spec if isinstance(spec, list) else [spec]):
                actions.append(tool.name)
        surface[tid] = {"real": True, "actions": actions}
    # ``files`` is real but built per-resolution (workspace-bound), so it is
    # special-cased in ``tools_for_role`` and absent from the static CATALOG.
    # Derive its action names from the same definitions the runtime uses.
    file_specs = _file_tools(None)
    surface["files"] = {"real": True, "actions": [file_specs["read"].name, file_specs["write"].name]}
    for tid in sorted(_STUBBED):
        surface.setdefault(tid, {"real": False, "actions": [f"{tid}_stub"]})
    return surface


def _stub_tool(tool_id: str) -> Tool:
    return Tool(
        name=f"{tool_id}_stub",
        description=f"{tool_id} integration (STUB — not wired in the runtime yet).",
        func=lambda _inputs, _tid=tool_id: (
            f"STUB: the '{_tid}' integration is not implemented in the runtime. "
            "This tool is declared in the role grants but has no live adapter yet."
        ),
        requires_approval=False,
        risk="medium",
    )


def _resolve_spec(spec: dict, access: ToolAccess) -> list[Tool]:
    """Pick the read/write candidates a grant should expose from a catalog entry.

    A spec maps ``read``/``write`` to a single :class:`Tool` or a list of Tools
    (M6 lets a tool id expose several read actions, e.g. memory read + search).
    """
    if access == ToolAccess.WRITE and spec.get("write"):
        candidates = spec["write"]
    elif spec.get("read"):
        candidates = spec["read"]
    else:
        return []  # write requested but no write impl
    if not isinstance(candidates, list):
        candidates = [candidates]
    return [t for t in candidates if t is not None]


def tools_for_role(
    role: Role,
    root: Path | None = None,
    *,
    org: Org | None = None,
    store: Store | None = None,
    servers: dict | None = None,
) -> list[Tool]:
    """Resolve a role's ``tool_grants`` into executable Tools (respecting access).

    ``store`` activates the ``memory``/``channel`` local adapters (M6). ``servers``
    overrides — or, when omitted, inherits — the registered MCP-style tool servers.
    """
    tools: dict[str, Tool] = {}
    if servers is None:
        from .toolservers import REGISTERED_SERVERS, server_tools

        server_map = dict(REGISTERED_SERVERS)
    else:
        from .toolservers import server_tools

        server_map = dict(servers)

    store_specs = _store_tools(store)
    for g in role.tool_grants:
        # MCP-style server grant: expose every tool the server advertises, still
        # gated by the same grant access + approval rules as built-ins.
        if g.tool in server_map:
            for tool in server_tools(server_map[g.tool], tool_prefix=g.tool):
                requires_approval = approval_needed(
                    grant_approval=g.requires_approval,
                    access=g.access,
                    tool=tool,
                    role=role,
                    org=org,
                )
                if requires_approval and not tool.requires_approval:
                    tool = tool.with_approval(True)
                tools[tool.name] = tool
            continue

        if g.tool == "files":
            spec = _file_tools(root)
        elif g.tool in ("memory", "channel"):
            spec = store_specs[g.tool]
        else:
            spec = CATALOG.get(g.tool)

        if spec is None:
            stub = _stub_tool(g.tool)
            requires_approval = approval_needed(
                grant_approval=g.requires_approval,
                access=g.access,
                tool=stub,
                role=role,
                org=org,
            )
            tools[g.tool] = stub.with_approval(requires_approval)
            continue

        for tool in _resolve_spec(spec, g.access):
            requires_approval = approval_needed(
                grant_approval=g.requires_approval,
                access=g.access,
                tool=tool,
                role=role,
                org=org,
            )
            if requires_approval and not tool.requires_approval:
                tool = tool.with_approval(True)
            tools[tool.name] = tool
    return list(tools.values())


def lookup(tools: list[Tool], name: str) -> Tool | None:
    for t in tools:
        if t.name == name:
            return t
    return None
