# Decision Log

> Running record of architectural and scoping decisions. Newest first.

## 2026-08-21 — Docs folder added
**Decision:** Create `docs/` with plan, implementation notes, roadmap, architecture, principles, transcript reference, and this log.
**Why:** Keep the video-derived design rationale and milestone state visible to any future work (or new collaborator).
**Consequence:** `README.md` now links to these docs.

## 2026-08-21 — M3: generic role library (no proper names)
**Decision:** Worker/director/add-on archetypes are generic functions (`director_product`, `amplifier`, `observer`, ...), not imitations of the video's named roles.
**Why:** The user explicitly asked for a *generic factory* that uses ideas, not replicas. Generality also serves the later business-ops/engineering/research packs.
**Consequence:** Any user's org is generated from the same library; specialized orgs are config over the same archetypes.

## 2026-08-21 — M3: schema-first design
**Decision:** Build `Org`/`Role`/`ToolGrant` pydantic models + loader/validator before any runtime code.
**Why:** Every later milestone (runtime, ambition loop, observers, packs) consumes this schema; bootstrap forces it to be exercised early.
**Consequence:** 16 offline tests pin the contract.

## 2026-08-21 — M3: stdlib `unittest`, no network
**Decision:** Tests use stdlib `unittest` (not pytest) because `pytest` isn't installed and the environment is offline-friendly.
**Consequence:** Test suite runs with `python -m unittest discover -s tests`; no extra installs.

## 2026-08-21 — M3: graded approval implemented
**Decision:** Under `review_external`/`approval_first`, all write grants get `requires_approval=true`. `autonomous` tier leaves writes ungated.
**Why:** Video's "risk tier stays the same, width expands" — more scope, same ceiling.
**Consequence:** Write-heavy roles surface approvals in generated YAML (see `orgs/Acme/roles/director_marketing.yaml`).

## 2026-08-21 — M3: quarterly goals into goals/current.md
**Decision:** `Org.quarterly_goals` persisted and rendered into `goals/current.md`, which every SOP references.
**Why:** "Goals reviewed quarterly" and goal-oriented proactivity (video 09:05).
**Consequence:** Goals are versioned, reviewable, and injected into the agent context later (M2).

## 2026-08-21 — M3: model tiering + budget
**Decision:** `fast`/`smart`/`big` per role; `small` budget downgrades `big`-tier directors to `smart`.
**Why:** "Not everything needs Opus — sub-agents are Haiku/Sonnet" (video 20:34).
**Consequence:** Budget choices matter at generation time (see `test_small_budget_downgrades_big_director`).

## 2026-08-21 — M3: lead_exec coordinator (generalized "chief of staff")
**Decision:** Optional `lead_exec` role sits on top when `use_lead` is chosen; directors/add-ons report to it.
**Why:** Generalizes the COS pattern without copying any named person.
**Consequence:** Without a lead, the first director is top of org (still a valid chart).