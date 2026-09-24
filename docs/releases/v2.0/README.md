# Release 2.0

> **Status:** Draft; implementation not started  
> **Current phase:** Phase 0 - Baseline  
> **Current status:** [Current implementation status](../../planning/CURRENT.md)

Release 2.0 adds the local management dashboard, durable operations and approvals, and the worker pool. This undated folder remains the stable home for the release throughout planning, implementation, QA, and release.

## Authoritative documents

- [Release checklist](RELEASE_CHECKLIST_2.0.md) - authoritative release-level status and Phase 0-5 gates.
- [Dashboard backend plan](DASHBOARD_BACKEND_PLAN.md) - detailed backend tasks `B0.1` and `B1-B5`.
- [Web Console plan](WEB_CONSOLE_PLAN.md) - detailed web tasks `P0-P5`.
- [QA record](QA_2.0.md) - error-path and live proof evidence.
- [Release notes](RELEASE_NOTES_2.0.md) - release-facing summary under construction.

## Phase implementation records

Create exactly one dated implementation folder when each release-checklist phase starts. Use [the phase template](implementation/PHASE_TEMPLATE.md).

| Release phase | Scope | Implementation record |
|---|---|---|
| Phase 0 | Baseline | Not started |
| Phase 1 | Backend engine | Not started |
| Phase 2 | Web Console | Not started |
| Phase 3 | Release quality | Not started |
| Phase 4 | Packaging and release | Not started |
| Phase 5 | Post-2.0 backlog | Not started |

Folder format: `implementation/YYYY-MM-DD-phase-N-short-slug/README.md`. The date is the phase start date. Keep completion dates, design decisions, verification, and handoff details inside the record rather than renaming the folder.

Detailed backend and web IDs belong in the corresponding release-phase record. Do not create separate dated histories for backend phases, web phases, or individual sessions.

## Completion workflow

1. Mark the relevant checklist and companion-plan rows `In Progress`.
2. Create or update the current dated phase record.
3. Implement and run the task-specific verification.
4. Record delivered behavior, decisions, deviations, evidence, known issues, and handoff information.
5. Update all relevant trackers before declaring the phase complete.
6. Advance [CURRENT.md](../../planning/CURRENT.md) to the next eligible phase.
