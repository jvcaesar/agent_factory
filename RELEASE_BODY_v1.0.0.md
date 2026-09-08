## Agent Factory 1.0.0 — Release

First stable release of Agent Factory: a generic, config-driven toolkit for designing and running a workforce of AI agents, generated from a short interview instead of hand-written orchestration code.

### Highlights

- **Bootstrap** an org chart from an interview or role pack (`business_ops`, `engineering`, `research`), then `validate` it.
- **Runtime engine** with a provider-agnostic LLM interface: **OpenAI**, **Ollama** (local Gemma/Qwen), and a deterministic **Fake** for offline tests.
- **Ambition loop** — proactive "do smart things" work generation, gated by `proactivity_level` and approval ceilings.
- **Insights & observability** — `observe`, `brief`, `status` (mission control) writing actionable findings to the store.
- **Multiplayer** — shared human↔agent `channel` (post/list/worker), store-backed `memory`/`channel` tools, MCP-style `ToolServer` registry, risk-aware `approval_needed()` permissions.
- **Security hardening** — filesystem confinement, SSRF allowlist/blocklist, atomic SQLite claims, insight prompt-sanitization.

### What's new in 1.0 (vs MVP 0.1.0)

- **CI pipeline** (GitHub Actions: 2 OS × 4 Pythons matrix, ruff lint gate, sdist+wheel build gate).
- **Ruff lint gate** + `dev` extra; `ruff check src tests` is clean.
- **`--version` flag** and a real package `__init__.py`.
- **Opt-in live-provider smoke tests** (`tests/integration/`, gated by `AGENT_FACTORY_LIVE_TESTS=1`): real OpenAI adapter verified live; Ollama adapter with auto bare-name→tagged-id resolution.
- **`agent_factory tools` command** — authoritative REAL vs STUB tool report.
- **Ollama fix**: bare model names (e.g. `gemma4`) are now auto-resolved to tagged ids (e.g. `gemma4:12b`) — real servers reject bare names with 404.
- **Cut advertised-but-unimplemented claims**: Anthropic/Google provider keys removed from `.env.example` (future adapter slot remains on the `LLMClient` interface).

### Known limitations

- **Single-process store** (SQLite only; PostgreSQL is a future backend behind the `Store` interface).
- **13 stub tools** — role grants declare 17 tool ids but only 4 have live adapters (`files`, `web`, `memory`, `channel`). Stub tools return placeholder text; org charts bootstrap cleanly before an integration exists.
- **No Anthropic adapter** — deferred to a future release.
- **Single-threaded** channel + job execution.

### Install

```bash
pip install agent_factory-1.0.0-py3-none-any.whl
# or: pip install -e ".[openai]"   # for OpenAI
# or: pip install -e ".[ollama]"   # for local Ollama
```

### Verify

```bash
agent_factory --version   # → 1.0.0
python -m unittest discover -s tests   # 163 tests, all offline / green
```

### Test matrix (CI)

| OS | Python |
|---|---|
| ubuntu-latest | 3.10, 3.11, 3.12, 3.13 |
| windows-latest | 3.10, 3.11, 3.12, 3.13 |

All 10 CI jobs green on the `v1.0.0` tag.

See [CHANGELOG.md](CHANGELOG.md) for the full change list.
