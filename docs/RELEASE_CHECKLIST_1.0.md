# Release 1.0 Checklist — Agent Factory

> **Purpose:** take the repo from "MVP complete (0.1.0)" to "Release 1.0".
> **How to use:** work top-to-bottom; every item has a concrete *"Done when"*.
> Tick boxes in the markdown as you go (GitHub renders progress), or make one
> GitHub issue per `RC-xx` and close them individually.

## Definition of done for 1.0

A fresh clone on a clean machine can: install the wheel, pass the full test
suite, run `agent_factory --version`, bootstrap/validate an org, and complete a
real (non-`fake`) provider run — with docs that say exactly what the code does
(no stale counts, no advertised-but-missing features).

---

## Progress tracker

| ID | Item | Phase | Est. | Status |
|----|------|-------|------|--------|
| P0-01 | Baseline tag & clean tree | 0 | S | ✅ |
| P0-02 | Record verified baseline numbers | 0 | S | ✅ |
| RC-01 | CI pipeline (tests + matrix) | 1 | M | ✅ |
| RC-02 | Lint gate (ruff) | 1 | S | ✅ |
| RC-03 | Version 1.0.0 + `--version` + `__init__.py` + CHANGELOG | 1 | S | ✅ |
| RC-04 | Live-provider smoke tests | 1 | M | ☐ |
| RC-05 | Tool-list command + "real vs stub" docs | 1 | S | ☐ |
| RC-06 | Anthropic: implement, or cut the claim | 1 | M | ☐ |
| RC-07 | Windows console encoding fix | 2 | S | ☐ |
| RC-08 | Test-count / docs drift sweep | 2 | S | ☐ |
| RC-09 | Docs HTML regeneration step | 2 | S | ☐ |
| RC-10 | Cleanup (drop `_ok.txt`, verify gitignore) | 2 | S | ☐ |
| RC-11 | Add `SECURITY.md` | 2 | S | ☐ |
| RC-12 | Error-path QA pass (12 commands × bad input) | 2 | M | ☐ |
| RC-13 | Release branch + tag `v1.0.0` | 3 | S | ☐ |
| RC-14 | sdist + wheel build, verified on fresh venv | 3 | S | ☐ |
| RC-15 | GitHub release notes + artifacts | 3 | S | ☐ |
| RC-16 | Live-provider end-to-end run (OpenAI or Ollama) | 3 | M | ☐ |
| RC-17 | README status → "Release 1.0" | 3 | S | ☐ |
| RC-18 | Post-1.0 backlog documented | 4 | S | ☐ |

---

## Phase 0 — Baseline (do first, ~5 min)

- [x] **P0-01 — Baseline tag + clean tree**
  - Tag the current verified MVP state before touching anything:
    `git tag v0.1.0-mvp`  (HEAD = `a1de2e6`, clean `git status`).
  - **Done when:** `git tag -l` shows `v0.1.0-mvp` and `git status` is empty.

- [x] **P0-02 — Record verified baseline numbers**
  - Baseline captured **2026-09-08** at tag `v0.1.0-mvp` (commit `a1de2e6`):
    - **146** tests pass offline (`python -m unittest discover -s tests`).
    - **12** CLI commands: `bootstrap, packs, validate, run, jobs, ambition,
      context, probe, observe, brief, status, channel`.
    - **17** known tool ids; **4** real adapters (`files`, `web`, `memory`,
      `channel`) — `files` is a special-case in `tools_for_role()` outside
      `tools.CATALOG` (which holds `web`, `memory`, `channel`); the other 11
      tool ids resolve to stubs.
    - Working tree clean at capture; `.env` and `orgs/` are gitignored.
  - These numbers are the cleanup target for RC-08 — update them if the suite
    size or tool surface changes.
  - **Done when:** the numbers recorded here match what the suite/repo actually report.

---

## Phase 1 — 1.0 blockers (ship nothing until these are green)

- [x] **RC-01 — CI pipeline (GitHub Actions)**
  - *Why:* today there is **no** `.github/` config; nothing verifies a fresh
    clone. A 1.0 without CI isn't defensible.
  - Create `.github/workflows/ci.yml` with:
    - **Test job:** matrix `{os: [ubuntu-latest, windows-latest], python:
      [3.10, 3.11, 3.12, 3.13]}`, run `python -m pip install -e .` then
      `python -m unittest discover -s tests -v`.
    - **Lint job (after RC-02):** `ruff check src tests`.
    - **Build job:** `python -m build` and assert the wheel contains the
      `agent_factory` package + entry point (ref RC-14).
  - *Note:* the first CI run (2026-09-08, on `e09ced3`) caught a real
    dependency bug: all 8 test-matrix cells failed at import/collection time
    because `requests` was only an *optional* `ollama` extra, but the core
    `web_fetch` tool (and its tests mimic with `@mock.patch("requests.Session")`)
    need it. Fixed by promoting `requests>=2.0` to core deps in
    `pyproject.toml` (commit `f3b…` / see git log). Local repro: uninstalling
    `requests` reproduces the CI failure exactly (3 errors, `ModuleNotFoundError:
    No module named 'requests'`).
  - **Done when:** a fresh clone + push gets a green check on all three jobs;
    the README badge points at this workflow.

