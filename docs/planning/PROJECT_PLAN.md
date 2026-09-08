# Agent Factory — Project Plan

> **Status:** Milestones 1–6 complete; external integrations and PostgreSQL remain future work · **Working directory:** `c:\MyCodeJunk\LearningAi\AI-agents\agent_factory`
> **Origin:** Greg Isenberg × Alli K. Miller video, *"My top secrets to running an AI Agent Workforce"* — used as a source of *patterns*, not a blueprint to copy.

## 1. Goal

Build a **generic, config-driven toolkit** for designing and running a
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
│   ├── cli.py                # bootstrap, validate, runtime, insights, channel
│   ├── config/               # pydantic schema + YAML loader/validator
│   ├── bootstrap/            # archetypes, interview, generator, prompt templates
│   ├── llm/                  # OpenAI, Ollama, and offline Fake providers
│   ├── packs/                # business_ops, engineering, research packs
│   └── runtime/              # agent loop, SQLite state, tools, insights, channel
├── tests/                    # stdlib unittest, offline & deterministic
├── orgs/                     # generated workforces (user output)
└── docs/                     # this plan + reference material
```

## 4. Milestone breakdown

| # | Name | Goal | Status |
|---|-------|------|--------|
| M1 | **Runtime** | LLM adapters, agent loop, SQLite state | ✅ implemented |
| M2 | **Ambition loop** | "do smart things" over goals/context | ✅ implemented |
| M3 | **Bootstrap** | Interview → validated org chart | ✅ implemented |
| M4 | **Insights** | observers/watchdogs + mission control | ✅ implemented |
| M5 | **Role packs** | specialized orgs from the same engine | ✅ implemented |
| M6 | **Multiplayer & tool surface** | shared channel, local tools, MCP-style servers, risk-aware approvals | ✅ implemented |

## 5. Current state and next work

The milestone scope is complete through M6. The project currently provides:

1. Org generation from an interview, YAML spec, or built-in role pack.
2. Validation of role references, reporting cycles, tools, models, and SOPs.
3. Runtime execution through OpenAI, Ollama, or the deterministic Fake provider.
4. Durable SQLite state for jobs, results, events, context, insights, and messages.
5. Proactive ambition, observer, daily brief, mission-control, and shared-channel flows.
6. Local files/web/memory/channel tools plus an MCP-style registration seam.

The next work is product hardening rather than another declared milestone:

- replace the third-party tool stubs with live adapters;
- add the deferred Anthropic provider;
- add a PostgreSQL-backed store for multi-process or hosted deployments;
- refresh generated HTML documentation when the Markdown guides change;
- add integration tests for live providers and external services.

## 6. Acceptance criteria for M3 (all met)

1. `agent_factory bootstrap` generates a complete org chart from an interactive interview **or** a `--spec` YAML file.
2. Generated orgs validate: no missing references, no cycles, proactivity in range, SOP paths resolve.
3. The engine is generic — no person-specific roles, no LLM/network dependency in generation.
4. Test suite runs offline via stdlib `unittest`, deterministic (no API keys).

## 7. Decisions and deferred work

- **Python 3.10+** with `pydantic` + `pyyaml`; tests on stdlib `unittest` (no extra installs in this environment).
- **Provider scope:** OpenAI, Ollama, and Fake are implemented. Anthropic remains a future adapter using the existing `LLMClient` interface.
- **State scope:** SQLite is implemented and is the supported store today. PostgreSQL remains a future backend behind the narrow `Store` interface.
- **Tool scope:** files, web, memory, and channel are live local tools. The declared third-party tools remain explicit stubs until their adapters are added.
- **Spec scope:** role packs and YAML specs cover the current business-ops, engineering, and research use cases; larger org customization can extend the existing archetype and pack seams.

The complete milestone details are recorded in `IMPLEMENTED_MILESTONE1.md`
through `IMPLEMENTED_MILESTONE6.md`, and the command-level workflow is in
`USER_GUIDE.md`.

See [DECISION_LOG.md](./DECISION_LOG.md) for the running decision record.