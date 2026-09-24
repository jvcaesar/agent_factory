# Phase 1 - Backend Engine

- **Release:** 2.0
- **Status:** Done
- **Started:** 2026-09-24
- **Completed:** 2026-09-24
- **Release checklist IDs:** `RC-01`, `RC-02`, `RC-03`, `RC-04`, `RC-05`
- **Backend IDs:** `B1.1-B1.2`, `B2.1-B2.3`, `B3.1-B3.3`, `B4.1-B4.4`, `B5.1-B5.4`
- **Web IDs:** Not applicable
- **Commits/PRs:** Branch `release/2.0`; phase changes not committed
- **Prerequisites:** Phase 0 complete; backend contracts locked in `B0.1`

## Objective

Implement the complete Release 2.0 backend engine foundation: concurrent-safe Store access, durable operations, cooperative cancellation, argument-aware approvals, durable approval decisions, and a bounded multi-org worker pool. Phase 1 exits only when `RC-01` through `RC-05` and backend tasks `B1-B5` are Done, the full offline suite and Ruff are green, and runtime has no web dependency.

## Delivered

- Phase 1 record created from the repository template.
- Phase 0 handoff and clean branch `release/2.0` at `02857d7` verified.
- B1.1 implemented thread-local SQLite connections, WAL/busy-timeout configuration, serialized writes, shared in-memory storage, and atomic creation of caller-owned running jobs.
- Orchestrator, ambition, and channel flows now create running jobs atomically instead of exposing an enqueue/start race.
- B1.2 added deterministic file/in-memory contention coverage, unique atomic claims, running-job exclusion, WAL verification, and close lifecycle checks.
- B2.1 added the transactional v1-to-v2 operations migration and verified that existing job rows survive upgrade.
- B2.2 added reusable operation payload validation, canonical JSON storage, filtered reads, guarded transitions, cooperative cancellation flags, and atomic claims.
- B2.3 completed operation lifecycle, default, validation-boundary, terminal-state, cancellation, and competing-claim coverage.
- B3.1 added explicit cancelled agent outcomes and cooperative checkpoints across agent, ambition, channel, observe, and brief flows without interrupting in-flight provider calls.
- B3.2 widened ApprovalFn to receive tool inputs and updated runtime, CLI allow/deny/ask policies, and existing tests.
- B3.3 proved exact approval arguments and cancellation before/between agent steps, before persistence, and after channel claims.
- B4.1 added transactional v2-to-v3 approval migration and verified direct and chained upgrades.
- B4.2 added canonical approval rows, org/status filtering, foreign-key links, and pending-only resolve/expire/cancel transitions with race coverage.
- B4.3 added the store-backed blocking callback with monotonic timeout, operation cancellation, separate shutdown interruption, and Tool.risk defaults. Shared in-memory connections use `read_uncommitted` so polling reads cannot block serialized decision writes.
- B4.4 added runtime-package export, invalid wait configuration checks, and three-way resolve/expire/cancel race coverage.
- B5.1 added the bounded worker lifecycle with idempotent start/stop, bounded joins, drain mode, round-robin org scheduling, alternating queue claims, transition callbacks, and per-unit exception containment.
- B5.2 added direct claimed-job execution and handlers for run, ambition, observe, brief, and channel-worker operations with CLI-consistent role fallback and normalized result summaries.
- B5.3 integrated operation cancellation and allow/deny/durable-ask approval policies. In-flight cancellation blocks the child job; a pending approval does not block a second worker; denial skips the tool while allowing the operation to finish.
- B5.4 completed worker coverage for allow mode, bounded approval-wait shutdown, cross-org database-local id isolation, provider/model forwarding, runtime export, fairness, drain behavior, exception survival, every operation kind, cancellation, and two-worker approval progress.

## Files Changed

- `src/agent_factory/runtime/state.py` - thread-safe connections, migrations, operations, approvals, and guarded state transitions.
- `src/agent_factory/runtime/agent.py`, `ambition.py`, `channel.py`, `insights.py`, and `orchestrator.py` - atomic jobs, cancellation, and widened approvals.
- `src/agent_factory/runtime/approvals.py` - durable block-and-wait approval policy.
- `src/agent_factory/runtime/worker.py` - bounded multi-org job and operation execution.
- `src/agent_factory/runtime/__init__.py` and `tools.py` - public runtime exports and ApprovalFn contract.
- `src/agent_factory/cli.py` - argument-aware interactive approval policy.
- `tests/test_store_concurrency.py`, `test_runtime_operations.py`, `test_runtime_approvals.py`, and `test_runtime_worker.py` - new Phase 1 coverage.
- Existing runtime tests - cancellation, atomic jobs, and approval argument assertions.
- Release tracking documents and this record - synchronized completion and handoff.

## Decisions and Contract Deviations

Phase 1 will clarify residual implementation details at the owning task before code is added. These are refinements of the Phase 0 contracts, not scope additions:

