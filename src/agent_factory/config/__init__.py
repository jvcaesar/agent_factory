"""Configuration schema for agent workforces.

The data model is intentionally generic: it describes *any* agent workforce
rather than a specific org. Every later milestone (runtime, ambition loop,
observers, role packs) consumes this schema, so it is the contract that the
whole factory builds on.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator

_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ApprovalPolicy(Enum):
    """How much human sign-off this role needs before acting."""

    AUTONOMOUS = "autonomous"  # acts on its own within granted tools
    REVIEW_EXTERNAL = "review_external"  # auto-internal, approve external/risky
    APPROVAL_FIRST = "approval_first"  # propose and wait before acting


class ModelTier(Enum):
    """Budget tiers: how expensive reasoning is allowed to be."""

    FAST = "fast"  # cheap, quick, high-volume sub-agents
    SMART = "smart"  # mid reasoning for domain directors
    BIG = "big"  # most capable, used sparingly for orchestration/amplify


class ToolAccess(Enum):
    READ = "read"
    WRITE = "write"


class ToolGrant(BaseModel):
    """A single tool grant: which tool, at what access, and any approval gate."""

    tool: str = Field(..., min_length=1, description="Tool id, e.g. 'notion'.")
    access: ToolAccess = ToolAccess.READ
    requires_approval: bool = False


class Role(BaseModel):
    """One agent role in the workforce.

    ``proactivity_level`` is the generalized "pyramid of proactivity":
        0 - only does what it is directly told
        1 - completes assigned tasks
        2 - finishes tasks, surfaces follow-ups
        3 - proposes new tasks / goals-aware
        4 - initiates new work, reports tradeoffs
        5 - self-directs new work and reports rollback + next steps
    """

    id: str = Field(..., pattern=_ID_RE.pattern)
    display_name: str
    title: str = Field(..., description="Job title, e.g. 'Director of Marketing'.")
    charter: str = Field(..., min_length=3)
    sop: str
    proactivity_level: int = Field(ge=0, le=5)
    model_tier: ModelTier = ModelTier.SMART
    provider: str | None = Field(
        default=None,
        description="Optional per-role LLM provider ('openai'|'ollama'|'fake'). Defaults to the global provider (env AGENT_FACTORY_PROVIDER).",
    )
    model: str | None = Field(
        default=None,
        description="Optional per-role model override. Defaults to the model resolved from model_tier + env.",
    )
    approval_policy: ApprovalPolicy = ApprovalPolicy.AUTONOMOUS
    reports_to: str | None = None
    tool_grants: list[ToolGrant] = Field(default_factory=list)
    subagents: list[str] = Field(default_factory=list, description="Worker archetype ids this role fans out to.")

    _KNOWN_PROVIDERS: ClassVar[set[str]] = {"openai", "ollama", "fake"}

    @field_validator("provider")
    @classmethod
    def _provider_must_be_known(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = (v or "").strip().lower()
        if v not in cls._KNOWN_PROVIDERS:
            raise ValueError(f"unknown provider {v!r} (expected openai | ollama | fake)")
        return v

    @field_validator("reports_to", "id")
    @classmethod
    def _must_be_canonical_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not isinstance(v, str) or not _ID_RE.fullmatch(v):
            raise ValueError(f"invalid id: {v!r}")
        return v

    @field_validator("subagents")
    @classmethod
    def _subagents_must_be_ids(cls, v: list[str]) -> list[str]:
        for item in v:
            if not isinstance(item, str) or not _ID_RE.fullmatch(item):
                raise ValueError(f"invalid subagent id: {item!r}")
        return v


class Org(BaseModel):
    """Top-level workforce definition."""

    name: str = Field(..., min_length=1)
    founder: str
    north_star: str = Field(..., min_length=3)
    human_team_size: int = Field(0, ge=0)
    quarterly_goals: list[str] = Field(default_factory=list)
    risk_tier: ApprovalPolicy = ApprovalPolicy.REVIEW_EXTERNAL
    budget_tier: Literal["small", "medium", "unlimited"] = "medium"
    roles: list[Role]

    def role(self, role_id: str) -> Role:
        for r in self.roles:
            if r.id == role_id:
                return r
        raise KeyError(f"no role with id {role_id!r}")

    def dependencies_of(self, role_id: str) -> list[Role]:
        """Roles that report, directly or transitively, to ``role_id``."""
        lookup = {r.id: r for r in self.roles}
        result: list[Role] = []
        stack = list(lookup[role_id].subagents)
        seen: set[str] = set()
        while stack:
            rid = stack.pop()
            if rid in seen or rid not in lookup:
                continue
            seen.add(rid)
            result.append(lookup[rid])
            stack.extend(lookup[rid].subagents)
        return result
