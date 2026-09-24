# Release 2.0 Checklist — Agent Factory

> **Status:** PHASE 1 COMPLETE; Phase 2 is ready but not started. Feature work is specified in two companion plans;
> this checklist is the release-level tracker that folds them in and adds the
> release-engineering gates 1.0 used.
> **Purpose:** take the repo from "Release 1.0 (single-process CLI)" to
> "Release 2.0 (local management dashboard)".
> **How to use:** work top-to-bottom; every item has a concrete *"Done when"*.
> Tick boxes as you go, or make one GitHub issue per `RC-xx` and close them
> individually. The two feature phases are tracked here at *phase* granularity —
> their per-task detail lives in each plan's own Progress Tracking table. Create
> one dated implementation record from [PHASE_TEMPLATE.md](implementation/PHASE_TEMPLATE.md)
> when each release phase starts, and complete its verification and handoff before
> closing the phase.

**Companion plans (the feature work):**
- [DASHBOARD_BACKEND_PLAN.md](DASHBOARD_BACKEND_PLAN.md) — engine enablement, phases `B1–B5`.
- [WEB_CONSOLE_PLAN.md](WEB_CONSOLE_PLAN.md) — FastAPI API + React SPA, phases `P0–P5`.

## Definition of done for 2.0

A fresh clone on a clean machine can: install the wheel with the `[web]` extra,
pass the full offline test suite, run `agent_factory --version` (→ `2.0.0`),
launch `agent_factory web` and reach the dashboard on `127.0.0.1`, create an org
through the Bootstrap Wizard, trigger an action (`run`/`ambition`/…) and watch it
complete with live status, and approve a risky action from the Approval Inbox —
with docs that say exactly what the code does (no stale counts, no
advertised-but-missing features).

> **Versioning note:** the public CLI contract is unchanged and the `web`
> surface is opt-in (additive), so strict SemVer would call this a MINOR bump.
> **2.0.0** is a *milestone* version reflecting the size of the jump (browser UI,
> worker pool, durable operations + approvals), consistent with how 1.0 was named.
> The only non-additive internal change is the `ApprovalFn` signature (private
> API); it ships behind the `Changed` section of the CHANGELOG, not as a public
> break.

---

## Progress tracker

| ID | Item | Phase | Est. | Status |
|----|------|-------|------|--------|
| P0-01 | Baseline tag (`v1.0.0`) & clean tree | 0 | S | Done (2026-09-24) |
| P0-02 | Record verified baseline numbers | 0 | S | Done (2026-09-24) |
| P0-03 | Lock backend data-model and type contracts (`B0.1`) | 0 | S | Done (2026-09-24) |
| RC-01 | Backend **B1** — `Store` concurrency (WAL + serialized writes) | 1 | M | Done (2026-09-24) |
| RC-02 | Backend **B2** — `operations` model | 1 | M | Done (2026-09-24) |
| RC-03 | Backend **B3** — cancellation + `ApprovalFn` widening | 1 | S | Done (2026-09-24) |
| RC-04 | Backend **B4** — durable approvals + `store_backed_approval` | 1 | M | Done (2026-09-24) |
| RC-05 | Backend **B5** — bounded worker pool | 1 | L | Done (2026-09-24) |
| RC-06 | Web **P0** — scaffolding & API contract | 2 | M | ☐ |
| RC-07 | Web **P1** — read API + app infra | 2 | M | ☐ |
| RC-08 | Web **P2** — action endpoints + SSE | 2 | M | ☐ |
| RC-09 | Web **P3** — approvals API | 2 | M | ☐ |
| RC-10 | Web **P4** — frontend SPA | 2 | L | ☐ |
| RC-11 | Web **P5.1** — `agent-factory web` CLI subcommand | 2 | S | ☐ |
| RC-12 | Version `2.0.0` + `--version` + `__init__.py` + CHANGELOG | 3 | S | ☐ |
| RC-13 | CI: frontend/Node job + web tests in the matrix | 3 | M | ☐ |
| RC-14 | Docs: Web Console section + HTML regen + README | 3 | M | ☐ |
| RC-15 | Test-count / docs drift sweep | 3 | S | ☐ |
| RC-16 | `SECURITY.md` update (web surface) | 3 | S | ☐ |
| RC-17 | Error-path QA pass (web + CLI) → `QA_2.0.md` | 3 | M | ☐ |
| RC-18 | Release branch + tag `v2.0.0` | 4 | S | ☐ |
| RC-19 | sdist + wheel (with `webapp/static`) verified on fresh venv | 4 | M | ☐ |
| RC-20 | GitHub release + notes (`RELEASE_NOTES_2.0.md`) | 4 | S | ☐ |
| RC-21 | Live end-to-end dashboard proof run → `QA_2.0.md` | 4 | M | ☐ |
| RC-22 | README status → "Release 2.0" | 4 | S | ☐ |
| RC-23 | Post-2.0 backlog documented | 5 | S | ☐ |

