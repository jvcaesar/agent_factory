# Plan: Dashboard Backend Enablement — Runtime changes for the Management Console

> **Companion document:** [WEB_CONSOLE_PLAN.md](WEB_CONSOLE_PLAN.md) (the FastAPI API + React
> SPA that consume the primitives built here). **This document lands first.**

This plan covers the **engine-level** changes that make the runtime ready to be *managed* from
a web dashboard: concurrent-safe state, a durable **operations** model for long-running LLM
actions, a durable **approvals** model for interactive approve/deny, cooperative cancellation,
and a **bounded worker pool** that executes work off the request path.

None of this depends on FastAPI, Node, or any web code. Every phase is pure Python, exercised
by the existing stdlib `unittest` suite, and each phase ends with the offline suite green. It
maps to the "After 1.0 → Multi-process state and execution" items already anticipated in
[ROADMAP.md](../../planning/ROADMAP.md), scoped to a single local host.

## Why this is a separate document

The web console is a *consumer* of the runtime. The runtime changes here are independently
valuable, independently testable, and riskier (they touch the core `Store`, agent loop, and
approval gate). Keeping them separate means they can be reviewed and merged as a foundation
**before** any web code exists, and the web plan can then treat these primitives as "ground
truth reused" exactly like it already treats `generate_org()` / `Store`.

**Delivery order:** `B1 → B2 → B3 → B4 → B5`. The web plan's Phase 1 needs **B1**, its Phase 2
needs **B2 + B5**, and its Phase 3 needs **B4**.

## Design decisions (locked)

- **Worker concurrency = bounded pool (Option B).** A pool of `N` worker threads (default `2`,
  configurable) drains queued jobs and operations. **All writes are serialized** through a
  single write path in `Store`; readers use SQLite WAL. The pool is bounded (not single) so an
  operation that is *blocked waiting for a human approval* parks on its own worker thread
  without stalling other queued work.
- **Approvals v1 = durable pending record + block-and-wait.** When the agent loop hits a tool
  that requires approval, a `store_backed_approval` callback writes a durable `approvals` row
  and **blocks that worker thread** until a human resolves it (or it times out / is cancelled).
  True agent-loop suspend/resume (checkpoint + resume without holding a thread) is explicitly
  deferred.
- **No behavior change for existing CLI flows.** `run`, `ambition`, `observe`, `brief`, and
  `channel worker` keep working exactly as today when driven from the CLI; the new pieces are
  additive and opt-in.

## Ground truth reused (do not reimplement)

- `Store` (SQLite) — [state.py](../../../src/agent_factory/runtime/state.py). Single connection,
  `_tx()` transaction wrapper, atomic `pull_next()` / `claim_next_in_channel()`, job lifecycle
  `queued → running → done|error|blocked`. Extend it; do not fork it.
- `run_agent(...)` — [agent.py](../../../src/agent_factory/runtime/agent.py). Takes
  `approval_fn: ApprovalFn | None`; the gate is `if tool.requires_approval: approved =
  deny_all(tool)` where `deny_all = approval_fn or (lambda _t: False)`. The step loop is
  `for step in range(max_steps)`. This is the injection point for cancellation and durable
  approvals.
- `run_job(...)` — [orchestrator.py](../../../src/agent_factory/runtime/orchestrator.py). Already
  does `enqueue → start → run_agent`; its docstring anticipates "a future worker pool can
  consume jobs via `pull_next`". The pool in **B5** is that worker.
- `ApprovalFn`, `approval_needed()`, `RISK_ORDER` — [tools.py](../../../src/agent_factory/runtime/tools.py).
- `run_ambition_loop()` — [ambition.py](../../../src/agent_factory/runtime/ambition.py);
  observer/brief entry points — [insights.py](../../../src/agent_factory/runtime/insights.py);
  channel worker — [channel.py](../../../src/agent_factory/runtime/channel.py). The pool dispatches
  to these by operation `kind`.
- Provider/model resolution — reuse the same helper `cmd_run` uses in
  [cli.py](../../../src/agent_factory/cli.py) to build an `LLMClient` from a job/operation's
  `provider`/`model` + environment. Do not duplicate provider-selection logic.

## Execution model for AI agents

- Each task is scoped to a small, independently verifiable diff (one concern). Tasks marked
  **[P]** in the same phase have no dependency on each other.
