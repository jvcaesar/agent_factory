"""Tests for the bounded multi-org runtime worker pool."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from _helpers import SRC  # noqa: F401

from agent_factory.config import Org, Role, ToolAccess, ToolGrant
from agent_factory.llm.fake import FakeLLM
from agent_factory.runtime import WorkerPool as ExportedWorkerPool
from agent_factory.runtime.state import Store
from agent_factory.runtime.worker import WorkerPool


class RecordingPool(WorkerPool):
    def __init__(self, *args, fail_tasks=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_tasks = set(fail_tasks or ())
        self.executed: list[tuple[str, str, int]] = []
        self.executed_lock = threading.Lock()

    def _execute_unit(self, org_key, entity_type, row, store):
        if entity_type == "job" and row["task"] in self.fail_tasks:
            raise RuntimeError(f"failed {row['task']}")
        if entity_type == "job":
            store.complete(row["id"], "done")
        else:
            store.transition_operation(row["id"], "running", "done", result="done")
        with self.executed_lock:
            self.executed.append((org_key, entity_type, row["id"]))
        self._publish(org_key, entity_type, row["id"], "done")


class TestWorkerLifecycle(unittest.TestCase):
    def setUp(self):
        self.stores = {"Acme": Store(":memory:"), "Other": Store(":memory:")}

    def tearDown(self):
        for store in self.stores.values():
            store.close()

    def pool(self, *, org_keys=None, **kwargs):
        return RecordingPool(
            org_keys or (lambda: self.stores),
            self.stores.__getitem__,
            lambda key: (None, key),
            poll_interval=0.005,
            **kwargs,
        )

    def wait_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            threading.Event().wait(0.005)
        self.fail("condition was not reached before timeout")

    def test_constructor_validates_limits(self):
        with self.assertRaisesRegex(ValueError, "size"):
            self.pool(size=0)
        with self.assertRaisesRegex(ValueError, "poll_interval"):
            RecordingPool(
                lambda: (), lambda _key: None, lambda _key: None, poll_interval=0
            )
        with self.assertRaisesRegex(ValueError, "approval_timeout"):
            self.pool(approval_timeout=-1)

    def test_start_and_stop_are_idempotent(self):
        pool = self.pool(size=2)
        pool.start()
        pool.start()
        self.assertTrue(pool.running)
        self.assertEqual(pool.worker_count, 2)
        pool.stop()
        pool.stop()
        self.assertFalse(pool.running)
        self.assertEqual(pool.worker_count, 0)

    def test_drain_finishes_queued_jobs_and_operations(self):
        job_id = self.stores["Acme"].enqueue("Acme", "worker", "task")
        operation_id = self.stores["Acme"].create_operation("Acme", "brief", {})
        pool = self.pool(size=1)
        pool.start()
        pool.stop(drain=True)
        self.assertEqual(self.stores["Acme"].get(job_id)["status"], "done")
        self.assertEqual(
            self.stores["Acme"].get_operation(operation_id)["status"], "done"
        )

    def test_claims_work_from_multiple_orgs(self):
        acme_id = self.stores["Acme"].enqueue("Acme", "worker", "acme")
        other_id = self.stores["Other"].enqueue("Other", "worker", "other")
        pool = self.pool(size=1)
        pool.start()
        self.wait_until(lambda: len(pool.executed) == 2)
        pool.stop()
        self.assertIn(("Acme", "job", acme_id), pool.executed)
        self.assertIn(("Other", "job", other_id), pool.executed)

    def test_same_operation_ids_in_different_orgs_are_isolated(self):
        acme_id = self.stores["Acme"].create_operation("Acme", "brief", {})
        other_id = self.stores["Other"].create_operation("Other", "brief", {})
        self.assertEqual(acme_id, other_id)
        pool = self.pool(size=2)
        pool.start()
        self.wait_until(lambda: len(pool.executed) == 2)
        pool.stop()
        self.assertIn(("Acme", "operation", acme_id), pool.executed)
        self.assertIn(("Other", "operation", other_id), pool.executed)

    def test_unit_failure_does_not_kill_worker(self):
        failed_id = self.stores["Acme"].enqueue("Acme", "worker", "fail")
        good_id = self.stores["Acme"].enqueue("Acme", "worker", "good")
        pool = self.pool(size=1, fail_tasks={"fail"})
        pool.start()
        self.wait_until(lambda: self.stores["Acme"].get(good_id)["status"] == "done")
        self.assertTrue(pool.running)
        pool.stop()
        self.assertEqual(self.stores["Acme"].get(failed_id)["status"], "error")
        self.assertEqual(self.stores["Acme"].get(good_id)["status"], "done")

    def test_transition_callback_receives_running_and_terminal_states(self):
        transitions = []
        job_id = self.stores["Acme"].enqueue("Acme", "worker", "task")
        pool = self.pool(size=1, on_transition=lambda *event: transitions.append(event))
        pool.start()
        self.wait_until(lambda: self.stores["Acme"].get(job_id)["status"] == "done")
        pool.stop()
        self.assertIn(("Acme", "job", job_id, "running"), transitions)
        self.assertIn(("Acme", "job", job_id, "done"), transitions)


class TestWorkerDispatch(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.lead = Role(
            id="lead_exec",
            display_name="Lead",
            title="Lead",
            charter="Lead the org.",
            sop="",
            proactivity_level=5,
            tool_grants=[],
            subagents=["worker"],
        )
        self.worker = Role(
            id="worker",
            display_name="Worker",
            title="Worker",
            charter="Do work.",
            sop="",
            proactivity_level=1,
            tool_grants=[],
            reports_to="lead_exec",
        )
        self.observer = Role(
            id="observer",
            display_name="Observer",
            title="Observer",
            charter="Observe work.",
            sop="",
            proactivity_level=1,
            tool_grants=[],
            reports_to="lead_exec",
        )
        self.org = Org(
            name="Acme",
            founder="Ada",
            north_star="Ship reliably",
            quarterly_goals=["Launch"],
            roles=[self.lead, self.worker, self.observer],
        )

    def tearDown(self):
        self.store.close()

    def wait_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            threading.Event().wait(0.005)
        self.fail("condition was not reached before timeout")

    def pool(self, llm):
        return WorkerPool(
            lambda: ["Acme"],
            lambda _key: self.store,
            lambda _key: (self.org, Path(".")),
            size=1,
            poll_interval=0.005,
            role_client=lambda _role, _provider, _model: llm,
        )

    def run_operation(self, kind, params, responses):
        operation_id = self.store.create_operation("Acme", kind, params)
        pool = self.pool(FakeLLM(responses=responses))
        pool.start()
        self.wait_until(
            lambda: self.store.get_operation(operation_id)["status"]
            in {"done", "error", "blocked", "cancelled"}
        )
        pool.stop()
        return self.store.get_operation(operation_id)

    def test_claimed_job_runs_without_enqueuing_duplicate(self):
        job_id = self.store.enqueue("Acme", "worker", "Do the task", "fake")
        pool = self.pool(FakeLLM(responses=['{"type":"final","output":"done"}']))
        pool.start()
        self.wait_until(lambda: self.store.get(job_id)["status"] == "done")
        pool.stop()
        self.assertEqual(self.store.stats()["jobs"], 1)
        self.assertEqual(self.store.get(job_id)["result"], "done")

    def test_runtime_package_exports_worker_pool(self):
        self.assertIs(ExportedWorkerPool, WorkerPool)

    def test_provider_and_model_overrides_reach_client_factory(self):
        received = []
        operation_id = self.store.create_operation(
            "Acme",
            "run",
            {
                "role": "worker",
                "task": "Do it",
                "provider": "fake",
                "model": "small-test-model",
            },
        )

        def client(role, provider, model):
            received.append((role.id, provider, model))
            return FakeLLM(responses=['{"type":"final","output":"done"}'])

        pool = WorkerPool(
            lambda: ["Acme"],
            lambda _key: self.store,
            lambda _key: (self.org, Path(".")),
            size=1,
            poll_interval=0.005,
            role_client=client,
        )
        pool.start()
        self.wait_until(lambda: self.store.get_operation(operation_id)["status"] == "done")
        pool.stop()
        self.assertEqual(received, [("worker", "fake", "small-test-model")])

    def test_run_operation_links_child_job(self):
        row = self.run_operation(
            "run",
            {"role": "worker", "task": "Do it"},
            ['{"type":"final","output":"run complete"}'],
        )
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["result"], "run complete")
        self.assertEqual(self.store.get(row["job_id"])["status"], "done")

    def test_ambition_operation_records_summary(self):
        proposals = {
            "type": "proposals",
            "proposals": [
                {
                    "title": "Draft launch brief",
                    "action": "Write the brief",
                    "rationale": "Launch",
                    "risk": "low",
                    "priority": 1,
                }
            ],
        }
        row = self.run_operation(
            "ambition",
            {"role": "lead_exec", "max_actions": 1},
            [json.dumps(proposals), '{"type":"final","output":"written"}'],
        )
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["result"], "1 action(s) executed from 1 proposal(s)")
        self.assertIsNotNone(row["job_id"])

    def test_observe_operation_uses_observer_and_persists(self):
        payload = {
            "type": "observations",
            "observations": [
                {
                    "level": "warning",
                    "kind": "blocker",
                    "title": "Blocked",
                    "detail": "Needs review",
                    "suggestion": "Review it",
                }
            ],
        }
        row = self.run_operation("observe", {}, [json.dumps(payload)])
        self.assertEqual(row["result"], "1 insight(s) recorded")
        self.assertEqual(self.store.list_insights()[0]["role"], "observer")

    def test_brief_operation_returns_text(self):
        row = self.run_operation("brief", {}, ["Do the next thing"])
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["result"], "Do the next thing")

    def test_channel_worker_operation_posts_reply(self):
        self.store.post_message("general", "human", "Ada", "Any update?")
        row = self.run_operation(
            "channel_worker",
            {"channel": "general", "max_messages": 1},
            ['{"type":"final","output":"On track"}'],
        )
        self.assertEqual(row["result"], "1 message(s) processed")
        messages = self.store.list_messages(channel="general")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "On track")


class BlockingFakeLLM(FakeLLM):
    def __init__(self, entered, release):
        super().__init__(responses=['{"type":"tool","tool":"unknown","tool_input":{}}'])
        self.entered = entered
        self.release = release

    def complete(self, messages, **kwargs):
        self.entered.set()
        if not self.release.wait(1):
            raise RuntimeError("test did not release provider call")
        return super().complete(messages, **kwargs)


class TestWorkerCancellation(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.role = Role(
            id="worker",
            display_name="Worker",
            title="Worker",
            charter="Do work.",
            sop="",
            proactivity_level=1,
            tool_grants=[],
        )
        self.org = Org(
            name="Acme",
            founder="Ada",
            north_star="Ship reliably",
            quarterly_goals=["Launch"],
            roles=[self.role],
        )

    def tearDown(self):
        self.store.close()

    def wait_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            threading.Event().wait(0.005)
        self.fail("condition was not reached before timeout")

    def test_running_operation_cancellation_blocks_child_job(self):
        entered = threading.Event()
        release = threading.Event()
        operation_id = self.store.create_operation(
            "Acme", "run", {"role": "worker", "task": "Wait"}
        )
        pool = WorkerPool(
            lambda: ["Acme"],
            lambda _key: self.store,
            lambda _key: (self.org, Path(".")),
            size=1,
            poll_interval=0.005,
            role_client=lambda _role, _provider, _model: BlockingFakeLLM(
                entered, release
            ),
        )
        pool.start()
        self.assertTrue(entered.wait(1))
        self.store.request_operation_cancel(operation_id)
        release.set()
        self.wait_until(
            lambda: self.store.get_operation(operation_id)["status"] == "cancelled"
        )
        pool.stop()
        operation = self.store.get_operation(operation_id)
        self.assertEqual(operation["error"], "cancelled")
        self.assertEqual(self.store.get(operation["job_id"])["status"], "blocked")
        self.assertEqual(self.store.get(operation["job_id"])["error"], "cancelled")


class TestWorkerApprovals(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = Store(":memory:")
        self.lead = Role(
            id="lead_exec",
            display_name="Lead",
            title="Lead",
            charter="Lead.",
            sop="",
            proactivity_level=3,
            tool_grants=[],
        )
        self.writer = Role(
            id="writer",
            display_name="Writer",
            title="Writer",
            charter="Write.",
            sop="",
            proactivity_level=1,
            tool_grants=[
                ToolGrant(
                    tool="files",
                    access=ToolAccess.WRITE,
                    requires_approval=True,
                )
            ],
            reports_to="lead_exec",
        )
        self.org = Org(
            name="Acme",
            founder="Ada",
            north_star="Ship reliably",
            quarterly_goals=["Launch"],
            roles=[self.lead, self.writer],
        )

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def wait_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            threading.Event().wait(0.005)
        self.fail("condition was not reached before timeout")

    def client_for(self, role, _provider, _model):
        if role.id == "writer":
            return FakeLLM(
                responses=[
                    json.dumps(
                        {
                            "type": "tool",
                            "tool": "files_write",
                            "tool_input": {
                                "path": "approved.txt",
                                "content": "approved",
                            },
                        }
                    ),
                    '{"type":"final","output":"writer finished"}',
                ]
            )
        return FakeLLM(responses=["brief finished"])

    def pool(self, *, size=2):
        return WorkerPool(
            lambda: ["Acme"],
            lambda _key: self.store,
            lambda _key: (self.org, self.root),
            size=size,
            poll_interval=0.005,
            role_client=self.client_for,
        )

    def test_pending_approval_does_not_block_second_worker(self):
        ask_id = self.store.create_operation(
            "Acme",
            "run",
            {
                "role": "writer",
                "task": "Write the file",
                "approval_mode": "ask",
            },
        )
        brief_id = self.store.create_operation("Acme", "brief", {})
        pool = self.pool()
        pool.start()
        self.wait_until(lambda: bool(self.store.list_approvals()))
        self.wait_until(lambda: self.store.get_operation(brief_id)["status"] == "done")
        pending = self.store.list_approvals()[0]
        self.store.resolve_approval(pending["id"], "approved")
        self.wait_until(lambda: self.store.get_operation(ask_id)["status"] == "done")
        pool.stop()
        self.assertTrue((self.root / "approved.txt").exists())

    def test_denied_approval_skips_tool_but_operation_finishes(self):
        operation_id = self.store.create_operation(
            "Acme",
            "run",
            {
                "role": "writer",
                "task": "Write the file",
                "approval_mode": "ask",
            },
        )
        pool = self.pool()
        pool.start()
        self.wait_until(lambda: bool(self.store.list_approvals()))
        pending = self.store.list_approvals()[0]
        self.store.resolve_approval(pending["id"], "denied")
        self.wait_until(lambda: self.store.get_operation(operation_id)["status"] == "done")
        pool.stop()
        self.assertFalse((self.root / "approved.txt").exists())
        self.assertEqual(self.store.get_operation(operation_id)["result"], "writer finished")

    def test_allow_mode_executes_without_pending_approval(self):
        operation_id = self.store.create_operation(
            "Acme",
            "run",
            {
                "role": "writer",
                "task": "Write the file",
                "approval_mode": "allow",
            },
        )
        pool = self.pool(size=1)
        pool.start()
        self.wait_until(lambda: self.store.get_operation(operation_id)["status"] == "done")
        pool.stop()
        self.assertEqual(self.store.list_approvals(), [])
        self.assertTrue((self.root / "approved.txt").exists())

    def test_stop_interrupts_pending_approval_with_bounded_join(self):
        operation_id = self.store.create_operation(
            "Acme",
            "run",
            {
                "role": "writer",
                "task": "Write the file",
                "approval_mode": "ask",
            },
        )
        pool = self.pool(size=1)
        pool.start()
        self.wait_until(lambda: bool(self.store.list_approvals()))
        pool.stop(timeout=1)
        self.assertFalse(pool.running)
        self.assertEqual(
            self.store.list_approvals(status="cancelled")[0]["status"],
            "cancelled",
        )
        self.assertEqual(self.store.get_operation(operation_id)["status"], "done")


if __name__ == "__main__":
    unittest.main()
