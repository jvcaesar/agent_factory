# Release Notes for v1.0.0

**Repository:** jvcaesar/agent_factory  
**Tag:** v1.0.0  
**Release Title:** Agent Factory 1.0.0

---

## Release Highlights

### Headline Features
- **Bootstrap** — Interview, `--spec`, or role packs → validated org chart
- **Runtime Engine** — Provider-agnostic LLM adapters with a JSON action protocol
- **Ambition Loop** — Proactive "do smart things" loop over goals + context
- **Insights & Observability** — `observe` / `brief` / `status` mission control
- **Role Packs** — `engineering`, `business_ops`, `research` packs + spec templates
- **Multiplayer Channel** — Shared human↔agent `channel` (post/list/worker)

### Supported Providers
| Provider | Status | Notes |
|----------|--------|-------|
| OpenAI | ✅ Real adapter | Requires `OPENAI_API_KEY` |
| Ollama | ✅ Real adapter | Local, auto-resolves bare model names |
| Fake | ✅ Offline | Deterministic, for testing |

### Security
- Filesystem confinement (path traversal protection)
- SSRF allowlist/blocklist for web requests
- Atomic SQLite claims for job deduplication
- Insight prompt-sanitization

### Known Limitations
- **Single-process store** — SQLite only; no PostgreSQL/multi-host yet
- **Stubbed tools** — 13 of 17 tool ids are stubs (see `agent_factory tools`)
- **No Anthropic** — Advertised-but-unimplemented provider was cut; remains a documented future adapter
- **Single-threaded** — Channel/job execution is currently serial

---

## Changelog

### Added
- **CI pipeline** (`.github/workflows/ci.yml`: test matrix — 2 OS × 4 Pythons —, ruff lint gate, sdist+wheel build gate)
- **Ruff lint gate**: `[tool.ruff]` config (E/F/W/I/B/UP/SIM/C4, E501 intentionally ignored) + `dev` extra; `ruff check src tests` is clean
- **`--version` flag** and a real package `__init__.py` exposing `agent_factory.__version__`
- **`CHANGELOG.md`** (this file)
- **`docs/planning/RELEASE_CHECKLIST_1.0.md`** — tracked checklist for the MVP → 1.0 hardening phase
- **Opt-in live-provider smoke tests** (`tests/integration/`, gated by `AGENT_FACTORY_LIVE_TESTS=1`): exercise the real OpenAI adapter and the real Ollama adapter
- **`agent_factory tools` command** and public `agent_factory.runtime.tools.tool_surface()` snapshot: report every declared tool id as REAL (4: `files`, `web`, `memory`, `channel`) or STUB (13)

### Changed
- Version bumps from `0.1.0` → `1.0.0`
- `requests>=2.0` promoted to **core dependencies** — the core `web_fetch` tool needs it at runtime

### Fixed
- **Latent bug**: `bootstrap/generator.py` used `Optional` without importing it (caught by new ruff gate)
- **Ollama bare model names rejected by real servers**: `OllamaLLM` now auto-resolves bare names to their tagged id via `GET /v1/models`

### Removed
- **Advertised-but-unimplemented providers cut**: the `anthropic` extra and `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` entries in `.env.example` were removed

---

## Artifacts

Attach these files from `dist/`:
- `agent_factory-1.0.0-py3-none-any.whl` (67,182 bytes)
- `agent_factory-1.0.0.tar.gz` (77,478 bytes)

---

## Instructions to Create Release

1. Go to https://github.com/jvcaesar/agent_factory/releases/new
2. Choose tag: `v1.0.0` (should already exist from RC-13)
3. Release title: `Agent Factory 1.0.0`
4. Paste the content above as release notes
5. Attach the two files from `dist/`
6. Publish release