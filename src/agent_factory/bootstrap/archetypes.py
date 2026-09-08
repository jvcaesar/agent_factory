"""Generic role archetypes.

These are *functions* a company might need, not people. Each archetype
carries a default charter, proactivity level, model tier, approval posture,
and the worker sub-agents it fans out to. The bootstrap generator instantiates
these with concrete org-specific values.

The set is deliberately broader than any single company so the same engine can
produce a business-operations, engineering, or research org.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import ApprovalPolicy, ModelTier, ToolAccess, ToolGrant


@dataclass(frozen=True)
class Archetype:
    """Static description of a role function (not yet an instance)."""

    id: str
    title: str
    charter: str
    proactivity: int
    model_tier: ModelTier = ModelTier.SMART
    approval_policy: ApprovalPolicy = ApprovalPolicy.AUTONOMOUS
    default_workers: tuple[str, ...] = ()
    tool_scope: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()

    def grants(self, tools: set[str]) -> list[ToolGrant]:
        """Build tool grants from the tools the user actually has."""
        grants: list[ToolGrant] = []
        for t in self.tool_scope:
            if t in tools:
                grants.append(ToolGrant(tool=t, access=ToolAccess.READ))
        for t in self.write_scope:
            if t in tools:
                grants.append(
                    ToolGrant(
                        tool=t,
                        access=ToolAccess.WRITE,
                        requires_approval=self.approval_policy != ApprovalPolicy.AUTONOMOUS,
                    )
                )
        return grants


# Tools the bootstrap can grant (the union of everything the runtime may expose).
KNOWN_TOOLS: set[str] = {
    "notion",
    "gmail",
    "calendar",
    "slack",
    "stripe",
    "supabase",
    "github",
    "files",
    "web",
    "sheets",
    "docs",
    "crm",
    "cms",
    "payments",
    "analytics",
    "memory",   # M6: company-memory read/search/write (durable context store)
    "channel",  # M6: shared human<->agent channel read/post
}

WORKER_RESEARCH = Archetype(
    id="worker_research",
    title="Research Worker",
    charter="Gather, filter, and synthesize information from granted sources into concise, sourced briefs.",
    proactivity=1,
    model_tier=ModelTier.FAST,
    tool_scope=("web", "notion", "docs", "files", "sheets", "memory", "channel"),
)

WORKER_WRITE = Archetype(
    id="worker_write",
    title="Content Worker",
    charter="Draft, edit, and polish on-brand written output from briefs and direction.",
    proactivity=2,
    model_tier=ModelTier.FAST,
    tool_scope=("docs", "files", "cms"),
    write_scope=("docs", "cms"),
)

WORKER_QA = Archetype(
    id="worker_qa",
    title="Quality Worker",
    charter="Review agent output against a rubric, catch errors and tone drift, and request fixes.",
    proactivity=2,
    model_tier=ModelTier.SMART,
    tool_scope=("docs", "files"),
)

WORKER_CODE = Archetype(
    id="worker_code",
    title="Engineering Worker",
    charter="Implement well-scoped changes, write tests, and keep the codebase building.",
    proactivity=1,
    model_tier=ModelTier.SMART,
    tool_scope=("files", "github"),
    write_scope=("files", "github"),
)
_t: dict[str, Archetype] = {
    "product": Archetype(
        id="director_product",
        title="Director of Product",
        charter="Own the product vision and roadmap; convert goals into shipped outcomes.",
        proactivity=4,
        default_workers=("worker_research", "worker_write", "worker_qa"),
        tool_scope=("notion", "docs", "analytics", "files", "web"),
        write_scope=("notion", "docs"),
    ),
    "engineering": Archetype(
        id="director_engineering",
        title="Director of Engineering",
        charter="Own technical delivery: architecture, implementation, review, and quality.",
        proactivity=3,
        default_workers=("worker_code", "worker_qa"),
        tool_scope=("github", "files", "notion", "docs"),
        write_scope=("github", "files"),
    ),
    "research": Archetype(
        id="director_research",
        title="Director of Research",
        charter="Own evidence gathering, analysis, and synthesis; deliver defensible findings.",
        proactivity=4,
        default_workers=("worker_research", "worker_write", "worker_qa"),
        tool_scope=("web", "notion", "docs", "sheets", "files"),
        write_scope=("docs", "sheets"),
    ),
    "marketing": Archetype(
        id="director_marketing",
        title="Director of Marketing",
        charter="Own brand, demand generation, and go-to-market; turn goals into audience outcomes.",
        proactivity=4,
        default_workers=("worker_write", "worker_research", "worker_qa"),
        tool_scope=("cms", "analytics", "crm", "slack", "docs"),
        write_scope=("cms", "docs", "slack"),
    ),
    "finance": Archetype(
        id="director_finance",
        title="Director of Finance",
        charter="Own budgeting, margins, and unit economics; keep spending aligned to goals.",
        proactivity=3,
        model_tier=ModelTier.SMART,
        default_workers=("worker_research", "worker_qa"),
        tool_scope=("sheets", "stripe", "payments", "files"),
        write_scope=("sheets",),
    ),
    "operations": Archetype(
        id="director_operations",
        title="Director of Operations",
        charter="Own processes and back-office work; reduce friction and keep systems running.",
        proactivity=3,
        default_workers=("worker_research", "worker_qa"),
        tool_scope=("files", "sheets", "calendar", "crm", "slack"),
        write_scope=("sheets", "files", "calendar"),
    ),
    "support": Archetype(
        id="director_support",
        title="Director of Customer Success",
        charter="Own triage, customer success, and feedback; turn signals into product input.",
        proactivity=3,
        default_workers=("worker_research", "worker_write", "worker_qa"),
        tool_scope=("crm", "gmail", "slack", "docs", "notion"),
        write_scope=("crm", "gmail", "slack"),
    ),
    "data": Archetype(
        id="director_data",
        title="Director of Data & Insights",
        charter="Own metrics, anomaly detection, and insight; tell people what to do next, not just show numbers.",
        proactivity=4,
        default_workers=("worker_research", "worker_qa"),
        tool_scope=("analytics", "sheets", "notion", "docs", "web"),
        write_scope=("docs", "sheets"),
    ),
    "partnerships": Archetype(
        id="director_partnerships",
        title="Director of Partnerships",
        charter="Own business development, alliances, and distribution channels.",
        proactivity=4,
        default_workers=("worker_research", "worker_write"),
        tool_scope=("web", "crm", "gmail", "docs"),
        write_scope=("crm", "gmail"),
    ),
    "people": Archetype(
        id="director_people",
        title="Director of People & Learning",
        charter="Own learning material, skilling, onboarding, and org culture context.",
        proactivity=3,
        default_workers=("worker_research", "worker_write", "worker_qa"),
        tool_scope=("docs", "notion", "files"),
        write_scope=("docs", "notion"),
    ),
    "ai_ops": Archetype(
        id="director_ai_ops",
        title="Director of Agent Operations",
        charter="Run the factory itself: monitor the fleet, resolve friction, manage access and evals.",
        proactivity=5,
        model_tier=ModelTier.BIG,
        default_workers=("worker_research", "worker_qa"),
        tool_scope=("files", "notion", "docs", "github", "slack"),
        write_scope=("notion", "docs", "github"),
    ),
}

# Optional "add-on" roles offered after the directors are chosen.
ADDONS: dict[str, Archetype] = {
    "amplifier": Archetype(
        id="amplifier",
        title="Amplifier",
        charter="Take promising net-new output and push it up a notch: bigger ambition, better framing.",
        proactivity=5,
        model_tier=ModelTier.BIG,
        tool_scope=("docs", "notion", "files"),
    ),
    "observer": Archetype(
        id="observer",
        title="Observer",
        charter="Watch the workforce for friction, access gaps, and contradictions; log findings and suggestions.",
        proactivity=4,
        model_tier=ModelTier.FAST,
        tool_scope=("files", "notion", "docs", "github"),
    ),
}

# Entry-path helpers so the CLI can ask about archetypes in plain terms.
DIRECTORS: dict[str, Archetype] = dict(_t)
ALL_WORKERS: dict[str, Archetype] = {
    a.id: a
    for a in (WORKER_RESEARCH, WORKER_WRITE, WORKER_QA, WORKER_CODE)
}

DOMAIN_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (key, a.title) for key, a in DIRECTORS.items()
)

