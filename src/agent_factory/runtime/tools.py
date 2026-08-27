"""Runtime tool framework.

Tools are the actions an agent can take on the world. Each role only sees the
tools it is *granted* (from its ``tool_grants``), and ``requires_approval``
tools are gated behind a human approval callback.

M1 ships a minimal set of real tools (``files``, ``web``) plus generic stubs
for the rest, so the *framework* (grants, approval, tool-calling loop) is real
even where third-party integrations are not yet wired.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

from ..config import ApprovalPolicy, Org, Role, ToolAccess

# A tool function takes a dict of inputs and returns a text result.
ToolFunc = Callable[[dict], str]
ApprovalFn = Callable[["Tool"], bool]

_MAX_WEB_RESPONSE_BYTES = 1024 * 1024
_MAX_WEB_REDIRECTS = 5
_ALLOWED_WEB_SCHEMES = {"http", "https"}
_BLOCKED_WEB_IPS = {
    "100.100.100.200",  # Alibaba Cloud metadata
    "169.254.169.254",  # common cloud metadata endpoint
    "169.254.170.2",    # AWS ECS metadata
}


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

def _confined_path(raw_path: object, root: Optional[Path]) -> tuple[Optional[Path], Optional[str]]:
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


def _files_read(inputs: dict, root: Optional[Path]) -> str:
    path = inputs.get("path", "")
    target, error = _confined_path(path, root)
    if error:
        return error
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR reading file: {exc}"
    return text[:8000] + ("...\n[truncated]" if len(text) > 8000 else "")


def _files_write(inputs: dict, root: Optional[Path]) -> str:
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


def _validate_web_url(url: object) -> tuple[Optional[str], Optional[str]]:
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

CATALOG: dict[str, dict[str, Tool]] = {
    "web": {
        "read": Tool("web_fetch", "Fetch the text body of a URL. Input: {url}.", _web_fetch),
    },
}


def _file_tools(root: Optional[Path]) -> dict[str, Tool]:
    return {
        "read": Tool(
            "files_read",
            "Read a local file relative to the agent workspace. Input: {path}.",
            lambda inputs: _files_read(inputs, root),
        ),
        "write": Tool(
            "files_write",
            "Write content to a local file relative to the agent workspace. Input: {path, content}.",
            lambda inputs: _files_write(inputs, root),
            requires_approval=True,
        ),
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


def tools_for_role(
    role: Role,
    root: Optional[Path] = None,
    *,
    org: Optional[Org] = None,
) -> list[Tool]:
    """Resolve a role's ``tool_grants`` into executable Tools (respecting access)."""
    tools: dict[str, Tool] = {}
    org_policy = org.risk_tier if org is not None else ApprovalPolicy.AUTONOMOUS
    approval_first = (
        role.approval_policy == ApprovalPolicy.APPROVAL_FIRST
        or org_policy == ApprovalPolicy.APPROVAL_FIRST
    )
    review_external = (
        role.approval_policy == ApprovalPolicy.REVIEW_EXTERNAL
        or org_policy == ApprovalPolicy.REVIEW_EXTERNAL
    )
    for g in role.tool_grants:
        spec = _file_tools(root) if g.tool == "files" else CATALOG.get(g.tool)
        if spec is None:
            requires_approval = g.requires_approval or approval_first or (
                g.access == ToolAccess.WRITE and review_external
            )
            tools[g.tool] = _stub_tool(g.tool).with_approval(requires_approval)
            continue
        if g.access == ToolAccess.WRITE and "write" in spec:
            chosen = spec["write"]
        elif "read" in spec:
            chosen = spec["read"]
        else:
            continue  # write requested but no write impl
        # A schema-level approval gate overrides the tool default.
        requires_approval = g.requires_approval or approval_first or (
            g.access == ToolAccess.WRITE and review_external
        )
        if requires_approval and not chosen.requires_approval:
            chosen = chosen.with_approval(True)
        tools[chosen.name] = chosen
    return list(tools.values())


def lookup(tools: list[Tool], name: str) -> Optional[Tool]:
    for t in tools:
        if t.name == name:
            return t
    return None
