"""Tests for durable operations and their schema migration."""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _helpers import SRC  # noqa: F401

from agent_factory.runtime.state import Store


class TestOperationMigration(unittest.TestCase):
    def test_v1_database_migrates_without_changing_existing_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jobs.db"
            store = Store(path)
            job_id = store.enqueue("Acme", "worker", "preserve me", "fake")
            store.close()

            connection = sqlite3.connect(path)
            connection.execute("DROP TABLE approvals")
            connection.execute("DROP TABLE operations")
            connection.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
            connection.commit()
            connection.close()

            migrated = Store(path)
            try:
                self.assertEqual(migrated.schema_version(), 3)
                self.assertEqual(migrated.get(job_id)["task"], "preserve me")
                table = migrated._conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='operations'"
                ).fetchone()
                self.assertIsNotNone(table)
                indexes = {
                    row["name"]
                    for row in migrated._conn.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='index' AND tbl_name='operations'"
                    ).fetchall()
                }
                self.assertIn("idx_operations_status_id", indexes)
                self.assertIn("idx_operations_org_status_id", indexes)
            finally:
                migrated.close()


class TestOperationStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_create_applies_defaults_and_canonical_json(self):
        operation_id = self.store.create_operation(
            "Acme",
            "run",
            {"task": "Do it", "role": "worker"},
        )
        row = self.store.get_operation(operation_id)
        self.assertEqual(row["kind"], "run")
        self.assertEqual(row["status"], "queued")
        self.assertEqual(
            row["params"],
            '{"approval_mode":"deny","model":null,"provider":null,'
            '"role":"worker","task":"Do it"}',
        )

    def test_create_rejects_invalid_kind_and_params(self):
        with self.assertRaisesRegex(ValueError, "invalid operation kind"):
            self.store.create_operation("Acme", "unknown", {})
        with self.assertRaisesRegex(ValueError, "requires non-empty 'role'"):
            self.store.create_operation("Acme", "run", {"task": "Do it"})
        with self.assertRaisesRegex(ValueError, "unknown run operation params"):
            self.store.create_operation(
                "Acme", "run", {"role": "worker", "task": "Do it", "extra": True}
            )
        with self.assertRaisesRegex(ValueError, "approval_mode"):
            self.store.create_operation(
                "Acme",
                "run",
                {"role": "worker", "task": "Do it", "approval_mode": "maybe"},
            )

    def test_list_filters_by_org_and_status(self):
        acme_id = self.store.create_operation("Acme", "brief", {})
        self.store.create_operation("Other", "brief", {})
        claimed = self.store.claim_next_operation()
        self.assertEqual(claimed["id"], acme_id)
        self.assertEqual(len(self.store.list_operations(org="Acme")), 1)
        self.assertEqual(len(self.store.list_operations(status="running")), 1)
        self.assertEqual(len(self.store.list_operations(org="Other", status="queued")), 1)

    def test_transition_is_guarded_by_source_status(self):
        operation_id = self.store.create_operation("Acme", "brief", {})
        claimed = self.store.claim_next_operation()
        self.assertEqual(claimed["id"], operation_id)
        done = self.store.transition_operation(
            operation_id, "running", "done", result="brief text"
        )
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["result"], "brief text")
        self.assertIsNone(
            self.store.transition_operation(operation_id, "running", "error", error="late")
        )
        with self.assertRaisesRegex(ValueError, "invalid operation transition"):
            self.store.transition_operation(operation_id, "done", "running")

    def test_request_cancel_handles_queued_and_running(self):
        queued_id = self.store.create_operation("Acme", "brief", {})
        queued = self.store.request_operation_cancel(queued_id)
        self.assertEqual(queued["status"], "cancelled")
        self.assertTrue(self.store.operation_cancel_requested(queued_id))

        running_id = self.store.create_operation("Acme", "brief", {})
        self.store.claim_next_operation()
        running = self.store.request_operation_cancel(running_id)
        self.assertEqual(running["status"], "running")
        self.assertTrue(self.store.operation_cancel_requested(running_id))

    def test_claim_returns_oldest_eligible_operation_once(self):
        first = self.store.create_operation("Acme", "brief", {})
        second = self.store.create_operation("Acme", "brief", {})
        self.assertEqual(self.store.claim_next_operation()["id"], first)
        self.assertEqual(self.store.claim_next_operation()["id"], second)
        self.assertIsNone(self.store.claim_next_operation())

    def test_all_operation_kinds_apply_locked_defaults(self):
        cases = {
            "run": {"role": "worker", "task": "Do it"},
            "ambition": {"role": "lead"},
            "observe": {},
            "brief": {},
            "channel_worker": {"channel": "general"},
        }
        for kind, params in cases.items():
            with self.subTest(kind=kind):
                operation_id = self.store.create_operation("Acme", kind, params)
                row = self.store.get_operation(operation_id)
                self.assertEqual(row["kind"], kind)
                self.assertTrue(row["params"].startswith("{"))

    def test_cancelled_queued_operation_is_never_claimed(self):
        cancelled_id = self.store.create_operation("Acme", "brief", {})
        eligible_id = self.store.create_operation("Acme", "brief", {})
        self.store.request_operation_cancel(cancelled_id)

        claimed = self.store.claim_next_operation()

        self.assertEqual(claimed["id"], eligible_id)
        self.assertEqual(self.store.get_operation(cancelled_id)["status"], "cancelled")

    def test_running_cancel_can_transition_to_cancelled(self):
        operation_id = self.store.create_operation("Acme", "brief", {})
        self.store.claim_next_operation()
        self.store.request_operation_cancel(operation_id)

        cancelled = self.store.transition_operation(
            operation_id, "running", "cancelled", error="cancelled"
        )

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["error"], "cancelled")
        self.assertIsNone(self.store.request_operation_cancel(operation_id))

    def test_missing_rows_and_invalid_filters_are_explicit(self):
        self.assertIsNone(self.store.get_operation(999))
        self.assertIsNone(self.store.request_operation_cancel(999))
        self.assertFalse(self.store.operation_cancel_requested(999))
        with self.assertRaisesRegex(ValueError, "invalid operation status"):
            self.store.list_operations(status="mystery")
        with self.assertRaisesRegex(ValueError, "limit must be positive"):
            self.store.list_operations(limit=0)

    def test_competing_claimers_return_each_operation_once(self):
        expected = {
            self.store.create_operation("Acme", "brief", {}) for _ in range(80)
        }
        claimed: list[int] = []
        claimed_lock = threading.Lock()

        def drain_operations():
            local: list[int] = []
            while True:
                row = self.store.claim_next_operation()
                if row is None:
                    break
                local.append(row["id"])
                self.store.transition_operation(row["id"], "running", "done", result="ok")
            with claimed_lock:
                claimed.extend(local)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(drain_operations) for _ in range(8)]
            for future in futures:
                future.result()

        self.assertEqual(set(claimed), expected)
        self.assertEqual(len(claimed), len(expected))
        self.assertEqual(len(self.store.list_operations(status="done")), len(expected))


if __name__ == "__main__":
    unittest.main()
