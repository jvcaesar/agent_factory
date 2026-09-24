# Plan: Web Console — Agent Factory Release 2.0 (Management Dashboard)

Release 2.0 adds a local **Web Console**: a FastAPI backend (launched via a new
`agent-factory web` CLI subcommand) serving a Vite + React + TypeScript SPA that lets you
**manage** an agent workforce from the browser, not just view it. It provides:
1. A **Bootstrap Wizard** — create a new org through web forms instead of the terminal
   interview (reuses `generate_org()`/`write_org()`, no duplicated business logic).
2. A **read-only Org Dashboard** — org chart, jobs, channel feed, insights, and mission-control
   status for an existing org (reuses `Store` read methods, no duplicated state logic).
3. **Action controls** — trigger `run`, `ambition`, `observe`, `brief`, and channel work from
   the UI. These are long-running LLM calls, so the web layer **enqueues** them and a bounded
   background **worker pool** executes them off the request path, with **live status** streamed
   back to the browser.
4. A live **Approval Inbox** — approve or deny risky tool calls that a running job/operation is
   waiting on, backed by a durable approvals record.

> **Prerequisite — [DASHBOARD_BACKEND_PLAN.md](DASHBOARD_BACKEND_PLAN.md).** This plan *consumes*
> engine primitives built there: the concurrency-safe `Store` (WAL + serialized writes), the
> durable `operations` and `approvals` models, cooperative cancellation, `store_backed_approval`,
> and the `WorkerPool`. Each phase below names the backend phase it needs. **Land the backend
> plan first.**

**Stack (locked):** Vite + React + TypeScript + Tailwind CSS + **shadcn/ui** (Radix) components,
**TanStack Query** (server state, polling), **TanStack Table** (job/insight/approval tables),
**React Hook Form + Zod** (forms), **react-router**. Live updates use **SSE** (primary) with a
TanStack Query **polling fallback**. Next.js is intentionally not used: this ships as a
pip-installed local tool, so FastAPI serves the static Vite build with zero Node runtime.

All web work is additive to the CLI — no existing command behavior changes.

## Ground truth reused (do not reimplement)
- `InterviewAnswers` dataclass — fields: `org_name, founder, north_star, quarterly_goals: list[str],
  human_team_size: int, domains: list[str], tools: set[str], risk_tier: ApprovalPolicy,
  budget_tier: str, add_amplifier: bool, add_observer: bool, use_lead: bool` —
  [interview.py](../../../src/agent_factory/bootstrap/interview.py). Has `.validate() -> list[str]`,
  `.from_dict(dict)`, `.to_dict()`.
- `generate_org(answers, directors=, workers=, addons=) -> Org` and
  `write_org(org, root: Path) -> None` — [generator.py](../../../src/agent_factory/bootstrap/generator.py).
- `DOMAIN_CHOICES`, `KNOWN_TOOLS`, `ADDONS` — [archetypes.py](../../../src/agent_factory/bootstrap/archetypes.py).
- `Store` class (SQLite) — [state.py](../../../src/agent_factory/runtime/state.py). Path convention:
  `<org_root>/.agentfactory/jobs.db` (confirmed in [cli.py](../../../src/agent_factory/cli.py), e.g. line 280-281).
  Read methods: `list_jobs`, `list_messages`, `list_insights`, `stats`, `recent_events`,
  `list_context`/`search_context`, `pending_messages`. **New in the backend plan:**
  `list_operations`/`get_operation` and `list_approvals`/`get_approval` (consumed here).
- `WorkerPool` — planned in `src/agent_factory/runtime/worker.py` (backend plan B5). The web
  process starts one pool in the app lifespan and enqueues jobs/operations for it to execute.
- `store_backed_approval` + the `operations`/`approvals` tables — backend plan B4/B2. The web
  layer never blocks on an LLM call itself; it only reads/writes these durable records.
- `_confined_path(raw_path, root)` pattern — [tools.py](../../../src/agent_factory/runtime/tools.py) line ~109 —
  mirror this logic for org-name path resolution (reject absolute paths and traversal outside
  the configured orgs root), per [FILESYSTEM_CONFINEMENT.md](../../architecture/FILESYSTEM_CONFINEMENT.md).
- CLI is `argparse`-based with subparsers, each wired via `set_defaults(func=cmd_xxx)` —
  [cli.py](../../../src/agent_factory/cli.py). New `web` subcommand follows the same pattern.

## Execution model for AI agents
- Each task below is scoped to be completed and verified independently (small diff, one
  concern). Tasks marked **[P]** within the same phase have no dependency on each other and
  can be assigned to different agents/sessions in parallel.