- Worker approval policy dispatch must distinguish `allow`, `deny`, and durable `ask` modes.
- Worker construction needs an injectable role-client factory for deterministic tests while defaulting to `client_for_role`.
- Default pool size is two; size one is valid but cannot guarantee progress while its only worker waits for approval.
- Worker shutdown interruption is separate from user-requested operation cancellation.
- Approval risk defaults to `Tool.risk`; canonical operation JSON uses sorted keys and compact separators.
- Observe cancellation checks after the provider call and before persistence; channel cancellation returns an interrupted claimed message to `pending`.
- Operation parameter validation is a reusable runtime function used by Store and future API callers.
- Standalone claimed jobs use deny-by-default approval because jobs do not persist an approval mode.
- Shared in-memory SQLite connections enable `read_uncommitted` so approval polling cannot block serialized decision writes; file stores retain WAL isolation.
- Non-draining shutdown interrupts approval waits without pretending the user cancelled the operation. The operation may finish after the denied tool call while the approval row records `cancelled`.
- Worker transition callbacks are runtime-neutral and carry `(org_key, entity_type, id, status)` for Phase 2 SSE binding.

## Verification

```text
git branch --show-current
git status --short
git log -1 --oneline
Result before Phase 1 edits: release/2.0, clean tree, 02857d7 Phase 0 completion

py -m unittest discover -s tests -p "test_runtime_state.py" -v
py -m unittest discover -s tests -p "test_runtime_agent.py" -v
py -m unittest discover -s tests -p "test_runtime_ambition.py" -v
py -m unittest discover -s tests -p "test_runtime_channel.py" -v
Result: 53 focused tests passed

py -m unittest discover -s tests -v
Result after B1.1: 169 tests passed in 1.410s; 3 skipped

py -m ruff check src tests tools
Result after B1.1: all checks passed

py -m unittest discover -s tests -p "test_store_concurrency.py" -v (twice)
Result: 6 tests passed on both runs

py -m unittest discover -s tests -v
Result after B1.2 / RC-01: 175 tests passed in 1.828s; 3 skipped

py -m ruff check src tests tools
Result after B1.2 / RC-01: all checks passed

py -m unittest discover -s tests -p "test_runtime_state.py" -v
py -m unittest discover -s tests -p "test_runtime_operations.py" -v
Result after B2.1 focused checks: 10 tests passed

py -m unittest discover -s tests -v
Result after B2.1: 176 tests passed in 1.903s; 3 skipped

py -m ruff check src tests tools
Result after B2.1: all checks passed

py -m unittest discover -s tests -p "test_runtime_operations.py" -v
Result after B2.2 focused checks: 7 tests passed

py -m unittest discover -s tests -v
Result after B2.2: 182 tests passed in 2.757s; 3 skipped

py -m ruff check src tests tools
Result after B2.2: all checks passed

py -m unittest discover -s tests -p "test_runtime_operations.py" -v (twice)
Result after B2.3: 12 tests passed on both runs

py -m unittest discover -s tests -v
Result after B2.3 / RC-02: 187 tests passed in 1.982s; 3 skipped

py -m ruff check src tests tools
Result after B2.3 / RC-02: all checks passed

focused agent/ambition/channel/insights suites
Result after B3.1: 54 affected-flow tests passed

py -m unittest discover -s tests -v
Result after B3.1: 187 tests passed in 1.868s; 3 skipped

py -m ruff check src tests tools
Result after B3.1: all checks passed

approval callback signature scan
Result after B3.2: no one-argument approval callbacks remain

focused agent/channel/ambition/CLI suites
Result after B3.2: 47 tests passed

py -m unittest discover -s tests -v
Result after B3.2: 187 tests passed in 1.909s; 3 skipped

py -m ruff check src tests tools
Result after B3.2: all checks passed

focused agent/insights/channel/ambition suites
Result after B3.3: 61 tests passed, including 7 new behavior tests

py -m unittest discover -s tests -v
Result after B3.3 / RC-03: 194 tests passed in 1.952s; 3 skipped

py -m ruff check src tests tools
Result after B3.3 / RC-03: all checks passed

focused state/operations/approval migration suites
Result after B4.1: 23 tests passed

py -m unittest discover -s tests -v
Result after B4.1: 196 tests passed in 2.005s; 3 skipped

py -m ruff check src tests tools
Result after B4.1: all checks passed

py -m unittest discover -s tests -p "test_runtime_approvals.py" -v
Result after B4.2: 8 tests passed

py -m unittest discover -s tests -v
Result after B4.2: 202 tests passed in 2.095s; 3 skipped

py -m ruff check src tests tools
Result after B4.2: all checks passed

C:\Python313\python.exe -m unittest discover -s tests -p "test_runtime_approvals.py" -v (3 times)
Result after B4.3: 13 tests passed on all runs

C:\Python313\python.exe -m unittest discover -s tests -v
Result after B4.3: 207 tests passed in 2.107s; 3 skipped

C:\Python313\python.exe -m ruff check src tests tools
Result after B4.3: all checks passed

C:\Python313\python.exe -m unittest discover -s tests -p "test_runtime_approvals.py" -v (twice)
Result after B4.4: 16 tests passed on both runs

C:\Python313\python.exe -m unittest discover -s tests -v
Result after B4.4 / RC-04: 210 tests passed in 2.626s; 3 skipped

C:\Python313\python.exe -m ruff check src tests tools
Result after B4.4 / RC-04: all checks passed

C:\Python313\python.exe -m unittest discover -s tests -p "test_runtime_worker.py" -k TestWorkerLifecycle -v
Result after B5.1: 6 tests passed

C:\Python313\python.exe -m unittest discover -s tests -v
Result after B5.1: 216 tests passed in 2.216s; 3 skipped

C:\Python313\python.exe -m ruff check src tests tools
Result after B5.1: all checks passed

C:\Python313\python.exe -m unittest discover -s tests -p "test_runtime_worker.py" -k TestWorkerDispatch -v
Result after B5.2: 6 tests passed

C:\Python313\python.exe -m unittest discover -s tests -v
Result after B5.2: 222 tests passed in 2.748s; 3 skipped

C:\Python313\python.exe -m ruff check src tests tools
Result after B5.2: all checks passed

focused TestWorkerCancellation and TestWorkerApprovals suites
Result after B5.3: 3 tests passed

C:\Python313\python.exe -m unittest discover -s tests -v
Result after B5.3: 225 tests passed in 2.451s; 3 skipped

C:\Python313\python.exe -m ruff check src tests tools
Result after B5.3: all checks passed

C:\Python313\python.exe -m unittest discover -s tests -p "test_runtime_worker.py" -v (twice)
Result after B5.4: 20 tests passed on both runs

C:\Python313\python.exe -m unittest discover -s tests -v
Result at Phase 1 exit: 230 tests passed in 2.391s; 3 skipped

C:\Python313\python.exe -m ruff check src tests tools
Result at Phase 1 exit: all checks passed

C:\Python313\python.exe tools/check_docs.py
C:\Python313\python.exe tools/build_docs.py --check
Result: documentation structure/links valid; PRODUCT.html and USER_GUIDE.html current

runtime web-import scan
Result: no FastAPI, Uvicorn, SSE, React, or Node imports under src/agent_factory/runtime

git diff --check
Result: no whitespace errors (line-ending warnings only)
```

