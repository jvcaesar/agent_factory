# QA — Release 2.0 (Management Dashboard)

> **Status:** DRAFT skeleton — fill in as RC-17 (error-path pass) and RC-21
> (live dashboard proof run) are executed. Mirrors the format of
> [QA_1.0.md](../v1.0.0/QA_1.0.md).
> **Tracked by:** [RELEASE_CHECKLIST_2.0.md](RELEASE_CHECKLIST_2.0.md) — RC-17, RC-21.

---

## RC-17 — Error-path QA (web + CLI)

Exercise the new `web` command and key API endpoints with bad input, plus a fresh
sweep of the existing CLI commands. Every handled case must exit cleanly (friendly
message, correct HTTP status / non-zero exit) — no tracebacks, no 500s on handled
paths. Paste captured output below; head each block `=== <case> (rc=N) clean ===`.

### CLI: `agent-factory web` bad input
- [ ] `web --org <missing>` → friendly error, non-zero exit
- [ ] `web --port <in-use>` → friendly bind error, no traceback
- [ ] `web` without the `[web]` extra installed → `pip install agent_factory[web]` hint

```
(paste output here)
```

### API: bad requests (TestClient / curl)
- [ ] `GET /api/orgs/../etc/tree` (path traversal) → 400
- [ ] `GET /api/orgs/<unknown>/status` → 404
- [ ] `POST /api/bootstrap` missing `org_name` → 422 `{errors}`
- [ ] `POST /api/bootstrap` duplicate org → 409
- [ ] `POST /api/orgs/{org}/approvals/{id}/decide` already-decided → 409
- [ ] any `/api/*` with a bad bearer token (when `--token` set) → 401

```
(paste status + body per case)
```

### Existing CLI sweep (regression)
- [ ] The 13 pre-2.0 commands still error cleanly (see [QA_1.0.md](../v1.0.0/QA_1.0.md) baseline).

---

## RC-21 — Live end-to-end dashboard proof run

With a real provider (OpenAI key or a running Ollama): launch `agent-factory web`
and drive the whole loop from the browser. Capture screenshots or trimmed output.

- [ ] Bootstrap Wizard creates a new org (files match `agent-factory bootstrap`)
- [ ] `run` action → operation + spawned job reach `done` (live SSE status)
- [ ] `ambition` action → operation `done`, proposals recorded
- [ ] `brief` action → narrative brief rendered
- [ ] `channel post → worker` → agent reply appears in-channel
- [ ] high-risk action → pending approval in the Inbox → **approve** → tool runs
- [ ] same high-risk action → **deny** path → tool does not execute; operation follows the eventual agent outcome

**Provider(s) exercised:** _(e.g. OpenAI `gpt-4o-mini`, Ollama `gemma3:12b`)_
**Org used:** _(e.g. `orgs/QA_2.0`)_
**Date:** _(fill on run)_
```
(paste trimmed flow output / screenshot references here)
```
