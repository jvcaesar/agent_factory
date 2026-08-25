# Milestone 2 — Ambition Loop ("do smart things") · Implemented

> Current step (M2) — makes the workforce *proactive*, not just reactive, by
> letting the lead (or any role with `proactivity_level >= 3`) initiate net-new
> work against goals + context.

## 1. What this milestone delivers

The generalized "do smart things" loop from the source material: a lead role
looks across goals + captured context + granted tools, **proposes** high-value
proactive actions, **executes** accepted ones through the existing M1 agent
loop, and **learns** by recording outcomes back into the context store.

Scope widens (more breadth to initiate work), but risk does not — risky actions
still go through the normal approval gate, and a `max_risk` filter can forbid
execution entirely.

## 2. New code

### `src/agent_factory/runtime/ambition.py`
- `Proposal` dataclass — `title, action, rationale, risk, priority`, plus a `slug()`.
- `parse_proposals(text)` — robust JSON extraction → sorted `list[Proposal]`; invalid risk defaults to `medium`.
- `propose_actions(org, role, llm, context_text, ...)` — returns `[]` when `proactivity_level < 3` (the gate); otherwise prompts for proposals in a JSON protocol.
- `run_ambition_loop(org, role, llm, store, ...)` — propose → (filter by `max_risk`/`max_actions`) → dispatch to a worker via `run_agent` → record outcome into context. Returns `(proposals, executed)`.

### `src/agent_factory/runtime/state.py` (extended)
Added a `context` table + methods:
- `upsert_context(key, content, source)` — diary/ambition notes, upsert-by-key.
- `get_context`, `list_context`, `search_context`, `context_blob()` (flat prompt-injectable block).

### CLI additions (`src/agent_factory/cli.py`)
- `ambition --org [--role --provider --approval --candidates --max-actions --max-risk]`
- `context --org [--add <key> --detail <text>] | [--search <term>] | [--limit N]`

## 3. The proposal protocol

The model responds (to a proactive role) with one JSON object:

```json
{"type":"proposals","proposals":[
  {"title":"Draft launch brief","action":"Write the launch brief for v1.",
   "rationale":"Advances the launch target","risk":"low","priority":1}
]}
```

`parse_proposals` tolerates fenced/loose JSON and plain-text fallback (→ empty).

## 4. Gates (same approval ceiling)

- **Proactivity gate:** roles with `proactivity_level < 3` cannot initiate.
- **Risk gate:** `max_risk` (default `medium`) — higher-risk proposals are
  recorded as skipped, never executed. Falls back to low/medium for unknown.
- **Budget gate:** `max_actions` limits how many proposals run per pass.
- **Tool/approval gate (inherited):** each executed proposal becomes a job run
  through `run_agent`, which enforces granted tools and `requires_approval`.

## 5. Test coverage

Added `tests/test_runtime_ambition.py`. Combined suite is now **53 tests,
all offline / green**:

```
python -m unittest discover -s tests
```

Covers: proposal parsing (sort, defaults, empty), proactive vs. passive
propose gating, full loop executes + records into context + marks jobs done,
high-risk skip, `max_actions` budget, and the context store (upsert, search,
blob).

## 6. Verified end-to-end

`agent_factory context --org orgs/Acme --add diary/...` then
`context --search demo` confirmed the diary flow writes and returns context.
`ambition --org orgs/Acme --role lead_exec --provider fake` loaded the org,
found the lead (proactivity 5), and ran the propose/execute pipeline.

> Note: with the default `--provider fake` the fake echoes the prompt, so it
> returns no proposals (proving the API wiring). The full propose→execute→learn
> path is exercised deterministically in the functional tests with a scripted
> fake.

## 7. Example usage

```
# capture a diary entry
python -m agent_factory context --org orgs/Acme \
    --add diary/2026-08-21 --detail "Client wants a live demo first."

# run the proactive loop (real provider)
python -m agent_factory ambition --org orgs/Acme --role lead_exec \
    --provider openai --max-actions 3 --max-risk medium

# search what was captured
python -m agent_factory context --org orgs/Acme --search demo
```