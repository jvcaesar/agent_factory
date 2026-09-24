# Phase 0 - Baseline

- **Release:** 2.0
- **Status:** Done
- **Started:** 2026-09-24
- **Completed:** 2026-09-24
- **Release checklist IDs:** `P0-01`, `P0-02`, `P0-03`
- **Backend IDs:** `B0.1`
- **Web IDs:** Not applicable
- **Commits/PRs:** Branch point `f238e90`; phase changes not committed
- **Prerequisites:** Release 1.0.0 documentation and planning structure complete

## Objective

Establish the verified Release 2.0 branch baseline, record reproducible product and test-surface counts, and lock the backend contracts required by Phase 1. Phase 0 exits only when `P0-01` through `P0-03` are verified and the Phase 1 handoff is complete.

## Delivered

- Confirmed tag `v1.0.0` exists.
- Confirmed `main` was clean at branch point `f238e90` before Phase 0 records were created.
- Created and switched to branch `release/2.0`.
- Verified the pre-feature baseline: 169 offline tests, 13 CLI commands, 4 real and 13 stub tools (17 declared), and package version 1.0.0.
- Locked backend contracts and synchronized the affected Web Console routes, behavior, QA expectations, and test counts.

## Files Changed

- `docs/releases/v2.0/implementation/2026-09-24-phase-0-baseline/README.md` - canonical Phase 0 evidence and handoff record.
- `docs/releases/v2.0/DASHBOARD_BACKEND_PLAN.md` - locked data, migration, concurrency, cancellation, approval, and worker contracts.
- `docs/releases/v2.0/WEB_CONSOLE_PLAN.md` and `QA_2.0.md` - synchronized org-scoped routes and approval/cancellation behavior.
- `docs/releases/v2.0/RELEASE_CHECKLIST_2.0.md`, `README.md`, and `docs/planning/CURRENT.md` - synchronized phase status and handoff.

## Decisions and Contract Deviations

- Use one app-global bounded worker pool over org-local Stores. Operation and approval ids remain database-local; API routes include the org key.
- Use thread-local SQLite connections with WAL and one serialized write lock per Store. Preserve in-memory tests through a named shared-cache database and anchor connection.
- Add transactional schema migrations: v1 current, v2 operations, v3 approvals. Update schema version only after successful DDL.
- Add atomic running child-job creation so synchronous ambition/channel/run flows cannot race the pool's queued-job claim.
- Limit Release 2.0 cancellation to operations. Queued operations cancel atomically; running operations cooperate at explicit checkpoints; interrupted child jobs use existing `blocked` status with error `cancelled`.
- Preserve boolean `ApprovalFn` behavior: denial prevents the tool call but does not itself block the operation. Approval timeout and cancellation are distinct atomic terminal transitions.
- Execute already-claimed jobs directly with `run_agent`; do not call `run_job`, which would enqueue a duplicate. Reuse `client_for_role` for provider/model precedence.
- Require fair cross-org/job-operation polling, per-unit exception containment, bounded shutdown, and a runtime-neutral transition callback for SSE consumers.
- Contract deviation: the original draft's single-Store worker, unscoped approval decision route, shared-connection WAL claim, and denial-forces-blocking behavior were replaced because they conflicted with current org-local storage and runtime semantics.

## Verification

```text
git status --short
git branch --show-current
git tag -l v1.0.0
git log -1 --oneline

Result before Phase 0 documentation edits:
- working tree clean
- branch: main
- tag: v1.0.0
- branch point: f238e90 Release 2.0 planning and re-organized the doc folder structure

git switch -c release/2.0
Result: switched to new branch release/2.0

py -m unittest discover -s tests -v
Result: 169 tests passed in 1.786s; 3 skipped

py -m agent_factory --version
Result: agent_factory 1.0.0

py -m agent_factory --help
Result: 13 commands: bootstrap, packs, tools, validate, run, jobs, ambition,
context, probe, observe, brief, status, channel

py -m agent_factory tools
Result: 4 real, 13 stub, 17 declared in role grants

py tools/check_docs.py
Result: documentation structure and links valid

contract contradiction scan across docs/releases/v2.0/*.md
Result: no superseded route, denial, connection, helper, or baseline-count requirements remain

py -m unittest discover -s tests -v
Result: 169 tests passed in 1.607s; 3 skipped

py -m ruff check src tests tools
Result: all checks passed

py tools/build_docs.py --check
Result: PRODUCT.html and USER_GUIDE.html up to date
```

## Known Issues and Deferred Work

- `RC-01` / `B1.1-B1.2`: Store concurrency implementation is deferred to Phase 1.
- `RC-02` through `RC-05`: operations, cancellation, approvals, and worker implementation remain Phase 1 work.
- No Phase 1 implementation record exists yet because Phase 1 has not started.

## Handoff

- **Next eligible phase:** Phase 1 - Backend engine
- **Next task:** `RC-01` / `B1.1` - Store concurrency and atomic running child jobs
- **Unmet dependencies:** None
- **Operational cautions:** Follow the locked thread-local connection and org-local Store contracts. Do not reintroduce a single Store for all orgs, direct job cancellation, CLI-specific client construction, or denial-forces-blocking semantics.
- **Resume instructions:** Create `implementation/YYYY-MM-DD-phase-1-backend-engine/README.md` from the template; mark `RC-01` and `B1.1` `In Progress`; implement only B1.1; run its focused concurrency/state checks before continuing to B1.2.

## Tracker Updates

- `P0-01`: Done - `v1.0.0`, clean branch point `f238e90`, and `release/2.0` verified.
- `P0-02`: Done - 169 tests, 13 commands, 4 real / 13 stub / 17 declared tools, version 1.0.0.
- `P0-03`: Done - backend and affected web contracts locked and synchronized.
- `B0.1`: Done - contract audit decisions recorded in the backend plan.
- `RC-01`: Not Started - next eligible task.
- `B1.1`: Not Started - begin only after the Phase 1 record exists.