---

## Phase 0 — Baseline (do first)

- [x] **P0-01 — Baseline tag + clean tree** *(Done 2026-09-24)*
  - Confirm `v1.0.0` is tagged and `git status` is clean before any 2.0 work; branch off `main`.
  - **Done when:** `git tag -l` shows `v1.0.0`, working tree clean, a `release/2.0` (or feature) branch exists.

- [x] **P0-02 — Record verified baseline numbers** *(Done 2026-09-24)*
  - Capture the pre-feature baseline to diff 2.0 against: **169** offline tests
    (`py -m unittest discover -s tests`; the shipped 1.0 suite had 163 and the
    documentation-governance work adds 6), **13** CLI commands (`bootstrap, packs,
    validate, run, jobs, ambition, context, probe, observe, brief, status,
    channel, tools`), tool surface **4 real / 13 stub / 17 declared**,
    version `1.0.0`. (2.0 adds the `web` command → 14, plus new web tests.)
  - **Done when:** the numbers here match a fresh suite/CLI run at branch point.

- [x] **P0-03 — Lock backend contracts (`B0.1`)** *(Done 2026-09-24)*
  - Review and finalize the operations, approvals, worker-pool, cancellation, and `ApprovalFn` contracts in the backend plan before implementation.
  - **Done when:** backend task `B0.1` is `Done`, deviations are recorded, and later backend phases can implement against stable contracts.

**Phase 0 exit:** `P0-01` through `P0-03` verified; the dated Phase 0 record contains baseline evidence, decisions, and a Phase 1 handoff.

---

## Phase 1 — Backend engine (blockers; ship nothing until green)

> Source of truth: [DASHBOARD_BACKEND_PLAN.md](DASHBOARD_BACKEND_PLAN.md). Each item
> below = one backend phase. **Rule:** the offline `unittest` suite stays green and
> `ruff` clean after every phase, with **zero web/Node imports** under
> `src/agent_factory/runtime/`.

- [x] **RC-01 — B1: `Store` concurrency** *(Done 2026-09-24)*
  - WAL journal mode, thread-local connections, all writes serialized through one write lock, and atomic running child-job creation.
  - **Done when:** `tests/test_store_concurrency.py` green (no `database is locked`, no double-claim under contention); full suite still green.

- [x] **RC-02 — B2: `operations` model** *(Done 2026-09-24)*
  - `operations` table + `create/list/get/update_status/request_cancel/claim_next_operation`; additive schema migration (`schema_version` bump).
  - **Done when:** `tests/test_runtime_operations.py` green; an existing org DB (`orgs/Acme`) migrates without touching existing rows.

- [x] **RC-03 — B3: cancellation + `ApprovalFn` widening** *(Done 2026-09-24)*
  - `should_cancel` hook in `run_agent`'s step loop; `ApprovalFn` widened to `(tool, tool_input) -> bool`; every call site updated (`_approval_policy`, ambition, channel, tests).
  - **Done when:** full suite green after the signature change (proves all call sites updated); cancel + approval-arg tests pass.

- [x] **RC-04 — B4: durable approvals** *(Done 2026-09-24)*
  - `approvals` table + `create/list_pending/get/resolve/expire`; `store_backed_approval` block-and-wait callback (timeout + cancel aware).
  - **Done when:** `tests/test_runtime_approvals.py` covers approve / deny / timeout / cancel, all green.

- [x] **RC-05 — B5: bounded worker pool** *(Done 2026-09-24)*
  - `runtime/worker.py` `WorkerPool` (default size 2), drains jobs + operations, serialized writes, cancel + `store_backed_approval` integration, dispatch by `kind`.
  - **Done when:** `tests/test_runtime_worker.py` green — job + each operation kind reach `done`; a pending approval on one worker doesn't block a second worker.

**Phase 1 exit:** backend plan `B1–B5` all `Done`; offline suite green; `ruff` clean; no web deps in runtime; the dated Phase 1 record contains verification and a Phase 2 handoff.

---

## Phase 2 — Web console (blockers)

> Source of truth: [WEB_CONSOLE_PLAN.md](WEB_CONSOLE_PLAN.md). Phase `P5`'s docs /
> security / regression tasks are tracked in **Phase 3** below to avoid
> double-counting; RC-11 here is just the `web` CLI subcommand (`P5.1`).

