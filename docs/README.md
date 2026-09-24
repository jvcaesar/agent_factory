# Agent Factory Documentation

Use this page as the documentation home.

## Current implementation

- [Current implementation status](planning/CURRENT.md) - active release phase, next task, and blockers.
- [Release 2.0](releases/v2.0/README.md) - current release plans, checklist, QA, and implementation records.
- [Roadmap](planning/ROADMAP.md) - future release and feature direction.
- [Foundation project plan](planning/PROJECT_PLAN.md) - completed Milestones 1-6 that formed Release 1.0.

## Product documentation

- [User guide](product/USER_GUIDE.md) ([HTML](product/USER_GUIDE.html))
- [Product overview](product/PRODUCT.md) ([HTML](product/PRODUCT.html))
- [Specification authoring](product/SPEC_AUTHORING.md)
- [Bootstrap guide](product/HOWTO_BOOTSTRAP.md)
- [Web Console design direction](product/WEB_CONSOLE_DIRECTIONS.html)
- [Forge palette](product/forge_palette.md)

Product documents describe current user-facing behavior. Their paths remain stable across releases.

## Architecture

- [Architecture](architecture/ARCHITECTURE.md)
- [Design principles](architecture/DESIGN_PRINCIPLES.md)
- [Decision log](architecture/DECISION_LOG.md)
- [Filesystem confinement](architecture/FILESYSTEM_CONFINEMENT.md)
- [SSRF protection](architecture/SSRF_PROTECTION.md)

Architecture documents are living references. Release-specific deviations and decisions are also recorded in the applicable phase implementation record.

## Release history

- [Release 1.0.0](releases/v1.0.0/README.md) - shipped evidence, QA, release notes, and milestones.
- [Release 2.0](releases/v2.0/README.md) - active release workspace.
- [Release 1.0 milestone history](milestones/README.md)

## Research notes

- [Source transcript notes](notes/TRANSCRIPT_NOTES.md)
- [Source transcript](notes/My%20top%20secrets%20to%20running%20an%20AI%20Agent%20Workforce%20-%20YouTube%20-%20transcript%20%28English%20%28auto-generated%29%29.md)

## Organization conventions

- Use stable, undated folders for releases, such as `releases/v2.0/`.
- Create a dated implementation folder only when a release-checklist phase starts.
- Name phase folders `YYYY-MM-DD-phase-N-short-slug`; the date is the phase start date.
- Record the completion date inside the phase record. Do not rename the folder.
- Keep one phase record for each release-checklist phase. Include backend and web task IDs in that record rather than creating parallel histories.
- Start from [CURRENT.md](planning/CURRENT.md) when resuming implementation.
