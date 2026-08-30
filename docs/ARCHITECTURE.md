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
│   ├── tools.py               #   Tool catalog (files/web + stubs), tools_for_role()
│   ├── state.py               #   SQLite Store: jobs/results/events + context/insights
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
`notion gmail calendar slack stripe supabase github files web sheets docs crm cms payments analytics`

### Budget tier → model tier behavior
- workers → `fast`
- directors → archetype default (`smart`/`big`), downgraded to `smart` on `small` budget
- `lead_exec`/`amplifier` → `big` on `unlimited` budget, else `smart`

### Approval gate behavior
- `ApprovalPolicy.AUTONOMOUS` → writes do **not** require approval.
- `REVIEW_EXTERNAL` / `APPROVAL_FIRST` → every write grant gets `requires_approval=true`.

## 4. Validation model (`config/loader.validate_org`)

Returns a list of error strings (empty == valid). Checks:
1. duplicate role ids
2. proactivity range
3. unknown `reports_to` / `subagents` refs
4. empty tool grants
5. reporting-graph cycles (DFS coloring)

## 5. Seams for future milestones

- **M4 insights:** done — `observer`/`brief` behavior lives in `runtime/insights.py`, writing to the `context`/`events`/`insights` store.
- **M5 role packs:** done — `packs/` registry + `--spec` templates; `generator` has an optional override seam but defaults are unchanged. State can still move to Postgres behind `Store`'s interface (M6+).
- **M6 multiplayer & tool surface:** add a human↔agent channel (e.g. shared Slack-style queue) and richer MCP/local tool adapters; `Store` and `tools.CATALOG` are the extension points.

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

python -m unittest discover -s tests -v   # 87 tests, offline
```