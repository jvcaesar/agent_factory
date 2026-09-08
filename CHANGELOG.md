# Changelog

All notable changes to **Agent Factory** are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): `Added` /
`Changed` / `Fixed` / `Removed`. Releases are tagged `v<version>` on GitHub.

## [1.0.0] - Unreleased

### Added
- **CI pipeline** (`.github/workflows/ci.yml`: test matrix — 2 OS × 4
  Pythons —, ruff lint gate, sdist+wheel build gate).
- **Ruff lint gate**: `[tool.ruff]` config (E/F/W/I/B/UP/SIM/C4,
  E501 intentionally ignored) + `dev` extra; `ruff check src tests` is clean.
- **`--version` flag** and a real package `__init__.py` exposing
  `agent_factory.__version__`.
- **`CHANGELOG.md`** (this file).
- **`docs/RELEASE_CHECKLIST_1.0.md`** — tracked checklist for the MVP → 1.0 hardening phase.
- **Opt-in live-provider smoke tests** (`tests/integration/`, gated by
  `AGENT_FACTORY_LIVE_TESTS=1`): exercise the real OpenAI adapter (verified
  live 2026-09-08) and the real Ollama adapter; each test skips with a clear
  reason when its prerequisite is missing. Default suite stays 100% offline.

### Changed
- Version bumps from `0.1.0` → `1.0.0`.
- `requests>=2.0` promoted to **core dependencies** — the core
  `web_fetch` tool needs it at runtime (previously only an optional
  `ollama` extra, which made the first CI run fail in every matrix cell).

### Fixed
- **Latent bug**: `bootstrap/generator.py` used `Optional` without importing
  it (masked at runtime by `from __future__ import annotations`),
  caught by the new ruff gate (F821).
- First CI run (2026-09-08) caught the `requests` core-dependency
  gap; see **Changed** above.
- **Ollama bare model names rejected by real servers**: Ollama returns
  `404 Not Found` for a bare name (e.g. `gemma4`); only tagged ids
  (`gemma4:12b`) work. `OllamaLLM` now auto-resolves bare names to their
  tagged id via `GET /v1/models` (cached per client; tagged names pass
  through; listing failure falls back to the configured name). Found by the
  new live smoke tests; covered by 7 offline unit tests.

## [0.1.0] - 2026-09-08  (MVP)

### Added
- **Runtime engine** (M1): provider-agnostic LLM adapters (OpenAI, Ollama,
  Fake — deterministic & offline), agent loop with a JSON action protocol,
  durable SQLite state (jobs/results/events/context/insights/messages).
- **Ambition loop** (M2): proactive "do smart things" loop over
  goals+context, gated by `proactivity_level` and approval ceilings.
- **Bootstrap** (M3): interview / `--spec` / role packs → validated org chart
  (archetypes, generator, prompts).
- **Insights & observability** (M4): `observe` / `brief` / `status`
  (mission control), writing actionable findings to the store.
- **Role packs** (M5): `bootstrap --pack business_ops|engineering|research`
  plus `examples/packs/*.yaml` spec templates.
- **Multiplayer & tool surface** (M6): shared human↔agent `channel`
  (post/list/worker), store-backed `memory`/`channel` tools, MCP-style
  `register_tool_server()` seam, risk-aware `approval_needed()` permissions.
- **Security hardening**: filesystem confinement, SSRF allowlist/blocklist,
  atomic SQLite claims, insight prompt-sanitization.
- **Docs**: architecture, decision log, design principles, user guide
  (+HTML), per-milestone notes, roadmap, project plan.

### Notes
- 146 offline tests (stdlib `unittest`, no API keys/network, deterministic
  via `FakeLLM`).
