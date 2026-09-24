"""Tests for durable approvals and their schema migration."""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _helpers import SRC  # noqa: F401

from agent_factory.runtime import store_backed_approval as exported_approval
from agent_factory.runtime.approvals import store_backed_approval
from agent_factory.runtime.state import Store
from agent_factory.runtime.tools import Tool


class TestApprovalMigration(unittest.TestCase):
    def _downgrade(self, path: Path, version: int) -> None:
        connection = sqlite3.connect(path)
        connection.execute("DROP TABLE approvals")
        if version == 1:
            connection.execute("DROP TABLE operations")
        connection.execute(
            "UPDATE meta SET value=? WHERE key='schema_version'", (str(version),)
        )
        connection.commit()
        connection.close()

    def test_v2_database_migrates_to_v3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jobs.db"
            store = Store(path)
            operation_id = store.create_operation("Acme", "brief", {})
            store.close()
            self._downgrade(path, 2)

            migrated = Store(path)
            try:
                self.assertEqual(migrated.schema_version(), 3)
                self.assertEqual(migrated.get_operation(operation_id)["kind"], "brief")
                table = migrated._conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='approvals'"
                ).fetchone()
                self.assertIsNotNone(table)
            finally:
                migrated.close()

    def test_v1_database_runs_chained_migrations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jobs.db"
            store = Store(path)
            job_id = store.enqueue("Acme", "worker", "preserve", "fake")
            store.close()
            self._downgrade(path, 1)

            migrated = Store(path)
            try:
                self.assertEqual(migrated.schema_version(), 3)
                self.assertEqual(migrated.get(job_id)["task"], "preserve")
                names = {
                    row["name"]
                    for row in migrated._conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("operations", names)
                self.assertIn("approvals", names)
            finally:
                migrated.close()


class TestApprovalStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_create_get_and_list_use_canonical_arguments(self):
        approval_id = self.store.create_approval(
            "Acme",
            "worker",
            "files_write",
            {"path": "out.txt", "content": "hello"},
            risk="high",
        )
        row = self.store.get_approval(approval_id)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["action_args"], '{"content":"hello","path":"out.txt"}')
        self.assertEqual([item["id"] for item in self.store.list_approvals(org="Acme")], [approval_id])
        self.assertEqual(self.store.list_approvals(org="Other"), [])

    def test_resolve_is_pending_only(self):
        approval_id = self.store.create_approval(
            "Acme", "worker", "files_write", {}, risk="high"
        )
        approved = self.store.resolve_approval(
            approval_id, "approved", decided_by="operator"
        )
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["decided_by"], "operator")
        self.assertIsNotNone(approved["decided_at"])
        self.assertIsNone(self.store.resolve_approval(approval_id, "denied"))
        self.assertFalse(self.store.expire_approval(approval_id))
        self.assertFalse(self.store.cancel_approval(approval_id))

    def test_expire_and_cancel_are_distinct(self):
        expired_id = self.store.create_approval(
            "Acme", "worker", "files_write", {}, risk="high"
        )
        cancelled_id = self.store.create_approval(
            "Acme", "worker", "files_write", {}, risk="high"
        )
        self.assertTrue(self.store.expire_approval(expired_id))
        self.assertTrue(self.store.cancel_approval(cancelled_id))
        self.assertEqual(self.store.get_approval(expired_id)["status"], "expired")
        self.assertEqual(self.store.get_approval(cancelled_id)["status"], "cancelled")

    def test_foreign_key_links_are_preserved(self):
        job_id = self.store.create_running_job("Acme", "worker", "task")
        operation_id = self.store.create_operation("Acme", "run", {"role": "worker", "task": "task"})
        approval_id = self.store.create_approval(
            "Acme",
            "worker",
            "files_write",
            {},
            risk="high",
            job_id=job_id,
            operation_id=operation_id,
        )
        row = self.store.get_approval(approval_id)
        self.assertEqual(row["job_id"], job_id)
        self.assertEqual(row["operation_id"], operation_id)

    def test_invalid_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid approval risk"):
            self.store.create_approval("Acme", "worker", "tool", {}, risk="extreme")
        approval_id = self.store.create_approval(
            "Acme", "worker", "tool", {}, risk="low"
        )
        with self.assertRaisesRegex(ValueError, "approval decision"):
            self.store.resolve_approval(approval_id, "maybe")
        with self.assertRaisesRegex(ValueError, "invalid approval status"):
            self.store.list_approvals(status="unknown")

    def test_competing_decisions_have_one_winner(self):
        approval_id = self.store.create_approval(
            "Acme", "worker", "tool", {}, risk="high"
        )
        barrier = threading.Barrier(3)

        def decide(decision):
            barrier.wait()
            return self.store.resolve_approval(approval_id, decision)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(decide, value) for value in ("approved", "denied")]
            barrier.wait()
            results = [future.result() for future in futures]
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertIn(self.store.get_approval(approval_id)["status"], {"approved", "denied"})

    def test_resolve_expire_cancel_race_has_one_winner(self):
        approval_id = self.store.create_approval(
            "Acme", "worker", "tool", {}, risk="high"
        )
        barrier = threading.Barrier(4)

        def transition(action):
            barrier.wait()
            return action()

        actions = (
            lambda: self.store.resolve_approval(approval_id, "approved") is not None,
            lambda: self.store.expire_approval(approval_id),
            lambda: self.store.cancel_approval(approval_id),
        )
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(transition, action) for action in actions]
            barrier.wait()
            results = [future.result() for future in futures]

        self.assertEqual(sum(results), 1)
        self.assertIn(
            self.store.get_approval(approval_id)["status"],
            {"approved", "expired", "cancelled"},
        )


