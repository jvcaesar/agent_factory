# Transcript Reference (distilled)

> Source: *"My top secrets to running an AI Agent Workforce"* — Greg Isenberg ×
> Alli K. Miller (`EzQAgnjTq2k`). These are the distilled *ideas* we generalized
> from; see `DESIGN_PRINCIPLES.md` for the pattern→feature map.
> Transcript file lives at the project root (auto-generated English captions).

| Time | Idea | What we took from it |
|------|------|----------------------|
| 02:17 | "Managing agents is wrong — you're setting up infrastructure, waiting for escalations"; SVP, not direct manager | Humans stay final say; engine owns routing/execution. `lead_exec` + `review_external` default. |
| 03:27 | Admin side of management should be fully gone | Export/import everything; automation of drudgery is a goal of later milestones. |
| 04:39 | Best prompt is "do smart things" (goals + full context + tools) | `Ambition loop` (M2) — proactive objective over goals+context. |
| 05:27 | Wants AI to push her past her own ceiling | `Amplifier` add-on archetype. |
| 06:58 | 3 employee types; type 3 = exceeds tasks *and* initiates new ones | `proactivity_level` (0–5) scale. |
| 07:46 | "Risk tier stays the same, width expands" | `Graded approval` — breadth yes, ceiling yes. |
| 08:43 | Alex Lieberman's pyramid of proactivity (L4 tradeoffs, L5 +rollback) | Encoded as level 4 / level 5 prose in SOPs and schema docs. |
| 09:05 | Goals written + reviewed quarterly => net-new tasks are goal-oriented | `goals/` store + `quarterly_goals` in `Org`. |
| 12:25 | "I want my whole company to be queryable" — all context codified | Context capture flow (M2 diary/context store). |
| 15:13 | COS + directors over business functions | Hub-and-spoke `reports_to` topology. |
| 16:57 | Agents cost ~$0 → hire weirdos: Phoebe (10x), Toby (watcher) | `amplifier` + `observer` generic add-ons. |
| 19:34 | Start with traditional job titles, then evolve | Directors/workers use plain titles; names are optional (`--names` future). |
| 20:17 | Ramp: one agent → proactive one → two cooperating → workforce + mission control | `ROADMAP.md` ordering (M1→M2→M4). |
| 20:34 | Not everything needs Opus; sub-agents Haiku/Sonnet | `ModelTier` fast/smart/big + budget tier. |
| 21:27 | Spin up a workforce from one prompt; iterate to 90%+ | `bootstrap` + `validate`; iteration loop via re-running bootstrap. |
| 22:20 | AI as watchdog for blockers (Slack, calendar, meetings) | `observer` + mission control (M4). |
| 26:04 | Not dashboards — "what should I do tomorrow, write me a script" | Insight→action as an explicit goal for M4. |
| 26:57 | Build the factory for the thing, not the thing | This project: primitives (queue, state, evals) as reusable layers. |

## Non-goal (explicit)
Reproducing Alli's specific fleet (Simon, her director mix, her exact tools) — see `DECISION_LOG.md`.