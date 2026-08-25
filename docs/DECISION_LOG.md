# Decision Log

> Running record of architectural and scoping decisions. Newest first.

## 2026-08-21 — M2: context lives in the SQLite store
**Decision:** Extend `Store` with a `context` table (`key`, `content`, `source`, timestamps) plus `upsert_context`/`search_context`/`context_blob`.
**Why:** The "company stays queryable" idea (video 12:25–13:33) means un-codified knowledge must be captured and injectable into prompts; SQLite keeps it durable, searchable, and co-located with jobs/events.
**Consequence:** Diary entries and ambition outcomes share one store, queried via `agent_factory context`.

## 2026-08-21 — M2: propose protocol is its own JSON shape
**Decision:** Proposals use `{"type":"proposals","proposals":[...]}` — separate from the M1 action protocol — and only proactive roles (`proactivity_level >= 3`) are allowed to propose.
**Why:** Mirrors the "do smart things" behavior while keeping the M1 tool/action loop unchanged. Gating by proactivity makes the scale meaningful.
**Consequence:** `propose_actions` is independent of execution; the loop remains provider-agnostic and fake-testable.

## 2026-08-21 — M2: risk/budget gates keep the approval ceiling
**Decision:** `run_ambition_loop` respects `max_risk` (skips high-risk) and `max_actions` (budget), and every executed proposal still runs through `run_agent` (grant + approval enforcement).
**Why:** From the video: "risk tier stays the same, width expands" — proactivity widens breadth, not the ceiling.
**Consequence:** High-risk proposals are recorded as skipped (visible) and never auto-executed.

## 2026-08-21 — M2: `context --add` creates the store on demand
**Decision:** `context --add` allows storing into a fresh org (creates the SQLite DB if missing); listing/searching still require an existing store.
**Why:** Seeding the diary must work before any jobs exist.
**Consequence:** The diary flow is usable as a first step.