- Tasks are numbered `<phase>.<task>` (e.g. `B2.2`). "Depends on" references these IDs.
- Every task ends with its own verification step — run it before marking the task done.
- **Progress tracking:** update the row in the [Progress Tracking](#progress-tracking) table to
  `In Progress` before starting, `Done` (with a note) immediately after its verification passes,
  or `Blocked` (with why) if stuck. This table is the single source of truth for "what's done".
- **Keep the offline suite green:** after every task, `py -m unittest discover -s tests -v`
  must pass with no network and no API keys, and `ruff check` must be clean.
- **Commit per task**, referencing the task ID (e.g. `runtime: add operations table (task B2.1)`).

---

## Progress Tracking

Status values: `Not Started` (default) · `In Progress` · `Done` · `Blocked`.

| Task | Description | Status | Notes |
|---|---|---|---|
| B0.1 | Lock data-model + type contracts (this doc) | Not Started | |
| B1.1 | `Store` concurrency: WAL + serialized writes + safe connections | Not Started | |
| B1.2 | `test_store_concurrency.py` | Not Started | |
| B2.1 | `operations` table + schema migration | Not Started | |
| B2.2 | `operations` Store methods (+ atomic claim) | Not Started | |
| B2.3 | `operations` tests | Not Started | |
| B3.1 | `should_cancel` hook in `run_agent` | Not Started | |
| B3.2 | Widen `ApprovalFn` to `(tool, tool_input)` + update call sites | Not Started | |
| B3.3 | Cancellation + approval-arg tests | Not Started | |
| B4.1 | `approvals` table + schema migration | Not Started | |
| B4.2 | `approvals` Store methods | Not Started | |
| B4.3 | `store_backed_approval` block-and-wait callback | Not Started | |
| B4.4 | `approvals` tests | Not Started | |
| B5.1 | `WorkerPool` class + lifecycle (start/stop/drain) | Not Started | |
| B5.2 | Dispatch by operation `kind` | Not Started | |
| B5.3 | Cancel + approval integration in the pool | Not Started | |
| B5.4 | Worker-pool tests (FakeLLM) | Not Started | |

---

## Data contracts (locked in B0, referenced by later phases)

### `operations` table

A durable record for a long-running action triggered off the request path (the web layer
enqueues these; the pool executes them). Distinct from `jobs`, which remain a single role+task
agent execution. An operation *may* spawn jobs and links to the most recent via `job_id`.

```sql
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org TEXT NOT NULL,
    kind TEXT NOT NULL,                     -- run|ambition|observe|brief|channel_worker
    params TEXT NOT NULL DEFAULT '{}',      -- JSON: role, task, provider, model, approval_mode, max_* ...
    status TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|error|blocked|cancelled
    result TEXT,                            -- human-readable summary on success
    error TEXT,                             -- message on failure
    job_id INTEGER REFERENCES jobs(id),     -- optional link to a spawned job
    cancel_requested INTEGER NOT NULL DEFAULT 0,  -- cooperative-cancel flag (0/1)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### `approvals` table

A durable "pending approval" ticket. Created by `store_backed_approval` when a running
job/operation hits a tool that requires approval; resolved by a human (via CLI or the web
console). `action_args` is a JSON preview of the tool input so the UI can show *what* is being
approved.

```sql
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org TEXT NOT NULL,
    job_id INTEGER REFERENCES jobs(id),
    operation_id INTEGER REFERENCES operations(id),
    role TEXT NOT NULL,
    tool TEXT NOT NULL,
    action_args TEXT NOT NULL DEFAULT '{}', -- JSON preview of tool_input
    risk TEXT NOT NULL DEFAULT 'high',      -- low|medium|high
    status TEXT NOT NULL DEFAULT 'pending', -- pending|approved|denied|expired|cancelled
    decided_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT
);
```

### `ApprovalFn` signature change

```python
# tools.py — before
ApprovalFn = Callable[[Tool], bool]
# tools.py — after (additive: args are now visible to the callback)
ApprovalFn = Callable[[Tool, Mapping[str, object]], bool]
```

All existing callbacks (the CLI `allow`/`deny`/`ask` policies, tests) must be updated to accept
the second argument. The default in `run_agent` becomes `lambda _t, _i: False`.

### `WorkerPool` interface

```python
class WorkerPool:
    def __init__(
        self,
        store: Store,
        build_llm,                 # (provider, model) -> LLMClient  (reuse CLI helper)
        load_org,                  # (org_name) -> (Org, root_path)  (reuse loader)
        *,
        size: int = 2,
        poll_interval: float = 0.5,
        approval_timeout: float | None = None,
    ) -> None: ...
    def start(self) -> None: ...           # spawn `size` daemon worker threads
    def stop(self, *, drain: bool = False) -> None: ...  # signal + join
