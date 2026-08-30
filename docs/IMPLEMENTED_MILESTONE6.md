# Milestone 6 — Multiplayer & Tool Surface · Implemented

> Current step (M6) — human teammates talk to the workforce through a shared
> channel ("Loop Alley", video 23:56), and the tool surface widens with
> store-backed `memory`/`channel` adapters, MCP-style local tool servers, and
> risk-aware permission rules. `Store` and `tools.CATALOG` are the extension
> points this milestone stretches.

## 1. What this milestone delivers

- **Shared human↔agent channel** — a durable, Slack-style channel in the
  store. A human posts a message (optionally addressed to a role); a channel
  worker lets the answering role process it through the *normal* agent loop
  (same tools grants, approvals, job ledger), and the agent's final answer is
  posted back into the same channel as a reply. Nobody waits in a private queue.
- **Store-backed local tools** — `memory` (read/search/write over the durable
  context store — "the company stays queryable") and `channel` (read/post over
  the shared channel). Both work offline and need no third-party service.
- **MCP-style local tool servers** — a `ToolServer` contract (describe your
  tools, execute by name) plus `register_tool_server()`, so any local/third
  party tool surface grafts onto the existing grant + approval system.
- **Risk-aware permissions** — every `Tool` carries a `risk` (low/medium/high);
  `approval_needed()` is now the single, testable decision rule
  (grant gate > approval-first > write/high-risk under review-external >
  high-risk under autonomous / defense-in-depth).
- **Channel tools wired into bootstrap** — `memory` and `channel` are new
  known tools; selecting them grants the lead (and research workers) real
  adapters instead of stubs.

## 2. New code

- `src/agent_factory/runtime/channel.py` — `Message`, `post_to_channel()`,
  `list_channel()`, `channel_blob()`, `default_lead()`, `run_channel_worker()`.
- `src/agent_factory/runtime/toolservers.py` — `ServerTool`, `ToolServer`
  protocol, `server_tools()`, `register_tool_server()` (+`REGISTERED_SERVERS`).
- `src/agent_factory/runtime/tools.py` — `Tool.risk` (+`with_risk`),
  `RISK_ORDER`, `approval_needed()`, `_resolve_spec()` (read/write lists),
  store-backed `_store_tools()` (memory/channel adapters).
- `src/agent_factory/runtime/state.py` — `messages` table + `post_message` /
  `claim_next_in_channel` / `claim_message` / `complete_message` /
  `list_messages` / `pending_messages` / `channel_blob`; `stats()` gains
  `pending_messages`.
- `src/agent_factory/runtime/agent.py` + `ambition.py` — thread the `Store`
  into `tools_for_role` so agents inside jobs see the live memory/channel tools.
- `src/agent_factory/cli.py` — `channel post|list|worker`; `status` now shows
  pending channel messages.
- `src/agent_factory/bootstrap/{archetypes,generator}.py` — `memory`/`channel`
  in `KNOWN_TOOLS`, granted to the lead / research workers when selected.

## 3. The channel protocol

```text
human posts ──> #general (pending, optional -> role id)
                    │  run_channel_worker claims it (pending->running, atomic)
                    ▼
          answering role: run_agent()  (tools + approvals + job ledger)
                    │
                    ▼
          reply posted back ──> #general (author = role, status done)
```

A second worker or a restart never double-answers a message: the
`pending -> running -> done` transitions are atomic in SQLite.

## 4. Usage

```bash
# A human teammate asks the workforce something (Loop Alley)
agent_factory channel post --org orgs/Acme \
    --text "Did the large financial services client respond to my email?" \
    --role lead_exec

# See the conversation (newest first)
agent_factory channel list --org orgs/Acme

# Run the channel worker: agents answer pending messages in-channel
agent_factory channel worker --org orgs/Acme --provider fake

# Mission control now also reports pending channel messages
agent_factory status --org orgs/Acme
```

MCP-style servers attach to any role grant without editing the catalog:

```python
from agent_factory.runtime import register_tool_server, server_tools

# any object with tool_descriptors() + execute_tool() — a local MCP server
register_tool_server("notion_lite", my_local_server)   # grants of "notion_lite" now resolve
```

## 5. Test coverage

Added `tests/test_runtime_channel.py` and `tests/test_runtime_toolservers.py`.
Combined suite is now **143 tests, all offline / green**:

```bash
python -m unittest discover -s tests
```

Covers: the message store (post/list, atomic claim, complete, stats, blob,
channel isolation), the worker (reply posted in-channel, addressed roles,
resolver override, unknown-role fallback to lead, max-messages budget, jobs
ledger), the CLI surface (`channel post/list/worker`), risk-based approval
rules (grant gate, approval-first, autonomous medium-write vs high-risk,
review-external writes + high-risk reads), memory/channel adapters (round
trip, store-missing errors, approval behavior), and MCP-style servers (prefix
wrapping, registry resolution through grants, per-grant overrides, approval
gating).

## 6. Verified end-to-end (fake provider)

```bash
agent_factory bootstrap --pack engineering --name "M6 Smoke" --out orgs/_m6_smoke
agent_factory channel post   --org orgs/_m6_smoke --text "..." --role lead_exec
agent_factory channel list   --org orgs/_m6_smoke
agent_factory channel worker --org orgs/_m6_smoke --provider fake
agent_factory channel list   --org orgs/_m6_smoke   # human msg done + agent reply
```