"""Interview flow and structured answers for the bootstrap.

Supports two paths:
  * interactive  — numbered menus / free text via ``ask``/``confirm`` callables
  * ``--spec``   — the same answers come from a YAML dict (drives tests)

Both produce the same :class:`InterviewAnswers` so generation logic never
depends on how answers were gathered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..config import ApprovalPolicy

# A minimal prompt function shaped like input() so interactive and CLI agree.
AskFn = Callable[[str, str], str]  # (question, default) -> answer
ConfirmFn = Callable[[str, bool], bool]  # (question, default) -> bool
ChoiceFn = Callable[[str, list[str], Optional[str]], str]  # (q, options, default) -> selection


@dataclass
class InterviewAnswers:
    org_name: str
    founder: str
    north_star: str
    quarterly_goals: list[str]
    human_team_size: int
    domains: list[str]  # keys into DIRECTORS
    tools: set[str] = field(default_factory=set)
    risk_tier: ApprovalPolicy = ApprovalPolicy.REVIEW_EXTERNAL
    budget_tier: str = "medium"  # small | medium | unlimited
    add_amplifier: bool = False
    add_observer: bool = False
    use_lead: bool = False

    def to_dict(self) -> dict:
        return {
            "org_name": self.org_name,
            "founder": self.founder,
            "north_star": self.north_star,
            "quarterly_goals": self.quarterly_goals,
            "human_team_size": self.human_team_size,
            "domains": self.domains,
            "tools": sorted(self.tools),
            "risk_tier": self.risk_tier.value,
            "budget_tier": self.budget_tier,
            "add_amplifier": self.add_amplifier,
            "add_observer": self.add_observer,
            "use_lead": self.use_lead,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InterviewAnswers":
        if not isinstance(d, dict):
            raise ValueError("interview spec must be a mapping")

        def boolean(name: str, default: bool = False) -> bool:
            value = d.get(name, default)
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
            return value

        def integer(name: str, default: int = 0) -> int:
            value = d.get(name, default)
            if isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
            try:
                return int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            org_name=str(d.get("org_name", "")),
            founder=str(d.get("founder", "")),
            north_star=str(d.get("north_star", "")),
            quarterly_goals=[str(g) for g in d.get("quarterly_goals", [])],
            human_team_size=integer("human_team_size"),
            domains=[str(x) for x in d.get("domains", [])],
            tools=set(str(x) for x in d.get("tools", [])),
            risk_tier=ApprovalPolicy(d.get("risk_tier", "review_external")),
            budget_tier=str(d.get("budget_tier", "medium")),
            add_amplifier=boolean("add_amplifier"),
            add_observer=boolean("add_observer"),
            use_lead=boolean("use_lead"),
        )

    def validate(self) -> list[str]:
        """Light sanity checks before generation; full checks happen via Org."""
        errors: list[str] = []
        if not self.org_name.strip():
            errors.append("org_name is required")
        if not self.north_star.strip():
            errors.append("north_star is required")
        if not self.domains:
            errors.append("select at least one domain")
        for d in self.domains:
            if d not in _directors_map():
                errors.append(f"unknown domain {d!r}")
        if self.budget_tier not in ("small", "medium", "unlimited"):
            errors.append(f"unknown budget_tier {self.budget_tier!r}")
        if self.quarterly_goals and any(not g.strip() for g in self.quarterly_goals):
            errors.append("goals may not be empty strings")
        return errors


# Lazily import to keep this module dependency-light and avoid import cost.
def _directors_map():
    from .archetypes import DIRECTORS

    return DIRECTORS
