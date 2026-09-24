"""High-level job orchestration used by the CLI.

Enqueues a job in the durable store, then runs the assigned role to completion
and records the result. The pull-based queue already supports simple
serial execution here; a future worker pool can consume jobs via ``pull_next``.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Org, Role
from ..llm.base import LLMClient
from .agent import run_agent
from .state import Store
from .tools import ApprovalFn


def run_job(
    org: Org,
    role: Role,
    task: str,
    llm: LLMClient,
    store: Store,
    *,
    root: Path | None = None,
    approval_fn: ApprovalFn | None = None,
    max_steps: int = 8,
    temperature: float = 0.2,
    provider: str | None = None,
):
    """Create a running job on ``role`` and execute it. Returns (job_id, outcome)."""
    job_id = store.create_running_job(org.name, role.id, task, provider)
    outcome = run_agent(
        org,
        role,
        task,
        llm,
        root=root,
        approval_fn=approval_fn,
        max_steps=max_steps,
        temperature=temperature,
        store=store,
        job_id=job_id,
    )
    return job_id, outcome
