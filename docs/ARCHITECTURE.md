# Architecture Reference

> How the current code is organized, and the contracts later milestones rely on.
> All paths are relative to the project root.

## 1. Module map

```
src/agent_factory/
├── cli.py                     # argparse CLI: bootstrap, validate
├── __main__.py                # python -m agent_factory support
├── config/
│   ├── __init__.py            # pydantic schema (Org, Role, ToolGrant, enums)
│   └── loader.py              # YAML loading (org_from_dict) + validate_org()
└── bootstrap/
    ├── __init__.py            # package docstring only
    ├── archetypes.py          # generic role library (workers/directors/add-ons)
    ├── interview.py           # InterviewAnswers dataclass + validation
    ├── generator.py           # answers → Org (in-memory) + write_org() (files)
    └── prompts.py             # Markdown templates (SOP / goals / org README)
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

- **M1 runtime:** insert a new `runtime/` package consuming `Org`; add a `run_agent(role, context)` with a `LLMClient` interface (the seam is `config`, not `bootstrap`).
- **M2 ambition loop:** add a `goals/context` store and a `propose/execute` loop on the lead role.
- **M4 insights:** `observer` role currently just has a charter; the runtime can attach scan + log behavior behind the same `Role` model.
- **M5 role packs:** add `src/agent_factory/packs/<name>/` with archetype overrides + `--spec` templates; `generator` stays untouched.

## 6. Running the code

```
cd agent_factory
set PYTHONPATH=src
python -m agent_factory bootstrap --spec tests/fixtures/demo_spec.yaml --out orgs/MyOrg
python -m agent_factory validate --root orgs/MyOrg
python -m unittest discover -s tests -v   # 16 tests, offline
```