- [ ] **RC-06 — P0: scaffolding & contract**
  - `web` extra (`fastapi`, `uvicorn`, `sse-starlette`) + `webapp/static/**` package-data; `webapp/` skeleton; API contract filled in; Vite + Tailwind + shadcn/ui + TanStack scaffold builds.
  - **Done when:** `pip install -e .[web]` works, `agent_factory.webapp` imports, `frontend/` builds, contract section complete.

- [ ] **RC-07 — P1: read API + app infra** *(needs RC-01)*
  - Path confinement + Store accessors + token dep, Pydantic schemas, read endpoints, `create_app` (lifespan starts pool + SSE bus, static serving, localhost bind, dev-only CORS).
  - **Done when:** `tests/test_web_api.py` green (reads + bootstrap; traversal→400, unknown→404); pool starts/stops with the app.

- [ ] **RC-08 — P2: action endpoints + SSE** *(needs RC-02, RC-05)*
  - `operations`-backed `run/ambition/observe/brief/channel/context` endpoints (enqueue → pool), `GET /api/orgs/{org}/stream` SSE.
  - **Done when:** `tests/test_web_actions.py` green — each action drains to `done` via FakeLLM; SSE emits transitions.

- [ ] **RC-09 — P3: approvals API** *(needs RC-04)*
  - `GET …/approvals?status=pending`, org-scoped `POST …/approvals/{id}/decide`, approval SSE events.
  - **Done when:** `tests/test_web_approvals.py` green — pending appears; approve executes the tool, deny prevents the tool call without forcing a blocked operation, races return 409, and a second worker remains unblocked.

- [ ] **RC-10 — P4: frontend SPA**
  - Typed client + TanStack Query hooks, app shell + routing, read views, action forms (RHF + Zod), live Approval Inbox, Bootstrap Wizard, SSE + polling fallback, production build served from `webapp/static`.
  - **Done when:** every view/form/inbox/wizard works end-to-end against the live backend with live updates; `tsc --noEmit` + `npm run build` clean.

- [ ] **RC-11 — P5.1: `agent-factory web` CLI subcommand**
  - `cmd_web` + subparser: `--org/--host/--port/--pool-size/--dev/--token`; lazy import with a friendly `[web]` hint; prints URL; default bind `127.0.0.1`.
  - **Done when:** `agent-factory web --org orgs` serves the app; `Ctrl+C` exits cleanly; missing extra → hint, not a traceback.

**Phase 2 exit:** web plan `P0–P4` + `P5.1` all `Done`; dashboard runs end-to-end from a source checkout; the dated Phase 2 record contains verification and a Phase 3 handoff.

---

## Phase 3 — Release quality (before tagging)

- [ ] **RC-12 — Version `2.0.0` + `--version` + `__init__.py` + CHANGELOG**
  - Bump `pyproject.toml` `1.0.0 → 2.0.0` and `src/agent_factory/__init__.py` `__version__`; add a `[2.0.0]` CHANGELOG entry (Added: web console, worker pool, operations/approvals; **Changed:** `ApprovalFn` signature, additive `Store` schema).
  - **Done when:** `agent_factory --version` prints `2.0.0`; CHANGELOG entry complete and linked from README.

- [ ] **RC-13 — CI: frontend/Node job + web tests in the matrix**
  - Add a `frontend` job to `.github/workflows/ci.yml` (`npm ci`, `npm run build`, `tsc --noEmit`); confirm the new `test_web_*.py` run offline in the existing Python matrix (they use `TestClient` + FakeLLM).
  - **Done when:** a fresh push gets green Python **and** frontend jobs; web tests execute in every matrix cell.

- [ ] **RC-14 — Docs: Web Console section + HTML regen + README**
  - Add a "Web Console" section to `USER_GUIDE.md` (install `[web]`, build + copy to `webapp/static`, `agent-factory web`, tour of dashboard/actions/approvals/wizard); regenerate HTML (`python tools/build_docs.py`); README feature list + Status mention.
  - **Done when:** `python tools/build_docs.py --check` is clean (CI `docs` job green); a fresh reader can run the console from the docs alone.

- [ ] **RC-15 — Test-count / docs drift sweep**
  - Update every current-facing doc from **163** to the new total (README, ARCHITECTURE, PRODUCT, USER_GUIDE, CHANGELOG); keep historical/milestone docs as point-in-time records.
  - **Done when:** no stale `163 tests` claim reads as current; counts match a fresh `unittest` run.

