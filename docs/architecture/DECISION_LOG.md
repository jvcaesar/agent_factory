# Decision Log

> Running record of architectural and scoping decisions. Newest first.

## 2026-08-25 — M5: role packs as data
**Decision:** Add a `packs` registry (`business_ops`, `engineering`, `research`) where each pack is pure data — an `InterviewAnswers`-style `spec` plus `archetype_overrides` applied with `dataclasses.replace`. New CLI: `bootstrap --pack <name>` (+ `--name/--founder/--north-star`) and `packs [--show <name>]`. `generate_org` gained an optional `directors/workers/addons` override seam with unchanged defaults.
**Why:** "Generic now, specialized later" — specialized workforces should be configuration over the same deterministic engine, not new code paths. Packs also double as `--spec` templates (`examples/packs/*.yaml`).
**Consequence:** `bootstrap --pack engineering` produces a 20-role org with vertical charters in one command; override keys accept both director domain keys and archetype ids (`engineering` or `director_engineering`). 113 tests passed at M5 time.

## 2026-08-25 — M4: insights store + observer/brief + mission control
**Decision:** Add an `insights` table (level/kind/title/detail/suggestion/status) to the SQLite store, a low-cost `observe` watchdog that scans jobs/events/context and persists findings, a `build_daily_brief` "what to do today" planner, and a `status` mission-control report. `Observation` prompts use plain `.format()` templates (not fragile triple-quoted f-strings).
**Why:** The video's "insight → action, not dashboards" (22:20–23:31, 26:04) requires turning raw state into actionable findings; the observability needs a durable home co-located with jobs/context.
**Consequence:** `observe`, `brief`, `status` CLI commands added; observer wiring proven via fake provider. (Encountered & fixed editor string-mangling that produced unterminated-string SyntaxErrors — wrote prompts with `.format()` templates to avoid it.) 95 tests passed at M4 time.

## 2026-08-27 — Modern OpenAI client, explicit model override, and atomic job start
**Decision:** The project supports the modern `openai>=1.0` client only. The `run` command accepts `--model`; provider-qualified values are supported, but a prefix that conflicts with `--provider` is rejected. Generated role YAML preserves provider/model fields, and jobs transition atomically from queued to running before execution.
**Why:** Keep provider behavior explicit, prevent silent loss of model configuration during YAML round trips, and make durable job state match actual execution.
**Consequence:** Users can select a model per run without editing configuration, while invalid provider/model combinations fail early. The test suite covers these contracts.

## 2026-08-25 — `OPENAI_VERIFY_SSL=0` made functional on legacy SDK via raw HTTP
**Decision:** When SSL verification is disabled and the installed `openai` package is legacy (<1.0, which ignores `verify_ssl_certs`), `OpenAILLM` bypasses the SDK and POSTs directly to `{base_url}/chat/completions` with `requests(verify=False)`.
**Why:** Corporate TLS-intercepting proxies present self-signed certs; the legacy SDK offers no working disable switch (`verify_ssl_certs is ignored` warning).
**Consequence:** OpenAI works behind such proxies with `OPENAI_VERIFY_SSL=0`; secure alternative remains `REQUESTS_CA_BUNDLE=<corp CA .pem>`. Verified live: `gpt-4o-mini` → `'OK.'` in 3.5s. All 4 configured models now reachable (3 local Ollama + 1 OpenAI). 87/87 tests passed at the time.


## 2026-08-25 — Per-role `MODEL_<role_id>` overrides + provider-qualified models
**Decision:** `resolve_role` now checks a per-role env var (`MODEL_<role_id>`) before the tier chain, and any model value may carry a provider prefix (`openai/gpt-4o`, `ollama/gemma4:12b`) that forces that provider for the role. Precedence — provider: CLI flag > env prefix > YAML prefix > `Role.provider` > `AGENT_FACTORY_PROVIDER`; model: `MODEL_<role_id>` > `Role.model` > tier chain > `MODEL_default` > built-in.
**Why:** Provider and model were resolved independently, so a bare `MODEL_lead_exec=gpt-4o` would have been sent to Ollama; users also had no way to mix providers per role from `.env` alone.
**Consequence:** One `.env` can run a mixed fleet (local default + cloud lead). New `probe` CLI command pings every configured pair; verified live (`ollama/gemma4:12b` → OK in 19.4s). 87/87 tests passed at the time.


## 2026-08-25 — Env config: generic `MODEL_*` vars + provider selection
**Decision:** `model_for_tier` now honors the generic, provider-agnostic env vars documented in `.env.example` — precedence: provider tier env (`OPENAI_MODEL_FAST`…) > provider general (`OPENAI_MODEL`) > `MODEL_fast/smart/big` > `MODEL_default` > built-in default. Provider routing for roles without an explicit `provider:` uses `AGENT_FACTORY_PROVIDER` (openai default; set to `ollama` for local models). Lookup is case-insensitive to survive Windows uppercase env normalization.
**Why:** The original `.env.example` documented `MODEL_default` etc., but the resolver never read them — a doc/code mismatch that silently routed local Gemma to OpenAI.
**Consequence:** `.env` alone fully determines per-role model+provider; regression-tested in `tests/test_model_resolution.py`.

## 2026-08-25 — Ollama: reasoning-model fallback
**Decision:** If the chat response's `content` is empty but a `reasoning` field exists (reasoning models like gemma4/deepseek-r1), use the reasoning trace as the reply text and flag it via `client.used_reasoning_fallback`.
**Why:** Live probe against local `gemma4:12b` returned empty content when the token budget was consumed by reasoning — blank replies would silently break the agent loop.
**Consequence:** Reasoning models work out of the box; callers can detect fallback. Verified live end-to-end against `http://localhost:11434/v1`.


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