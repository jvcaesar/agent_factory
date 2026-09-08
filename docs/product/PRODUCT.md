# Agent Factory — Product Overview

> **Ship an AI workforce, not an agent script.**

Agent Factory is an open-source CLI that turns a short conversation (or a YAML file)
into a **complete, governed AI workforce**: an org chart of specialized agents with
roles, SOPs, goals, shared memory, and a shared channel — running on the LLM provider
you choose, with durable state and human-approval guardrails built in.

**Version 0.1.0 · Python 3.10+ · Works fully offline · 143 automated tests, zero API keys required**

---

## The problem

Most "AI agents" today are demos in disguise:

- A **single mega-prompt** doing five jobs badly, with no memory between runs.
- **One-off scripts** whose work evaporates when the terminal closes.
- **No guardrails** — an agent with a tool and a dream can touch anything.
- **No visibility** — you can't answer "what did my agents do today?" without
  reading stdout from a run that no longer exists.
- **Vendor lock-in** — the agent logic and the LLM are welded together.

Teams don't need another demo. They need a **workforce**: specialized roles,
durable records of what was done, escalation paths to humans, and governance
that doesn't depend on developers remembering to add it.

---

## What Agent Factory does

Describe the company you want, and Agent Factory builds it — then keeps it running:

1. **Bootstrap** — an interactive interview, a YAML spec, or a pre-built pack
   (business ops, engineering, research) generates a validated org chart:
   20+ roles with titles, reporting lines, SOPs, tool grants, and goals.
2. **Run** — every role is a runnable agent backed by an LLM. Work flows through
   a durable SQLite store: every job, result, and event is recorded and queryable.
3. **Grow** — a proactive lead proposes its own next steps against the north star;
   guardrails decide what actually executes.
4. **Observe** — a watchdog observer surfaces friction and blockers as insights;
   the lead briefs you every morning: *what should I do today?*
5. **Talk** — you post questions to a shared channel; the addressed role answers
   in-thread, using its normal tools and permissions.

---

## Key features

| | Feature | What you get |
|---|---------|--------------|
| 🏭 | **One-command workforces** | `bootstrap` from an interview, a YAML spec, or a pre-built pack — validated before anything runs |
| 🧩 | **Specialized roles, not mega-prompts** | Each agent has its own YAML, SOP, tools, and reporting line |
| 💾 | **Durable by default** | Jobs, results, events, memory, insights, and conversations live in a portable SQLite file inside the org folder |
| 🛡️ | **Governance built in** | Tool grants, risk tiers, and approval policies (`ask` / `deny` / `allow`) enforced on *every* tool call |
| 🚀 | **Proactive, not passive** | The lead proposes net-new work (risk-rated, prioritized) and executes it within your guardrails |
| 👀 | **Mission control** | `status`, `observe`, and `brief` answer "what's happening?" and "what should I do today?" |
| 💬 | **Human-in-the-loop channel** | A shared `#general` where humans ask and agents answer — with atomic claims so nothing is ever answered twice |
| 🔌 | **Provider freedom** | OpenAI, local Ollama (Gemma/Qwen), or a built-in offline `fake` provider — switch per run or per role |
| 🧰 | **Extensible tool surface** | A risk-rated tool catalog plus MCP-style local tool servers that inherit the same governance |
| 📦 | **Portable orgs** | An org is just files + one SQLite file. Copy it, commit it, reset it by deleting `jobs.db` |

---

## How it works

```
                        ┌──────────────────────────────────────┐
                        │            YOU (the human)           │
                        │   bootstrap · run · brief · channel   │
                        └───────┬───────────────────┬──────────┘
                                │                   │
                     ┌──────────▼─────────┐  ┌──────▼───────────────┐
                     │   BOOTSTRAP        │  │  SHARED CHANNEL      │
                     │  interview / spec  │  │  #general (SQLite)   │
                     │  / pre-built pack  │  │  post → worker → reply│
                     └──────────┬─────────┘  └──────▲───────────────┘
                                │                   │
                     ┌──────────▼────────────────────┴───────────┐
                     │              VALIDATED ORG CHART          │
                     │   org.yaml · roles/ · sops/ · goals/      │
                     └──────────────────────┬────────────────────┘
                                            │
              ┌─────────────────────────────▼─────────────────────────────┐
              │                     RUNTIME ENGINE                        │
              │   agent loop: LLM actions → granted tools → approvals     │
              └───────┬──────────────┬───────────────┬────────────────────┘
                      │              │               │
          ┌───────────▼───┐  ┌───────▼──────┐  ┌─────▼─────────────┐
          │  DURABLE STORE │  │  GUARDRAILS  │  │   OBSERVER        │
          │  jobs · results│  │  grants ·    │  │  insights ·       │
          │  events ·      │  │  risk tiers ·│  │  briefs ·         │
          │  context ·     │  │  approvals   │  │  status           │
          │  insights ·    │  └──────────────┘  └───────────────────┘
          │  messages      │
          └────────────────┘
                      │
          ┌───────────▼───────────────────────────────────┐
          │                 LLM PROVIDERS                 │
          │        openai · ollama (local) · fake         │
          └───────────────────────────────────────────────┘
```