- [ ] **RC-16 — `SECURITY.md` update (web surface)**
  - Document: default `127.0.0.1` bind (`0.0.0.0` only via explicit `--host`), optional bearer token, that the console can trigger spend/external actions, and the approval model; bump the supported-versions table to `2.0.x`.
  - **Done when:** `SECURITY.md` covers the web surface; a reviewer can state the console's posture in 5 minutes.

- [ ] **RC-17 — Error-path QA pass (web + CLI) → `QA_2.0.md`**
  - Exercise the new `web` command + key API endpoints with bad input (unknown org, traversal, bad token, duplicate bootstrap, decide-already-decided) plus a fresh sweep of the 13 existing commands; record in `docs/releases/v2.0/QA_2.0.md`.
  - **Done when:** every handled case exits cleanly (no tracebacks / no 500s on handled paths); QA log committed.

---

## Phase 4 — Packaging & release day (in order)

- [ ] **RC-18 — Release branch + tag `v2.0.0`**
  - Cut/confirm `release/2.0` at a green-CI commit; annotate the tag (web console, worker pool, operations + approvals; providers unchanged; test count; 2.0.0).
  - **Done when:** branch + tag pushed; tag points at a fully green commit.

- [ ] **RC-19 — sdist + wheel, verified from a fresh venv**
  - `python -m build`; inspect the wheel contains `agent_factory/webapp/static/**` (the built SPA) + entry points; smoke-install into a clean venv with `pip install "dist/agent_factory-2.0.0-*.whl[web]"`, then `agent_factory --version` and `agent_factory web` reaches the dashboard with no `frontend/` source or `npm run dev`.
  - **Done when:** fresh-venv smoke passes end-to-end; sdist non-empty.

- [ ] **RC-20 — GitHub release + notes**
  - Build artifacts in `dist/`; draft `RELEASE_NOTES_2.0.md` + `RELEASE_BODY_v2.0.0.md` (highlights, what's new, upgrade notes for the `ApprovalFn` change, install with `[web]`, known limitations); publish the release page with both artifacts.
  - **Done when:** artifacts built, notes drafted, release page live listing the changelog + artifacts.

- [ ] **RC-21 — Live end-to-end dashboard proof run → `QA_2.0.md`**
  - With a real provider: `agent-factory web`, create an org via the wizard, run **four** flows through the UI (`run`, `ambition`, `brief`, `channel post → worker`), and approve one high-risk action from the Approval Inbox. Capture screenshots/output.
  - **Done when:** `QA_2.0.md` shows all flows + one approval completing with real model output.

- [ ] **RC-22 — README status flip**
  - Status block → "**Release 2.0** (date)"; add the web console to the feature list; link `RELEASE_CHECKLIST_2.0.md` + `QA_2.0.md`.
  - **Done when:** a new reader can tell from the README exactly what 2.0 adds without opening the plans.

---

## Phase 5 — Post-2.0 backlog (explicitly *not* required for 2.0)

- [ ] **RC-23 — Document the post-2.0 roadmap** (in `docs/planning/ROADMAP.md` "after 2.0")
  - PostgreSQL `Store` backend for multi-process/hosted use (replaces the in-process write lock).
  - True agent-loop **suspend/resume** approvals (stop parking a worker thread per pending approval).
  - Multi-user auth (beyond the local bearer token) for a hosted deployment.
  - Token-level streaming of agent output over SSE (v2.0 streams coarse state envelopes only).
  - Continued replacement of the 13 stubbed tool adapters; structured `--json` output; telemetry export.
  - **Done when:** `ROADMAP.md` has a dated "after 2.0" section and nothing in Phases 1–4 silently depends on these.

---

## Definition-of-done final check (run once, in a fresh clone)

```text
git clone → pip install "…[web]" (or -e .[web]) → py -m unittest discover -s tests   ✅
→ agent_factory --version                                     shows 2.0.0            ✅
→ agent_factory bootstrap --pack engineering → validate → run --provider fake        ✅
→ agent_factory web --org orgs → open 127.0.0.1:8765          dashboard loads        ✅
   → wizard creates an org → action runs to done (live) → approve from inbox         ✅
→ one real-provider dashboard flow (RC-21)                    completes              ✅
→ cd frontend && npm run build && tsc --noEmit                clean                  ✅
→ python tools/build_docs.py --check                          all docs up to date    ✅
→ grep stale "163 tests" in current-facing *.md               nothing                ✅
→ ruff check src tests                                        0 errors               ✅
→ wheel contains agent_factory/webapp/static/**, SECURITY.md covers web surface      ✅
```

When every box above is ticked, cut **v2.0.0** and update this file's header with
a "Released" date.
