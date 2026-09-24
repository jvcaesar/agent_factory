"""Bounded background worker pool for jobs and durable operations."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable
from typing import Any

from ..config import Org, Role
from ..llm.base import LLMClient
from ..llm.factory import client_for_role
from .agent import run_agent
from .ambition import run_ambition_loop
from .approvals import store_backed_approval
from .channel import default_lead, run_channel_worker
from .insights import build_daily_brief, observe
from .state import Store

TransitionCallback = Callable[[str, str, int, str], None]
RoleClientFactory = Callable[[Role, str | None, str | None], LLMClient]


class WorkerPool:
    """Drain org-local job and operation queues with a bounded thread pool."""

    def __init__(
        self,
        org_keys: Callable[[], Iterable[str]],
        open_store: Callable[[str], Store],
        load_org: Callable[[str], tuple[Org, Any]],
        *,
        size: int = 2,
        poll_interval: float = 0.5,
        approval_timeout: float | None = None,
        on_transition: TransitionCallback | None = None,
        role_client: RoleClientFactory | None = None,
    ) -> None:
        if size < 1:
            raise ValueError("worker pool size must be at least 1")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if approval_timeout is not None and approval_timeout < 0:
            raise ValueError("approval_timeout must be non-negative or None")
        self._org_keys = org_keys
        self._open_store = open_store
        self._load_org = load_org
        self.size = size
        self.poll_interval = poll_interval
        self.approval_timeout = approval_timeout
        self._on_transition = on_transition
        self._role_client = role_client or self._default_role_client
        self._stop = threading.Event()
        self._approval_interrupt = threading.Event()
        self._state_lock = threading.Lock()
        self._schedule_lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._drain = False
        self._org_offset = 0
        self._prefer_operation = False

    @staticmethod
    def _default_role_client(
        role: Role,
        provider: str | None,
        model: str | None,
    ) -> LLMClient:
        return client_for_role(
            role,
            provider_override=provider,
            model_override=model,
        )

    @property
    def running(self) -> bool:
        with self._state_lock:
            return bool(self._threads) and all(thread.is_alive() for thread in self._threads)

    @property
    def worker_count(self) -> int:
        with self._state_lock:
            return sum(thread.is_alive() for thread in self._threads)

    def start(self) -> None:
        with self._state_lock:
            if any(thread.is_alive() for thread in self._threads):
                return
            self._threads = []
            self._stop.clear()
            self._approval_interrupt.clear()
            self._drain = False
            for index in range(self.size):
                thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"agent-factory-worker-{index + 1}",
                    daemon=True,
                )
                self._threads.append(thread)
                thread.start()

    def stop(self, *, drain: bool = False, timeout: float = 5.0) -> None:
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        with self._state_lock:
            threads = list(self._threads)
            if not threads:
                return
            self._drain = drain
            self._approval_interrupt.set()
            self._stop.set()
        for thread in threads:
            thread.join(timeout)
        alive = [thread.name for thread in threads if thread.is_alive()]
        if alive:
            raise TimeoutError(f"worker threads did not stop: {', '.join(alive)}")
        with self._state_lock:
            self._threads = []
            self._drain = False

    def _worker_loop(self) -> None:
        while True:
            if self._stop.is_set() and not self._drain:
                return
            unit = self._claim_one()
            if unit is None:
                if self._stop.is_set():
                    return
                self._stop.wait(self.poll_interval)
                continue
            org_key, entity_type, row = unit
            store = self._open_store(org_key)
            try:
                self._execute_unit(org_key, entity_type, row, store)
            except Exception as exc:
                self._record_failure(org_key, entity_type, row, store, exc)

    def _claim_one(self):
        with self._schedule_lock:
            keys = list(dict.fromkeys(self._org_keys()))
            if not keys:
                return None
            start = self._org_offset % len(keys)
            ordered = keys[start:] + keys[:start]
            self._org_offset = (start + 1) % len(keys)
            entity_order = (
                ("operation", "job") if self._prefer_operation else ("job", "operation")
            )
            self._prefer_operation = not self._prefer_operation
            for org_key in ordered:
                store = self._open_store(org_key)
                for entity_type in entity_order:
                    row = (
                        store.claim_next_operation()
                        if entity_type == "operation"
                        else store.pull_next()
                    )
                    if row is not None:
                        self._publish(org_key, entity_type, row["id"], "running")
                        return org_key, entity_type, row
            return None

    def _execute_unit(self, org_key: str, entity_type: str, row, store: Store) -> None:
        org, root = self._load_org(org_key)
        if entity_type == "job":
            self._execute_job(org_key, org, root, row, store)
            return
        self._execute_operation(org_key, org, root, row, store)

    def _execute_job(self, org_key: str, org: Org, root, row, store: Store) -> None:
        role = org.role(row["role"])
        llm = self._role_client(role, row["provider"], None)
        outcome = run_agent(
            org,
            role,
            row["task"],
            llm,
            root=root,
            approval_fn=lambda _tool, _tool_input: False,
            store=store,
            job_id=row["id"],
        )
        self._publish(org_key, "job", row["id"], "done" if outcome.finished else "blocked")

    def _execute_operation(self, org_key: str, org: Org, root, row, store: Store) -> None:
        params = json.loads(row["params"])
        provider = params.get("provider")
        model = params.get("model")

        def client_of(role: Role) -> LLMClient:
            return self._role_client(role, provider, model)

        def should_cancel() -> bool:
            return store.operation_cancel_requested(row["id"])

        def allow(_tool, _tool_input) -> bool:
            return True

        def deny(_tool, _tool_input) -> bool:
            return False

        approval_mode = params.get("approval_mode", "deny")
        if approval_mode == "allow":
            approval_fn = allow
        elif approval_mode == "ask":
            approval_fn = store_backed_approval(
                store,
                org=org_key,
                role=params.get("role") or default_lead(org).id,
                operation_id=row["id"],
                timeout=self.approval_timeout,
                should_cancel=should_cancel,
                poll_interval=self.poll_interval,
                interrupt=self._approval_interrupt,
            )
        else:
            approval_fn = deny

        result: str
        job_id = None

        if row["kind"] == "run":
            role = org.role(params["role"])
            llm = client_of(role)
            job_id = store.create_running_job(
                org.name,
                role.id,
                params["task"],
                provider=llm.name,
            )
            outcome = run_agent(
                org,
                role,
                params["task"],
                llm,
                root=root,
                approval_fn=approval_fn,
                store=store,
                job_id=job_id,
                should_cancel=should_cancel,
            )
            result = outcome.output
        elif row["kind"] == "ambition":
            role = org.role(params["role"])
            proposals, executed = run_ambition_loop(
                org,
                role,
                client_of(role),
                store,
                root=root,
                approval_fn=approval_fn,
                role_client=client_of,
                max_actions=params["max_actions"],
                max_risk=params["max_risk"],
                should_cancel=should_cancel,
            )
            job_id = executed[-1][2] if executed else None
            result = f"{len(executed)} action(s) executed from {len(proposals)} proposal(s)"
        elif row["kind"] == "observe":
            role = self._operation_role(org, params.get("role"), prefer_observer=True)
            findings = observe(
                org,
                role,
                store,
                client_of(role),
                should_cancel=should_cancel,
            )
            result = f"{len(findings)} insight(s) recorded"
        elif row["kind"] == "brief":
            role = self._operation_role(org, params.get("role"))
            result = build_daily_brief(
                org,
                role,
                store,
                client_of(role),
                should_cancel=should_cancel,
            )
        elif row["kind"] == "channel_worker":
            selected = (
                org.role(params["role"])
                if params.get("role") is not None
                else default_lead(org)
            )
            answered = run_channel_worker(
                org,
                store,
                client_of(selected),
                channel=params["channel"],
                role_resolver=lambda _message: selected,
                role_client=client_of,
                root=root,
                approval_fn=approval_fn,
                max_messages=params["max_messages"],
                should_cancel=should_cancel,
            )
            job_id = answered[-1][2] if answered else None
            result = f"{len(answered)} message(s) processed"
        else:
            raise ValueError(f"unsupported operation kind: {row['kind']!r}")

        cancelled = should_cancel()
        updated = store.transition_operation(
            row["id"],
            "running",
            "cancelled" if cancelled else "done",
            result=None if cancelled else result,
            error="cancelled" if cancelled else None,
            job_id=job_id,
        )
        if updated is None:
            raise RuntimeError(f"operation {row['id']} could not complete")
        self._publish(org_key, "operation", row["id"], updated["status"])

    @staticmethod
    def _operation_role(org: Org, role_id: str | None, *, prefer_observer: bool = False) -> Role:
        if role_id is not None:
            return org.role(role_id)
        if prefer_observer:
            for role in org.roles:
                if role.id == "observer":
                    return role
        return default_lead(org)

    def _record_failure(
        self,
        org_key: str,
        entity_type: str,
        row,
        store: Store,
        exc: Exception,
    ) -> None:
        if entity_type == "job":
            store.fail(row["id"], str(exc))
            status = "error"
        else:
            updated = store.transition_operation(
                row["id"], "running", "error", error=str(exc)
            )
            status = updated["status"] if updated is not None else "error"
        self._publish(org_key, entity_type, row["id"], status)

    def _publish(self, org_key: str, entity_type: str, entity_id: int, status: str) -> None:
        if self._on_transition is not None:
            self._on_transition(org_key, entity_type, entity_id, status)
