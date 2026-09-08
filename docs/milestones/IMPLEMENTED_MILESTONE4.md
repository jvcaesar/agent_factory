# Milestone 4 — Insights: Observers + Mission Control · Implemented

> Current step (M4) — adds a **visibility & action layer**: low-cost observer
> (watchdog) agents surface friction/access gaps/blockers/contradictions/
> opportunities, persisted as insights; a "what to do today" brief turns them
> into action (not a dashboard); and a mission-control `status` report shows the
> queue, open insights, and work in flight.

## 1. What this milestone delivers

- **Observer / watchdog** — scans jobs + recent events (approval denials,
  errors) + captured context + existing insights and reports findings.
- **Insight store** — durable `insights` table (level/kind/title/detail/
  suggestion/status) with list/update/aggregate access.
- **Daily brief ("insight → action")** — a prioritized "what should I do today"
  plan that routes actions to roles and names first steps (the video's
  "not dashboards — tell me what to do next", 26:04).
- **Mission control** — a `status` CLI report (job counts, open insights,
  recent jobs, approval events).

## 2. New code

### `src/agent_factory/runtime/insights.py`
- `Observation` dataclass (`level`, `kind`, `title`, `detail`, `suggestion`, `slug`).
- `parse_observations(text, max_count)` — robust JSON extraction (via the shared
  `protocol.extract_json_object`); bad levels/kinds normalize to `info`/`friction`.
- `observe(org, role, store, llm, ...)` — builds a state/context prompt, gets
  observations from the LLM, persists each to the insight store (dedup by slug).
- `build_daily_brief(org, role, store, llm, ...)` — turns open insights + job
  state into an actionable "what to do today" brief.
- `_state_summary(store)` — prompt-friendly snapshot: job counts, recent jobs,
  recent approval denials.

### `src/agent_factory/runtime/state.py` (extended)
- `insights` table + `add_insight`, `update_insight_status`, `list_insights`.
- `recent_events` (across all jobs) and `stats()` (mission-control aggregates).

### CLI additions (`src/agent_factory/cli.py`)
- `observe --org [--role --provider --model --limit]` — run an observer pass.
- `brief --org [--role --provider --model]` — generate the daily brief.
- `status --org [--limit]` — mission-control report.

## 3. The observation protocol

The observer responds with one JSON object:

```json
{"type": "observations", "observations": [
  {"level": "info|low|warning|critical", "kind": "friction|access_gap|contradiction|blocker|opportunity",
   "title": "...", "detail": "...", "suggestion": "..."}
]}
```

Persisted insights start `status='open'`; they can be marked `accepted`/`dismissed`.

## 4. Test coverage

Added `tests/test_runtime_insights.py`. At the time of M4 the combined suite was **95 tests,
all offline / green**:

```
python -m unittest discover -s tests
```

Covers: observation parsing (list, plain-text → empty, bad level/kind default,
max_count), the observer persisting insights, the insight store (add/status/
stats), and the daily brief returning LLM text.

## 5. Verified end-to-end (fake provider)

```
python -m agent_factory run --org orgs/Acme --role worker_research_1 --task "..." --provider fake
python -m agent_factory status  --org orgs/Acme
python -m agent_factory observe --org orgs/Acme --provider fake --limit 2
python -m agent_factory brief   --org orgs/Acme --provider fake
```

Confirmed: a job runs and records, mission-control shows job counts, the
observer surfaces a finding, and the brief builds the full prompt (with a real
provider these would produce live findings/answers).

## 6. Usage

```
# Observer pass (use a real provider for real findings)
python -m agent_factory observe --org orgs/Acme --provider openai --limit 5

# Mission control
python -m agent_factory status --org orgs/Acme

# Daily brief ("what to do today")
python -m agent_factory brief --org orgs/Acme --provider openai
```