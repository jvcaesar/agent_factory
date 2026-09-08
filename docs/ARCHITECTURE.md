# Architecture Reference

> How the current code is organized, and the contracts later milestones rely on.
> All paths are relative to the project root.

## 1. Module map

```
src/agent_factory/
├── cli.py                     # argparse CLI: bootstrap, validate, run, jobs
├── __main__.py                # python -m agent_factory support
├── config/
│   ├── __init__.py            # pydantic schema (Org, Role, ToolGrant, enums)
│   └── loader.py              # YAML loading (org_from_dict) + validate_org()
├── bootstrap/
│   ├── __init__.py            # package docstring only
│   ├── archetypes.py          # generic role library (workers/directors/add-ons)
│   ├── interview.py           # InterviewAnswers dataclass + validation
│   ├── generator.py           # answers → Org (in-memory) + write_org() (files)
│   └── prompts.py             # Markdown templates (SOP / goals / org README)
├── llm/                       # M1: provider-agnostic LLM clients
│   ├── base.py                #   LLMClient ABC, ChatMessage, LLMResult
│   ├── fake.py                #   FakeLLM (offline tests)
│   ├── openai_client.py       #   OpenAILLM (legacy + modern API)
│   ├── ollama_client.py       #   OllamaLLM (local Gemma/Qwen)
│   ├── factory.py             #   get_client(provider) <- AGENT_FACTORY_PROVIDER
│   └── __init__.py            #   re-exports
├── runtime/                   # M1+M2: execute an Org
│   ├── __init__.py            #   re-exports
│   ├── tools.py               #   Tool catalog (files/web/memory/channel + stubs), risk rules,
│   │                          #   tools_for_role(), approval_needed()
│   ├── toolservers.py         #   M6: ToolServer protocol + register_tool_server (local MCP)
│   ├── channel.py             #   M6: shared human<->agent channel + run_channel_worker()
│   ├── state.py               #   SQLite Store: jobs/results/events + context/insights/messages
│   ├── agent.py               #   run_agent() loop, build_system_prompt(), parse_action()
│   ├── orchestrator.py        #   run_job() — enqueue + run + record
│   ├── ambition.py            #   M2: propose_actions(), run_ambition_loop(), Proposal
│   └── insights.py            #   M4: observe() / build_daily_brief(), Observation
├── packs/                     # M5: role packs (dataset workforces)
│   └── __init__.py            #   RolePack registry + build_answers/overrides
└── cli.py                     # argparse CLI: bootstrap, validate, run, jobs,
                               #   ambition, context, probe, observe, brief, status,
                               #   packs
```

## 2. Data flow

```
  interactive interview  ─┐
                         ├─> InterviewAnswers ─> generate_org() ─> Org
  --spec YAML file ──────┘                              │
                                                        └─> write_org() ─> orgs/<name>/
                                                             (roles/*.yaml, sops/*.md,
                                                              goals/current.md,
                                                              org.yaml, settings.yaml,
                                                              README.md)

  agent_factory validate --root orgs/<name>  ──────> load_org_yaml() + validate_org()
```

## 3. Key contracts

### `Org` (schema)
`name, founder, north_star, human_team_size, quarterly_goals, risk_tier, budget_tier, roles[]`

### `Role` (schema)
`id, display_name, title, charter, sop, proactivity_level(0-5), model_tier,
approval_policy, reports_to, tool_grants[], subagents[]`

### built-in tool ids (from `archetypes.KNOWN_TOOLS`)
`notion gmail calendar slack stripe supabase github files web sheets docs crm cms payments analytics memory channel`
(real adapters: `files`, `web`, and — since M6 — `memory`/`channel`, plus any
`register_tool_server` entry; everything else resolves to a stub)

### Budget tier → model tier behavior
- workers → `fast`
- directors → archetype default (`smart`/`big`), downgraded to `smart` on `small` budget
- `lead_exec`/`amplifier` → `big` on `unlimited` budget, else `smart`

### Approval gate behavior (M6 risk-aware rules — `approval_needed`)
- `ApprovalPolicy.AUTONOMOUS` → only **high-risk** tools are gated (defense in depth).
- `REVIEW_EXTERNAL` → every write grant and **high-risk** reads are gated.
- `APPROVAL_FIRST` → every tool call is gated.
- A schema-level grant (`ToolGrant.requires_approval`) is always absolute.
- `files_write` is `risk=high`; `web_fetch`/`memory_read`/`channel_list` are `low`;
  `memory_write`/`channel_post` are `medium` (so autonomous orgs may post
  in-channel without approvals, while review-external orgs gate them).

## 4. Validation model (`config/loader.validate_org`)

Returns a list of error strings (empty == valid). Checks:
1. duplicate role ids
2. proactivity range
3. unknown `reports_to` / `subagents` refs
4. empty tool grants
5. reporting-graph cycles (DFS coloring)

## 5. Seams for future milestones

- **M4 insights:** done — `observer`/`brief` behavior lives in `runtime/insights.py`, writing to the `context`/`events`/`insights` store.
- **M5 role packs:** done — `packs/` registry + `--spec` templates; `generator` has an optional override seam but defaults are unchanged. State can still move to Postgres behind `Store`'s interface.
- **M6 multiplayer & tool surface:** done — shared human↔agent channel (`runtime/channel.py`), store-backed `memory`/`channel` adapters + MCP-style servers (`runtime/toolservers.py`), and risk-aware permissions (`approval_needed`). `Store` and `tools.CATALOG` are still the extension points for external integrations.

## 6. Running the code

```
cd agent_factory
set PYTHONPATH=src
python -m agent_factory bootstrap --spec tests/fixtures/demo_spec.yaml --out orgs/MyOrg
python -m agent_factory validate --root orgs/MyOrg

# M5: one-command workforce from a role pack
python -m agent_factory packs
python -m agent_factory bootstrap --pack engineering --name "Acme Eng" --out orgs/Eng

# M1: run a job (offline first, then real providers)
python -m agent_factory run --org orgs/Acme --role worker_research_1 ^
    --task "List the quarterly targets." --provider fake --approval deny
python -m agent_factory jobs --org orgs/Acme

# M2: seed context, then the proactive loop
python -m agent_factory context --org orgs/Acme --add diary/today --detail "..."
python -m agent_factory ambition --org orgs/Acme --role lead_exec --max-actions 2

# M6: talk to the workforce from a shared channel (Loop Alley), then run it
python -m agent_factory channel post --org orgs/Acme --text "Did the client respond?"
python -m agent_factory channel worker --org orgs/Acme --provider fake
python -m agent_factory channel list --org orgs/Acme

python -m unittest discover -s tests -v   # 163 tests, offline
```