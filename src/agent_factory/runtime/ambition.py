"""M2 — The ambition loop ("do smart things").

A proactive work loop for the lead (or any role with ``proactivity_level >= 3``):

1. **Propose** — look across goals + captured context + granted tools and
   propose high-value net-new actions (the generalized "do smart things").
2. **Execute** — dispatch each accepted proposal to an appropriate worker via
   the existing :func:`~agent_factory.runtime.agent.run_agent`, so the same
   approval ceiling and tool grants still apply.
3. **Learn** — record the outcome back into the context store so the next loop
   builds on what has already been done.

Scope widens (more breadth to initiate work), but risk does not: risky actions
still require approval through the normal gate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config import Org, Role
from ..llm.base import ChatMessage, LLMClient
from .agent import run_agent
from .state import Store
from .tools import tools_for_role

RISK_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass
class Proposal:
    title: str
    action: str
    rationale: str = ""
    risk: str = "medium"
    priority: int = 5

    def slug(self) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return s[:48] or "proposal"


def _extract_json(text: str) -> Optional[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def parse_proposals(text: str) -> list[Proposal]:
    """Parse the model's proposal response into a list of :class:`Proposal`."""
    data = _extract_json(text)
    if not data:
        return []
    raw = data.get("proposals", [])
    if not isinstance(raw, list):
        return []
    proposals = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).strip()
        if not action:
            continue
        risk = str(item.get("risk", "medium")).lower()
        if risk not in RISK_ORDER:
            risk = "medium"
        proposals.append(
            Proposal(
                title=str(item.get("title", action[:40])).strip() or action[:40],
                action=action,
                rationale=str(item.get("rationale", "")).strip(),
                risk=risk,
                priority=int(item.get("priority", 5) or 5),
            )
        )
    proposals.sort(key=lambda p: p.priority)
    return proposals


def _propose_prompt(org: Org, role: Role, tools: list, context_text: str, max_candidates: int) -> str:
    tool_lines = [f"- {t.name}: {t.description}" for t in tools] or ["- (none granted)"]
    goals = "\n".join(f"- {g}" for g in org.quarterly_goals) or "(none defined)"
    return f"""You are {role.title} (role `{role.id}`) in the workforce "{org.name}".

You are licensed to INITIATE net-new work on your own (proactivity level {role.proactivity_level}).

NORTH STAR
{org.north_star}

QUARTERLY TARGETS
{goals}

CAPTURED CONTEXT (diary / prior results — the company should stay queryable)
{context_text or "(no context captured yet)"}

YOUR GRANTED TOOLS (propose only actions that can use these)
{tool_lines}

TASK
Look across the goals and context and propose up to {max_candidates} high-value
proactive actions. Prefer actions that (a) advance a quarterly target and (b)
can actually be executed with the granted tools by a worker. Rank by priority
(1 = most valuable).

Respond with EXACTLY ONE JSON object and no other prose:
{{"type": "proposals", "proposals": [
  {{"title": "<short title>", "action": "<concrete task a worker should do>",
    "rationale": "<why it moves a goal forward>", "risk": "low|medium|high", "priority": 1}}
]}}"""
def propose_actions(
    org: Org,
    role: Role,
    llm: LLMClient,
    context_text: str,
    *,
    max_candidates: int = 5,
    temperature: float = 0.3,
) -> list[Proposal]:
    """Propose net-new actions for a role. Returns [] if the role isn't proactive enough."""
    if role.proactivity_level < 3:
        return []
    tools = tools_for_role(role)
    messages = [ChatMessage("user", _propose_prompt(org, role, tools, context_text, max_candidates))]
    result = llm.complete(messages, temperature=temperature)
    return parse_proposals(result.text)


def _pick_worker(org: Org, role: Role) -> Role:
    """Choose a worker under ``role`` to execute a proposal, or the role itself."""
    for sub in role.subagents:
        try:
            return org.role(sub)
        except KeyError:
            continue
    return role


def run_ambition_loop(
    org: Org,
    role: Role,
    llm: LLMClient,
    store: Store,
    *,
    root: Optional[Path] = None,
    approval_fn=None,
    max_candidates: int = 5,
    max_actions: int = 2,
    max_risk: str = "medium",
    temperature: float = 0.2,
):
    """Run one full ambition pass. Returns (proposals, executed).

    ``executed`` is a list of (Proposal, AgentOutcome, job_id). Proposals above
    ``max_risk`` are skipped without execution.
    """
    context_text = store.context_blob()
    proposals = propose_actions(org, role, llm, context_text, max_candidates=max_candidates)

    executed = []
    for proposal in proposals[:max_actions]:
        if RISK_ORDER.get(proposal.risk, 2) > RISK_ORDER.get(max_risk, 2):
            store.upsert_context(
                f"ambition/skipped-{proposal.slug()}",
                f"[proposed: {proposal.title}]\nrisk={proposal.risk} exceeds max_risk={max_risk} — not executed.",
                source="ambition",
            )
            continue
        worker = _pick_worker(org, role)
        job_id = store.enqueue(org.name, worker.id, proposal.action, provider=llm.name)
        outcome = run_agent(
            org,
            worker,
            proposal.action,
            llm,
            root=root,
            approval_fn=approval_fn,
            store=store,
            job_id=job_id,
            temperature=temperature,
        )
        store.upsert_context(
            f"ambition/{proposal.slug()}",
            f"[{proposal.title}]\nACTION: {proposal.action}\nRESULT: {outcome.output}",
            source="ambition",
        )
        executed.append((proposal, outcome, job_id))

    return proposals, executed

