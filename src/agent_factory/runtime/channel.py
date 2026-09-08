"""M6 — the shared human↔agent channel (the "Loop Alley" pattern).

A durable, Slack-style channel living in the :class:`~agent_factory.runtime.state.Store`
where human teammates and agent roles talk in one thread:

1. a human posts a message into ``#general`` (any channel id), optionally
   addressed to a specific role;
2. a **channel worker** claims the oldest pending message, lets the answering
   role (the requested role, an explicit resolver, or the org lead) process it
   through the normal :func:`~agent_factory.runtime.agent.run_agent` loop —
   same tool grants and approval gates as any other job;
3. the agent's final answer is posted back into the same channel as a reply,
   so the human never has to wait in a private queue.

Every step is durable in SQLite, so a second worker or a restart can safely
continue where the last one stopped (pending -> running -> done transitions are
atomic).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config import Org, Role
from ..llm.base import LLMClient
from .agent import AgentOutcome, run_agent
from .state import Store
from .tools import ApprovalFn


@dataclass(frozen=True)
class Message:
    """One durable message in a shared channel (as returned by the worker)."""

    id: int
    channel: str
    author_role: str  # 'human' or a role id
    author: str
    content: str
    status: str = "pending"
    requested_role: str | None = None
    reply_to: int | None = None


def post_to_channel(
    store: Store,
    channel: str,
    content: str,
    *,
    author_role: str = "human",
    author: str = "human",
    requested_role: str | None = None,
    reply_to: int | None = None,
) -> int:
    """Post a message from a human (or agent) into the shared channel."""
    return store.post_message(
        channel,
        author_role,
        author,
        content,
        requested_role=requested_role,
        reply_to=reply_to,
    )


def list_channel(store: Store, channel: str = "general", limit: int = 50) -> list:
    """Newest-first listing of a channel's conversation."""
    return store.list_messages(channel=channel, limit=limit)


def channel_blob(store: Store, channel: str = "general", limit: int = 30) -> str:
    """Flatten recent channel traffic into a prompt-friendly text block."""
    return store.channel_blob(channel=channel, limit=limit)


def default_lead(org: Org) -> Role:
    """The role at the top of the org (nothing reports to it), or the first role."""
    for role in org.roles:
        if role.reports_to is None:
            return role
    return org.roles[0]


def _resolve_role(org: Org, message: dict, resolver: Callable[[dict], Role | None] | None) -> Role:
    requested = message["requested_role"]
    if requested:
        try:
            return org.role(requested)
        except KeyError:
            pass
    if resolver is not None:
        resolved = resolver(message)
        if resolved is not None:
            return resolved
    return default_lead(org)


def run_channel_worker(
    org: Org,
    store: Store,
    llm: LLMClient,
    *,
    channel: str = "general",
    role_resolver: Callable[[dict], Role | None] | None = None,
    role_client: Callable[[Role], LLMClient] | None = None,
    root: Path | None = None,
    approval_fn: ApprovalFn | None = None,
    max_messages: int = 5,
    temperature: float = 0.2,
) -> list[tuple[dict, AgentOutcome, int]]:
    """Process pending channel messages and post an agent reply for each.

    ``role_resolver`` may force/override which role answers each message;
    ``role_client`` (optional) picks a per-role model/provider client, in the
    same shape as :func:`~agent_factory.runtime.ambition.run_ambition_loop`.

    Returns a list of ``(message_row, outcome, job_id)`` for every answered
    message. Messages are claimed atomically, so overlapping workers never
    answer the same message twice.
    """
    client_of = role_client or (lambda _r: llm)
    answered: list[tuple[dict, AgentOutcome, int]] = []

    for _ in range(max_messages):
        message = store.claim_next_in_channel(channel)
        if message is None:
            break
        role = _resolve_role(org, dict(message), role_resolver)
        role_llm = client_of(role)
        task = (
            f"A human teammate posted this into the shared channel #{channel}:\n\n"
            f"{message['content']}\n\n"
            "Answer it directly, taking whatever granted-tool actions are useful. "
            "Finish with a 'final' answer that will be posted back to the channel."
        )
        job_id = store.enqueue(
            org.name, role.id, f"channel reply: {message['content'][:60]}", provider=role_llm.name
        )
        if not store.start(job_id):
            raise RuntimeError(f"could not start channel reply job {job_id}")
        outcome = run_agent(
            org,
            role,
            task,
            role_llm,
            root=root,
            approval_fn=approval_fn,
            store=store,
            job_id=job_id,
            temperature=temperature,
        )
        store.post_message(
            channel,
            author_role=role.id,
            author=f"{role.title} ({role.id})",
            content=outcome.output,
            reply_to=message["id"],
            status="done",
        )
        store.complete_message(message["id"])
        answered.append((dict(message), outcome, job_id))

    return answered
