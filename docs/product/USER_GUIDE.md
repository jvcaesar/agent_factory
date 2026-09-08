# Agent Factory — User Guide

A practical, step-by-step guide to using the `agent_factory` CLI. The offline
examples use the deterministic `fake` provider, so they can be reproduced
without an API key. Real model output requires either OpenAI or a local Ollama
server.

> **How to read this guide**
> Each command section shows: **Purpose** → **Command** → **Expected output**
> → **Notes**. Sections are ordered the way you would actually use the tool:
> create a workforce → run work → make it proactive → observe it → talk to it.

**The mental model in one paragraph:** you *bootstrap* an org chart (roles,
SOPs, goals) from a short interview, a YAML spec, or a pre-built pack. Each
role becomes a runnable agent backed by an LLM. Work runs through a durable
SQLite store in the org folder (`jobs`, `context`, `insights`, `messages`),
so every job, proposal, finding, and channel conversation is recorded and
queryable. Guardrails (risk tier + approval policy) are enforced on every
tool call, and the human talks to agents through a shared channel.

---

## Table of contents

1. [Installation & setup](#1-installation--setup)
2. [Quick start (5 commands, offline)](#2-quick-start-5-commands-offline)
3. [Create your workforce](#3-create-your-workforce)
4. [Run work](#4-run-work)
5. [Memory & proactivity](#5-memory--proactivity)
6. [Observability](#6-observability)
7. [Talk to your workforce](#7-talk-to-your-workforce)
8. [Providers & models](#8-providers--models)
9. [Command reference (cheat sheet)](#9-command-reference-cheat-sheet)
10. [Where your data lives](#10-where-your-data-lives)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)

---

## 1. Installation and setup

**Purpose:** get the CLI installed and pick an LLM provider.

From PowerShell, run these commands in the repository root:

```powershell
py --version                     # requires Python 3.10+
py -m pip install -e .           # core: pydantic and pyyaml
py -m pip install -e ".[openai]" # OpenAI support, when needed
# or: py -m pip install -e ".[ollama]"  # local Ollama support
```

Select a provider in the current PowerShell session. `fake` is the best first
run:

```powershell
$env:AGENT_FACTORY_PROVIDER = "fake"       # offline, deterministic
# $env:AGENT_FACTORY_PROVIDER = "openai"   # also set OPENAI_API_KEY
# $env:AGENT_FACTORY_PROVIDER = "ollama"   # Ollama at localhost:11434
```

The environment variable lasts for the current terminal session. The CLI also
accepts `--provider` for a single command.

**Check that your configured providers are reachable** with `probe`:

```bash
agent_factory probe
```

*Expected output (with a working provider):*

```
Probing 3 configured provider/model pair(s)...

[OK]   openai  gpt-4o-mini           0.9s  -> 'OK'
[OK]   openai  gpt-4o                1.4s  -> 'OK'
[OK]   openai  o1                    2.1s  -> 'OK' [reasoning-fallback]

3/3 reachable.
```

`probe` pings every `MODEL_*` pair configured in your environment (or the
provider's built-in defaults if none are set) and reports one `[OK]`/`[FAIL]`
line per pair. Exit code is `0` only if all pairs answer. Limit it with
`--only openai` or `--only ollama`.

> Running the tests? They are fully offline: `py -m unittest discover -s tests`
> (163 tests at the time of writing, no API keys).

---

## 2. Quick start (5 commands, offline)

Copy-paste this to see the whole system work in under a minute — no API key:

```bash
$env:AGENT_FACTORY_PROVIDER = "fake"                # PowerShell

agent_factory bootstrap --pack business_ops --name "Demo Co" ^
    --north-star "Become the trusted advisor for our clients" --out orgs/Demo
agent_factory validate --root orgs/Demo
agent_factory run --org orgs/Demo --role worker_research_1 ^
    --task "List the quarterly targets." --approval deny
agent_factory status --org orgs/Demo
agent_factory channel post --org orgs/Demo --text "Did the client respond?" --role lead_exec
```

If these commands succeed you have a valid org, one completed job, a
mission-control report, and a message queued in the shared channel. The
channel message is answered only after you run `channel worker`.

---

## 3. Create your workforce

### 3.1 `bootstrap` — three ways to generate an org

**Purpose:** turn intent (an interview, a spec file, or a pack) into a
validated org chart on disk: `org.yaml`, `settings.yaml`, per-role YAML + SOPs,
and `goals/current.md`.

#### Option A — pre-built pack (fastest, recommended first)

```bash
agent_factory packs                                   # see what is available
agent_factory bootstrap --pack business_ops --name "Demo Co" ^
    --north-star "Become the trusted advisor for our clients" --out orgs/Demo
```

*Expected output of `packs`:*

```
business_ops    Business Operations         Go-to-market and operations workforce: marketing, operations, support, finance, data, and partnerships.
engineering     Software Engineering        Delivery-focused workforce: product, engineering, research, data, and agent-operations.
research        Research & Analysis         Evidence workforce: research, data, product-use, and partnership research.
```

*Expected output of `bootstrap --pack`:*

```
Generated org 'Demo Co' at: orgs/Demo
  pack: business_ops
  roles: 23  lead=True  risk=review_external  budget=medium
  top -> lead_exec (Org Lead (Chief of Staff), proactivity 5)
```

Available packs: `business_ops`, `engineering`, `research`. Each pack ships a
ready-made spec you can use directly as a `--spec` file, e.g.
`agent_factory bootstrap --spec examples/packs/research.yaml --out orgs/Research`.

#### Option B — interactive interview

```bash
agent_factory bootstrap
```

You will be asked for: the workforce name, your (founder) name, the
north-star goal, 2–3 quarterly targets, which domains to staff, which tools
roles may use, and the risk/budget tiers. Answers are written to
`orgs/<name>/` when the generated chart validates.

#### Option C — YAML spec (non-interactive, repeatable)

```bash
agent_factory bootstrap --spec my_answers.yaml --out my_org
```

A spec is plain YAML — here is the business-ops pack's own spec
(`examples/packs/business_ops.yaml`):

```yaml
org_name: MyCo Operations
founder: Founder
north_star: Drive predictable growth and operational efficiency across revenue, service, and brand.
quarterly_goals:
  - Lift pipeline and closed revenue
  - Reduce support resolution time
  - Ship a monthly business-health report
human_team_size: 2
domains: [marketing, operations, support, finance, data, partnerships]
tools: [files, web, memory, channel]
risk_tier: review_external
budget_tier: medium
add_amplifier: true
add_observer: true
use_lead: true
```

See [`docs/product/SPEC_AUTHORING.md`](SPEC_AUTHORING.md) for every field.

> `--pack` and `--spec` are mutually exclusive — pick one.

### 3.2 What a generated org looks like

```
orgs/Demo/
├── org.yaml                  # the org chart (roles, reports_to, tools, model tiers)
├── settings.yaml             # risk tier, budget tier, defaults
├── README.md                 # human-readable summary of the org
├── goals/current.md          # north star + quarterly targets agents act against
├── roles/*.yaml              # one file per role (23 roles in the demo org)
├── sops/*.md                 # one SOP per role (how the role works)
└── .agentfactory/jobs.db     # created on first run — the durable store
```

### 3.3 `validate` — check any org tree

**Purpose:** confirm an org folder is structurally valid before running it.

```bash
agent_factory validate --root orgs/Demo
```

*Expected output:*

```
OK: orgs\Demo is a valid org (23 roles).
```

Validation checks every role's `reports_to` links, tool grants, model tiers,
and the settings/goals files. A broken tree exits non-zero with a specific
error message.

---

## 4. Run work

### 4.1 `run` — give a role a job

**Purpose:** enqueue a task for a specific role and run it through the agent
loop (LLM actions + granted tools + approval gating), recording everything in
the store.

```bash
agent_factory run --org orgs/Demo --role worker_research_1 ^
    --task "List the quarterly targets." --approval deny
```

*Expected output (fake provider):*

```
job #1 [worker_research_1] -> done in 1 step(s)
events:
--- output ---
List the quarterly targets.
```

Notes:

- `--role` must be a role id from `orgs/Demo/roles/` (e.g. `lead_exec`,
  `director_marketing`, `worker_research_1`).
- `--approval` controls what happens when the agent wants to use a tool that
  needs approval: `deny` (refuse and continue — safe default), `allow`
  (approve automatically), `ask` (prompt you in the terminal).
- `--max-steps` caps the agent loop (default keeps jobs bounded); use
  `--provider`/`--model` to override the role's configured LLM for one run
  (see [§8](#8-providers--models)).

### 4.2 `jobs` — the durable job ledger

**Purpose:** list every job ever recorded in the org's store.

```bash
agent_factory jobs --org orgs/Demo
```

*Expected output:*

```
id   org            role                     status    task
1    Demo Co        worker_research_1        done      List the quarterly targets.
```

Statuses: `queued → running → done`, or `error` / `blocked` (e.g. all
tool calls needed approval). Every job's events and final output are stored
in `.agentfactory/jobs.db` (see [§10](#10-where-your-data-lives)).

---

## 5. Memory & proactivity

### 5.1 `context` — the shared company memory

**Purpose:** capture facts the whole workforce should be able to query — the
"diary flow". Agents see relevant context in their prompts, and roles granted
the `memory` tool can read/search it themselves.

```bash
# add an entry:  context --org <org> --add <key> --detail <text>
agent_factory context --org orgs/Demo --add diary/today ^
    --detail "Client wants a demo before signing."

# list everything
agent_factory context --org orgs/Demo

# search by substring
agent_factory context --org orgs/Demo --search demo
```

*Expected output of `list` / `search` (same table):*

```
key                                  source     content
diary/today                          diary      Client wants a demo before signing.
```

Notes:

- `source` records where the entry came from (`diary` = you typed it;
  `ambition` = the proactive loop logged a proposal/execution).
- Adding the same `--add` key again updates the entry.

### 5.2 `ambition` — the proactive "do smart things" loop

**Purpose:** let a high-proactivity lead *initiate* net-new work against the
north star, quarterly goals, and captured context — it proposes actions
(risk-rated, prioritized), then executes up to `--max-actions` of them as
real jobs.

```bash
agent_factory ambition --org orgs/Demo --role lead_exec --max-actions 2
```

*Expected output (fake provider — real models produce concrete titles):*

```
Proposals from lead_exec (proactivity 5):
  - <short title> (risk=medium, priority=1)
      action: <concrete task a worker should do>

Executed 1 action(s):
  job #2 [<short title>] -> done
```

Notes:

- Only roles with `proactivity_level >= 3` initiate; lower levels are
  passively assigned work. The lead role generated by `bootstrap` has level 5.
- `--max-actions` and `--max-risk` are your guardrails: a proposal whose
  risk exceeds the tier's ceiling is proposed but not executed, and
  `requires_approval` tools still go through the approval gate.
- Executed proposals become real jobs in the ledger (and context entries),
  so `status` and `brief` see them.

---

## 6. Observability

### 6.1 `status` — mission control

**Purpose:** one report answering "what is my workforce doing right now":
job queue counts, recent jobs, open insights, approvals, pending channel
messages.

```bash
agent_factory status --org orgs/Demo
```

*Expected output:*

```
Mission control — Demo Co
  Jobs: 2 total  (queued=0, running=0, done=2, error=0, blocked=0)
  Open insights: 1
  Pending channel messages: 0

  Recent jobs:
    #2 [director_marketing] done: <concrete task a worker should do>
    #1 [worker_research_1] done: List the quarterly targets.

  Open insights: none

  Recent approval events: none
```

(`--limit` controls how many recent jobs are shown; default 20.)

### 6.2 `observe` — the observer/watchdog pass

**Purpose:** run the cheap observer role to surface friction, access gaps,
blockers, contradictions, and opportunities as *insights* in the store — not
a dashboard, input for the brief.

```bash
agent_factory observe --org orgs/Demo --limit 3
```

*Expected output (fake provider):*

```
Observer observer surfaced 1 finding(s):
  [info/friction] <short title>
      detail: <what you found>
      suggest: <what to do about it>
```

Each finding is `[level/kind]` — e.g. `info/friction`,
`warn/access_gap`, `blocker`. `--role` lets you use a different observer
role; the default is the org's `observer` role (or the lead).

### 6.3 `brief` — "what should I do today"

**Purpose:** turn open insights + context + job state into a short,
prioritized action plan (WHAT / WHO / FIRST STEP) as if the org lead were
briefing the founder.

```bash
agent_factory brief --org orgs/Demo
```

*Expected output:* the brief prompt sent to the lead's model; with a real
provider the reply is the actual plan. With the `fake` provider the prompt is
echoed back verbatim, so you see exactly what the model receives:

```
You are Org Lead (Chief of Staff) (role `lead_exec`) acting as the founder's morning brief for the workforce "Demo Co".

STATE OF THE WORKFORCE
Job counts: 2 total (queued=0, running=0, done=2, error=0, blocked=0). Open insights: 1. Recent jobs: #2 [director_marketing] done: ... #1 [worker_research_1] done: ...

OPEN INSIGHTS
- [info/friction] <short title>. (<what you found>) Suggestion: <what to do about it>

CAPTURED CONTEXT
[diary/today] (diary) Client wants a demo before signing. ...

Produce a short, prioritized "what should I do today" plan ...
```

> **Fake provider and placeholders:** `fake` is an echo client, so outputs
> contain placeholders like `<short title>`. With `openai`/`ollama` you get
> real content in the same shape. All offline examples in this guide use the
> same commands — only the text inside changes.

---

## 7. Talk to your workforce

The shared channel (video 23:56, "Loop Alley") is how a human teammate asks
the workforce things: you post into `#general`, a channel worker runs the
addressed role through the *normal* agent loop, and the agent's answer is
posted back into the same channel as a reply.

### 7.1 `channel post` — a human asks something

```bash
agent_factory channel post --org orgs/Demo ^
    --text "Did the client respond to my email?" --role lead_exec
```

*Expected output:*

```
posted message #1 to #general (addressed to lead_exec) — queued for an agent reply
```

`--role` addresses a specific role (default: the org lead); omit it to let
the lead route the question. `--author` overrides the displayed human name
(default: the org founder).

### 7.2 `channel worker` — agents answer in-channel

```bash
agent_factory channel worker --org orgs/Demo
```

*Expected output (fake provider):*

```
#general: answered 1 message(s)
  #1 by 1 step(s): A human teammate posted this into the shared channel #general:

Did the client r...
```

Notes:

- The worker claims pending messages **atomically** (`pending → running →
  done` in SQLite), so a second worker or a restart never double-answers.
- `--max-messages` (default 5) bounds one worker run; `--approval`,
  `--provider`, `--model`, `--temperature` behave exactly like `run`;
  `--role` forces one role to answer regardless of addressing.
- The answering role runs with its normal grants, so tools it uses are
  recorded in the job ledger like any other job.

### 7.3 `channel list` — read the conversation

```bash
agent_factory channel list --org orgs/Demo
```

*Expected output (newest first; `*` = the human's message, `->` = the agent's reply):*

```
#general (2 message(s), newest first)
-> #2   [lead_exec:Org Lead (Chief of Staff) (lead_exec)] (done) A human teammate posted this into the shared channel #general:

Did th...
*  #1   [human:Founder] -> lead_exec (done) Did the client respond to my email?
```

Both messages show `(done)` — a question stays `pending` until a worker
claims it, then `running` while answered, then `done` once the reply is
posted. `--channel` switches channels (default `general`).

---

## 8. Providers & models

Every command that runs an LLM (`run`, `ambition`, `observe`, `brief`,
`channel worker`) accepts the same two overrides:

| Flag | Meaning | Example |
|------|---------|---------|
| `--provider` | `openai` \| `ollama` \| `fake` for this one run | `--provider ollama` |
| `--model` | override the role/environment model; may carry a `provider/` prefix | `--model ollama/qwen2.5:7b` |

Rules:

- Defaults come from `AGENT_FACTORY_PROVIDER` (default `openai`) and the
  role's model tier (`fast` / `smart` / `big`, driven by the org's
  `budget_tier`).
- If `--model` has a provider prefix that conflicts with `--provider`
  (e.g. `--provider openai --model ollama/qwen2.5:7b`), you get a clear
  configuration error instead of a silent mismatch.
- Per-role environment models: set `MODEL_DEFAULT`, `MODEL_FAST`,
  `MODEL_SMART`, `MODEL_BIG`, or role-specific `MODEL_<ROLE_ID>` vars —
  `probe` shows every pair it finds.

Providers:

| Provider | Needs | Good for |
|----------|-------|----------|
| `fake` | nothing | tests, demos, headless smoke runs (echoes input) |
| `openai` | `OPENAI_API_KEY` (+ optional `OPENAI_BASE_URL`), `pip install -e ".[openai]"` | production-quality work |
| `ollama` | local Ollama at `http://localhost:11434/v1` (override `OLLAMA_BASE_URL`/`OLLAMA_MODEL`), `pip install -e ".[ollama]"` | private/local models (Gemma, Qwen, …) |

There is no Anthropic adapter yet. Installing the optional Anthropic package
does not enable an Anthropic provider.

### Live and stubbed tools

The following tools execute locally: `files`, `web`, `memory`, and `channel`.
Third-party tool ids such as `notion`, `gmail`, `calendar`, `slack`, `stripe`,
`supabase`, `github`, `sheets`, `docs`, `crm`, `cms`, `payments`, and
`analytics` are currently declared integration stubs. A role may be granted
one of these tools, but calling it returns a `STUB` message and does not modify
the external service.

---

## 9. Command reference (cheat sheet)

| Command | Purpose | Milestone |
|---------|---------|-----------|
| `bootstrap` | interview → validated org chart in `orgs/<name>/` | M3 |
| `bootstrap --pack <id>` | same, from a pre-built workforce pack (`packs` lists them) | M5 |
| `bootstrap --spec file.yaml` | same, non-interactive from YAML | M3 |
| `packs` | list built-in role packs | M5 |
| `validate --root <org>` | check an org tree is structurally valid | M3 |
| `run --org --role --task` | enqueue + execute a job with one role | M1 |
| `jobs --org` | list the durable job ledger | M1 |
| `context --org [--add/--search]` | capture / list / search shared memory | M2 |
| `ambition --org --role` | proactive propose→execute loop for a lead | M2 |
| `status --org` | mission-control report (jobs, insights, channel) | M4 |
| `observe --org` | observer pass → insights (friction, gaps, blockers) | M4 |
| `brief --org` | "what should I do today" action plan | M4 |
| `channel post/list/worker --org` | shared human↔agent conversation | M6 |
| `probe` | ping every configured provider/model pair | M1 |

Common flags on LLM-running commands: `--provider`, `--model`,
`--approval ask|deny|allow`, `--temperature`.

---

## 10. Where your data lives

Everything durable lives **inside the org folder**, so an org is portable:

```
orgs/Demo/.agentfactory/jobs.db      # SQLite store
```

| Table | Written by | Read by |
|-------|-----------|---------|
| `jobs`, `results`, `events` | `run`, `ambition`, `channel worker` | `jobs`, `status` |
| `context` | `context --add`, `ambition` | prompts, `context list/search` |
| `insights` | `observe` | `status`, `brief` |
| `messages` | `channel post`, `channel worker` | `channel list`, `status` |

Delete `jobs.db` to reset an org's history (the chart itself is plain files).

---

## 11. Troubleshooting & FAQ

**`run` says the role does not exist.** Role ids are file names under
`roles/` without `.yaml` — check `orgs/Demo/roles/` or `org.yaml`.

**A job ends `blocked`.** Every tool the agent tried required approval and
`--approval deny` refused them all. Re-run with `--approval ask` to approve
interactively, or lower the tool risk in the role's YAML.

**`bootstrap` fails validation.** Read the specific error (bad `reports_to`
link, unknown tool, missing goal). If hand-editing `org.yaml`, re-run
`validate` before running jobs.

**The output contains `<short title>` placeholders.** You are on the `fake`
provider — it echoes prompts for deterministic offline runs. Switch to
`openai`/`ollama` for real content.

**`probe` reports `[FAIL] ...`.** Check `OPENAI_API_KEY` / base URL (OpenAI),
or that Ollama is running (`ollama serve`) and the model is pulled
(`ollama pull qwen2.5:7b`).

**A third-party tool returns `STUB`.** This is expected for the integrations
listed in the “Live and stubbed tools” section. Use `files`, `web`, `memory`,
or `channel` for the currently implemented tool surface, or register a local
MCP-style server through the runtime API.

**Two channel workers at once?** Safe. Message claims are atomic
(`pending → running`), so each question is answered exactly once.

**Can I extend the tools?** Yes — see `docs/architecture/ARCHITECTURE.md`: the `Tool`
catalog (`runtime/tools.py`) and `register_tool_server()` for MCP-style
local servers (`runtime/toolservers.py`) are the extension points; new tools
inherit the same grant + risk + approval gating.