## 2026-08-21 — M1: provider strategy (OpenAI default + Ollama local + Fake)
**Decision:** Implement a single `LLMClient` interface with three adapters: OpenAI (default real provider), Ollama (local Gemma/Qwen), Fake (offline tests). Providers chosen via `AGENT_FACTORY_PROVIDER`.
**Why:** User specified OpenAI as default, local Ollama models for experimentation, a provider-agnostic interface for later, and the fake path for tests.
**Consequence:** Agent loop is provider-agnostic by construction; swapping providers never touches agent code. Anthropic was deferred (video's Claude angle) — a future adapter slots onto the same interface.

## 2026-08-21 — M1: JSON action protocol for the agent loop
**Decision:** The model responds to the system prompt in a small JSON protocol (`{"type":"final"|"tool", ...}`); the loop parses it. No vendor-specific function-calling schemas.
**Why:** Keeps the loop identical across OpenAI/Ollama/Fake and fully offline-testable with a scripted fake.
**Consequence:** Relies on the model producing JSON; system prompt instructs it strictly, `parse_action` handles fenced/loose JSON and plain-text fallback.

## 2026-08-21 — M1: OpenAI adapter supports legacy (0.28.x) API
**Decision:** Detect at construction time whether `openai.OpenAI` exists; use the modern client if so, otherwise fall back to the legacy module-level `ChatCompletion.create`. `OPENAI_BASE_URL` allowed for compatible endpoints.
**Why:** The environment has `openai 0.28.1`, which exposes the legacy API only — but adapters should also work on newer installs.
**Consequence:** Robust across openai versions without two code paths in callers.

## 2026-08-21 — M1: Ollama adapter uses requests + OpenAI-compatible endpoint
**Decision:** `OllamaLLM` POSTs to `http://localhost:11434/v1/chat/completions` via `requests` (no extra SDK).
**Why:** Ollama exposes an OpenAI-compatible HTTP API; `requests` is already present; keeps local model support dependency-light.
**Consequence:** Local Gemma/Qwen work by pointing at the local server; the model name is configurable at runtime.

## 2026-08-21 — M1: minimal real tools + stubs
**Decision:** Ship real `files`/`web` tools and stubs for the rest; the *framework* (grants, approval, tool loop) is real even where integrations aren't.
**Why:** Wiring Notion/Gmail/Stripe/etc. is a large surface; M1's goal is a working loop + state, not every adapter.
**Consequence:** Granted-but-unwired tools return an explicit "STUB" message so the loop is honest about what's available.

## 2026-08-21 — M1: SQLite durable state in the org folder
**Decision:** `Store` wraps SQLite with `jobs`/`results`/`events`; DB lives at `<org>/.agentfactory/jobs.db`.
**Why:** Durable, queryable, zero-setup on Windows; narrow interface so Postgres can replace it (M5).
**Consequence:** Jobs/events/results are queryable via `agent_factory jobs`.

## 2026-08-21 — M1: test bug — Windows paths in JSON tool calls
**Decision (fixed):** Tests embedded raw backslashes in JSON strings (`C:\Users\...`), which is invalid JSON (`\U` escape). Switched tests to build payloads with `json.dumps` and to enqueue real jobs before asserting on them.
**Why:** Invalid JSON made `parse_action` fall back to "final", so tool calls weren't exercised.
**Consequence:** Tests now correctly exercise tool execution, approval gating, and state recording.

## 2026-08-21 — Docs folder added
**Decision:** Create `docs/` with plan, implementation notes, roadmap, architecture, principles, transcript reference, and this log.
**Why:** Keep the video-derived design rationale and milestone state visible to any future work (or new collaborator).
**Consequence:** `README.md` now links to these docs.

## 2026-08-21 — M3: generic role library (no proper names)
**Decision:** Worker/director/add-on archetypes are generic functions (`director_product`, `amplifier`, `observer`, ...), not imitations of the video's named roles.
**Why:** The user explicitly asked for a *generic factory* that uses ideas, not replicas. Generality also serves the later business-ops/engineering/research packs.
**Consequence:** Any user's org is generated from the same library; specialized orgs are config over the same archetypes.

## 2026-08-21 — M3: schema-first design
**Decision:** Build `Org`/`Role`/`ToolGrant` pydantic models + loader/validator before any runtime code.
**Why:** Every later milestone (runtime, ambition loop, observers, packs) consumes this schema; bootstrap forces it to be exercised early.
**Consequence:** 16 offline tests pin the contract.

## 2026-08-21 — M3: stdlib `unittest`, no network
**Decision:** Tests use stdlib `unittest` (not pytest) because `pytest` isn't installed and the environment is offline-friendly.
**Consequence:** Test suite runs with `python -m unittest discover -s tests`; no extra installs.

## 2026-08-21 — M3: graded approval implemented
**Decision:** Under `review_external`/`approval_first`, all write grants get `requires_approval=true`. `autonomous` tier leaves writes ungated.
**Why:** Video's "risk tier stays the same, width expands" — more scope, same ceiling.
**Consequence:** Write-heavy roles surface approvals in generated YAML (see `orgs/Acme/roles/director_marketing.yaml`).

## 2026-08-21 — M3: quarterly goals into goals/current.md
**Decision:** `Org.quarterly_goals` persisted and rendered into `goals/current.md`, which every SOP references.
**Why:** "Goals reviewed quarterly" and goal-oriented proactivity (video 09:05).
**Consequence:** Goals are versioned, reviewable, and injected into the agent context later (M2).

## 2026-08-21 — M3: model tiering + budget
**Decision:** `fast`/`smart`/`big` per role; `small` budget downgrades `big`-tier directors to `smart`.
**Why:** "Not everything needs Opus — sub-agents are Haiku/Sonnet" (video 20:34).
**Consequence:** Budget choices matter at generation time (see `test_small_budget_downgrades_big_director`).

## 2026-08-21 — M3: lead_exec coordinator (generalized "chief of staff")
**Decision:** Optional `lead_exec` role sits on top when `use_lead` is chosen; directors/add-ons report to it.
**Why:** Generalizes the COS pattern without copying any named person.
**Consequence:** Without a lead, the first director is top of org (still a valid chart).