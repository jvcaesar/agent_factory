"""Load and validate the config/ object tree from YAML, org dirs, or Org models.

The factory works primarily in memory (an :class:`~agent_factory.config.Org`),
but persists orgs as YAML so they are diffable, reviewable, and reusable.
"""

from __future__ import annotations

from pathlib import Path
from collections import Counter
from typing import Optional

import yaml

from . import ApprovalPolicy, ModelTier, Org, Role, ToolAccess, ToolGrant


class ConfigError(ValueError):
    """Raised when an organization YAML document is malformed."""


def _strict_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _role_from_dict(d: dict) -> Role:
    if not isinstance(d, dict):
        raise ConfigError("role entry must be a mapping")
    grants = []
    for g in d.get("tool_grants", []) or []:
        grants.append(
            ToolGrant(
                tool=g["tool"],
                access=ToolAccess(g.get("access", "read")),
                requires_approval=_strict_bool(
                    g.get("requires_approval", False), "requires_approval"
                ),
            )
        )
    return Role(
        id=d["id"],
        display_name=d.get("display_name", d["id"]),
        title=d.get("title", d["id"]),
        charter=d.get("charter", ""),
        sop=d.get("sop", ""),
        proactivity_level=int(d.get("proactivity_level", 2)),
        model_tier=ModelTier(d.get("model_tier", "smart")),
        provider=d.get("provider") or None,
        model=d.get("model") or None,
        approval_policy=ApprovalPolicy(d.get("approval_policy", "autonomous")),
        reports_to=d.get("reports_to"),
        tool_grants=grants,
        subagents=d.get("subagents", []) or [],
    )


def org_from_dict(data: dict) -> Org:
    """Build an :class:`Org` from a parsed YAML dict, applying defaults."""
    if not isinstance(data, dict):
        raise ConfigError("organization document must be a mapping")
    roles = [_role_from_dict(r) for r in data.get("roles", [])]
    return Org(
        name=data["name"],
        founder=data.get("founder", ""),
        north_star=data.get("north_star", ""),
        human_team_size=int(data.get("human_team_size", 0)),
        quarterly_goals=[str(g) for g in data.get("quarterly_goals", []) or []],
        risk_tier=ApprovalPolicy(data.get("risk_tier", "review_external")),
        budget_tier=data.get("budget_tier", "medium"),
        roles=roles,
    )


def load_org_yaml(path: str | Path) -> Org:
    """Load and validate an Org from a YAML file."""
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"could not load organization config {source}: {exc}") from exc
    try:
        return org_from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid organization config {source}: {exc}") from exc


def validate_org(org: Org, root: str | Path | None = None) -> list[str]:
    """Return a list of validation errors (empty == valid).

    Checks that every ``reports_to``/``subagents`` reference resolves, the
    reporting graph has no cycles, ``proactivity_level`` is in range, and, when
    ``root`` is provided, SOP paths exist beneath that org root.
    """
    errors: list[str] = []
    lookup = {r.id: r for r in org.roles}

    # duplicate ids
    if len(lookup) != len(org.roles):
        counts = Counter(r.id for r in org.roles)
        dupes = {role_id for role_id, count in counts.items() if count > 1}
        errors.append(f"duplicate role ids: {sorted(dupes)}")

    for r in org.roles:
        if not (0 <= r.proactivity_level <= 5):
            errors.append(f"role {r.id}: proactivity_level out of range 0..5")

        for dep in (r.reports_to, *r.subagents):
            if dep is not None and dep not in lookup:
                errors.append(f"role {r.id}: unknown reference {dep!r}")

        for g in r.tool_grants:
            if not g.tool:
                errors.append(f"role {r.id}: empty tool grant")

        if root is not None and r.sop:
            org_root = Path(root).resolve()
            sop_path = (org_root / r.sop).resolve()
            try:
                sop_path.relative_to(org_root)
            except ValueError:
                errors.append(f"role {r.id}: SOP path escapes org root: {r.sop!r}")
            else:
                if not sop_path.is_file():
                    errors.append(f"role {r.id}: SOP file not found: {r.sop!r}")

    # cycle detection over the reporting graph
    visiting: set[str] = set()
    done: set[str] = set()
    def visit(node: str) -> None:
        if node in done or node not in lookup:
            return
        if node in visiting:
            errors.append(f"reporting cycle detected at role {node!r}")
            return
        visiting.add(node)
        nxt = lookup[node].reports_to
        if nxt is not None:
            visit(nxt)
        visiting.discard(node)
        done.add(node)

    for r in org.roles:
        visit(r.id)

    return errors
