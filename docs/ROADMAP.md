# Roadmap — Upcoming Steps

> Ordered so each milestone builds on the last. Milestone 3 (bootstrap) is done;
> the remaining milestones turn the generated charts into a *running factory*.

## M1 — Runtime engine ✅ (implemented)
Convert the generated config into live agents.

- **Goal:** load an `Org` from disk and run it. **Done** — see `IMPLEMENTED_MILESTONE1.md`.
- **LLM adapters:** provider-agnostic `LLMClient` — OpenAI (default, dual API-gen support), Ollama (local Gemma/Qwen), Fake (offline). Selected via `AGENT_FACTORY_PROVIDER`.
- **Agent loop:** each role becomes a runnable agent; JSON action protocol, grants respected, `requires_approval` gated.
- **SQLite state:** durable `jobs`/`results`/`events` store in the org folder.
- **Tests:** 40 total, offline via FakeLLM.
- **Exit criteria met:** `run` CLI enqueues a job and a worker completes it end-to-end with recorded state.

## M2 — Ambition loop ✅ (implemented)
Make the workforce *proactive*, not just reactive.

- **Goal:** the lead role is licensed to initiate net-new work against goals + context, per its `proactivity_level`. **Done** — see `IMPLEMENTED_MILESTONE2.md`.
- **Context store:** diary/context flow added to the SQLite store (`context` table) so "the company stays queryable" (video 12:25–13:33).
- **Scope/permission breadth:** propose→execute→learn loop (`propose_actions`, `run_ambition_loop`); `max_risk`/`max_actions` gates keep the approval ceiling.
- **Tests:** 53 total, offline; proactive-vs-passive gating verified with fake-LLM scenarios (role with level ≥ 3 initiates; level < 3 does not).

## M3 — (done) Bootstrap
See `IMPLEMENTED_MILESTONE3.md`.

## M4 — Insights (observers + mission control)
- **Observer roles:** low-cost scan agents that log friction, access gaps, contradictions.
- **Watchdogs:** "insight → action," not just dashboards — tell the user *what to do tomorrow* (video 22:20–23:31, 26:04).
- **Mission control:** a CLI/report view of queue, agent activity, handoffs, and open approvals.

## M5 — Role packs (specialized orgs)
- Package the same engine for business-ops, engineering, and research orgs.
- Larger orgs: many directors + many workers, with repeatable `--spec` templates.
- Consider `site-packages`-style naming (sphinx/video 2015-titles-then-evolve, 19:34).

## M6 — Multiplayer & tool surface (optional, later)
- Human teammates talk to the workforce via a shared channel (video 23:56 Loop Alley pattern).
- Broader MCP/local tool surface + permission model polish.

## Suggested order & reasoning

1. **M1** first — nothing can *run* until roles can actually execute; it also
   de-risks schema gaps (e.g., tool contracts) before building on them.
2. **M2** next — proactivity is the "product" of the video and the biggest
   differentiator; needs M1 to exist.
3. **M4** — valuable visibility layer; depends on running agents.
4. **M5** — packs on top of an already-working engine (your original
   "generic now, specialized later").

## Trackable definition of done (per milestone)

- [x] M3 bootstrap + 16 tests
- [x] M1 runtime: provider adapter, agent loop, SQLite, offline tests (24 more — 40 total)
- [x] M2 ambition loop: proactive propose/execute, context store, guarded scope (13 more — 53 total)
- [ ] M4 mission control + observers/watchdogs
- [ ] M5 role packs (business-ops / engineering / research)
- [ ] M6 multiplayer + wider tool surface

Each milestone should keep the test suite green (offline, no API keys).