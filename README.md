# Agent Factory
# Uses the ideas and principles from a youtube video whose title and transcript are also in this folder.
# Implemented in VS code with extension Cline and it's free model deepseek/deepseek-v4-flash

[![CI](https://github.com/jvcaesar/agent_factory/actions/workflows/ci.yml/badge.svg)](https://github.com/jvcaesar/agent_factory/actions/workflows/ci.yml)

A generic, config-driven toolkit for designing and eventually running a
**workforce of AI agents** — generated from a short interview instead of
hand-written orchestration code.

The design generalizes recurring patterns for agentic workforces into
reusable primitives:

- **Hierarchy topology** — a hub-and-spoke `reports_to` tree; any lead role
  can spawn any sub-tier. This is the generalized form of an "AI chief of
  staff + directors + workers" org.
- **Proactivity scale (`proactivity_level` 0–5)** — how much each role is
  licensed to *initiate* net-new work, from "only does assigned tasks" to
  "finds and executes new high-value work, then reports tradeoffs."
- **Goal orientation** — every org has a written north-star + quarterly
  targets that agents act against, not open-ended churn.
- **Graded approval** — more autonomy in *breadth*, same approval ceiling for
  *risky* actions (external sends, writes, money).
- **Model tiering** — `fast` / `smart` / `big` per role, driven by a budget
  tier so expensive reasoning is reserved for the roles that need it.
- **Insightable observers** — cheap scan roles that log friction/access gaps
  and answer "what should I do next" rather than just displaying a dashboard.
- **Bootstrap** — an interview that turns answers into a validated org chart,
  so you go from "I want a workforce" to role files in minutes.

> This is a *generic engine*. The specific org of any individual is an
> application of these patterns, not a template this project reproduces.

## Documentation

The `docs/` folder is the project's source of truth:

- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) — step-by-step user guide with real command examples and expected output ([styled HTML version](docs/USER_GUIDE.html))
- [`docs/PRODUCT.md`](docs/PRODUCT.md) — product overview & marketing one-pager: features, benefits, personas, user stories, comparison ([dark-themed HTML version](docs/PRODUCT.html))
- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — the detailed plan being used for implementation
- [`docs/IMPLEMENTED_MILESTONE3.md`](docs/IMPLEMENTED_MILESTONE3.md) — everything implemented in the current step (M3 bootstrap)
- [`docs/IMPLEMENTED_MILESTONE1.md`](docs/IMPLEMENTED_MILESTONE1.md) — everything implemented in the current step (M1 runtime engine)
- [`docs/IMPLEMENTED_MILESTONE2.md`](docs/IMPLEMENTED_MILESTONE2.md) — everything implemented in the current step (M2 ambition loop)
- [`docs/IMPLEMENTED_MILESTONE4.md`](docs/IMPLEMENTED_MILESTONE4.md) — everything implemented in the current step (M4 insights / observers / mission control)
- [`docs/IMPLEMENTED_MILESTONE5.md`](docs/IMPLEMENTED_MILESTONE5.md) — everything implemented in the current step (M5 role packs)
- [`docs/IMPLEMENTED_MILESTONE6.md`](docs/IMPLEMENTED_MILESTONE6.md) — everything implemented in the current step (M6 multiplayer / shared channel + wider tool surface)
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — the roadmap (M1–M6)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module map, data flow, contracts, seams for later milestones
- [`docs/DESIGN_PRINCIPLES.md`](docs/DESIGN_PRINCIPLES.md) — the generic patterns and guiding rules
- [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) — running record of design decisions
- [`CHANGELOG.md`](CHANGELOG.md) — version history (0.1.0 MVP → 1.0.0)
- [`docs/RELEASE_CHECKLIST_1.0.md`](docs/RELEASE_CHECKLIST_1.0.md) — the concrete, trackable checklist for shipping MVP → Release 1.0
- [`docs/TRANSCRIPT_NOTES.md`](docs/TRANSCRIPT_NOTES.md) — distilled ideas from the source video (with timestamps)
- [`docs/SPEC_AUTHORING.md`](docs/SPEC_AUTHORING.md) — how to write `--spec` YAML by hand
- [`docs/HOWTO_BOOTSTRAP.md`](docs/HOWTO_BOOTSTRAP.md) — what each bootstrap command does, and which ones to actually run

## Status

- **Milestone 6 (Multiplayer & tool surface)** — implemented. See
  [`docs/IMPLEMENTED_MILESTONE6.md`](docs/IMPLEMENTED_MILESTONE6.md).
- **Milestone 5 (Role packs)** — implemented. See
  [`docs/IMPLEMENTED_MILESTONE5.md`](docs/IMPLEMENTED_MILESTONE5.md).
- **Milestone 4 (Insights)** — implemented. See
  [`docs/IMPLEMENTED_MILESTONE4.md`](docs/IMPLEMENTED_MILESTONE4.md).
- **Milestone 3 (Bootstrap)** — implemented. See
  [`docs/IMPLEMENTED_MILESTONE3.md`](docs/IMPLEMENTED_MILESTONE3.md).
- **Milestone 2 (Ambition loop)** — implemented. See
  [`docs/IMPLEMENTED_MILESTONE2.md`](docs/IMPLEMENTED_MILESTONE2.md).
- **Milestone 1 (Runtime engine)** — implemented. See
  [`docs/IMPLEMENTED_MILESTONE1.md`](docs/IMPLEMENTED_MILESTONE1.md).

## Quick start

```bash
# 1. Interactive interview → generates orgs/<chart-name>/ (roles, sops, goals)
agent_factory bootstrap

# 2. Generate from a spec file instead (non-interactive)
agent_factory bootstrap --spec my_answers.yaml --out my_org

# 3. Validate any org tree
agent_factory validate --root orgs/my_org

# 4. Run a job with a configured role (M1)
set AGENT_FACTORY_PROVIDER=fake     # or openai / ollama — see Providers below
agent_factory run --org orgs/Acme --role worker_research_1 ^
    --task "List the quarterly targets." --approval deny

# Override the role/environment model (provider prefix is optional)
agent_factory run --org orgs/Acme --role worker_research_1 ^
  --provider ollama --model qwen2.5:7b ^
  --task "List the quarterly targets." --approval deny

# 5. Inspect the durable job store
agent_factory jobs --org orgs/Acme

# 6. Capture context, then run the proactive "do smart things" loop (M2)
agent_factory context --org orgs/Acme --add diary/today --detail "Client wants a demo first"
agent_factory ambition --org orgs/Acme --role lead_exec --max-actions 2

# 7. Observability & insights (M4)
agent_factory status   --org orgs/Acme            # mission control
agent_factory observe  --org orgs/Acme --limit 5  # observer/watchdog pass
agent_factory brief    --org orgs/Acme            # "what to do today" plan

# 8. Role packs (M5): pre-built specialized workforces
agent_factory packs                               # list packs
agent_factory bootstrap --pack engineering ^
    --name "MyCo Eng" --north-star "Ship fast, keep quality high" --out orgs/Eng
agent_factory bootstrap --spec examples/packs/research.yaml --out orgs/Research

# 9. Talk to the workforce from a shared channel (M6, "Loop Alley")
agent_factory channel post --org orgs/Acme ^
    --text "Did the client respond to my email?" --role lead_exec
agent_factory channel worker --org orgs/Acme --provider fake   # agents reply in-channel
agent_factory channel list  --org orgs/Acme
```

Requires Python 3.10+ and `pydantic` + `pyyaml`. Tests run on stdlib
`unittest` with no extra installs:

```bash
py -m unittest discover -s tests -v   # offline, no API keys needed
```

**Live-provider smoke tests** are opt-in and never run in the default suite.
Set `AGENT_FACTORY_LIVE_TESTS=1` to exercise the *real* adapters:

```bash
# OpenAI: needs OPENAI_API_KEY (honors OPENAI_BASE_URL / OPENAI_MODEL)
AGENT_FACTORY_LIVE_TESTS=1 py -m unittest discover -s tests/integration -v

# Ollama: needs a local server. Bare model names (e.g. `gemma4`) are
# auto-resolved to their tagged id (`gemma4:12b`) by the adapter — a tagged
# `OLLAMA_MODEL` works too and skips one lookup.
AGENT_FACTORY_LIVE_TESTS=1 py -m unittest discover -s tests/integration -v
```

Each test skips with a clear reason when its prerequisite is missing.

## Tool surface (real vs stub)

Role grants declare 17 tool ids, but only 4 have live adapters in the runtime
today. Run `agent_factory tools` for the authoritative, live list:

| Tool id | Status | Actions | Notes |
|---|---|---|---|
| `files` | **REAL** | `files_read`, `files_write` | Workspace-confined; writes need approval (high risk) |
| `web` | **REAL** | `web_fetch` | SSRF-allowlisted fetch |
| `memory` | **REAL** | `memory_read`, `memory_search`, `memory_write` | Durable org context store |
| `channel` | **REAL** | `channel_list`, `channel_post` | Shared human<->agent channel |
| `analytics`, `calendar`, `cms`, `crm`, `docs`, `github`, `gmail`, `notion`, `payments`, `sheets`, `slack`, `stripe`, `supabase` | STUB | `<id>_stub` | Declared in grants; invoking returns a "not wired yet" placeholder |

Granting a stub tool never fails — the agent simply receives the placeholder
text — so org charts bootstrap cleanly before an integration exists.

## Providers (M1)

Selected via `AGENT_FACTORY_PROVIDER` (default `openai`) or `--provider`:

Install the provider extras before using live models:

```bash
pip install -e ".[openai]"   # OpenAI
pip install -e ".[ollama]"   # Ollama
```

- **`openai`** (default) — set `OPENAI_API_KEY`. Optional `OPENAI_BASE_URL` for
  compatible endpoints. Requires the modern `openai>=1.0` API.
- **`ollama`** — local Gemma/Qwen via the OpenAI-compatible endpoint at
  `http://localhost:11434/v1` (override `OLLAMA_BASE_URL` / `OLLAMA_MODEL`).
- **`fake`** — deterministic offline client for tests and headless smoke runs.

`--model` is currently available on `run`. It overrides role and environment
model settings. Values may use `provider/model`, for example
`ollama/qwen2.5:7b`. If `--provider` is also supplied, a conflicting provider
prefix is rejected with a clear error.

See [`docs/IMPLEMENTED_MILESTONE1.md`](docs/IMPLEMENTED_MILESTONE1.md) for details.

## Roadmap

- [x] **M1 Runtime** — LLM adapters (OpenAI/Ollama/Fake), agent loop, SQLite state
- [x] **M2 Ambition loop** — "do smart things" proactive loop over goals/context
- [x] **M3 Bootstrap** — interview → validated org chart
- [x] **M4 Insights** — observers/watchdogs + mission-control view
- [x] **M5 Role packs** — business-ops / engineering / research orgs from the
  same primitives
- [x] **M6 Multiplayer & tool surface** — shared human↔agent channel
  (`channel post|list|worker`), store-backed `memory`/`channel` tools,
  MCP-style `ToolServer` registry, risk-aware `approval_needed()` rules
  (163 tests, all offline / green)

## Development

Regenerate the HTML docs from their Markdown sources:

```bash
pip install -e ".[dev]"        # brings in ruff + markdown
python tools/build_docs.py     # rebuilds docs/PRODUCT.html, docs/USER_GUIDE.html
python tools/build_docs.py --check   # CI mode: fail if committed HTML is stale
```

The `docs` job in `.github/workflows/ci.yml` runs `--check` on every push/PR, so the committed HTML can never silently drift from the Markdown.

## Security

See [SECURITY.md](SECURITY.md) for the full security policy, including:
- Supported versions
- How to report a vulnerability
- Security considerations for the tool surface, provider API keys, and local models