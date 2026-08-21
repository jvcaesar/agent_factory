"""Load and validate the config/ object tree from YAML, org dirs, or Org models.

The factory works primarily in memory (an :class:`~agent_factory.config.Org`),
but persists orgs as YAML so they are diffable, reviewable, and reusable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from . import ApprovalPolicy, ModelTier, Org, Role, ToolAccess, ToolGrant


def _role_from_dict(d: dict) -> Role:
    grants = []
    for g in d.get("tool_grants", []) or []:
        grants.append(
            ToolGrant(
                tool=g["tool"],
                access=ToolAccess(g.get("access", "read")),
                requires_approval=bool(g.get("requires_approval", False)),
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
        approval_policy=ApprovalPolicy(d.get("approval_policy", "autonomous")),
        reports_to=d.get("reports_to"),
        tool_grants=grants,
        subagents=d.get("subagents", []) or [],
    )


def org_from_dict(data: dict) -> Org:
    """Build an :class:`Org` from a parsed YAML dict, applying defaults."""
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
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return org_from_dict(data)


def validate_org(org: Org) -> list[str]:
    """Return a list of validation errors (empty == valid).

    Checks that every ``reports_to``/``subagents`` reference resolves, the
    reporting graph has no cycles, ``proactivity_level`` is in range, and SOP
    paths exist if given relative to an org root directory.
    """
    errors: list[str] = []
    lookup = {r.id: r for r in org.roles}

    # duplicate ids
    if len(lookup) != len(org.roles):
        ids = [r.id for r in org.roles]
        dupes = {i for i in ids if ids.count(i) > 1}
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

    # cycle detection over the reporting graph
    visiting: set[str] = set()
    done: set[str] = set()
    order: list[Role] = []

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
        order.append(lookup[node])

    for r in org.roles:
        visit(r.id)

    return errors
