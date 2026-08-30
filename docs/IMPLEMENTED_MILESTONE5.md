# Milestone 5 — Role Packs · Implemented

> Current step (M5) — pre-built, specialized workforces on the same engine.
> `business_ops`, `engineering`, and `research` packs generate complete org
> charts (with vertical-tuned charters) in one command, and ship as repeatable
> `--spec` templates.

## 1. What this milestone delivers

- **Role pack registry** — named, data-only configurations that produce a full
  org chart for a vertical use case. Each pack carries:
  - `spec` — `InterviewAnswers`-style defaults (domains, tools, goals, risk,
    budget, add-ons), also usable directly as a `--spec` file.
  - `archetype_overrides` — targeted charter tweaks applied via
    `dataclasses.replace`, keeping the generator one deterministic engine.
- **`bootstrap --pack <name>`** — one-command workforce generation, with
  `--name` / `--founder` / `--north-star` overrides.
- **`packs` CLI** — list packs and `packs --show <name>` prints the spec YAML.
- **Repeatable spec templates** — `examples/packs/*.yaml` for every pack, so
  teams can copy + edit a spec and use `bootstrap --spec` for variant orgs.

## 2. New code

- `src/agent_factory/packs/__init__.py` — `RolePack` dataclass, `PACKS` registry,
  `get_pack`, `list_packs`, `build_answers`, `overridden_archetypes`.
- `src/agent_factory/bootstrap/generator.py` (small, backward-compatible) —
  `generate_org(answers, *, directors=None, workers=None, addons=None)` override
  seam; defaults are unchanged.
- `src/agent_factory/cli.py` — `bootstrap --pack` (`--name/--founder/--north-star`)
  and the `packs` subcommand.
- `examples/packs/{business_ops,engineering,research}.yaml` — spec templates.

## 3. The packs

| Pack | Domains | Highlight override |
|------|---------|-------------------|
| `business_ops` | marketing, operations, support, finance, data, partnerships | director_operations / finance / support charters tuned for go-to-market ops |
| `engineering` | product, engineering, research, ai_ops, data | director_engineering + worker_code / worker_qa charters for delivery discipline |
| `research` | research, data, product, partnerships | director_research + worker_research charters for defensible findings |

All packs default to `review_external` risk, `medium` budget, `use_lead`,
`add_amplifier`, and `add_observer`.

Override keys may reference a director by domain key **or** archetype id
(`"engineering"` or `"director_engineering"`) — both resolve.

## 4. Usage

```
# List packs
agent_factory packs

# Print the engineering pack's spec (for reuse/customization)
agent_factory packs --show engineering

# Generate an engineering org from a pack
agent_factory bootstrap --pack engineering --name "Acme Eng" ^
    --north-star "Ship fast, keep quality high" --out orgs/Eng

# Or from the reusable spec template
agent_factory bootstrap --spec examples/packs/research.yaml --out orgs/Research
```

Every pack output is a normal org: validate it (`agent_factory validate --root
orgs/Eng`), run jobs on it, observe it, etc.

## 5. Test coverage

Added `tests/test_packs.py`. Combined suite is now **113 tests, all offline /
green**:

```
python -m unittest discover -s tests
```

Covers: registry contents + sorted listing, unknown-pack errors, override keys
resolve to known archetypes, overrides change charters, pack specs build valid
answers with CLI overrides, end-to-end `bootstrap --pack` writes a valid org
with the overridden charters present, example spec files all generate valid
orgs, and the `--pack`/`--spec` conflict is rejected.

## 6. Verified end-to-end

`agent_factory bootstrap --pack engineering --name 'Acme Eng' --north-star 'Ship
fast, keep quality high' --out orgs/AcmeEng` generated a **20-role valid org**
(`validate` OK), and `orgs/AcmeEng/roles/director_engineering.yaml` carried the
pack's delivery charter.