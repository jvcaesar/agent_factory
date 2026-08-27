"""The agent loop: turns a Role + task + LLM into a completed job.

Design goals:
  * Provider-agnostic: the loop only talks to :class:`LLMClient`; the model
    responds in a small JSON "action protocol" (``final`` or ``tool``).
  * Deterministic and offline-testable via :class:`FakeLLM`.
  * Every tool call is validated against the role's grants and gated by
    ``requires_approval`` through an approval callback.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..config import Org, Role
from ..llm.base import ChatMessage, LLMClient
from .state import Store
from .tools import ApprovalFn, Tool, lookup, tools_for_role
from .protocol import extract_json_object


@dataclass
class Action:
    kind: str  # "final" | "tool"
    output: str = ""
    tool: str = ""
    tool_input: dict = field(default_factory=dict)


@dataclass
class AgentOutcome:
    finished: bool
    output: str = ""
    steps: int = 0
    events: list[str] = field(default_factory=list)


class AgentLimitError(Exception):
    """Raised when the agent exceeds its step budget."""


def _read_sop(root: Optional[Path], role: Role) -> str:
    if root is None or not role.sop:
        return ""
    p = Path(root) / role.sop
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_system_prompt(org: Org, role: Role, tools: list[Tool], sop_text: str = "") -> str:
    goals = "\n".join(f"- {g}" for g in org.quarterly_goals) or "- (define targets at next goal review)"
    tool_lines = []
    for t in tools:
        approval = " (REQUIRES APPROVAL)" if t.requires_approval else " (no approval)"
        tool_lines.append(f"- {t.name}{approval}: {t.description}")
    tool_block = "\n".join(tool_lines) if tool_lines else "- (none granted)"

    proactivity = {
        0: "Only does exactly what it is told.",
        1: "Completes assigned tasks as specified.",
        2: "Finishes assigned tasks and surfaces follow-ups.",
        3: "Proposes new tasks; is goals-aware.",
        4: "Initiates new high-value work and reports tradeoffs.",
        5: "Self-directs new work and reports rollback + next steps.",
    }.get(role.proactivity_level, "Acts within its role.")

    return f"""You are {role.title} (role `{role.id}`) in the AI workforce "{org.name}".

NORTH STAR
{org.north_star}

QUARTERLY TARGETS
{goals}

PROACTIVITY (level {role.proactivity_level})
{proactivity}

STANDARD OPERATING PROCEDURE
{sop_text or "(no SOP file on disk; rely on your charter and goals.)"}

YOUR GRANTED TOOLS — use ONLY these:
{tool_block}

APPROVAL RULE
Any tool marked "REQUIRES APPROVAL" is blocked until a human approves. You must
NOT assume approval. If you need an approved tool, call it anyway; the runtime
will either approve or deny and tell you the result.

ROLE CHARTER
{role.charter}

ACTION PROTOCOL
Respond with EXACTLY ONE JSON object and no other prose. Two shapes:

For returning the final answer:
{{"type": "final", "output": "<your answer>"}}

For calling a tool:
{{"type": "tool", "tool": "<tool_name>", "tool_input": {{"key": "value"}}}}

Never invent tool names that are not in YOUR GRANTED TOOLS."""
def parse_action(text: str) -> Action:
    data = extract_json_object(text)
    if not isinstance(data, dict):
        # Not parseable as an action protocol message -> treat text as final.
        return Action(kind="final", output=text)
    kind = data.get("type", "final")
    if kind == "tool":
        tool_input = data.get("tool_input") or {}
        if not isinstance(tool_input, Mapping):
            return Action(kind="tool", tool="", tool_input={})
        return Action(
            kind="tool",
            tool=str(data.get("tool", "")),
            tool_input=dict(tool_input),
        )
    return Action(kind="final", output=str(data.get("output") or data.get("answer") or text))


def run_agent(
    org: Org,
    role: Role,
    task: str,
    llm: LLMClient,
    *,
    root: Optional[Path] = None,
    approval_fn: Optional[ApprovalFn] = None,
    max_steps: int = 8,
    temperature: float = 0.2,
    store: Optional[Store] = None,
    job_id: Optional[int] = None,
) -> AgentOutcome:
    """Run one role to completion. Returns an :class:`AgentOutcome`."""
    tools = tools_for_role(role, root=root, org=org)
    deny_all: ApprovalFn = approval_fn or (lambda _t: False)
    system = build_system_prompt(org, role, tools, _read_sop(root, role))
    messages: list[ChatMessage] = [ChatMessage("system", system), ChatMessage("user", task)]
    outcome = AgentOutcome(finished=False, events=[])

    def _event(type_: str, detail: str) -> None:
        outcome.events.append(f"[{type_}] {detail}")
        if store is not None and job_id is not None:
            store.add_event(job_id, type_, detail)

    try:
        for step in range(max_steps):
            result = llm.complete(messages, temperature=temperature)
            action = parse_action(result.text)
            outcome.steps = step + 1

            if action.kind == "final":
                outcome.finished = True
                outcome.output = action.output
                if store is not None and job_id is not None:
                    store.complete(job_id, action.output)
                    store.add_result(job_id, role.id, action.output)
                return outcome

            # Tool call
            tool = lookup(tools, action.tool)
            if tool is None:
                _event("error", f"agent requested unknown/un-granted tool {action.tool!r}")
                messages.append(ChatMessage("user", f"Tool {action.tool!r} is not in your granted tools. Re-answer with a 'final' or an allowed tool."))
                continue

            if tool.requires_approval:
                approved = deny_all(tool)
                if not approved:
                    _event("approval", f"denied approval for {tool.name}")
                    messages.append(ChatMessage("user", f"Your call to {tool.name} was NOT approved. Do not retry it; end with a 'final' answer instead."))
                    continue

            _event("tool_call", f"{tool.name}({action.tool_input})")
            try:
                output = tool.execute(action.tool_input)
            except Exception as exc:
                output = f"ERROR executing {tool.name}: {exc}"
            messages.append(ChatMessage("user", f"Tool {tool.name} returned:\n{output}"))

        raise AgentLimitError(
            f"agent for role {role.id!r} exceeded {max_steps} steps without a final answer"
        )
    except Exception as exc:
        if store is not None and job_id is not None:
            store.fail(job_id, str(exc))
        raise

