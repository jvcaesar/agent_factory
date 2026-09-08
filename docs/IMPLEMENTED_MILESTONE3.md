# Milestone 3 — Bootstrap · Implemented

> Current step (M3) — everything that is built and working as of this document.

## 1. What this milestone delivers

The **bootstrap** command turns an interview into a validated on-disk org chart.
It is a pure, deterministic function of (topology + domains + risk + budget +
tools). No LLM, no network — so it is fully offline and testable.

### Files created

| Path | Role |
|------|------|
| `src/agent_factory/config/__init__.py` | pydantic schema: `Org`, `Role`, `ToolGrant`, enums |
| `src/agent_factory/config/loader.py` | YAML load + validation (refs, cycles, ranges, SOP existence) |
| `src/agent_factory/bootstrap/archetypes.py` | 4 workers + 11 directors + 2 add-ons (role library) |
| `src/agent_factory/bootstrap/interview.py` | `InterviewAnswers` (interactive + `--spec`) + validation |
| `src/agent_factory/bootstrap/generator.py` | `InterviewAnswers` → `Org`, then writes all files |
| `src/agent_factory/bootstrap/prompts.py` | Markdown templates: SOP runbooks, goals doc, org README |
| `src/agent_factory/cli.py` | CLI entry: `bootstrap` (interactive/`--spec`), `validate` |
| `src/agent_factory/__main__.py` | `python -m agent_factory ...` support |
| `tests/` | 16 offline tests at M3 time (stdlib `unittest`); the suite has grown since — see current counts in the README |
| `orgs/Acme/` | Sample generated org (18 roles) |
| `tests/fixtures/demo_spec.yaml` | Scripted interview answers driving the demo/test |
| `pyproject.toml`, `.gitignore`, `README.md`, `LICENSE` | Project scaffolding |

## 2. The data model (the contract later milestones depend on)

- **`Org`** — name, founder, north star, human team size, quarterly goals, risk tier, budget tier, roles.
- **`Role`** — id, display name, title, charter, SOP path, **proactivity level 0–5**, model tier, approval policy, reports_to, tool grants, subagents.
- **`ToolGrant`** — tool id + access (read/write) + requires_approval.
- **Enums** — `ApprovalPolicy` (autonomous/review_external/approval_first), `ModelTier` (fast/smart/big), `ToolAccess`.

## 3. Role library (generic, no names)

- **Workers:** `worker_research`, `worker_write`, `worker_qa`, `worker_code`.
- **Directors:** `director_product`, `director_engineering`, `director_research`,
  `director_marketing`, `director_finance`, `director_operations`,
  `director_support`, `director_data`, `director_partnerships`, `director_people`,
  `director_ai_ops`.
- **Add-ons:** `amplifier` (pushes output up a notch), `observer` (logs friction/access gaps).
- **Top coordinator:** `lead_exec` (generalized "chief of staff").

## 4. Generation rules implemented

- One director per chosen domain; each fans out into its default workers.
- Optional `lead_exec` coordinator; directors/add-ons report to it.
- Optional `amplifier` / `observer` add-ons.
- **Model tiering:** workers → `fast`, lead/`amplifier` → `big` on unlimited budget,
  `small` budget auto-downgrades `big` directors to `smart`.
- **Graded approval:** under `review_external` or `approval_first`, write grants
  require human approval ("risk tier constant, width expands" — video 07:46).

## 5. Validation rules (`agent_factory validate`)

- All `reports_to` / `subagents` refs resolve.
- No reporting cycles.
- No duplicate role ids.
- `proactivity_level` in range 0–5.
- SOP files exist on disk.
- `test_schema_rejects_bad_id`, `test_cycle_detected`, etc. cover these.

## 6. Test coverage (16 passing)

`test_bootstrap_demo.py` (8) + `test_loader_validation.py` (8). All run offline via:

```
python -m unittest discover -s tests
```

## 7. Verified end-to-end

```
set PYTHONPATH=src
python -m agent_factory bootstrap --spec tests/fixtures/demo_spec.yaml --out orgs/Acme
python -m agent_factory validate --root orgs/Acme   # OK: valid org (18 roles)
```

## 8. Sample generated output (orgs/Acme)

- `org.yaml` — aggregate definition (loads via `load_org_yaml`)
- `roles/*.yaml` — one file per role
- `sops/*.md` — SOP runbook per role
- `goals/current.md` — north star + quarterly targets (from spec)
- `settings.yaml` — org settings + known tools
- `README.md` — human-readable org summary