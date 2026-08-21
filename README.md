# Agent Factory
# Uses the ideas and principles from a youtube video whose title and transcript are also in this folder.

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

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — the detailed plan being used for implementation
- [`docs/IMPLEMENTED_MILESTONE3.md`](docs/IMPLEMENTED_MILESTONE3.md) — everything implemented in the current step (M3 bootstrap)
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — upcoming steps (M1–M6)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module map, data flow, contracts, seams for later milestones
- [`docs/DESIGN_PRINCIPLES.md`](docs/DESIGN_PRINCIPLES.md) — the generic patterns and guiding rules
- [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) — running record of design decisions
- [`docs/TRANSCRIPT_NOTES.md`](docs/TRANSCRIPT_NOTES.md) — distilled ideas from the source video (with timestamps)
- [`docs/SPEC_AUTHORING.md`](docs/SPEC_AUTHORING.md) — how to write `--spec` YAML by hand

## Status

Milestone 3 (of the roadmap) — the **`bootstrap`** command is implemented:

`agent_factory bootstrap` runs an interactive interview and writes a complete
org chart (role YAML + SOP markdown runbooks + goals + settings). A
`--spec` mode takes the same answers from a YAML file, which is how the test
suite drives it deterministically without any LLM or network.

## Quick start

```bash
# 1. Interactive interview → generates orgs/<chart-name>/ (roles, sops, goals)
agent_factory bootstrap

# 2. Generate from a spec file instead (non-interactive)
agent_factory bootstrap --spec my_answers.yaml --out my_org

# 3. Validate any org tree (all milestones reuse this)
agent_factory validate --root orgs/my_org
```

Requires Python 3.10+ and `pydantic` + `pyyaml`. Tests run on stdlib
`unittest` with no extra installs:

```bash
py -m unittest discover -s tests -v   # or: python -m unittest discover -s tests
```

## Roadmap

- [x] **M3 Bootstrap** — interview → validated org chart (this milestone)
- [ ] **M1 Runtime** — LLM adapters (Anthropic first), agent loop, SQLite state
- [ ] **M2 Ambition loop** — "do smart things" proactive loop over goals/context
- [ ] **M4 Insights** — observers/watchdogs + mission-control view
- [ ] **M5 Role packs** — business-ops / engineering / research orgs from the
  same primitives