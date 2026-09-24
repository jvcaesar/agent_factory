# Release Notes for v2.0.0 (DRAFT)

**Repository:** jvcaesar/agent_factory
**Tag:** v2.0.0 (pending)
**Release Title:** Agent Factory 2.0.0 — Management Dashboard

> **Status:** DRAFT — finalize at RC-20. Tracked by
> [RELEASE_CHECKLIST_2.0.md](RELEASE_CHECKLIST_2.0.md). Fill the Changelog section
> from the `[2.0.0]` entry in [CHANGELOG.md](../../../CHANGELOG.md) (RC-12).

---

## Release Highlights

### Headline Features
- **Web Console** — a local browser dashboard to *manage* the workforce
  (`agent-factory web`), not just view it
- **Bootstrap Wizard** — create an org from web forms (reuses the CLI generator)
- **Action controls** — trigger `run` / `ambition` / `observe` / `brief` / channel
  work from the UI; executed off the request path by a bounded worker pool with
  live SSE status
- **Approval Inbox** — approve/deny risky tool calls from the browser, backed by a
  durable approvals record
- **Engine enablement** — WAL-mode concurrent `Store`, durable `operations` +
  `approvals`, cooperative cancellation, and a bounded `WorkerPool`

### Stack
- Backend: FastAPI + Uvicorn (opt-in `[web]` extra); serves the static SPA (zero Node at runtime)
- Frontend: Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Query/Table + React Hook Form/Zod
- Live updates: SSE (primary) + polling fallback

### Supported Providers
| Provider | Status | Notes |
|----------|--------|-------|
| OpenAI | ✅ Real adapter | Requires `OPENAI_API_KEY` |
| Ollama | ✅ Real adapter | Local, auto-resolves bare model names |
| Fake | ✅ Offline | Deterministic, for testing |

### Security
- Localhost bind (`127.0.0.1`) by default; `0.0.0.0` only via an explicit `--host`
- Optional bearer token gates `/api`
- Org-path confinement on every endpoint; CORS enabled only in `--dev`
- Existing filesystem / SSRF / risk-gating protections unchanged

### Upgrade notes
- **Internal API change:** `ApprovalFn` widened to `(tool, tool_input)`. No public
  CLI change; `Store` schema migrations are additive (existing org DBs upgrade in place).

### Known Limitations
- **Approvals hold a worker slot** — a pending approval parks a pool worker
  (default `--pool-size 2`); raise it if many stack up
- **Single-host store** — SQLite + WAL; no PostgreSQL / multi-host yet
- **Coarse SSE** — state envelopes only; no token-level output streaming
- **Local-first auth** — no multi-user login

---

## Changelog

### Added
- _(fill from the `[2.0.0]` CHANGELOG entry at RC-12)_

### Changed
- `ApprovalFn` signature widened to `(tool, tool_input)`; additive `Store` schema (`operations`, `approvals` tables)

### Fixed
- _(fill on release)_

### Removed
- _(none expected)_
