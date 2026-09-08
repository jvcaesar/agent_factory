# Running bootstrap — Command Guide

> Every Python command you may see for driving the factory, what it does, and
> which ones to actually run. The short version is at the bottom.

## The commands

All three run through Python's `-m` (module) mode, i.e. "run the installed
`agent_factory` package as a program." Here is the role of each.

### 1. `set PYTHONPATH=src`
This is **not a Python command** — it's a Windows Environment Variable. It tells
Python where to find the `agent_factory` package (the code lives in `src\`).
Without it, `python -m agent_factory` fails with `ModuleNotFoundError`. Set it
**once per terminal session**, before using the other commands:

```
set PYTHONPATH=src
```

### 2. `python -m agent_factory bootstrap`
The **main command**. Runs the **interactive interview** — it asks you questions
(org name, north star, domains, tools, risk, budget, add-on roles) and then
**generates a brand-new org chart** under `orgs\<name>\`.

### 3. `python -m agent_factory bootstrap --spec <file> --out orgs/<name>`
**Not a second step** — an *alternative* to #2. It runs the exact same generator
but feeds the answers from a scripted YAML file instead of typing them. This is
for repeatable, deterministic, non-interactive generation (the tests use it).

### 4. `python -m agent_factory validate --root orgs/<name>`
A **quality check** against an already-generated org folder. It verifies
references resolve, no cycles, proactivity in range, SOP files exist. It does
**not** create anything.

## Do you run all of them?

**No.** #2 and #3 are mutually exclusive — choose **one**:

- Want to answer questions yourself → `bootstrap` (interactive).
- Want to reuse a saved spec file, or generate the same way every time →
  `bootstrap --spec`.

After either, run `validate` if you want to confirm the chart is sound.

### Typical session

```
set PYTHONPATH=src
python -m agent_factory bootstrap                     # or the --spec variant
python -m agent_factory validate --root orgs/MyOrg
```

The `--spec` variant and `validate` are optional comforts. The only truly
required step to get a workforce is **one `bootstrap` invocation**.

## Do you need this before the next milestone?

**Not as a separate prerequisite — but the next milestone will need org data.**

- `bootstrap` is a *tool for you* to use, not a blocker. There is nothing you
  must run "now" to unblock development.
- M1 (the runtime that turns a chart into running agents) will **load an
  `org.yaml` from disk** and execute it. You'll want at least one generated org
  to run against — and you already have one: **`orgs/Acme/`** (18 roles), plus
  the demo spec at `tests/fixtures/demo_spec.yaml`.

So the practical answers:

- Want a personalized workforce for M1 → run `bootstrap` (interactive) whenever
  you like, or point us at a `--spec`.
- Want to keep moving now → proceed to M1; it targets an existing org (Acme or a
  fresh one). `bootstrap` stays a **repeatable companion** to runtime, not a
  one-time gate.

## Note on the interactive path

The interview uses simple numbered menus and comma-separated lists. These work
fine in a PowerShell terminal but aren't great for scripts — which is exactly
why `--spec` exists.

## TL;DR

- `set PYTHONPATH=src` — do this once, first.
- Run **either** `bootstrap` **or** `bootstrap --spec` — not both.
- Run `validate` afterward if you want to confirm the result.
- None of this is a hard gate for the next milestone; you already have a valid
  org (`orgs/Acme`) to use.