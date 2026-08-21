# Roadmap — Upcoming Steps

> Ordered so each milestone builds on the last. Milestone 3 (bootstrap) is done;
> the remaining milestones turn the generated charts into a *running factory*.

## M1 — Runtime engine (next)
Convert the generated config into live agents.

- **Goal:** load an `Org` from disk and run it.
- **LLM adapters:** provider-agnostic client — Anthropic first (video's Claude fleet), then OpenAI. Selected via env vars (`AGENT_FACTORY_PROVIDER`, API keys).
- **Agent loop:** each `Role` becomes a runnable agent: system prompt = charter + SOP; context = goals doc + org; tools = granted, respecting `requires_approval`.
- **SQLite state:** durable job queue (pull-based workers) + results ledger, so agents hand off work and are observable.
- **Tests:** inject a fake LLM for deterministic, offline results.
- **Exit criteria:** a CLI that enqueues a job and a configured worker completes it end-to-end with recorded state.

## M2 — Ambition loop ("do smart things")
Make the workforce *proactive*, not just reactive.

- **Goal:** the lead role is licensed to initiate net-new work against goals + context, per its `proactivity_level`.
- **Context store:** capture un-codified knowledge (diary/context flow) so "the company stays queryable" (video 12:25–13:33).
- **Scope/permission breadth:** more autonomy in breadth, same approval ceiling for risky actions.
- **Tests:** fake-LLM scenarios proving a role with level ≥ 3 proposes/initiates new work correctly.

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

- [x] M3 bootstrap + 16 tests (this doc's step)
- [ ] M1 runtime: provider adapter, agent loop, SQLite, offline tests
- [ ] M2 ambition loop: proactive propose/execute, context store, guarded scope
- [ ] M4 mission control + observers/watchdogs
- [ ] M5 role packs (business-ops / engineering / research)
- [ ] M6 multiplayer + wider tool surface

Each milestone should keep the test suite green (offline, no API keys).