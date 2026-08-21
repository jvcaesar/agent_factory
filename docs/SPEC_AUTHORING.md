# Authoring Org Specs (--spec)

> Reference for hand-writing the YAML fed to `agent_factory bootstrap --spec`,
> or for understanding what the generated chart means. Start from
> `tests/fixtures/demo_spec.yaml`.

## Top-level fields

```yaml
org_name: My Org            # required
founder: Ada                # optional, shown in goals/README
north_star: <string>        # required — the goal agents act against
quarterly_goals:            # optional, rendered into goals/current.md
  - Target one
  - Target two
human_team_size: 3          # optional int
domains:                    # required, non-empty; keys into DIRECTORS
  - product
  - engineering
  - marketing
  - data
tools:                      # optional — subset of KNOWN_TOOLS
  - notion
  - gmail
  - github
risk_tier: review_external  # autonomous | review_external | approval_first
budget_tier: medium         # small | medium | unlimited
add_amplifier: true         # optional add-on role
add_observer: true          # optional add-on role
use_lead: true              # optional top coordinator (Chief of Staff)
```

## Valid `domains` (director archetypes)

| key | creates |
|-----|---------|
| `product` | director_product + research/write/qa workers |
| `engineering` | director_engineering + code/qa workers |
| `research` | director_research + research/write/qa workers |
| `marketing` | director_marketing + write/research/qa workers |
| `finance` | director_finance |
| `operations` | director_operations |
| `support` | director_support |
| `data` | director_data |
| `partnerships` | director_partnerships |
| `people` | director_people |
| `ai_ops` | director_ai_ops (highest proactivity/big model) |

## Valid `tools` (KNOWN_TOOLS)

`notion gmail calendar slack stripe supabase github files web sheets docs crm cms payments analytics`

## Behavior to remember

- Default `risk_tier` is `review_external` → all write grants get `requires_approval: true`.
- Default `budget_tier` is `medium`; `small` downgrades `big`-tier directors to `smart`.
- `use_lead: true` makes everything report to `lead_exec`; `false` leaves the first director at top.
- `amplifier` + `observer` are pure capability add-ons (generic "10x-er" and "watcher").

## Validation

Run `agent_factory validate --root orgs/<name>` after generation. It checks refs,
cycles, duplicate ids, proactivity range, and that SOP files exist.