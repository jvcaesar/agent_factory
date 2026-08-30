# Roadmap — Upcoming Steps

> Ordered so each milestone builds on the last. Milestone 3 (bootstrap) is done;
> the remaining milestones turn the generated charts into a *running factory*.

## M1 — Runtime engine ✅ (implemented)
Convert the generated config into live agents.

- **Goal:** load an `Org` from disk and run it. **Done** — see `IMPLEMENTED_MILESTONE1.md`.
- **LLM adapters:** provider-agnostic `LLMClient` — OpenAI (default, modern SDK), Ollama (local Gemma/Qwen), Fake (offline). Selected via `AGENT_FACTORY_PROVIDER`, with per-run `--model` overrides.
- **Agent loop:** each role becomes a runnable agent; JSON action protocol, grants respected, `requires_approval` gated.
- **SQLite state:** durable `jobs`/`results`/`events` store in the org folder.
- **Tests:** 87 total, offline via FakeLLM.
- **Exit criteria met:** `run` CLI enqueues a job and a worker completes it end-to-end with recorded state.

## M2 — Ambition loop ✅ (implemented)
Make the workforce *proactive*, not just reactive.

- **Goal:** the lead role is licensed to initiate net-new work against goals + context, per its `proactivity_level`. **Done** — see `IMPLEMENTED_MILESTONE2.md`.
- **Context store:** diary/context flow added to the SQLite store (`context` table) so "the company stays queryable" (video 12:25–13:33).
- **Scope/permission breadth:** propose→execute→learn loop (`propose_actions`, `run_ambition_loop`); `max_risk`/`max_actions` gates keep the approval ceiling.
- **Tests:** 87 total, offline; proactive-vs-passive gating verified with fake-LLM scenarios (role with level ≥ 3 initiates; level < 3 does not).

## M3 — (done) Bootstrap
See `IMPLEMENTED_MILESTONE3.md`.

## M4 — Insights ✅ (implemented)
- **Observer roles:** low-cost scan agents log friction, access gaps, blockers, contradictions, opportunities (video 22:20–23:31).
- **Watchdogs / insight → action:** "what should I do today" brief, not dashboards (video 26:04).
- **Mission control:** `status` CLI report of queue, agent activity, open insights, approvals. See `IMPLEMENTED_MILESTONE4.md`. 95 tests.

## M5 — Role packs ✅ (implemented)
- Package the engine for business-ops, engineering, and research orgs via a `packs` registry (`bootstrap --pack <name>`), with per-pack archetype charter overrides.
- Larger orgs & repeatable templates: `examples/packs/*.yaml` usable directly as `--spec`.
- Naming: pack ids are plain function names (`business_ops`, `engineering`, `research`). See `IMPLEMENTED_MILESTONE5.md`. 113 tests.

## M6 — Multiplayer & tool surface ✅ (implemented)
- Human teammates talk to the workforce via a shared Slack-style channel
  (video 23:56 Loop Alley pattern) — `channel post|list|worker`; the worker runs
  the answering role through the normal agent loop and posts the reply back
  in-channel.
- Broader MCP/local tool surface + permission model polish: store-backed
  `memory`/`channel` adapters, a `ToolServer`/`register_tool_server` framework
  for local MCP-style servers, and risk-aware `approval_needed()` rules.
- See `IMPLEMENTED_MILESTONE6.md`. 143 tests.

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
- [x] M1 runtime: provider adapter, agent loop, SQLite, offline tests
- [x] M2 ambition loop: proactive propose/execute, context store, guarded scope
- [x] M4 mission control + observers/watchdogs (+8 tests — 95 total)
- [x] M5 role packs (business-ops / engineering / research) (+16 tests — 113 total)
- [x] M6 multiplayer + wider tool surface (+30 tests — 143 total)

Each milestone should keep the test suite green (offline, no API keys).