class TestStoreBackedApproval(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.tool = Tool(
            name="files_write",
            description="write a file",
            func=lambda _args: "ok",
            requires_approval=True,
            risk="high",
        )

    def tearDown(self):
        self.store.close()

    def _wait_for_pending(self):
        for _ in range(100):
            rows = self.store.list_approvals()
            if rows:
                return rows[0]
            threading.Event().wait(0.005)
        self.fail("approval did not become pending")

    def _start_callback(self, callback, tool_input):
        result = []
        thread = threading.Thread(
            target=lambda: result.append(callback(self.tool, tool_input)),
            daemon=True,
        )
        thread.start()
        return thread, result

    def test_approved_decision_returns_true(self):
        callback = store_backed_approval(
            self.store, org="Acme", role="worker", poll_interval=0.005
        )
        thread, result = self._start_callback(callback, {"path": "out.txt"})
        pending = self._wait_for_pending()
        self.store.resolve_approval(pending["id"], "approved", decided_by="Ada")
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [True])
        self.assertEqual(self.store.get_approval(pending["id"])["status"], "approved")

    def test_runtime_package_exports_callback(self):
        self.assertIs(exported_approval, store_backed_approval)

    def test_invalid_wait_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timeout"):
            store_backed_approval(
                self.store, org="Acme", role="worker", timeout=-1
            )
        with self.assertRaisesRegex(ValueError, "poll_interval"):
            store_backed_approval(
                self.store, org="Acme", role="worker", poll_interval=0
            )

    def test_denied_decision_returns_false(self):
        callback = store_backed_approval(
            self.store, org="Acme", role="worker", poll_interval=0.005
        )
        thread, result = self._start_callback(callback, {})
        pending = self._wait_for_pending()
        self.store.resolve_approval(pending["id"], "denied")
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [False])
        self.assertEqual(self.store.get_approval(pending["id"])["status"], "denied")

    def test_timeout_expires_approval(self):
        callback = store_backed_approval(
            self.store,
            org="Acme",
            role="worker",
            timeout=0.02,
            poll_interval=0.005,
        )
        self.assertFalse(callback(self.tool, {}))
        self.assertEqual(self.store.list_approvals(status="expired")[0]["status"], "expired")

    def test_operation_cancellation_cancels_approval(self):
        cancelled = threading.Event()
        callback = store_backed_approval(
            self.store,
            org="Acme",
            role="worker",
            should_cancel=cancelled.is_set,
            poll_interval=0.005,
        )
        thread, result = self._start_callback(callback, {})
        self._wait_for_pending()
        cancelled.set()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [False])
        self.assertEqual(self.store.list_approvals(status="cancelled")[0]["status"], "cancelled")

    def test_interrupt_cancels_wait_without_operation_cancel(self):
        interrupt = threading.Event()
        callback = store_backed_approval(
            self.store,
            org="Acme",
            role="worker",
            interrupt=interrupt,
            poll_interval=0.5,
        )
        thread, result = self._start_callback(callback, {})
        self._wait_for_pending()
        interrupt.set()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [False])
        self.assertEqual(self.store.list_approvals(status="cancelled")[0]["status"], "cancelled")

if __name__ == "__main__":
    unittest.main()
