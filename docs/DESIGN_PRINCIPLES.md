# Design Principles — The Generic Factory

> These are the *reusable patterns* this project is built around. They generalize
> the ideas from the source video without copying any specific org.

## 1. Pattern → feature map

Each row: the idea discussed in the video, then how the factory generalizes it
into a named, configurable property.

| Pattern (from video) | Generalized feature |
|---|---|
| "AI chief of staff + directors + workers" | **Hierarchy topology** — hub-and-spoke `reports_to` tree; any lead can spawn any sub-tier |
| "do smart things" prompt | **Ambition loop** — lead role gets a proactive objective + tool breadth; what it does is decided by goals+context, not hard-coded tasks |
| 3 employee types / pyramid of proactivity | **`proactivity_level` (0–5)** — a license-to-initiate scale per role |
| Phoebe "how do we 10x it" | **Amplifier pattern** — a review-capable add-on role that improves net-new output |
| Toby "watch for friction / access gaps" | **Observer pattern** — a low-cost add-on role that logs friction + access gaps |
| Watchdog with insight→action | **Insightable observers** — "don't just show a dashboard, tell me what to do next" |
| "not everything needs Opus" | **Model tiering** — `fast/smart/big` per role, budget-driven |
| "risk tier stays the same, width expands" | **Graded approval** — more autonomy in *breadth*, same approval ceiling for *risky* actions |
| "interview me → workforce in one prompt" | **Bootstrap** — data-driven org generation from an interview/spec |
| "build the factory, not the thing" | **Runtime primitives** — role registry, state, queue, eval as reusable layers (M1+) |
| Goals reviewed quarterly; company stays queryable | **Goal orientation + context capture** — goals doc injected into every role; diary/context flow planned (M2) |

## 2. Guiding rules

1. **Data over code.** A role is YAML + a SOP markdown file, not a Python class.
   New workforces are new config, not new code.
2. **Generic is the goal.** Do not bake any specific company's titles, names,
   or structure into the engine.
3. **Proactivity is a scale, not a mode.** 0–5 per role; ambitious by default
   for leads, conservative for workers.
4. **Capability widening ≠ risk widening.** Expand what agents *may do*, keep
   the approval ceiling for what is *irreversible*.
5. **Always offline-testable.** Generation and (later) runtime behavior must be
   deterministic with a fake LLM — never require network or keys for tests.
6. **Everything stays queryable.** Goals, decisions, and context live in
   versioned, searchable files.

## 3. Explicit non-goals

- Reproducing any individual's org chart (see `DECISION_LOG.md`).
- Replacing humans as liability owners — humans stay the final say (video
  02:17–03:27 "SVP, not manager" mindset).
- Dashboards-pretty-over-actionable output — insights must drive action.
- Locking to one model vendor at design time.