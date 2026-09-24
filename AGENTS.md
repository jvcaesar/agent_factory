# Agent Factory Agent Instructions

These instructions apply to every coding agent working in this repository.

## Before implementation

1. Read [`docs/planning/CURRENT.md`](docs/planning/CURRENT.md).
2. Read the active release checklist and the companion plan for the task.
3. If the current release-checklist phase has started, read its dated implementation record under `docs/releases/<release>/implementation/`.
4. Confirm prerequisites and identify the exact tracker IDs being implemented.
5. Mark the applicable tracker rows `In Progress` before changing implementation code.

## Phase records

Release folders are stable and undated. Create one dated implementation folder only when a release-checklist phase begins:

```text
docs/releases/<release>/implementation/YYYY-MM-DD-phase-N-short-slug/README.md
```

The folder date is the phase start date. Do not rename the folder when the phase completes. Use the release's `implementation/PHASE_TEMPLATE.md` for required content.

Create one record per release-checklist phase. Record backend, web, or other companion-plan task IDs inside that record; do not create parallel dated histories for subplans or individual sessions.

## During implementation

- Keep the release checklist and companion-plan task statuses synchronized.
- Append verified progress, material design decisions, contract deviations, and relevant evidence to the current phase record.
- Run the narrowest relevant test after each substantive change, then broader checks appropriate to the affected surface.
- Mark blocked work `Blocked` with the reason and unmet dependency. Do not continue through an unmet phase dependency.

## Before stopping or declaring completion

- Record exact verification commands and summarized results.
- Update known issues and deferred work with tracker IDs.
- Leave a concrete handoff: next eligible phase or task, unmet dependencies, operational cautions, and resume steps.
- Update every affected tracker row.
- Update `docs/planning/CURRENT.md` with the current phase, next task, blockers, and active phase-record link.
- Declare a phase `Done` only after its release-checklist exit criteria pass.

A `SKILL.md` is intentionally not used for this process. Phase tracking and handoff are mandatory repository policy, not an optional workflow.