**Everything on this diagram is a plain file or one SQLite database inside your org
folder.** No hidden cloud state, no daemon required — the CLI is the platform.

## Workflows — a day with your workforce

**Morning**

```text
$ agent_factory brief --org orgs/Demo
→ the lead's prioritized plan: WHAT / WHO / FIRST STEP
```

**During the day**

```text
$ agent_factory run --org orgs/Demo --role worker_research_1 --task "..." 
$ agent_factory channel post --org orgs/Demo --text "Did the client respond?" 
$ agent_factory channel worker --org orgs/Demo        # agents answer in-thread
```

**Any time**

```text
$ agent_factory status --org orgs/Demo                # mission control
$ agent_factory observe --org orgs/Demo               # surface friction as insights
$ agent_factory ambition --org orgs/Demo --role lead_exec   # let the lead take initiative
```

**Every step is recorded.** `jobs --org` shows the full ledger; `status` shows
queue counts, open insights, and pending channel messages at a glance.

---

## Benefits

| Without Agent Factory | With Agent Factory |
|---|---|
| Agent work lives in chat scrollback | Every job, result, and event in a queryable ledger |
| One mega-prompt pretending to be a team | A real org chart: specialized roles with SOPs and managers |
| "What did the agent do?" — *no idea* | `status` + `jobs` + `observe`: full observability in one command |
| Hope the agent doesn't do something rash | Risk-tiered tools + approval gates enforced on every call |
| Rewrite the agent to switch models | Swap `openai` / `ollama` / `fake` with one flag — logic unchanged |
| Runaway API costs during development | Free, deterministic offline `fake` provider for tests and demos |
| Agent logic welded to a vendor SDK | Org charts are plain YAML; runtime, tools, and providers are pluggable |

**The net effect:** you go from *prompt babysitter* to *manager of a workforce*
that records its own work, escalates when it should, and briefs you when you
need it.

---

## Who is it for?

### 🧑‍💻 Indie builders & solopreneurs
Spin up a "tiny company" — research, ops, and comms roles — that keeps working
while you build the product. The offline `fake` provider means you can develop
the whole workflow without spending a cent on API calls.

### 🚀 Startup & product teams
Give your product a governed multi-agent backend without building the plumbing:
durable state, approvals, observability, and a human-in-the-loop channel are all
included. Org charts are YAML, so you can ship workforce templates as config.

### 🏢 Internal platform & AI teams
Stand up department workforces (ops, research, support) with real governance:
tool grants per role, risk tiers, and approval policies your security team can
actually review — enforced in code, not in a prompt paragraph.

### 🎓 Educators & workshop leaders
Teach multi-agent patterns with zero setup friction: the entire course can run
offline on the `fake` provider, and 143 automated tests show students what
production discipline looks like.

### 🤝 Agencies & consultants
Prototype client automations in minutes with pre-built packs, then hand over a
portable folder — files plus one SQLite database — that the client owns entirely.

## User stories

> **As a founder**, I want to say what my company does and get a working team back,
> so that I stop writing agent plumbing and start delegating real work.
> → *`bootstrap --pack business_ops` → 23 validated roles in one command.*

> **As a developer**, I want agent experiments to survive the terminal closing,
> so that I can debug what happened yesterday.
> → *Every job lands in `jobs.db` with its events and output; `jobs --org` replays it.*

> **As a team lead**, I want my AI lead to suggest the next best action — but not
> execute anything dangerous without me, so that initiative never means risk.
> → *`ambition` proposes risk-rated actions; `--max-risk` and the approval gate
> decide what actually runs.*

> **As an ops manager**, I want to ask the workforce questions where I work,
> so that I don't learn another tool.
> → *`channel post` + `channel worker`: ask in `#general`, get an in-thread answer
> from the right role.*

> **As a security reviewer**, I want to see exactly which tools each role can use
> and what needs human approval, so that I can sign off with evidence.
> → *Tool grants live in YAML per role; risk tiers and approval events are recorded
> in the store.*

> **As an educator**, I want to demo a multi-agent system in a classroom with no
> internet and no budget, so that students focus on patterns, not setup.
> → *`AGENT_FACTORY_PROVIDER=fake` runs everything offline, deterministically.*

