"""Integration tests for the agent loop, driven by a deterministic FakeLLM."""

import json
import pathlib
import tempfile
import unittest

from _helpers import SRC  # noqa: F401

from agent_factory.config import Org, Role, ToolAccess, ToolGrant
from agent_factory.llm.fake import FakeLLM
from agent_factory.runtime.agent import AgentLimitError, parse_action, run_agent
from agent_factory.runtime.orchestrator import run_job
from agent_factory.runtime.state import Store


def action(**data):
    return json.dumps(data)


def tool_call(name, tool_input):
    return json.dumps({"type": "tool", "tool": name, "tool_input": tool_input})


def make_org(role):
    return Org(
        name="Acme",
        founder="Ada",
        north_star="Ship great things",
        quarterly_goals=["Launch v1"],
        roles=[role],
    )


ROLE_READ = Role(
    id="worker_research_1",
    display_name="Research Worker",
    title="Research Worker",
    charter="Gather and synthesize information.",
    sop="",
    proactivity_level=2,
    tool_grants=[ToolGrant(tool="files", access=ToolAccess.READ)],
)

ROLE_WRITE = Role(
    id="worker_write_1",
    display_name="Content Worker",
    title="Content Worker",
    charter="Draft content.",
    sop="",
    proactivity_level=2,
    tool_grants=[ToolGrant(tool="files", access=ToolAccess.WRITE, requires_approval=True)],
)


class TestParseAction(unittest.TestCase):
    def test_final(self):
        a = parse_action('{"type": "final", "output": "hello"}')
        self.assertEqual(a.kind, "final")
        self.assertEqual(a.output, "hello")

    def test_tool(self):
        a = parse_action('{"type": "tool", "tool": "files_read", "tool_input": {"path": "x"}}')
        self.assertEqual(a.kind, "tool")
        self.assertEqual(a.tool, "files_read")
        self.assertEqual(a.tool_input, {"path": "x"})

    def test_fenced_json(self):
        a = parse_action('```json\n{"type": "final", "output": "ok"}\n```')
        self.assertEqual(a.kind, "final")
        self.assertEqual(a.output, "ok")

    def test_plain_text_falls_back_to_final(self):
        a = parse_action("Just a normal sentence.")
        self.assertEqual(a.kind, "final")
        self.assertEqual(a.output, "Just a normal sentence.")

    def test_invalid_tool_input_is_recoverable(self):
        a = parse_action('{"type":"tool","tool":"files_read","tool_input":"bad"}')
        self.assertEqual(a.kind, "tool")
        self.assertEqual(a.tool, "")
        self.assertEqual(a.tool_input, {})


class TestRunAgent(unittest.TestCase):
    def test_final_direct(self):
        store = Store(":memory:")
        org = make_org(ROLE_READ)
        jid = store.enqueue("Acme", ROLE_READ.id, "task", "fake")
        llm = FakeLLM(responses=[action(type="final", output="answer")])
        out = run_agent(org, ROLE_READ, "task", llm, store=store, job_id=jid)
        self.assertTrue(out.finished)
        self.assertEqual(out.output, "answer")
        # job recorded done
        row = store.get(jid)
        self.assertEqual(row["status"], "done")
        store.close()

    def test_tool_then_final(self):
        tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(tmp.name)
        probe = root / "note.txt"
        probe.write_text("hi", encoding="utf-8")
        llm = FakeLLM(
            responses=[
                tool_call("files_read", {"path": "note.txt"}),
                action(type="final", output="saw it"),
            ]
        )
        out = run_agent(make_org(ROLE_READ), ROLE_READ, "task", llm, root=root, max_steps=5)
        self.assertTrue(out.finished)
        self.assertEqual(out.output, "saw it")
        self.assertEqual(out.steps, 2)
        self.assertTrue(any("tool_call" in e for e in out.events))
        tmp.cleanup()

    def test_approval_denied_blocks_tool(self):
        tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(tmp.name)
        target = root / "out.txt"
        llm = FakeLLM(
            responses=[
                tool_call("files_write", {"path": str(target), "content": "secret"}),
                action(type="final", output="stopped"),
            ]
        )
        # approval_fn -> False (auto-deny)
        out = run_agent(make_org(ROLE_WRITE), ROLE_WRITE, "task", llm, root=root, max_steps=5)
        self.assertTrue(out.finished)
        self.assertTrue(any("approval" in e and "denied" in e for e in out.events))
        self.assertFalse(target.exists(), "tool must not execute when approval denied")
        tmp.cleanup()

    def test_approval_allowed_executes_tool(self):
        tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(tmp.name)
        target = root / "out.txt"
        llm = FakeLLM(
            responses=[
                tool_call("files_write", {"path": "out.txt", "content": "hello"}),
                action(type="final", output="wrote it"),
            ]
        )
        out = run_agent(
            make_org(ROLE_WRITE), ROLE_WRITE, "task", llm, root=root,
            approval_fn=lambda _t: True, max_steps=5,
        )
        self.assertTrue(out.finished)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "hello")
        tmp.cleanup()

    def test_unknown_tool_errors_but_recovers(self):
        llm = FakeLLM(
            responses=[
                tool_call("rm_rf", {}),
                action(type="final", output="recovered"),
            ]
        )
        out = run_agent(make_org(ROLE_READ), ROLE_READ, "task", llm, max_steps=5)
        self.assertTrue(out.finished)
        self.assertTrue(any("unknown" in e for e in out.events))

    def test_max_steps_exceeded_raises(self):
        llm = FakeLLM(responses=[tool_call("files_read", {})] * 10)
        with self.assertRaises(AgentLimitError):
            run_agent(make_org(ROLE_READ), ROLE_READ, "task", llm, max_steps=2)

    def test_failed_run_marks_job_error(self):
        class FailingLLM(FakeLLM):
            def complete(self, messages, **kwargs):
                raise RuntimeError("provider unavailable")

        store = Store(":memory:")
        with self.assertRaises(RuntimeError):
            run_job(
                make_org(ROLE_READ), ROLE_READ, "task", FailingLLM(), store
            )
        job_id = store.list_jobs()[0]["id"]
        self.assertEqual(store.get(job_id)["status"], "error")
        self.assertIn("provider unavailable", store.get(job_id)["error"])
        store.close()


if __name__ == "__main__":
    unittest.main()