- Tasks are numbered `<phase>.<task>` (e.g. `1.3`). "Depends on" references these IDs.
- Every task ends with its own verification step — run it before marking the task done.
- Do not start a task whose "Depends on" list isn't fully complete.
- **Progress tracking:** before starting a task, update its row in the
  [Progress Tracking](#progress-tracking) table to `In Progress`. Immediately after a task's
  verification step passes, update the row to `Done` and fill in the `Notes` column (date,
  commit/PR reference, or anything the next agent should know — e.g. a contract deviation).
  If blocked, set status to `Blocked` and explain why in `Notes` instead of guessing forward.
  This table is the single source of truth for "what's done" — check it before picking up any
  task so parallel agents don't duplicate work.
- **Commit & push per task:** once a task's verification step passes and its Progress Tracking
  row is updated to `Done`, commit the change with a message describing what was implemented
  (reference the task ID, e.g. `"webapp: add read-only org endpoints (task 1.3)"`) and push it.
  Keep commits scoped to one task so history stays reviewable and parallel agents' work doesn't
  get tangled together. If pushing directly to a shared/protected branch isn't allowed by repo
  policy, push to a per-task feature branch instead and note the branch name in the task's
  `Notes` column.

---

## Progress Tracking

Status values: `Not Started` (default) · `In Progress` · `Done` · `Blocked`.

| Task | Description | Backend dep | Status | Notes |
|---|---|---|---|---|
| 0.1 | Add `web` optional-dependency extra + `webapp/static` package-data | — | Not Started | |
| 0.2 | Backend `webapp/` package skeleton | — | Not Started | |
| 0.3 | API contract doc (reads + actions + approvals + SSE) | — | Not Started | |
| 0.4 | Scaffold frontend (Vite + Tailwind + shadcn/ui + TanStack) | — | Not Started | |
| 1.1 | Path confinement + Store accessors + token dep | B1 | Not Started | |
| 1.2 | Pydantic schemas | — | Not Started | |
| 1.3 | Read-only org endpoints | B1 | Not Started | |
| 1.4 | Bootstrap endpoints | — | Not Started | |
| 1.5 | App factory + lifespan (pool + SSE bus) + static serving | B1, B5 | Not Started | |
| 1.6 | CORS dev-mode + localhost bind + optional token | — | Not Started | |
| 1.7 | Backend read/bootstrap test suite | — | Not Started | |
| 2.1 | `operations`-backed action endpoints | B2, B5 | Not Started | |
| 2.2 | SSE stream endpoint | B2 | Not Started | |
| 2.3 | Action endpoint tests (worker + FakeLLM) | B5 | Not Started | |
| 3.1 | Approval endpoints (list pending + decide) | B4 | Not Started | |
| 3.2 | Approval SSE events + tests | B4 | Not Started | |
| 4.1 | API client + typed hooks (TanStack Query + Zod) | — | Not Started | |
| 4.2 | App shell + routing + nav + theme | — | Not Started | |
| 4.3 | Read views (home/overview/chart/jobs/channel/insights/context) | — | Not Started | |
| 4.4 | Action forms (run/ambition/observe/brief/channel) | — | Not Started | |
| 4.5 | Approval Inbox (live) | — | Not Started | |
| 4.6 | Bootstrap Wizard | — | Not Started | |
| 4.7 | Live updates (SSE + polling fallback) | — | Not Started | |
| 4.8 | Production build wiring (copy dist → webapp/static) | — | Not Started | |
| 5.1 | `agent-factory web` CLI subcommand | — | Not Started | |
| 5.2 | Documentation (USER_GUIDE + README) | — | Not Started | |
| 5.3 | Security pass | — | Not Started | |
| 5.4 | Full regression + update ROADMAP/RELEASE_CHECKLIST | — | Not Started | |

---

## Phase 0 — Scaffolding & contracts (must finish before later phases parallelize)

Goal: lock the API contract and project skeleton so backend and frontend agents can work
independently afterward.

### 0.1 — Add `web` optional-dependency extra
- Depends on: none.
- Edit [pyproject.toml](../../../pyproject.toml): add under `[project.optional-dependencies]`:
  ```toml
  web = ["fastapi>=0.110", "uvicorn>=0.27", "sse-starlette>=2.0"]
  ```
  Also add `"webapp/static/**"` under `[tool.setuptools.package-data]` for `agent_factory` so the
  built SPA ships in the wheel.
- Verify: `pip install -e .[web]` succeeds; `python -c "import fastapi, uvicorn, sse_starlette"` works.

### 0.2 — Backend `webapp/` package skeleton
- Depends on: 0.1.
- Create `src/agent_factory/webapp/__init__.py` and docstring-only stubs: `app.py`, `deps.py`,
  `schemas.py`, `events.py`, `routes_orgs.py`, `routes_bootstrap.py`, `routes_actions.py`,
  `routes_approvals.py`. (The worker **pool** itself lives in `runtime/worker.py`, backend plan
  B5 — `webapp` only starts/stops it.)
- Verify: `python -c "import agent_factory.webapp"` works.

### 0.3 — API contract doc (source of truth for backend + frontend)
- Depends on: none (parallel with 0.1/0.2).
- Fill in the [API Contract](#api-contract) section below: every endpoint (reads, actions,
  approvals, bootstrap), request/response JSON shape, status codes, and the SSE event envelope.
  Both the backend and frontend agents work from this, so they can proceed in parallel.
- Verify: the contract covers every endpoint referenced in Phases 1-3.

### 0.4 — Scaffold frontend (Vite + Tailwind + shadcn/ui + TanStack)
- Depends on: none (parallel with 0.1-0.3).
- `npm create vite@latest frontend -- --template react-ts` at repo root, then install and init:
  Tailwind CSS (+ `postcss`/`autoprefixer`), **shadcn/ui** (`components.json`, `@/` path alias in
  `vite.config.ts` + `tsconfig`), `@tanstack/react-query`, `@tanstack/react-table`,
  `react-router-dom`, `react-hook-form`, `zod`, `@hookform/resolvers`, `lucide-react`, and locally
  bundled Sora + DM Mono font assets (no runtime CDN dependency). Configure Tailwind colors and
  radii through the CSS variables in the [Alloy Design System Contract](#alloy-design-system-contract),
  not hard-coded component colors.
- Add `.gitignore` entries for `frontend/node_modules/` and `frontend/dist/`.
- Verify: `cd frontend && npm install && npm run build` produces `frontend/dist/index.html`; a
  shadcn/ui `Button` renders in the default `App.tsx`.

**Phase 0 exit criteria:** `pip install -e .[web]` works, `agent_factory.webapp` importable,
`frontend/` builds with Tailwind + shadcn/ui, and the API contract section is filled in.

---

## Phase 1 — Backend API foundation: reads + app infra

Read endpoints, schemas, and the app factory. **Depends on backend plan B1** (WAL + serialized
writes) so FastAPI request threads read the store safely while the pool writes. Tasks marked
**[P]** are parallel.

### 1.1 — Path confinement + Store accessors + token dependency
- Depends on: 0.2, backend B1.
- In `deps.py`:
  - `resolve_org_path(orgs_root, org) -> Path` — mirror `_confined_path()`: reject absolute or
    `..`-traversing names → `HTTPException(400)`; require the resolved folder to contain
    `org.yaml`, else `HTTPException(404)`.
  - `get_store(org_root) -> Store` — `Store(org_root / ".agentfactory" / "jobs.db")`.
  - `get_orgs_root()` and `get_pool()` — read from `app.state` (set at `create_app` time).
  - `require_token` — optional dependency that checks `Authorization: Bearer <token>` when a token
    is configured; a no-op when none is set.
- Verify: unit test confirms `resolve_org_path` rejects `"../etc"`, `"/abs/path"`, and an org
  folder with no `org.yaml`; `require_token` rejects a bad token only when a token is configured.

### 1.2 — Pydantic schemas **[P]**
- Depends on: 0.2, 0.3.
- In `schemas.py`, define: `OrgSummary`, `RoleNode` (recursive), `JobRow`, `JobDetail`
  (job + events + results), `MessageRow`, `InsightRow`, `ContextRow`, `StatusSummary`,
  `OperationRow`, `ApprovalRow`, the action request bodies (`RunRequest`, `AmbitionRequest`,
  `ObserveRequest`, `BriefRequest`, `ChannelPostRequest`, `ChannelWorkerRequest`,
  `ContextRequest`), `ApprovalDecision`, `BootstrapOptions`, `BootstrapRequest`,
  `BootstrapResponse`, and `ErrorResponse`.
- Verify: `python -c "from agent_factory.webapp.schemas import *"` succeeds; `model_json_schema()`
  runs on each without error.

### 1.3 — Read-only org endpoints **[P]**
- Depends on: 1.1, 1.2.
- In `routes_orgs.py` (`APIRouter`):
  - `GET /api/orgs` → scan `orgs_root` for subdirs with `org.yaml` → `list[OrgSummary]`.
  - `GET /api/orgs/{org}/tree` → parse `org.yaml` + `roles/*.yaml` → nested `RoleNode`.
  - `GET /api/orgs/{org}/jobs?status=&limit=` → `Store.list_jobs` → `list[JobRow]`.
  - `GET /api/orgs/{org}/jobs/{id}` → job + `events_for` + `results_for` → `JobDetail`.
  - `GET /api/orgs/{org}/messages?channel=&limit=` → `list[MessageRow]`.
  - `GET /api/orgs/{org}/insights?status=&level=&limit=` → `list[InsightRow]`.
  - `GET /api/orgs/{org}/context?search=&limit=` → `list[ContextRow]`.
  - `GET /api/orgs/{org}/operations?status=&limit=` → `list[OperationRow]`.
  - `GET /api/orgs/{org}/status` → `stats()` + `recent_events(60)` (+ pending-approval count) →
    `StatusSummary`.
- Verify: each exercised via `TestClient` against a bootstrapped fixture org returns 200 with the
  expected shape; unknown org → 404; traversal name → 400.

### 1.4 — Bootstrap endpoints **[P]**
- Depends on: 1.1, 1.2.
- In `routes_bootstrap.py`:
  - `GET /api/bootstrap/options` → `BootstrapOptions` from `DOMAIN_CHOICES`, `KNOWN_TOOLS`,
    `ADDONS`, risk tiers, budget tiers — reuse the constants `cli.py` uses, don't hardcode copies.
  - `POST /api/bootstrap` → `InterviewAnswers.from_dict(body)`, `.validate()`; on errors →
    `422 {"errors": [...]}`; else `generate_org()` + `write_org(org, orgs_root / org_name)`
    (refuse overwrite → `409`); return `BootstrapResponse`.
- Verify: `TestClient` POST with a valid payload creates the same file set as `agent-factory
  bootstrap --spec`; missing `org_name` → 422; duplicate → 409.

### 1.5 — App factory + lifespan + static serving
- Depends on: 1.3, 1.4, backend B1 + B5.
- In `app.py`: `create_app(orgs_root, *, dev=False, token=None, pool_size=2) -> FastAPI`. Store
  config in `app.state`. Use a **lifespan** that starts a `WorkerPool(size=pool_size)` and the SSE
  event bus on startup and stops them with bounded `stop(drain=False)` on shutdown. The app owns
  the org-local Store cache and closes it after workers join. Include routers under `/api`. Mount
  `webapp/static` via `StaticFiles(html=True)` at `/` if it exists; else a plain `GET /` returns a
  JSON hint (`"frontend not built; run npm run build in frontend/ or npm run dev"`).
- Verify: `TestClient(create_app(tmp))` serves `/api/orgs` (200) and, with no `static/`, `GET /`
  returns the hint (not 500); the pool starts and stops cleanly with the app lifespan.

### 1.6 — CORS dev-mode + localhost bind + token
- Depends on: 1.5.
- Enable CORS for `http://localhost:5173` **only when `dev=True`** (production serves same-origin
  and needs none). Document that the server binds `127.0.0.1` by default (see 5.1) and that a
  `token`, when set, gates `/api`.
- Verify: with `dev=True` an OPTIONS preflight from `:5173` succeeds; with `dev=False` no CORS
  headers are added.

### 1.7 — Backend read/bootstrap test suite
- Depends on: 1.3, 1.4, 1.5, 1.6.
- `tests/test_web_api.py` (FastAPI `TestClient`): seed a temp org via `generate_org`/`write_org`;
  cover `GET /api/orgs`, `/tree`, `/jobs` (empty), traversal → 400, unknown → 404, and the
  bootstrap 201/422/409 cases.
- Verify: `py -m unittest tests.test_web_api -v` green; `ruff check src/agent_factory/webapp
  tests/test_web_api.py` clean.

**Phase 1 exit criteria:** read + bootstrap endpoints pass via `TestClient`; the app factory
serves static or the dev hint; the worker pool starts/stops with the app; `ruff` clean.

---

## Phase 2 — Action endpoints + live status (the "manage" leap)

Trigger long-running work without blocking HTTP: endpoints **enqueue** a job/operation and
return its id; the **worker pool** executes it; the browser follows progress over SSE.
**Depends on backend B2 (operations) + B5 (worker pool).**

### 2.1 — `operations`-backed action endpoints
- Depends on: 1.5, backend B2 + B5.
- In `routes_actions.py` (async actions return `202 {"operation_id": ...}`):
  - `POST /api/orgs/{org}/run` (`RunRequest`: role, task, provider?, model?, approval_mode) →
    `Store.create_operation(kind="run", ...)`.
  - `POST /api/orgs/{org}/ambition` (`AmbitionRequest`: role, max_actions, max_risk, approval_mode).
  - `POST /api/orgs/{org}/observe`, `POST /api/orgs/{org}/brief` (role?, provider?, model?).
  - `POST /api/orgs/{org}/channel/worker` (`ChannelWorkerRequest`: channel, role?, max_messages,
    approval_mode).
  - `POST /api/orgs/{org}/channel/post` (`ChannelPostRequest`) → `Store.post_message` (synchronous,
    no LLM → `201`).
  - `POST /api/orgs/{org}/context` (`ContextRequest`) → `Store.upsert_context` (synchronous → `201`).
  - `POST /api/orgs/{org}/operations/{id}/cancel` → `Store.request_operation_cancel`; queued
    operations become `cancelled`, running operations set the cooperative cancel flag, terminal
    operations return 409.
  - `approval_mode` reuses the CLI `allow|deny|ask` semantics: `ask` maps to the durable approval
    flow (Phase 3); `allow`/`deny` map to the fixed policies.
- Verify: posting each action creates a queued operation the pool then drains (see 2.3); cancel
  flips an in-flight operation to `cancelled`.

### 2.2 — SSE stream endpoint
- Depends on: 2.1, backend B2.
- In `events.py`: an SSE hub (per-org subscriber set) and `GET /api/orgs/{org}/stream` (via
  `sse-starlette`). The pool/store publish small envelopes on state changes:
  `{"type": "job"|"operation"|"approval"|"event", "id": ..., "status": ...}`, plus periodic
  keep-alive comments. The browser uses these to invalidate TanStack Query caches.
- Verify: a `TestClient`/httpx subscriber receives an `operation` event when an action posted in
  2.1 transitions `queued → running → done`.

### 2.3 — Action endpoint tests
- Depends on: 2.1, 2.2, backend B5.
- `tests/test_web_actions.py` (FakeLLM, small pool, short intervals): `run` → operation and its
  spawned job reach `done`; `ambition`/`observe`/`brief` → operation `done` with the expected
  rows; `channel/post` + `channel/worker` produce a reply; cancel path works; SSE emits the
  transitions.
- Verify: `py -m unittest tests.test_web_actions -v` green; `ruff` clean.

**Phase 2 exit criteria:** every action enqueues and is executed by the pool with live SSE
status; synchronous actions (channel post, context) work inline; all covered by offline tests.

---

## Phase 3 — Interactive approvals API

Surface durable pending approvals and let the operator decide. **Depends on backend B4
(`approvals` + `store_backed_approval`).**

### 3.1 — Approval endpoints
- Depends on: 1.5, backend B4.
- In `routes_approvals.py`:
  - `GET /api/orgs/{org}/approvals?status=pending&limit=` → `Store.list_approvals` →
    `list[ApprovalRow]` (includes `tool`, `action_args`, `risk`, `role`, linked job/operation).
  - `POST /api/orgs/{org}/approvals/{id}/decide` (`ApprovalDecision`: `decision: approved|denied`,
    `decided_by?`) → `Store.resolve_approval`; returns the updated row.
- Verify: with a paused FakeLLM operation (from B4/B5) that created a pending approval, `GET`
  lists it; `POST .../decide {approved}` lets the tool run and the operation finish; `{denied}`
  prevents that tool call while allowing the agent to recover or finish normally.

### 3.2 — Approval SSE events + tests
- Depends on: 3.1, 2.2.
- Publish `approval` envelopes (`created`, `resolved`) on the org SSE stream so the Approval
  Inbox updates live.
- `tests/test_web_approvals.py`: pending appears via API + SSE; approve → tool executes; deny →
  tool does not execute and the operation follows its eventual agent outcome; duplicate/racing
  decisions return 409; cross-org approval ids remain isolated; a second queued operation still runs on another pool worker while one
  is parked (proves Option-B pool behavior end-to-end through the API).
- Verify: `py -m unittest tests.test_web_approvals -v` green.

**Phase 3 exit criteria:** operators can list and resolve approvals over the API with live SSE
updates; approve/deny alter operation outcomes; offline tests cover it.

---

## Phase 4 — Frontend SPA (React + Vite + shadcn/ui)

Built against the 0.3 contract; wired to the live backend once Phases 1-3 are up. Uses TanStack
Query for all server state and SSE for live invalidation with a polling fallback. Tasks marked
**[P]** are parallel.

### Alloy Design System Contract

The Web Console **must implement the approved Alloy design**, not the default shadcn/ui theme.
The interactive visual source of truth is
[WEB_CONSOLE_DIRECTIONS.html](../../product/WEB_CONSOLE_DIRECTIONS.html). Treat it as a reference
to reproduce with reusable React components and tokens, not as application code to copy. Where
this plan and the reference differ, functional/accessibility requirements in this plan win while
the Alloy visual language remains intact.

**Brand and themes**
- Product lockup: the compact geometric Agent Factory mark + `AGENT FACTORY` wordmark shown in
  the reference. Deliver the mark as a reusable component and provide favicon/app-icon variants;
  do not use decorative illustrations, photography, glassmorphism, or gradient decoration.
- **Alloy Night is the default on first use.** A sun/moon segmented control switches themes and
  persists an explicit choice in `localStorage`; both modes use the same spacing, geometry,
  hierarchy, status meanings, and component behavior. Set `color-scheme` appropriately.
- Typography: **Sora** for interface/display text and **DM Mono** for IDs, timestamps, model names,
  keyboard hints, code, and machine state. Bundle WOFF2 assets into the Vite build so the packaged
  console works offline; use sensible local fallbacks while fonts load.
- Geometry: 4px spacing base, 6px control/panel radius, restrained 1px borders, minimal elevation,
  stable control dimensions, and compact data density. Cards are only for discrete records,
  approvals, and framed tools; page sections remain unframed.

**Semantic color tokens** (expose as CSS variables and map into Tailwind/shadcn tokens):

| Token | Alloy Night | Alloy Light | Use |
|---|---:|---:|---|
| `surface` | `#151719` | `#F3F5F6` | App/workspace background |
| `surface-raised` | `#1D2023` | `#FFFFFF` | Controls, rows, discrete panels |
| `surface-subtle` | `#252A2E` | `#E8ECEE` | Hover, table header, inset content |
| `text` | `#F2F1EC` | `#191C1F` | Primary text |
| `text-muted` | `#9BA3AA` | `#626B72` | Secondary text |
| `border` | `#353B40` | `#D5DADE` | Dividers and control boundaries |
| `accent` | `#F2AD3D` | `#D48A12` | Brand, selection, primary attention |
| `success` | `#5AC7A7` | `#247E69` | Complete/connected/approved |
| `info` | `#6EA2FF` | `#356FCB` | Running, links, informational states |
| `danger` | `#EF6A5B` | `#C64F45` | Failed, denied, destructive actions |
| `rail` | `#101214` | `#191C1F` | Persistent navigation anchor |

Color must never be the only status signal: pair it with text and/or a Lucide icon. Check all
foreground/background pairs at WCAG AA; add derived focus, hover, disabled, warning, chart, and
overlay tokens without changing these anchors. Use Lucide icons through `lucide-react`, with
tooltips and accessible names for unfamiliar icon-only controls.

**Reusable Alloy building blocks**
- Layout: `AppShell`, collapsible `NavRail`, `TopBar`, `OrgSwitcher`, `PageHeader`, `ThemeToggle`,
  responsive mobile drawer, and keyboard command trigger.
- Data/status: `MetricStrip`, `DataTable`, `StatusBadge`, `LiveIndicator`, `EventTimeline`,
  `OperationProgress`, `EmptyState`, `Skeleton`, `Toast`, and `ErrorState`.
- Domain: `ApprovalPanel`, `OrgTree`, `RoleGlyph`, `InsightCallout`, `ChannelThread`, and shared
  action-form framing. Build these before view-specific copies; do not nest cards inside cards.
- Motion: 120-220ms transitions for hover, selection, panel entry, and resolved approvals; a
  restrained pulse only for genuinely live work. Honor `prefers-reduced-motion` and never animate
  layout dimensions in a way that causes content shift.
- Responsive behavior: desktop uses the compact rail and dense tables; mobile uses a drawer,
  preserves primary actions, and converts wide tables to intentional reduced-column or detail-row
  views. No horizontal page overflow at 390px, 768px, 1280px, or 1440px widths.

### 4.1 — API client + typed hooks
- Depends on: 0.3, 0.4.
- `src/api/client.ts` (fetch wrapper: base URL from `VITE_API_BASE_URL`, bearer token, error
  mapping), `src/api/endpoints.ts` (one fn per contract endpoint), `src/api/types.ts` (interfaces
  mirroring the Pydantic schemas), `src/api/sse.ts` (EventSource subscription + reconnect).
  `src/hooks/` — one TanStack Query hook per resource plus `useOrgStream.ts` (SSE → cache
  invalidation).
- Verify: `tsc --noEmit` clean; a manual `listOrgs()` smoke test against a running backend returns
  the expected shape.

### 4.2 — App shell + routing + nav + theme **[P]**
- Depends on: 4.1.
- `main.tsx` (QueryClientProvider + Router), `App.tsx` (`<Routes>`), `components/layout/`
  (`AppShell`, `NavRail`, `TopBar`, `OrgSwitcher`, `ThemeToggle`), and the complete Alloy semantic
  token/theme layer in `index.css`. Dark is the first-run default; an explicit dark/light choice
  persists across reloads without a flash of the wrong theme. Routes: `/`,
  `/orgs/:org` (overview), `/orgs/:org/chart`, `/orgs/:org/jobs`, `/orgs/:org/channel`,
  `/orgs/:org/insights`, `/orgs/:org/context`, `/orgs/:org/approvals`, `/bootstrap`.
- Verify: `npm run dev`, navigate every route in both themes, reload to confirm persistence, and
  confirm no console errors or 404 gaps. Capture Playwright screenshots of the overview at 1440px
  and 390px in both modes and compare them with the approved reference; run an automated
  accessibility scan and keyboard-navigation smoke test.

### 4.3 — Read views **[P]**
- Depends on: 4.1, 4.2.
- `routes/Home.tsx` (org list + empty-state → `/bootstrap`), `OrgOverview.tsx` (status cards incl.
  pending-approval count), `OrgChart.tsx` (recursive `components/org/RoleNode.tsx`), `Jobs.tsx`
  (TanStack Table + status filter + drill-in to `JobDetail`), `Channel.tsx` (feed + post box),
  `Insights.tsx` (table + status update), `Context.tsx` (diary + search). Compose the Alloy
  building blocks above; do not create per-route substitutes for shared status, table, or
  empty/loading patterns.
- Verify: each renders real data against the running backend with no console errors.

### 4.4 — Action forms **[P]**
- Depends on: 4.1, 4.2.
- `components/actions/` with React Hook Form + Zod: `RunTaskForm`, `AmbitionForm`
  (max-actions/max-risk), `ObserveForm`, `BriefForm`, `ChannelWorkerForm`. On submit → the Phase 2
  endpoints; show the returned operation and its live status using `OperationProgress`. Buttons
  and progress motion follow Alloy tokens and reduced-motion behavior.
- Verify: submitting each form enqueues work that appears (via SSE) moving to `done`.

### 4.5 — Approval Inbox (live) **[P]**
- Depends on: 4.1, 4.2, Phase 3.
- `routes/Approvals.tsx` + `components/approvals/` — list pending approvals (tool, args, risk,
  role) with the Alloy `ApprovalPanel`; Approve/Deny buttons →
  `POST /orgs/{org}/approvals/{id}/decide`;
  live via SSE. Risk is communicated with label + icon + color, and approval resolution uses a
  short, non-layout-shifting state transition.
- Verify: a pending approval appears without manual refresh; deciding it updates the list and the
  linked operation.

### 4.6 — Bootstrap Wizard **[P]**
- Depends on: 4.1, 4.2.
- `routes/BootstrapWizard.tsx` — multi-step form from `getBootstrapOptions()` mirroring the CLI
  interview (identity → goals/team → domains → tools → risk/budget/addons). Submit →
  `postBootstrap()`; 201 → redirect to `/orgs/:org`; 422 → inline field errors; 409 → "org exists".
  Use the same Alloy shell, controls, focus treatment, and status language; do not turn the wizard
  into a separate marketing/landing-page visual style.
- Verify: a full walkthrough against the backend creates a real org that then appears in the
  dashboard.

### 4.7 — Live updates (SSE + polling fallback)
- Depends on: 4.3-4.6.
- `useOrgStream` subscribes to `/api/orgs/{org}/stream` and invalidates the relevant queries on
  each envelope; TanStack Query `refetchInterval` provides a polling fallback when SSE is
  unavailable.
- Verify: killing the SSE connection still refreshes views via polling; with SSE up, updates are
  near-immediate with no redundant polling storms.

### 4.8 — Production build wiring
- Depends on: 4.7.
- `npm run build` → `frontend/dist/`; a documented build step (see 5.2, e.g. a `tools/` helper or
  npm script) copies `frontend/dist/` → `src/agent_factory/webapp/static/` so `agent-factory web`
  serves it. Confirm `create_app` (1.5) serves it when `dev=False`.
- Verify: with `static/` populated and no `npm run dev` running, `agent-factory web` serves the
  full app at `http://127.0.0.1:8765`.

**Phase 4 exit criteria:** all views + forms + approval inbox + wizard work end-to-end against the
live backend with live SSE updates; the built SPA is served by FastAPI from `webapp/static`;
Alloy Night and Alloy Light match the approved reference, persist correctly, pass WCAG AA and
keyboard checks, honor reduced motion, and have no overlap or horizontal overflow at the required
desktop/mobile widths.

---

## Phase 5 — CLI wiring, docs, security, regression

### 5.1 — `agent-factory web` CLI subcommand
- Depends on: Phase 1 (1.5).
- In [cli.py](../../../src/agent_factory/cli.py): `cmd_web(args)` builds `create_app(Path(args.org),
  dev=args.dev, token=args.token, pool_size=args.pool_size)` and runs it via
  `uvicorn.run(host=args.host, port=args.port)`. Import `uvicorn`/`fastapi` lazily and print a
  friendly `pip install agent_factory[web]` hint on `ImportError`. Subparser flags: `--org`
  (default `./orgs`), `--host` (default `127.0.0.1`), `--port` (default `8765`), `--pool-size`
  (default `2`), `--dev` (flag), `--token` (optional). Print the URL before serving.
- Verify: `agent-factory web --org orgs` starts, prints the URL, `Ctrl+C` exits cleanly; without
  the `web` extra it prints the hint, not a traceback; default bind is `127.0.0.1`.

### 5.2 — Documentation **[P]**
- Depends on: none (finalize flag names before merge).
- Add a "Web Console" section to [USER_GUIDE.md](../../product/USER_GUIDE.md): install
  `pip install agent_factory[web]`, build the frontend (`cd frontend && npm install && npm run
  build`, then the copy-to-`webapp/static` step), run `agent-factory web --org ./orgs`, and a tour
  of dashboard + actions + approvals + wizard. One-line mention in [README.md](../../../README.md).
- Verify: a fresh clone following the steps reaches a working console.

### 5.3 — Security pass **[P]**
- Depends on: Phases 1-3.
- Confirm: binds `127.0.0.1` by default (`0.0.0.0` only via explicit `--host`); `--token` gates
  `/api` when set; path confinement holds on every org param; responses never leak secrets/env or
  absolute filesystem paths; CORS only in `--dev`. Note in [SECURITY.md](../../../SECURITY.md) that
  the console can trigger spend/external actions and is localhost-only by default.
- Verify: traversal → 400; token enforced when set; a scan of responses shows no secret/env/path
  leakage.

### 5.4 — Full regression + roadmap update
- Depends on: 5.1, 5.2, 5.3.
- Run the full offline suite (`py -m unittest discover -s tests -v`) — 169 Phase 0 baseline tests plus
  the new web tests — and `ruff check` repo-wide, and `cd frontend && npm run build && tsc
  --noEmit`. Add a Release 2.0 entry mirroring [RELEASE_CHECKLIST_1.0.md](../v1.0.0/RELEASE_CHECKLIST_1.0.md)
  and annotate [ROADMAP.md](../../planning/ROADMAP.md).
- Verify: all tests green; lint clean; frontend builds; checklist maps 1:1 to shipped tasks.
- Visual verify: run the Phase 4 Playwright screenshot matrix for Alloy Night/Light at desktop and
  mobile widths and include the reviewed captures in the Release 2.0 checklist.

**Phase 5 / Release 2.0 exit criteria:** `agent-factory web` works end-to-end from a clean install
per the docs; full test suite + lint + frontend build clean; docs and roadmap updated.

---

## Suggested agent assignment for parallel execution
- **Backend engine:** complete [DASHBOARD_BACKEND_PLAN.md](DASHBOARD_BACKEND_PLAN.md) `B1 → B5`
  first — it gates web Phases 1-3.
- **Agent A (web backend):** Phase 0 (0.1-0.3), then Phase 1, then Phase 2, then Phase 3, then 5.1.
- **Agent B (frontend):** Phase 0 (0.4), then Phase 4 (4.1-4.2, then 4.3-4.6 in parallel), then
  4.7-4.8 once Agent A's endpoints are live.
- **Agent C (contract/docs):** 0.3 first (unblocks A and B), then 5.2-5.3 near the end.
- Sync points: Phase 0 fully done before A/B parallelize; backend `B2+B5` done before web Phase 2;
  `B4` done before web Phase 3; A's endpoints live before B's 4.7-4.8.

## Directory structure

Backend web layer — ships inside the pip package:
```
src/agent_factory/webapp/
├── __init__.py
├── app.py              # create_app(orgs_root, *, dev, token, pool_size) + lifespan (pool + SSE bus)
├── deps.py             # resolve_org_path, get_store, get_orgs_root, get_pool, require_token
├── schemas.py          # Pydantic request/response models (the API contract)
├── events.py           # SSE hub + GET /api/orgs/{org}/stream
├── routes_orgs.py      # read endpoints
├── routes_bootstrap.py # options + create org
├── routes_actions.py   # run/ambition/observe/brief/channel/context (enqueue → pool)
├── routes_approvals.py # list pending + decide
└── static/             # BUILT SPA copied here at build time; served by FastAPI (gitignored)
```
The worker **pool** lives in `runtime/worker.py` (backend plan B5); `webapp/app.py` only starts and
stops it in the FastAPI lifespan.

Frontend source — repo root, NOT shipped in the wheel (`node_modules/` + `dist/` gitignored):
```
frontend/
├── index.html  package.json  vite.config.ts  tailwind.config.ts  postcss.config.js
├── components.json            # shadcn/ui config
├── tsconfig*.json  .env.development   # VITE_API_BASE_URL for `npm run dev`
└── src/
    ├── main.tsx  App.tsx  index.css  vite-env.d.ts
    ├── lib/                  # utils.ts (cn), query.ts (QueryClient)
    ├── api/                  # client.ts, endpoints.ts, sse.ts, types.ts
    ├── schemas/              # Zod schemas (mirror Pydantic)
    ├── hooks/                # TanStack Query hooks + useOrgStream.ts
    ├── components/           # ui/ (shadcn), layout/, jobs/, org/, channel/, insights/, approvals/, actions/, common/
    └── routes/               # Home, OrgOverview, OrgChart, Jobs, Channel, Insights, Context, Approvals, BootstrapWizard
```
Packaging: `npm run build` → `frontend/dist/`, copied to `src/agent_factory/webapp/static/`
(included via `package-data` from 0.1); FastAPI serves `webapp/static` when present, else the dev
hint. Vite uses the `@/` path alias (shadcn convention).

## API Contract

Base path `/api`. All responses `application/json`. Errors use `{"detail": "..."}` (FastAPI
default) for 400/404/409, and `{"errors": [...]}` for 422 bootstrap validation. When a `--token`
is configured, `/api/*` requires `Authorization: Bearer <token>`.

### Reads
| Method & Path | Response (200) | Errors |
|---|---|---|
| `GET /orgs` | `OrgSummary[]` = `{name, founder, north_star}[]` | — |
| `GET /orgs/{org}/tree` | `RoleNode` = `{id, title, proactivity_level, tool_grant_count, children: RoleNode[]}` | 400, 404 |
| `GET /orgs/{org}/jobs?status=&limit=` | `JobRow[]` = `{id, org, role, task, status, provider, created_at}[]` | 400, 404 |
| `GET /orgs/{org}/jobs/{id}` | `JobDetail` = `{job: JobRow, events: EventRow[], results: ResultRow[]}` | 400, 404 |
| `GET /orgs/{org}/messages?channel=&limit=` | `MessageRow[]` | 400, 404 |
| `GET /orgs/{org}/insights?status=&level=&limit=` | `InsightRow[]` | 400, 404 |
| `GET /orgs/{org}/context?search=&limit=` | `ContextRow[]` | 400, 404 |
| `GET /orgs/{org}/operations?status=&limit=` | `OperationRow[]` = `{id, kind, status, result, error, job_id, created_at}[]` | 400, 404 |
| `GET /orgs/{org}/status` | `StatusSummary` = `{stats: {...}, recent_events: EventRow[], pending_approvals: int}` | 400, 404 |

### Actions (async return `202` unless noted)
| Method & Path | Request | Response | Errors |
|---|---|---|---|
| `POST /orgs/{org}/run` | `RunRequest` = `{role, task, provider?, model?, approval_mode}` | `{operation_id}` | 400, 404, 422 |
| `POST /orgs/{org}/ambition` | `AmbitionRequest` = `{role, max_actions, max_risk, approval_mode}` | `{operation_id}` | 400, 404, 422 |
| `POST /orgs/{org}/observe` | `{role?, provider?, model?}` | `{operation_id}` | 400, 404 |
| `POST /orgs/{org}/brief` | `{role?, provider?, model?}` | `{operation_id}` | 400, 404 |
| `POST /orgs/{org}/channel/worker` | `ChannelWorkerRequest` = `{channel, role?, max_messages, approval_mode}` | `{operation_id}` | 400, 404, 422 |
| `POST /orgs/{org}/channel/post` | `ChannelPostRequest` = `{channel, text, author, role}` | `201 {message_id}` (sync) | 400, 404, 422 |
| `POST /orgs/{org}/context` | `ContextRequest` = `{key, detail, source?}` | `201 {key}` (sync) | 400, 404, 422 |
| `POST /orgs/{org}/operations/{id}/cancel` | — | `{operation_id, status}` | 400, 404 |

### Approvals
| Method & Path | Request | Response | Errors |
|---|---|---|---|
| `GET /orgs/{org}/approvals?status=pending&limit=` | — | `ApprovalRow[]` = `{id, role, tool, action_args, risk, status, job_id, operation_id, created_at}[]` | 400, 404 |
| `POST /orgs/{org}/approvals/{id}/decide` | `ApprovalDecision` = `{decision: "approved"\|"denied", decided_by?}` | `ApprovalRow` | 400, 404, 409 (already decided), 422 |

### Bootstrap
| Method & Path | Request | Response | Errors |
|---|---|---|---|
| `GET /bootstrap/options` | — | `BootstrapOptions` = `{domains, tools, risk_tiers, budget_tiers, addons}` | — |
| `POST /bootstrap` | `BootstrapRequest` (= `InterviewAnswers.to_dict()` shape) | `201 BootstrapResponse` = `{org_name, path, role_count}` | 422 `{errors}`, 409 exists |

### SSE
`GET /orgs/{org}/stream` (`text/event-stream`) emits envelopes
`{"type": "job"|"operation"|"approval"|"event", "id": int, "status": string}` plus periodic
keep-alive comments. Clients invalidate the matching TanStack Query cache on each envelope.

*(Exact field shapes are finalized in 0.3/1.2 — update this table in place if a shape changes.)*

## Relevant files
- `pyproject.toml` — `web` extra + `webapp/static/**` package-data (0.1).
- `src/agent_factory/webapp/` — `app, deps, schemas, events, routes_orgs, routes_bootstrap,
  routes_actions, routes_approvals` (Phases 0-3).
- `src/agent_factory/runtime/worker.py`, `state.py` (operations/approvals), `tools.py`
  (`store_backed_approval`) — built in [DASHBOARD_BACKEND_PLAN.md](DASHBOARD_BACKEND_PLAN.md),
  consumed here.
- `src/agent_factory/cli.py` — `cmd_web` + subparser (5.1); reuse `_approval_policy` + option
  constants and the `InterviewAnswers` shape for wizard parity.
- `src/agent_factory/bootstrap/{interview,generator,archetypes}.py` — reused by wizard endpoints.
- New: `frontend/` (see [Directory structure](#directory-structure)).
- New tests: `tests/test_web_api.py` (1.7), `tests/test_web_actions.py` (2.3),
  `tests/test_web_approvals.py` (3.2).

## Verification (release-level, see also per-task verification above)
1. Backend engine: [DASHBOARD_BACKEND_PLAN.md](DASHBOARD_BACKEND_PLAN.md) plan-level verification
   passes (offline suite green; WAL/operations/approvals/worker covered).
2. `py -m unittest discover -s tests -v` green (169 at the Phase 0 baseline + new web tests); `ruff check`
   clean repo-wide; `cd frontend && npm run build && tsc --noEmit` clean.
3. Manual: `pip install -e .[web]`, build + copy the frontend, `agent-factory web --org orgs`,
   open the printed URL; create an org via the wizard; run an action and watch it move to `done`
   live; trigger a high-risk action and approve it from the Approval Inbox.
4. Manual: the dashboard for `orgs/Acme` matches `agent-factory status`/`jobs`/`channel list` for
   the same org.
5. Visual/accessibility: Alloy Night is the first-run default; the persisted Alloy Light toggle
  works without a wrong-theme flash; desktop/mobile screenshots match
  [WEB_CONSOLE_DIRECTIONS.html](../../product/WEB_CONSOLE_DIRECTIONS.html); keyboard navigation,
  reduced motion, WCAG AA contrast, and zero horizontal page overflow are verified in both modes.

## Further Considerations
1. **Auth is local-first.** Default bind is `127.0.0.1` with an optional bearer token; there is no
   multi-user login. A hosted/multi-user deployment would need real auth plus the PostgreSQL
   `Store` backend (roadmap), reusing these same endpoints.
2. **Approvals hold a worker slot.** Per the backend plan, a pending approval parks a pool worker
   (Option B, default size 2). If many approvals stack up, raise `--pool-size` or adopt true
   suspend/resume later; the API and UI are unaffected.
3. **True streaming logs.** v1 streams coarse state envelopes over SSE; token-level streaming of an
   agent's output is a later enhancement that does not change the contract.
