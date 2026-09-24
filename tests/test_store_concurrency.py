"""Concurrency coverage for the SQLite runtime Store."""

from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _helpers import SRC  # noqa: F401

from agent_factory.runtime.state import Store


class TestStoreConcurrency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp_dir.name) / "jobs.db")

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_file_store_uses_wal(self):
        mode = self.store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

    def test_concurrent_writers_and_readers_share_state(self):
        writer_count = 6
        jobs_per_writer = 20
        barrier = threading.Barrier(writer_count + 2)

        def write_jobs(writer: int):
            barrier.wait()
            return [
                self.store.enqueue("Acme", f"worker-{writer}", f"task-{index}")
                for index in range(jobs_per_writer)
            ]

        def read_jobs():
            barrier.wait()
            observed = 0
            while observed < writer_count * jobs_per_writer:
                observed = max(observed, self.store.stats()["jobs"])
            return observed

        with ThreadPoolExecutor(max_workers=writer_count + 2) as executor:
            writers = [executor.submit(write_jobs, writer) for writer in range(writer_count)]
            readers = [executor.submit(read_jobs) for _ in range(2)]
            ids = [job_id for future in writers for job_id in future.result()]
            observed = [future.result() for future in readers]

        self.assertEqual(len(ids), writer_count * jobs_per_writer)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(observed, [len(ids), len(ids)])
        self.assertEqual(self.store.stats()["queued"], len(ids))

    def test_competing_claims_return_each_job_once(self):
        expected = {
            self.store.enqueue("Acme", "worker", f"task-{index}") for index in range(80)
        }
        claimed: list[int] = []
        claimed_lock = threading.Lock()

        def drain_queue():
            local: list[int] = []
            while True:
                row = self.store.pull_next()
                if row is None:
                    break
                local.append(row["id"])
                self.store.complete(row["id"], "done")
            with claimed_lock:
                claimed.extend(local)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(drain_queue) for _ in range(8)]
            for future in futures:
                future.result()

        self.assertEqual(set(claimed), expected)
        self.assertEqual(len(claimed), len(expected))
        self.assertEqual(self.store.stats()["done"], len(expected))

    def test_running_child_job_is_not_claimable(self):
        running_id = self.store.create_running_job("Acme", "worker", "owned")
        queued_id = self.store.enqueue("Acme", "worker", "queued")

        claimed = self.store.pull_next()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], queued_id)
        self.assertEqual(self.store.get(running_id)["status"], "running")
        self.assertIsNone(self.store.pull_next())

    def test_in_memory_store_is_visible_across_threads(self):
        store = Store(":memory:")
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                job_id = executor.submit(
                    store.enqueue, "Acme", "worker", "threaded"
                ).result()
                row = executor.submit(store.get, job_id).result()
            self.assertIsNotNone(row)
            self.assertEqual(row["task"], "threaded")
        finally:
            store.close()

    def test_close_is_idempotent_and_rejects_new_work(self):
        self.store.close()
        self.store.close()
        with self.assertRaisesRegex(RuntimeError, "store is closed"):
            self.store.list_jobs()


if __name__ == "__main__":
    unittest.main()
