"""Org generation: InterviewAnswers -> :class:`~agent_factory.config.Org` + files.

A pure rules engine over {topology + domains + risk + budget + tools}. No
LLM, no network — deterministic, so the test suite can assert exact outcomes.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..config import ApprovalPolicy, ModelTier, Org, Role, ToolAccess, ToolGrant
from .archetypes import ADDONS, ALL_WORKERS, DIRECTORS, KNOWN_TOOLS
from .interview import InterviewAnswers
from .prompts import render_goals, render_org_readme, render_sop


def _lead_role(tools: set[str], risk: ApprovalPolicy, budget: str) -> Role:
    """The generic org lead that ties directors together (and routes work)."""
    tier = ModelTier.BIG if budget == "unlimited" else ModelTier.SMART
    grants: list[str] = ["files"]
    if "notion" in tools:
        grants.append("notion")
    return Role(
        id="lead_exec",
        display_name="Org Lead",
        title="Org Lead (Chief of Staff)",
        charter=(
            "Organize the workforce: route work to the right directors, "
            "keep goals in front of everyone, and decide what should or "
            "should not happen with escalations."
        ),
        sop="sops/lead_exec.md",
        proactivity_level=5,
        model_tier=tier,
        approval_policy=ApprovalPolicy.AUTONOMOUS,
        reports_to=None,
        tool_grants=[
            ToolGrant(tool="files", access=ToolAccess.READ, requires_approval=False)
        ]
        + ([ToolGrant(tool="notion", access=ToolAccess.READ, requires_approval=False)] if "notion" in tools else []),
        subagents=[],
    )


def generate_org(answers: InterviewAnswers) -> Org:
    """Build an :class:`Org` from interview answers (no writes to disk)."""
    errors = answers.validate()
    if errors:
        raise ValueError("invalid answers: " + "; ".join(errors))

    roles: list[Role] = []
    lead_subagents: list[str] = []
    budget = answers.budget_tier
    risk = answers.risk_tier

    def apply_risk(grants: list[ToolGrant]) -> list[ToolGrant]:
        """Gate write grants behind human approval unless org is fully autonomous."""
        if risk == ApprovalPolicy.AUTONOMOUS:
            return grants
        out = []
        for g in grants:
            if g.access == ToolAccess.WRITE:
                g = g.model_copy(update={"requires_approval": True})
            out.append(g)
        return out

    if answers.use_lead:
        roles.append(_lead_role(answers.tools, answers.risk_tier, budget))
        lead_subagents.append(roles[0].id)

    used_workers: dict[str, int] = {}

    def worker_instance(wid: str) -> str:
        idx = used_workers.get(wid, 0) + 1
        used_workers[wid] = idx
        return f"{wid}_{idx}"

    for domain in answers.domains:
        arch = DIRECTORS[domain]
        dir_id = arch.id
        dir_tier = arch.model_tier
        if budget == "small" and dir_tier == ModelTier.BIG:
            dir_tier = ModelTier.SMART
        director = Role(
            id=dir_id,
            display_name=arch.title,
            title=arch.title,
            charter=arch.charter,
            sop=f"sops/{dir_id}.md",
            proactivity_level=arch.proactivity,
            model_tier=dir_tier,
            approval_policy=arch.approval_policy,
            reports_to=roles[0].id if answers.use_lead else None,
            tool_grants=apply_risk(arch.grants(answers.tools)),
            subagents=[],
        )
        for wid in arch.default_workers:
            warch = ALL_WORKERS[wid]
            wname = worker_instance(wid)
            worker = Role(
                id=wname,
                display_name=f"{warch.title} {used_workers[wid]}",
                title=warch.title,
                charter=warch.charter,
                sop=f"sops/{wname}.md",
                proactivity_level=warch.proactivity,
                model_tier=warch.model_tier,
                approval_policy=warch.approval_policy,
                reports_to=dir_id,
                tool_grants=apply_risk(warch.grants(answers.tools)),
                subagents=[],
            )
            director.subagents.append(wname)
            roles.append(worker)
        roles.append(director)
        lead_subagents.append(dir_id)

    addon_map = {"amplifier": answers.add_amplifier, "observer": answers.add_observer}
    for name, enabled in addon_map.items():
        if not enabled:
            continue
        a = ADDONS[name]
        roles.append(
            Role(
                id=a.id,
                display_name=a.title,
                title=a.title,
                charter=a.charter,
                sop=f"sops/{a.id}.md",
                proactivity_level=a.proactivity,
                model_tier=a.model_tier,
                approval_policy=a.approval_policy,
                reports_to=roles[0].id if answers.use_lead else None,
                tool_grants=apply_risk(a.grants(answers.tools)),
                subagents=[],
            )
        )
        lead_subagents.append(a.id)

    if answers.use_lead and len(roles) > 1:
        roles[0].subagents = [x for x in lead_subagents[1:] if x not in roles[0].subagents]

    return Org(
        name=answers.org_name,
        founder=answers.founder,
        north_star=answers.north_star,
        human_team_size=answers.human_team_size,
        quarterly_goals=list(answers.quarterly_goals),
        risk_tier=answers.risk_tier,
        budget_tier=budget,
        roles=roles,
    )
def write_org(org: Org, root: Path) -> None:
    """Persist an org as YAML roles, markdown sops/goals, and a settings file."""
    root = Path(root)
    (root / "roles").mkdir(parents=True, exist_ok=True)
    (root / "sops").mkdir(parents=True, exist_ok=True)
    (root / "goals").mkdir(parents=True, exist_ok=True)

    for role in org.roles:
        role_dict = {
            "id": role.id,
            "display_name": role.display_name,
            "title": role.title,
            "charter": role.charter,
            "sop": role.sop,
            "proactivity_level": role.proactivity_level,
            "model_tier": role.model_tier.value,
            "approval_policy": role.approval_policy.value,
            "reports_to": role.reports_to,
            "tool_grants": [
                {"tool": g.tool, "access": g.access.value, "requires_approval": g.requires_approval}
                for g in role.tool_grants
            ],
            "subagents": role.subagents,
        }
        with open(root / "roles" / f"{role.id}.yaml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(role_dict, fh, sort_keys=False, allow_unicode=True)
        with open(root / role.sop, "w", encoding="utf-8") as fh:
            fh.write(render_sop(org, role, role.subagents))

    with open(root / "goals" / "current.md", "w", encoding="utf-8") as fh:
        fh.write(render_goals(org, list(org.quarterly_goals)))

    with open(root / "README.md", "w", encoding="utf-8") as fh:
        fh.write(render_org_readme(org))

    settings = {
        "org": org.name,
        "risk_tier": org.risk_tier.value,
        "budget_tier": org.budget_tier,
        "known_tools": sorted(KNOWN_TOOLS),
    }
    with open(root / "settings.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(settings, fh, sort_keys=False, allow_unicode=True)

    # Aggregate org definition so `validate --root` can load everything at once.
    org_dict = {
        "name": org.name,
        "founder": org.founder,
        "north_star": org.north_star,
        "human_team_size": org.human_team_size,
        "risk_tier": org.risk_tier.value,
        "budget_tier": org.budget_tier,
        "quarterly_goals": list(org.quarterly_goals),
    "roles": [
            {
                "id": r.id,
                "display_name": r.display_name,
                "title": r.title,
                "charter": r.charter,
                "sop": r.sop,
                "proactivity_level": r.proactivity_level,
                "model_tier": r.model_tier.value,
                "approval_policy": r.approval_policy.value,
                "reports_to": r.reports_to,
                "tool_grants": [
                    {"tool": g.tool, "access": g.access.value, "requires_approval": g.requires_approval}
                    for g in r.tool_grants
                ],
                "subagents": r.subagents,
            }
            for r in org.roles
        ],
    }
    with open(root / "org.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(org_dict, fh, sort_keys=False, allow_unicode=True)