---

## Target customers & use cases

| Segment | Typical use case | Why Agent Factory fits |
|---|---|---|
| Solo founders | A back-office that researches, drafts, and follows up | Pre-built packs + one-command bootstrap |
| SaaS startups | Governed multi-agent features shipped as config | YAML org charts, pluggable providers |
| Platform/AI teams | Department workforces with auditable governance | Grants, risk tiers, approval events in the store |
| Consultancies | Fast client prototypes they fully own | Portable org folders, no hidden cloud state |
| Education | Teaching multi-agent architecture offline | Deterministic `fake` provider, 163 offline tests |
| Hackathons | A working "AI company" demo in minutes | `bootstrap --pack` → running workforce before coffee |

## How it compares

| | Agent scripts & notebooks | Workflow automation tools | Agent Factory |
|---|---|---|---|
| Team structure | ❌ one mega-prompt | ⚠️ rigid predefined steps | ✅ validated org chart of specialized roles |
| Durable history | ❌ lost on exit | ⚠️ run logs only | ✅ jobs, events, memory, insights, messages |
| Governance | ❌ prompt-level at best | ⚠️ basic permissions | ✅ grants + risk tiers + approval gates, enforced |
| Proactivity | ❌ none | ❌ trigger-driven only | ✅ lead proposes and executes within guardrails |
| Human interaction | ❌ rerun the script | ⚠️ forms & notifications | ✅ shared channel with in-thread agent answers |
| Observability | ❌ stdout | ⚠️ dashboards | ✅ `status` / `observe` / `brief` CLI-native |
| Model freedom | ⚠️ whatever you coded | ❌ vendor-bound | ✅ OpenAI / Ollama / fake, per run or per role |
| Offline capability | ⚠️ depends | ❌ rarely | ✅ fully offline mode built in |

---

## Governance & safety, by design

- **Least privilege:** roles only get the tools their YAML grants them.
- **Risk tiers:** every tool carries `low` / `medium` / `high` risk; org policy
  decides which tiers require approval.
- **Approval policies:** `deny` (safe default), `ask` (interactive), or `allow` —
  overridable per run, and every approval decision is recorded as an event.
- **Bounded initiative:** proactive actions have a `--max-risk` ceiling and a
  `--max-actions` budget; over-ceiling proposals are logged but never executed.
- **Exactly-once channel answers:** message claims are atomic in SQLite — two
  workers or a crash mid-answer can never double-reply.
- **Everything auditable:** jobs, events, approvals, insights, and messages are
  rows in a database you own.

## Developer experience

- **Zero-to-demo offline:** `AGENT_FACTORY_PROVIDER=fake` — no keys, no cost,
  deterministic output for tests and CI.
- **Battle-tested:** 143 automated tests run offline in seconds.
- **Extensible by design:** add tools to the risk-rated catalog, or graft on
  MCP-style local tool servers via `register_tool_server()` — new tools inherit
  the full grant + risk + approval pipeline automatically.
- **Plain files in, plain files out:** org charts are YAML; state is SQLite;
  SOPs are markdown. Nothing to migrate, nothing to export.
- **Swappable intelligence:** `--provider` / `--model` on every LLM-running
  command; per-role `MODEL_*` environment overrides; `probe` verifies every pair.

---

## Shipped so far — the M1 → M6 roadmap

| Milestone | Delivered |
|---|---|
| **M1 — Runtime engine** | Agent loop, tool execution with grants & approvals, durable job store, `probe` |
| **M2 — Memory & proactivity** | Shared context (diary flow), `ambition` propose→execute loop with guardrails |
| **M3 — Bootstrap** | Interview / YAML / spec → validated org charts, `validate`, SOP & goal generation |
| **M4 — Observability** | `status` mission control, `observe` insights, `brief` action plans |
| **M5 — Role packs** | Pre-built workforces (`business_ops`, `engineering`, `research`), `packs` |
| **M6 — Multiplayer & tools** | Shared human↔agent channel with atomic workers, risk-tiered tool catalog, MCP-style tool servers |

---

## Get started in five commands

```bash
pip install -e .                                   # Python 3.10+, no API key needed
set AGENT_FACTORY_PROVIDER=fake                    # offline & deterministic
agent_factory bootstrap --pack business_ops --name "Demo Co" --out orgs/Demo
agent_factory run --org orgs/Demo --role worker_research_1 --task "List the quarterly targets."
agent_factory status --org orgs/Demo
```

Swap the provider to `openai` or `ollama` when you are ready for real intelligence —
every command stays the same.

**Full documentation:** [`USER_GUIDE.md`](USER_GUIDE.md) ·
[`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) · [`ROADMAP.md`](../planning/ROADMAP.md)