```

---

## Phase B1 — `Store` concurrency (foundation for a web server + pool)

Goal: make `Store` safe for concurrent readers (the web request threads) plus a small pool of
writer threads, without changing any existing method's external behavior.

### B1.1 — WAL + serialized writes + safe connections
- Depends on: B0.1.
- In [state.py](../../../src/agent_factory/runtime/state.py):
  - Open the connection with `check_same_thread=False`; on init run `PRAGMA journal_mode=WAL`
    and `PRAGMA busy_timeout=<ms>` alongside the existing `PRAGMA foreign_keys=ON`.
  - Add a private `threading.Lock` (`self._write_lock`); acquire it inside `_tx()` so **all
    writes are serialized** through one path. Reads do not take the lock (WAL allows concurrent
    readers).
  - Keep the public method surface identical. This is an internal hardening change.
- Verify: existing `test_runtime_state.py` and the full suite still pass unchanged.

### B1.2 — Concurrency test
- Depends on: B1.1.
- New `tests/test_store_concurrency.py`: spin up several threads that interleave
  `enqueue`/`pull_next`/`complete` and reader calls (`list_jobs`, `stats`) against one `Store`;
  assert no `database is locked` errors, no lost updates, and that `pull_next` never hands the
  same job to two threads (atomic claim holds under contention).
- Verify: `py -m unittest tests.test_store_concurrency -v` green; run it a few times for flakiness.

**Phase B1 exit criteria:** full offline suite green; new concurrency test green; `ruff` clean.

---

## Phase B2 — `operations` model

Goal: a durable queue for long-running actions the dashboard triggers, with an atomic claim so
the pool can drain it race-free (mirroring `pull_next`).

### B2.1 — Table + migration
- Depends on: B1.1.
- Add the `operations` DDL (above) to the schema bootstrap in `Store`; bump `schema_version`.
  Migration is additive and idempotent (`CREATE TABLE IF NOT EXISTS`), so existing org DBs
  upgrade transparently on first open.
- Verify: opening a pre-existing org DB (e.g. `orgs/Acme`) creates the table without touching
  existing rows; `schema_version()` reflects the bump.

### B2.2 — Store methods (+ atomic claim) **[P]**
- Depends on: B2.1.
- Add to `Store`:
  - `create_operation(org, kind, params: dict) -> int`
  - `get_operation(op_id) -> sqlite3.Row | None`
  - `list_operations(org=None, status=None, limit=100) -> list[Row]`
  - `update_operation_status(op_id, status, *, result=None, error=None, job_id=None) -> None`
  - `request_operation_cancel(op_id) -> None` (sets `cancel_requested=1`)
  - `operation_cancel_requested(op_id) -> bool`
  - `claim_next_operation() -> Row | None` — atomic `UPDATE ... WHERE id=(SELECT id ... WHERE
    status='queued' ORDER BY id LIMIT 1) AND status='queued' RETURNING *` (same pattern as
    `pull_next`).
- Verify: unit-level calls exercise each method; `claim_next_operation` returns each queued op
  exactly once under two competing threads.

### B2.3 — Tests
- Depends on: B2.2.
- New cases in `tests/test_runtime_operations.py`: create → list (filter by status/org) →
  claim → update to `done`/`error` → cancel flag round-trips.
- Verify: `py -m unittest tests.test_runtime_operations -v` green.

**Phase B2 exit criteria:** operations CRUD + atomic claim covered by tests; suite green; `ruff` clean.

---

## Phase B3 — Cancellation + `ApprovalFn` widening

Goal: two small, additive seams in the agent loop that the pool and durable approvals need.

### B3.1 — `should_cancel` hook
- Depends on: B0.1.
- In [agent.py](../../../src/agent_factory/runtime/agent.py), add
  `should_cancel: Callable[[], bool] | None = None` to `run_agent(...)`. At the top of each
  `for step in range(max_steps)` iteration, if `should_cancel and should_cancel()`, record a
  `cancelled` event and return an `AgentOutcome(finished=False, ...)` (or `store.block(job_id,
  "cancelled")` when a store/job is attached). Default `None` preserves today's behavior.
- Verify: a FakeLLM test where `should_cancel` flips to `True` after step 1 stops the loop
  promptly and records the cancellation; with the default `None`, existing agent tests are
  unchanged.

### B3.2 — Widen `ApprovalFn`
- Depends on: B0.1.
- Change `ApprovalFn` to `Callable[[Tool, Mapping[str, object]], bool]` in
  [tools.py](../../../src/agent_factory/runtime/tools.py). Update the gate in `run_agent` to
  `approved = approval_gate(tool, action.tool_input)` and the default to `lambda _t, _i: False`.
  Update every call site that constructs an approval callback: `_approval_policy` in
  [cli.py](../../../src/agent_factory/cli.py) (`allow`/`deny`/`ask`), and any callback passed by
  [ambition.py](../../../src/agent_factory/runtime/ambition.py) /
  [channel.py](../../../src/agent_factory/runtime/channel.py) and the tests in
  `tests/test_runtime_tools.py`.
- Verify: full suite green after the signature change (this proves all call sites were updated).

### B3.3 — Tests **[P]**
- Depends on: B3.1, B3.2.
- Add cases asserting (a) the approval callback receives the actual `tool_input` dict, and
  (b) cancellation mid-run behaves as specified.
- Verify: `py -m unittest tests.test_runtime_agent tests.test_runtime_tools -v` green.

**Phase B3 exit criteria:** both seams in place, all existing call sites updated, suite green.

---

## Phase B4 — Durable interactive approvals

Goal: persist "pending approval" tickets and provide a block-and-wait callback so a running
job/operation can pause for a human decision surfaced anywhere (CLI or web).

### B4.1 — Table + migration
- Depends on: B1.1.
- Add the `approvals` DDL (above); bump `schema_version`; idempotent/additive as in B2.1.
- Verify: table created on open of an existing DB; no impact on existing rows.

### B4.2 — Store methods **[P]**
- Depends on: B4.1.
- Add: `create_approval(org, role, tool, action_args: dict, *, risk, job_id=None,
  operation_id=None) -> int`; `get_approval(approval_id) -> Row | None`;
  `list_pending_approvals(org=None, limit=100) -> list[Row]`;
  `resolve_approval(approval_id, decision: str, *, decided_by="") -> None`
  (`decision ∈ {approved, denied}`, stamps `decided_at`); `expire_approval(approval_id)`.
- Verify: create → list_pending → resolve transitions persist and `decided_at` is set.

### B4.3 — `store_backed_approval` callback
- Depends on: B4.2, B3.2.
- New callable factory (in `runtime/tools.py` or a new `runtime/approvals.py`):
  `store_backed_approval(store, *, org, role, job_id=None, operation_id=None, risk_of=<fn>,
  timeout=None, should_cancel=None, poll_interval=0.5) -> ApprovalFn`.
  The returned `(tool, tool_input) -> bool`:
  1. resolves risk for `tool`, writes an `approvals` row (`status='pending'`, `action_args` =
     JSON preview of `tool_input`);
  2. **blocks**, polling `get_approval` every `poll_interval` until status is
     `approved`/`denied`, or `timeout` elapses (→ `expire_approval`, return `False`), or
     `should_cancel()` is `True` (→ `expire_approval`, return `False`);
  3. returns `True` only on `approved`.
- Verify: a threaded test — one thread runs the callback (parks on pending), another calls
  `resolve_approval(..., "approved")`; the callback returns `True`. Repeat for `denied` → `False`,
  and a timeout path → `False`.

### B4.4 — Tests **[P]**
- Depends on: B4.3.
- `tests/test_runtime_approvals.py`: cover approve, deny, timeout, and cancel paths (all with
  short timeouts / poll intervals so tests stay fast and offline).
- Verify: `py -m unittest tests.test_runtime_approvals -v` green.

**Phase B4 exit criteria:** durable approvals + block-and-wait callback covered by tests; suite green.

---

## Phase B5 — Bounded worker pool

Goal: execute jobs and operations off the request path, honoring cancellation and durable
approvals, with writes serialized per B1.

### B5.1 — `WorkerPool` + lifecycle
- Depends on: B1.1, B2.2.
- New `src/agent_factory/runtime/worker.py` implementing the `WorkerPool`
  interface above. `size` daemon threads; each loops: try `store.pull_next()` (a job) then
  `store.claim_next_operation()` (an operation); if both `None`, sleep `poll_interval`; else
  execute the claimed unit. `stop(drain=False)` signals a stop event and joins; `drain=True`
  finishes the queue first.
- Verify: start a pool against an empty store, confirm threads idle without busy-spinning
  (respect `poll_interval`); `stop()` joins cleanly with no lingering threads.

### B5.2 — Dispatch by kind
- Depends on: B5.1, B2.2.
- Job units: build the `LLMClient` from the job row's provider/model, then call `run_agent(...,
  store=store, job_id=row["id"], approval_fn=..., should_cancel=...)`.
- Operation units: dispatch `kind` →
  `run` (enqueue+run a job for `role`/`task`), `ambition` (`run_ambition_loop`),
  `observe`/`brief` ([insights.py](../../../src/agent_factory/runtime/insights.py)),
  `channel_worker` ([channel.py](../../../src/agent_factory/runtime/channel.py)). Record
  `running → done|error` on the operation, linking `job_id` where one is spawned.
- Verify: a FakeLLM operation of each kind drives the operation to `done` and writes the
  expected rows (result/insights/message) for that kind.

### B5.3 — Cancel + approval integration
- Depends on: B5.2, B3.1, B4.3.
- Pass `should_cancel=lambda: store.operation_cancel_requested(op_id)` (and the analogous job
  check) into `run_agent`. Construct the pool's `approval_fn` via `store_backed_approval(...)`
  bound to the current org/role/job/operation and the pool's `approval_timeout`. Because the
  pool has `size ≥ 2`, a worker parked on a pending approval does not stall other queued work.
- Verify: with a FakeLLM that requests a high-risk tool, an operation parks with a pending
  approval while a *second* queued operation still completes on another worker; resolving the
  approval unblocks the first.

### B5.4 — Worker-pool tests
- Depends on: B5.3.
- `tests/test_runtime_worker.py` (FakeLLM, short intervals): job drains to `done`; each
  operation kind drains to `done`; cancel flips an in-flight unit to `blocked/cancelled`;
  approval approve/deny alters the outcome; a pending approval on one worker does not block a
  second worker.
- Verify: `py -m unittest tests.test_runtime_worker -v` green; run twice for flakiness.

**Phase B5 exit criteria:** the pool executes jobs + all operation kinds, honors cancel and
durable approvals, keeps writes serialized, and is fully covered by offline FakeLLM tests.

---

## Relevant files

- [state.py](../../../src/agent_factory/runtime/state.py) — WAL + write lock (B1); `operations`
  table + methods (B2); `approvals` table + methods (B4); `schema_version` bumps.
- [agent.py](../../../src/agent_factory/runtime/agent.py) — `should_cancel` hook (B3.1); updated
  approval gate (B3.2).
- [tools.py](../../../src/agent_factory/runtime/tools.py) — `ApprovalFn` widening (B3.2);
  `store_backed_approval` (B4.3, or a new `runtime/approvals.py`).
- [orchestrator.py](../../../src/agent_factory/runtime/orchestrator.py) — reused by the pool (B5).
- [ambition.py](../../../src/agent_factory/runtime/ambition.py),
  [insights.py](../../../src/agent_factory/runtime/insights.py),
  [channel.py](../../../src/agent_factory/runtime/channel.py) — dispatch targets (B5.2).
- [cli.py](../../../src/agent_factory/cli.py) — `_approval_policy` signature update (B3.2); the
  provider/model → `LLMClient` helper reused by the pool (B5.2).
- New: `src/agent_factory/runtime/worker.py` (B5).
- New tests: `tests/test_store_concurrency.py`, `tests/test_runtime_operations.py`,
  `tests/test_runtime_approvals.py`, `tests/test_runtime_worker.py` (plus additions to
  `test_runtime_agent.py` / `test_runtime_tools.py`).

## Verification (plan-level)

1. `py -m unittest discover -s tests -v` — the full offline suite (163 pre-existing + new
   tests) is green with no network and no API keys, after **every** phase.
2. `ruff check` — clean across `src/` and `tests/`.
3. Opening an existing org DB (`orgs/Acme`) migrates schema additively (new tables appear;
   existing `jobs`/`events`/`messages`/`context`/`insights` rows untouched).
4. No import of `fastapi`, `uvicorn`, or any web/Node dependency anywhere under
   `src/agent_factory/runtime/`.

## Further considerations

1. **Thread-holding approvals.** v1 parks a worker thread on each pending approval; with pool
   `size=2` and many simultaneous approvals this can saturate the pool. Mitigations if it
   becomes real: raise `size`, add a dedicated "awaiting-approval" parking area off the pool,
   or implement true suspend/resume (checkpoint the agent loop). Deferred.
2. **PostgreSQL.** The write-lock + WAL approach is a single-host design. A future `Store`
   backend for multi-process/hosted use (already on the roadmap) would replace the in-process
   lock with DB-level row locking behind the same method surface.
3. **Operation heartbeat / stale reclaim.** If a worker dies mid-operation, the row stays
   `running`. A later increment can add an `updated_at` heartbeat + a reclaim sweep. Not needed
   for a single local host.