- [x] **RC-02 — Lint gate (ruff)**
  - `[tool.ruff]` added to `pyproject.toml` (target py310, line-length 88) with
    `select = [E, F, W, I, B, UP, SIM, C4]`, `ignore = [E501]` (intentional:
    long prompts/docblocks are idiomatic here); `dev = ["ruff>=0.8,<0.9"]`.
  - `ruff check src tests` is clean: 0 errors after auto-fix (170 fixes) plus
    manual fixes in `generator.py` (F821 — true latent bug: `Optional` used
    without import), `cli.py` (3× E731 lambdas → defs, B007), `packs`,
    `ollama_client.py`/`ambition.py` (SIM105 suppress), `fake.py` (SIM108),
    `interview.py` (C401), `test_loader_validation.py` (C408).
  - The `lint` job in `.github/workflows/ci.yml` runs the same command and is a
    required gate — **note:** branch protection (required checks) must be
    enabled in the repo's GitHub settings once the workflow has run once.
  - Version pin: ruff `0.8.x` is pinned because this dev machine cannot load
    the native `0.16.x` binary ("not a valid application for this OS
    platform"); `0.8.x` runs and is what CI installs, keeping local == CI.
  - **Done when:** `ruff check src tests` exits 0 locally *and* the `lint` job
    is green in CI (pending first push).
  - Add `ruff` as a `dev` extra in `pyproject.toml` (`[project.optional-dependencies] dev = ["ruff>=0.6"]`) plus a `[tool.ruff]` section (line-length 88, target py310).
  - First run in fix mode, then enforce.
  - **Done when:** `ruff check src tests` exits 0 locally *and* is a required
    green job in the RC-01 workflow.

- [x] **RC-03 — Version 1.0.0 + `--version` + package `__init__.py` + CHANGELOG**
  - `src/agent_factory/__init__.py` added: module docstring + `__version__ = "1.0.0"`.
  - `pyproject.toml` `version` bumped `0.1.0` → `1.0.0`.
  - `--version` flag added to `cli.main()` (argparse `action="version"`,
    reads `agent_factory.__version__`).
  - `CHANGELOG.md` added at repo root (Keep-a-Changelog format; `0.1.0` MVP
    + `1.0.0` entries) and linked from the README docs list.
  - Verified: `python -m agent_factory --version` prints `agent_factory 1.0.0`;
    `import agent_factory; agent_factory.__version__` == `"1.0.0"`.
  - **Done when:** ~~`python -m agent_factory --version` prints `1.0.0`~~ ✅;
    the wheel contains `agent_factory/__init__.py` (re-check at RC-14 build
    gate); CHANGELOG has both entries ✅.

- [ ] **RC-04 — Live-provider smoke tests (opt-in, not CI-by-default)**
  - *Why:* today only `FakeLLM` is exercised; the real OpenAI/Ollama adapters
    are the biggest correctness risk in the entire product.
  - Add `tests/integration/test_live_providers.py` that `skipUnless(
    os.environ.get("AGENT_FACTORY_LIVE_TESTS") == "1", ...)` and:
    - `openai` — if `OPENAI_API_KEY` set: `complete()` returns non-empty
      text for a trivial prompt (`0.1` per `temperature`).
    - `ollama` — if `http://localhost:11434` is reachable: same.
  - Keep the default suite 100% offline; document the flag in `README.md`.
  - **Done when:** normal suite stays green offline, and
    `AGENT_FACTORY_LIVE_TESTS=1 python -m unittest discover -s tests/integration`
    passes (or you have recorded a clear reason each provider is skipped).

- [ ] **RC-05 — Tool-list command + "real vs stub" docs**
  - *Why:* 4 of the 15 known tool ids are real; the other 11 resolve to stubs.
    Users deserve to know up-front.
  - Add `agent_factory tools [--list]` printing the known tools with
    `REAL`/`STUB` tags (they can inspect `tools.CATALOG` + `toolservers`).
  - Add a "Tool surface" table to `README.md`:
    real: `files`, `web`, `memory`, `channel`; stub: the rest, with a one-line
    "how to replace with `register_tool_server()`".
  - **Done when:** the command's output and the README table agree with code;
    the word "stub" appears everywhere a stub tool is offered.

- [ ] **RC-06 — Anthropic: implement, or cut the claim**
  - *Why:* `pyproject.toml` lists an `anthropic` extra and `.env.example`
    declares `ANTHROPIC_API_KEY`, but no adapter exists — an advertised-but-
    missing feature.
  - **Option A (implement):** add `llm/anthropic_client.py` behind `LLMClient`,
    wire it in `llm/factory.get_client` + `KNOWN_PROVIDERS`, market as the
    third-supported provider.
  - **Option B (cut, recommended for 1.0 scope):** remove the `anthropic`
    extra from `pyproject.toml`, drop `ANTHROPIC_API_KEY` from `.env.example`
    (and the "future adapter slot" comment), and note "Anthropic: not yet"
    under Post-1.0 (RC-18).
  - **Done when:** outcome of a choice — either a working `anthropic` provider
    with a test, or zero references to an Anthropic provider in code/docs.

---

## Phase 2 — Release quality (should be done before tagging)

- [ ] **RC-07 — Windows console encoding fix**
  - *Why:* on Windows (`cp1252` console) CLI output shows mojibake — confirmed,
    e.g. `Mission control ù SmokeTest` instead of `—`.
  - At the top of `cli.main()` add a best-effort
    `sys.stdout.reconfigure(encoding="utf-8")` /
    `sys.stderr.reconfigure(encoding="utf-8")` guarded by
    `hasattr(sys.stdout, "reconfigure")` (Python 3.7+, fine for 3.10+).
  - **Done when:** `agent_factory status` and `agent_factory channel list` show
    ASCII-faithful output (em-dashes/`→`) on `cmd.exe` and PowerShell without
    `PYTHONUTF8=1`; existing tests still pass.

- [ ] **RC-08 — Test-count / docs drift sweep**
  - *Why:* docs still claim "143 tests" (README, ROADMAP, milestone docs,
    ARCHITECTURE) but the suite actually runs **146**; older docs mention 87/95/
    97/113.
  - Update every count to the final number after RC-01–RC-07 land (run
    `python -m unittest discover -s tests` and use the real count).
  - Add a tiny helper `scripts/check_docs.py`? (optional) or a PR-template note:
    "did you update test counts?"
  - **Done when:** `grep -rn "143 tests\|97 tests\|95 tests\|113 tests" . --include='*.md'` returns nothing; the README quickstart count matches a fresh run.

- [ ] **RC-09 — Docs HTML regeneration**
  - *Why:* `docs/USER_GUIDE.html` / `docs/PRODUCT.html` are hand-generated
    snapshots; they drift from the Markdown.
  - Add `scripts/render_docs.py` (stdlib or pandoc if available) that renders
    `USER_GUIDE.md` → `USER_GUIDE.html` and `PRODUCT.md` → `PRODUCT.html`
    deterministically, and re-generate before release.
  - **Done when:** running the script twice produces `git diff` = empty
    (deterministic output) and the HTML files contain the 1.0 updates.

- [ ] **RC-10 — Cleanup / gitignore audit**
  - Delete the committed `_ok.txt` ("compile OK") leftover; ensure `.gitignore`
    still covers `.env`, `orgs/`, `tmp/`, `*/__pycache__`, `*.egg-info`,
    `dist/`, `build/`.
  - **Done when:** `git status` clean after a full `python -m build &&
    python -m unittest discover -s tests`; `_ok.txt` gone from `git ls-files`.

- [ ] **RC-11 — Add `SECURITY.md` (repo root, linked from README)**
  - Document: the trust model (roles, `proactivity_level`, risk tiers),
    existing mitigations (SSRF allowlist/blocklist, filesystem confinement,
    `approval_needed()` gates, atomic message claims, insight sanitization), a
    "responsible disclosure" email/issue template, and known-limitations note
    (agents execute config, `.env` holds keys).
  - **Done when:** `SECURITY.md` exists and README links to it; a reviewer can
    explain the security posture in 5 minutes from this file.

- [ ] **RC-12 — Error-path QA pass (record in `docs/QA_1.0.md`)**
  - For each of the 12 CLI commands, exercise at least one bad input and record
    the result in `docs/QA_1.0.md` (expected: friendly exit code + stderr, no
    traceback for *handled* paths). Suggested cases:
    - `bootstrap --spec tests/fixtures/missing.yaml`
    - `validate --root /nonexistent` and a circular-`reports_to` YAML
    - `run --org orgs/DoesNotExist`
    - `run --org <valid> --role nope` (unknown role)
    - `ambition`/`brief`/`observe` with no history/store
    - `channel post --text ""` and `channel worker` with zero pending
    - `--approval ask` in a non-TTY (should degrade to deny, not crash)
  - Fix exceptions thrown on *expected* bad input.
  - **Done when:** QA log lists 12 commands × bad input with exit code recorded;
    the only acceptable tracebacks are genuinely unexpected bugs.

---

## Phase 3 — Packaging & release day (follow in order)

- [ ] **RC-13 — Release branch + tag**
  - Create `release/1.0.0` from `main`; run the full Phase 1–2 checklist on it;
    address anything that fails by fixing on `main` and cherry-picking back.
  - Commit the RC-03 version bump + CHANGELOG entry; tag `v1.0.0`
    (`git tag -a v1.0.0 -m "Release 1.0.0"`).
  - **Done when:** the release branch's `git status` is clean and the tag
    points at a commit whose tests were green *on that commit*.

- [ ] **RC-14 — sdist + wheel, verified from a fresh venv**
  - Build both: `python -m build` (sdist + wheel).
  - Inspect the wheel (`unzip -l`) — must contain `agent_factory/__init__.py`,
    all subpackages, and the `entry_points.txt` with the `agent_factory` console
    script.
  - Smoke-install into a *fresh* venv (no `src` on `PYTHONPATH`):
    `pip install dist/agent_factory-1.0.0-py3-none-any.whl` then
    `agent_factory --version` and a `--pack engineering` bootstrap.
  - **Done when:** the fresh-venv smoke test passes and the sdist is non-empty.
    (Baseline 2026-09-08: wheel builds with 34 entries — will grow with
    RC-03's `__init__.py`.)

- [ ] **RC-15 — GitHub release + notes**
  - Draft a `v1.0.0` release on GitHub using the CHANGELOG entry: headline
    features (bootstrap, runtime, ambition, insights, packs, channel), provider
    list, security notes, and *known limitations* (single-process store,
    stubbed tools, no Anthropic unless RC-06-A).
  - Attach the `dist/` artifacts from RC-14.
  - **Done when:** the release page lists the changelog and both artifacts;
    the tag points at the RC-13 commit.

- [ ] **RC-16 — Live end-to-end proof run (record in `docs/QA_1.0.md`)**
  - With a real provider (OpenAI key or running Ollama): bootstrap an org from
    the `engineering` pack, then run **four** flows: `run`, `ambition`,
    `brief`, and `channel post → worker → list`. Record samples of the output.
  - **Done when:** the QA doc contains one page showing all four flows
    completing with real model output (truncated where long).

- [ ] **RC-17 — README status flip**
  - Change the top README Status block to "**Release 1.0** (2026-…)" and point
    the docs list at `RELEASE_CHECKLIST_1.0.md`; state supported providers,
    the tool-surface table (RC-05), and the live-test flag (RC-04).
  - **Done when:** a new reader can tell from the README exactly what 1.0
    supports without opening the milestone docs.

---

## Phase 4 — Post-1.0 backlog (explicitly *not* required for 1.0)

- [ ] **RC-18 — Document the post-1.0 roadmap**
  - Move these into `docs/ROADMAP.md` "after 1.0" (keep the 1.0 scope honest):
    - PostgreSQL store behind the `Store` interface (multi-process/hosted).
    - Parallel / multi-worker channel + job execution (currently single-threaded).
    - Real adapters for the 11 stubbed tools (or a documented plugin pattern).
    - Anthropic adapter, if RC-06 chose Option B.
    - Live-provider integration suite wired into CI (needs secrets) once keys exist.
    - Structured `--json` output mode; telemetry/observability metrics export.
  - **Done when:** `ROADMAP.md` has a dated "after 1.0" section and nothing in
    Phase 1–3 silently depends on these.

---

## Definition-of-done final check (run once, in a fresh clone)

```text
git clone  → pip install wheel (or -e .)  → python -m unittest discover -s tests  ✅
→ agent_factory --version                                    shows 1.0.0         ✅
→ agent_factory bootstrap --pack engineering → validate → run --provider fake   ✅
→ agent_factory channel post|worker|list                       completes          ✅
→ one real-provider flow (RC-16)                                completes          ✅
→ grep -rn "143\|97\|95\|113 tests" **/*.md                     nothing            ✅
→ ruff check src tests                                          0 errors           ✅
→ git ls-files has no _ok.txt, has SECURITY.md, CHANGELOG.md                       ✅
```

When every box above is ticked, cut **v1.0.0** and update this file's header
with a "Released" date.