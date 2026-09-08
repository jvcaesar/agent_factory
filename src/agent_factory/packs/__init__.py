"""M5 — Role packs: pre-built, specialized workforces on the same engine.

A *role pack* is a curated, named configuration that produces a full org chart
for a vertical use case — business operations, software engineering, or
research & analysis. Packs are pure data:

* ``spec`` — the ``InterviewAnswers``-style defaults (domains, tools, goals,
  risk, budget, add-ons), usable directly as a ``--spec`` template.
* ``archetype_overrides`` — targeted charter/tier/tool tweaks applied on top of
  the generic archetypes (via ``dataclasses.replace``), so the generator stays
  a single deterministic engine.

Nothing here is hard-coded to a specific person or company — each pack is an
application of the same generic hierarchy + proactivity + approval + tiering
primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..bootstrap.archetypes import ADDONS, ALL_WORKERS, DIRECTORS
from ..bootstrap.interview import InterviewAnswers


@dataclass(frozen=True)
class RolePack:
    id: str
    name: str
    description: str
    spec: dict
    archetype_overrides: dict = field(default_factory=dict)


PACKS: dict[str, RolePack] = {}


def _register(pack: RolePack) -> RolePack:
    PACKS[pack.id] = pack
    return pack


# ---------------------------------------------------------------------------
# Business operations
# ---------------------------------------------------------------------------
_register(
    RolePack(
        id="business_ops",
        name="Business Operations",
        description="Go-to-market and operations workforce: marketing, operations, "
        "support, finance, data, and partnerships.",
        spec={
            "org_name": "MyCo Operations",
            "founder": "Founder",
            "north_star": "Drive predictable growth and operational efficiency "
            "across revenue, service, and brand.",
            "quarterly_goals": [
                "Lift pipeline and closed revenue",
                "Reduce support resolution time",
                "Ship a monthly business-health report",
            ],
            "human_team_size": 2,
            "domains": ["marketing", "operations", "support", "finance", "data", "partnerships"],
            "tools": [
                "notion", "gmail", "calendar", "slack", "crm", "docs",
                "sheets", "cms", "analytics", "files",
            ],
            "risk_tier": "review_external",
            "budget_tier": "medium",
            "add_amplifier": True,
            "add_observer": True,
            "use_lead": True,
        },
        archetype_overrides={
            "director_operations": {
                "charter": "Own the go-to-market operating engine: processes, "
                "systems, and dashboards that keep revenue and delivery moving."
            },
            "director_finance": {
                "charter": "Own unit economics and budget health; surface "
                "spending risks before they become problems."
            },
            "director_support": {
                "charter": "Own triage and customer success; turn tickets and "
                "feedback into product and ops input."
            },
        },
    )
)
# ---------------------------------------------------------------------------
# Software engineering
# ---------------------------------------------------------------------------
_register(
    RolePack(
        id="engineering",
        name="Software Engineering",
        description="Delivery-focused workforce: product, engineering, research, "
        "data, and agent-operations.",
        spec={
            "org_name": "MyCo Engineering",
            "founder": "Founder",
            "north_star": "Ship reliable, high-quality software faster with a "
            "self-reviewing team.",
            "quarterly_goals": [
                "Cut cycle time from ticket to deploy",
                "Raise automated test coverage",
                "Ship and review the quarterly platform roadmap",
            ],
            "human_team_size": 5,
            "domains": ["product", "engineering", "research", "ai_ops", "data"],
            "tools": ["files", "github", "notion", "docs", "web", "slack", "analytics"],
            "risk_tier": "review_external",
            "budget_tier": "medium",
            "add_amplifier": True,
            "add_observer": True,
            "use_lead": True,
        },
        archetype_overrides={
            "director_engineering": {
                "charter": "Own technical delivery and architecture: set "
                "standards, unblock engineers, and keep quality gates high."
            },
            "worker_code": {
                "charter": "Implement well-scoped changes with tests and "
                "self-review; keep the build green and the diff reviewable."
            },
            "worker_qa": {
                "charter": "Review diffs for errors, edge cases, and test "
                "coverage; demand fixes before merge."
            },
        },
    )
)


# ---------------------------------------------------------------------------
# Research & analysis
# ---------------------------------------------------------------------------
_register(
    RolePack(
        id="research",
        name="Research & Analysis",
        description="Evidence workforce: research, data, product-use, and "
        "partnership research.",
        spec={
            "org_name": "MyCo Research",
            "founder": "Founder",
            "north_star": "Produce defensible, decision-ready research that "
            "moves strategy forward.",
            "quarterly_goals": [
                "Publish the quarterly market landscape",
                "Deliver three deep-dive briefs on key questions",
                "Stand up an evidence library the company can query",
            ],
            "human_team_size": 2,
            "domains": ["research", "data", "product", "partnerships"],
            "tools": ["web", "notion", "docs", "sheets", "files", "github", "analytics"],
            "risk_tier": "review_external",
            "budget_tier": "medium",
            "add_amplifier": True,
            "add_observer": True,
            "use_lead": True,
        },
        archetype_overrides={
            "director_research": {
                "charter": "Own evidence gathering, analysis, and synthesis; "
                "deliver defensible findings that change decisions."
            },
            "worker_research": {
                "charter": "Gather, filter, and synthesize information from "
                "granted sources into concise, sourced, decision-ready briefs."
            },
        },
    )
)
# ---------------------------------------------------------------------------
# Registry access and helpers
# ---------------------------------------------------------------------------


def list_packs() -> list[RolePack]:
    """Return all registered packs, sorted by id."""
    return [PACKS[key] for key in sorted(PACKS)]


def get_pack(pack_id: str) -> RolePack:
    """Return a pack by id, or raise a helpful KeyError."""
    if pack_id not in PACKS:
        raise KeyError(f"unknown pack {pack_id!r}; available: {sorted(PACKS)}")
    return PACKS[pack_id]


def build_answers(
    pack: RolePack,
    *,
    org_name: str | None = None,
    founder: str | None = None,
    north_star: str | None = None,
) -> InterviewAnswers:
    """Build an :class:`InterviewAnswers` from a pack's spec, with CLI overrides.

    Missing required fields fall back to sensible pack defaults so
    ``bootstrap --pack <name>`` works with zero required flags.
    """
    spec = dict(pack.spec)
    if org_name or not spec.get("org_name"):
        spec["org_name"] = org_name or pack.name
    if founder or not spec.get("founder"):
        spec["founder"] = founder or "Founder"
    if north_star or not spec.get("north_star"):
        spec["north_star"] = north_star or f"{pack.name}: ship the quarter."
    return InterviewAnswers.from_dict(spec)


def overridden_archetypes(pack: RolePack) -> tuple[dict, dict, dict]:
    """Apply a pack's archetype overrides to the generic role library.

    Returns (directors, workers, addons) dicts of :class:`Archetype` instances
    with the pack's charter/tier/tool tweaks applied via ``dataclasses.replace``.
    Override keys may reference a director by its domain key OR by its archetype
    id (e.g. ``"engineering"`` or ``"director_engineering"``); worker/addon keys
    are referenced by archetype id. Unknown ids raise ValueError.
    """
    directors = dict(DIRECTORS)
    workers = dict(ALL_WORKERS)
    addons = dict(ADDONS)

    # Index both naming conventions to the (pool, key) that owns the archetype.
    index: dict[str, tuple[dict, str]] = {}
    for key, arch in directors.items():
        index[arch.id] = (directors, key)
        index[key] = (directors, key)
    for key, _ in workers.items():
        index[key] = (workers, key)
    for key, _ in addons.items():
        index[key] = (addons, key)

    for archetype_id, overrides in pack.archetype_overrides.items():
        if archetype_id not in index:
            raise ValueError(
                f"pack {pack.id!r} overrides unknown archetype {archetype_id!r}"
            )
        pool, pool_key = index[archetype_id]
        pool[pool_key] = replace(pool[pool_key], **overrides)
    return directors, workers, addons


__all__ = [
    "PACKS",
    "RolePack",
    "list_packs",
    "get_pack",
    "build_answers",
    "overridden_archetypes",
]