## Known Issues and Deferred Work

- Phase 2 Web Console work is explicitly deferred and not started.
- The web app must own the org-local Store cache and close Stores only after `WorkerPool.stop()` joins workers.
- A configured pool size of one is valid, but progress while its only worker waits for approval requires size two or greater.
- True agent-loop suspend/resume, stale-operation reclaim, direct job cancellation, and PostgreSQL remain deferred roadmap work.

## Handoff

- **Next eligible phase:** Phase 2 - Web Console
- **Next task:** `RC-06` / Web `0.1` - optional web dependencies, package-data contract, and scaffold
- **Unmet dependencies:** None
- **Operational cautions:** Keep Stores org-local; use the org path key in operation/approval routes; call bounded `WorkerPool.stop(drain=False)` before closing Stores; bind `on_transition` to SSE without importing web dependencies into runtime; keep approval decisions org-scoped.
- **Resume instructions:** Create `implementation/YYYY-MM-DD-phase-2-web-console/README.md`; mark `RC-06` and Web `0.1` `In Progress`; implement only Web P0 scaffolding/contract first; run import/build checks before Web P1.

## Tracker Updates

- `RC-01`: Done - B1.1 and B1.2 verified; full suite and Ruff green.
- `B1.1`: Done - focused tests, full suite, and Ruff passed.
- `B1.2`: Done - concurrency tests passed twice.
- `RC-02`: Done - migration, methods, lifecycle/race tests, full suite, and Ruff passed.
- `B2.1`: Done - migration and preservation tests passed.
- `B2.2`: Done - 7 focused tests, full suite, and Ruff passed.
- `B2.3`: Done - operations tests passed twice.
- `RC-03`: Done - cancellation seams, ApprovalFn widening, direct behavior tests, full suite, and Ruff passed.
- `B3.1`: Done - affected-flow tests, full suite, and Ruff passed.
- `B3.2`: Done - signature scan, focused tests, full suite, and Ruff passed.
- `B3.3`: Done - direct behavioral tests passed.
- `RC-04`: Done - migrations, methods, callback, race coverage, full suite, and Ruff passed.
- `B4.1`: Done - migration tests, full suite, and Ruff passed.
- `B4.2`: Done - focused tests, full suite, and Ruff passed.
- `B4.3`: Done - focused stress runs, full suite, and Ruff passed.
- `B4.4`: Done - approval suite passed twice.
- `RC-05`: Done - B5.1-B5.4 verified; full suite, Ruff, docs, and import boundary green.
- `B5.1`: Done - lifecycle tests, full suite, and Ruff passed.
- `B5.2`: Done - focused dispatch tests, full suite, and Ruff passed.
- `B5.3`: Done - focused tests, full suite, and Ruff passed.
- `B5.4`: Done - worker suite passed twice; Phase 1 exit checks passed.
- `RC-06`: Not Started - next eligible release task.
- Web `0.1`: Not Started - begin only after the Phase 2 record exists.
