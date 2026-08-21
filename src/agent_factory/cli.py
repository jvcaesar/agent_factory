"""Command-line interface for agent_factory.

Commands:
  bootstrap                Interactive interview -> generated org chart
  bootstrap --spec file    Same from a YAML answers file (non-interactive)
  validate --root dir      Validate a generated org tree
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .bootstrap.archetypes import DOMAIN_CHOICES, KNOWN_TOOLS
from .bootstrap.generator import generate_org, write_org
from .bootstrap.interview import AskFn, ConfirmFn, ChoiceFn, InterviewAnswers
from .config import ApprovalPolicy
from .config.loader import load_org_yaml, validate_org

RISK_CHOICES = ["autonomous", "review_external", "approval_first"]
BUDGET_CHOICES = ["small", "medium", "unlimited"]
TOOL_CHOICES = sorted(KNOWN_TOOLS)


def _def_input(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
        return val or default
    val = input(f"{prompt}: ").strip()
    return val if val else default


def _def_choice(prompt: str, options: list[str], default: str | None = None) -> str:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        raw = input("Pick number (or name): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        if raw == "" and default:
            return default
        print("  Invalid choice; try again.")


def _def_confirm(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please answer y or n.")


def _multiselect(prompt: str, options: list[str], ask: ChoiceFn) -> list[str]:
    print(f"\n{prompt} (comma-separated numbers, e.g. '1,3,5'; empty=all)")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    raw = input("> ").strip()
    if not raw:
        return list(options)
    selected: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(options):
            selected.append(options[int(part) - 1])
        elif part in options:
            selected.append(part)
    return selected
def _interactive() -> InterviewAnswers:
    ask: AskFn = _def_input
    confirm: ConfirmFn = _def_confirm
    choice: ChoiceFn = _def_choice

    org_name = ask("What should we call your workforce/company")
    founder = ask("Your name (the founder)", "Founder")
    north_star = ask("What is your north-star goal")
    print("\nGive 2-3 quarterly, measurable targets (one per line; empty line to stop):")
    goals: list[str] = []
    while len(goals) < 3:
        g = input("  target> ").strip()
        if not g:
            break
        goals.append(g)

    team = int(ask("How many humans are on the team", "0") or "0")

    domain_opts = [label for _, label in DOMAIN_CHOICES]
    chosen_labels = _multiselect("Which domains should your workforce cover first?", domain_opts, choice)
    chosen = [key for key, label in DOMAIN_CHOICES if label in chosen_labels]

    print("\nWhich tools does your organization actually use? (empty=all)")
    tool_picks = _multiselect("Tools", TOOL_CHOICES, choice)
    tools = set(tool_picks)

    risk = choice("How much human sign-off do you want?", RISK_CHOICES, "review_external")
    budget = choice("What is your model budget?", BUDGET_CHOICES, "medium")

    use_lead = confirm("Add an Org Lead (Chief of Staff) coordinator on top?", True)
    add_amp = confirm("Add an Amplifier role (pushes net-new output up a notch)?")
    add_obs = confirm("Add an Observer role (logs friction and access gaps)?")

    return InterviewAnswers(
        org_name=org_name,
        founder=founder,
        north_star=north_star,
        quarterly_goals=goals,
        human_team_size=team,
        domains=chosen,
        tools=tools,
        risk_tier=ApprovalPolicy(risk),
        budget_tier=budget,
        add_amplifier=add_amp,
        add_observer=add_obs,
        use_lead=use_lead,
    )


def _load_spec(path: Path) -> InterviewAnswers:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return InterviewAnswers.from_dict(data)


def cmd_bootstrap(args: argparse.Namespace) -> int:
    if args.spec:
        answers = _load_spec(Path(args.spec))
    else:
        answers = _interactive()

    errs = answers.validate()
    if errs:
        print("Invalid answers:", "; ".join(errs), file=sys.stderr)
        return 2

    org = generate_org(answers)
    write_org(org, args.out)
    print(f"\nGenerated org '{org.name}' at: {args.out}")
    print(f"  roles: {len(org.roles)}  "
          f"lead={answers.use_lead}  risk={org.risk_tier.value}  budget={org.budget_tier}")
    for r in org.roles:
        if r.reports_to is None:
            print(f"  top -> {r.id} ({r.title}, proactivity {r.proactivity_level})")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    org_yaml = root / "org.yaml"
    if not org_yaml.exists():
        print(f"No org.yaml found under {root}", file=sys.stderr)
        return 2
    org = load_org_yaml(org_yaml)
    errors = validate_org(org)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: {root} is a valid org ({len(org.roles)} roles).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_factory", description="Generate and manage AI agent workforces.")
    sub = parser.add_subparsers(dest="command", required=True)

    bp = sub.add_parser("bootstrap", help="Interview -> generated org chart")
    bp.add_argument("--spec", help="Load answers from a YAML spec file (non-interactive)")
    bp.add_argument("--out", default="orgs/MyOrg", help="Output directory for the generated org")
    bp.set_defaults(func=cmd_bootstrap)

    vp = sub.add_parser("validate", help="Validate a generated org tree")
    vp.add_argument("--root", default="orgs/MyOrg", help="Root directory of the org")
    vp.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

