"""Tests for the SQLite-backed job state store (offline)."""

import pathlib
import tempfile
import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.runtime.state import Store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name) / "jobs.db"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_enqueue_and_get(self):
        jid = self.store.enqueue("Acme", "worker_research_1", "Do a thing", "fake")
        row = self.store.get(jid)
        self.assertIsNotNone(row)
        self.assertEqual(row["role"], "worker_research_1")
        self.assertEqual(row["status"], "queued")

    def test_pull_next_claims_running(self):
        jid = self.store.enqueue("Acme", "w", "t", "fake")
        pulled = self.store.pull_next()
        self.assertEqual(pulled["id"], jid)
        self.assertEqual(self.store.get(jid)["status"], "running")

    def test_pull_next_empty_when_all_processed(self):
        jid = self.store.enqueue("Acme", "w", "t", "fake")
        self.store.pull_next()
        self.store.complete(jid, "ok")
        self.assertIsNone(self.store.pull_next())

    def test_complete_and_results(self):
        jid = self.store.enqueue("Acme", "w", "t", "fake")
        self.store.pull_next()
        self.store.complete(jid, "the answer")
        self.store.add_result(jid, "w", "the answer")
        self.assertEqual(self.store.get(jid)["status"], "done")
        self.assertEqual(len(self.store.results_for(jid)), 1)

    def test_fail_and_block(self):
        jid = self.store.enqueue("Acme", "w", "t", "fake")
        self.store.fail(jid, "boom")
        self.assertEqual(self.store.get(jid)["status"], "error")

        jid2 = self.store.enqueue("Acme", "w", "t", "fake")
        self.store.block(jid2, "needs human")
        self.assertEqual(self.store.get(jid2)["status"], "blocked")

    def test_list_jobs_filter(self):
        for i in range(3):
            self.store.enqueue("Acme", "w", f"t{i}", "fake")
        self.assertEqual(len(self.store.list_jobs(status="queued")), 3)
        self.assertEqual(len(self.store.list_jobs(status="done")), 0)

    def test_events(self):
        jid = self.store.enqueue("Acme", "w", "t", "fake")
        self.store.add_event(jid, "tool_call", "files_read({})")
        evs = self.store.events_for(jid)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["type"], "tool_call")

    def test_in_memory_works(self):
        mem = Store(":memory:")
        jid = mem.enqueue("Acme", "w", "t", "fake")
        self.assertIsNotNone(mem.get(jid))
        mem.close()


if __name__ == "__main__":
    unittest.main()
