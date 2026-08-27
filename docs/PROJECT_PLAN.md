# Agent Factory — Project Plan

> **Status:** Milestones 1–3 complete · **Working directory:** `c:\MyCodeJunk\LearningAi\AI-agents\agent_factory`
> **Origin:** Greg Isenberg × Alli K. Miller video, *"My top secrets to running an AI Agent Workforce"* — used as a source of *patterns*, not a blueprint to copy.

## 1. Goal

Build a **generic, config-driven toolkit** for designing and eventually running a
*workforce of AI agents*. The workforce is defined as data (role charts, SOPs,
goals, approvals), not hard-coded orchestration. It must be able to express
different specialized workforces (business-ops, engineering, research) from the
same primitives.

## 2. Core premise: ideas, not imitation

The source material shows one person running a specific 34-agent fleet. This
project does **not** reproduce their named org (Simon, Phoebe, Toby, their
director mix). It generalizes the *underlying patterns* into named, configurable
properties of a reusable engine. See `DESIGN_PRINCIPLES.md` for the full
pattern→feature map.

## 3. Architecture


[Plan continues → see ARCHITECTURE.md for the reference model.]

```
agent_factory/
├── src/agent_factory/
│   ├── cli.py                # bootstrap (interactive/--spec) + validate
│   ├── config/               # pydantic schema + YAML loader/validator
│   └── bootstrap/            # archetypes, interview, generator, prompt templates
├── tests/                    # stdlib unittest, offline & deterministic
├── orgs/                     # generated workforces (user output)
└── docs/                     # this plan + reference material
```

## 4. Milestone breakdown

| # | Name | Goal | Status |
|---|-------|------|--------|
| M3 | **Bootstrap** | Interview → validated org chart | ✅ implemented |
| M1 | **Runtime** | LLM adapters, agent loop, SQLite state | ✅ implemented |
| M2 | **Ambition loop** | "do smart things" over goals/context | ✅ implemented |
| M4 | **Insights** | observers/watchdogs + mission control | ahead |
| M5 | **Role packs** | specialized orgs from the same engine | ahead |

## 5. Current goal — Milestone 4 (insights)

See [IMPLEMENTED_MILESTONE3.md](./IMPLEMENTED_MILESTONE3.md) for the build
detail, and [ROADMAP.md](./ROADMAP.md) for what comes next.

## 6. Acceptance criteria for M3 (all met)

1. `agent_factory bootstrap` generates a complete org chart from an interactive interview **or** a `--spec` YAML file.
2. Generated orgs validate: no missing references, no cycles, proactivity in range, SOP paths resolve.
3. The engine is generic — no person-specific roles, no LLM/network dependency in generation.
4. Test suite runs offline via stdlib `unittest`, deterministic (no API keys).

## 7. Decisions and open questions

- **Python 3.10+** with `pydantic` + `pyyaml`; tests on stdlib `unittest` (no extra installs in this environment).
- **Anthropic-first** provider ordering planned for M1 (matches the video's Claude-based fleet), with provider-agnostic adapters.
- **SQLite → Postgres** state path planned for M1/M5.
- **Open question:** exact `--spec` extension points for larger orgs (many directors + many workers) — revisit at M5 role packs.

See [DECISION_LOG.md](./DECISION_LOG.md) for the running decision record.