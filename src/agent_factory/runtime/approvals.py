"""Durable approval callbacks backed by the runtime Store."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping

from .state import Store
from .tools import ApprovalFn, Tool


def store_backed_approval(
    store: Store,
    *,
    org: str,
    role: str,
    job_id: int | None = None,
    operation_id: int | None = None,
    risk_of: Callable[[Tool], str] | None = None,
    timeout: float | None = None,
    should_cancel: Callable[[], bool] | None = None,
    poll_interval: float = 0.5,
    interrupt: threading.Event | None = None,
) -> ApprovalFn:
    """Create an ApprovalFn that persists and waits for a human decision."""
    if timeout is not None and timeout < 0:
        raise ValueError("timeout must be non-negative or None")
    if poll_interval <= 0:
        raise ValueError("poll_interval must be positive")
    resolve_risk = risk_of or (lambda tool: tool.risk)
    wake = interrupt or threading.Event()

    def approve(tool: Tool, tool_input: Mapping[str, object]) -> bool:
        approval_id = store.create_approval(
            org,
            role,
            tool.name,
            tool_input,
            risk=resolve_risk(tool),
            job_id=job_id,
            operation_id=operation_id,
        )
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            row = store.get_approval(approval_id)
            if row is None:
                return False
            if row["status"] != "pending":
                return row["status"] == "approved"
            if should_cancel is not None and should_cancel():
                store.cancel_approval(approval_id)
                return False
            if wake.is_set():
                store.cancel_approval(approval_id)
                return False
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    store.expire_approval(approval_id)
                    return False
                wake.wait(min(poll_interval, remaining))
            else:
                wake.wait(poll_interval)

    return approve
