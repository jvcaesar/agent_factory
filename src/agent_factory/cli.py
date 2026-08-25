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
from typing import Callable

import yaml

from .bootstrap.archetypes import DOMAIN_CHOICES, KNOWN_TOOLS
from .bootstrap.generator import generate_org, write_org
from .bootstrap.interview import AskFn, ConfirmFn, ChoiceFn, InterviewAnswers
from .config import ApprovalPolicy
from .config.loader import load_org_yaml, validate_org
from .llm import get_client
from .runtime import Store, run_job
from .runtime.ambition import run_ambition_loop

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
def _approval_policy(args) -> Callable:
    mode = args.approval
    if mode == "allow":
        return lambda _t: True
    if mode == "deny":
        return lambda _t: False
    # "ask" — prompt the user per tool call.
    from .runtime.tools import Tool

    def _ask(tool: Tool) -> bool:
        while True:
            raw = input(f"APPROVE tool call '{tool.name}'? [{tool.description}] (y/n): ").strip().lower()
            if raw in ("y", "yes"):
                return True
            if raw in ("n", "no"):
                return False
            print("  answer y or n")

    return _ask


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.org)
    org = load_org_yaml(root / "org.yaml")
    errors = validate_org(org)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    try:
        role = org.role(args.role)
    except KeyError:
        print(f"No role named {args.role!r} in this org. Available: {[r.id for r in org.roles]}", file=sys.stderr)
        return 2

    db = root / ".agentfactory" / "jobs.db"
    store = Store(db)
    try:
        llm = get_client(args.provider)
        approval_fn = _approval_policy(args)
        job_id, outcome = run_job(
            org,
            role,
            args.task,
            llm,
            store,
            root=root,
            approval_fn=approval_fn,
            max_steps=args.max_steps,
            temperature=args.temperature,
            provider=args.provider,
        )
    except Exception as exc:
        print(f"Run failed for role {role.id!r}: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()

    print(f"\njob #{job_id} [{role.id}] -> {'done' if outcome.finished else 'incomplete'} in {outcome.steps} step(s)")
    print("events:")
    for e in outcome.events:
        print(f"  {e}")
    print("--- output ---")
    print(outcome.output)
    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
    db = Path(args.org) / ".agentfactory" / "jobs.db"
    if not db.exists():
        print(f"No job store at {db}", file=sys.stderr)
        return 2
    store = Store(db)
    try:
        print(f"{'id':<4} {'org':<14} {'role':<24} {'status':<9} {'task'}")
        for j in store.list_jobs(status=args.status, limit=args.limit):
            print(f"{j['id']:<4} {j['org']:<14} {j['role']:<24} {j['status']:<9} {j['task'][:60]}")
        return 0
    finally:
        store.close()

def cmd_ambition(args: argparse.Namespace) -> int:
    root = Path(args.org)
    org = load_org_yaml(root / "org.yaml")
    errors = validate_org(org)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    role_id = args.role or next(
        (r.id for r in org.roles if r.reports_to is None), None
    )
    if role_id is None:
        print("No lead role found and --role not given.", file=sys.stderr)
        return 2
    role = org.role(role_id)
    if role.proactivity_level < 3:
        print(f"Role {role_id!r} has proactivity_level {role.proactivity_level} < 3; it cannot initiate work.", file=sys.stderr)
        return 2

    db = root / ".agentfactory" / "jobs.db"
    store = Store(db)
    try:
        llm = get_client(args.provider)
        approval_fn = _approval_policy(args)
        proposals, executed = run_ambition_loop(
            org,
            role,
            llm,
            store,
            root=root,
            approval_fn=approval_fn,
            max_candidates=args.candidates,
            max_actions=args.max_actions,
            max_risk=args.max_risk,
        )
    except Exception as exc:
        print(f"Ambition loop failed for role {role.id!r}: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()

    print(f"\nProposals from {role.id} (proactivity {role.proactivity_level}):")
    for p in proposals:
        print(f"  - {p.title} (risk={p.risk}, priority={p.priority})")
        print(f"      action: {p.action}")
    print(f"\nExecuted {len(executed)} action(s):")
    for proposal, outcome, job_id in executed:
        print(f"  job #{job_id} [{proposal.title}] -> {'done' if outcome.finished else 'incomplete'}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    root = Path(args.org)
    db = root / ".agentfactory" / "jobs.db"
    if not db.exists() and not args.add:
        print(f"No job store at {db}", file=sys.stderr)
        return 2
    store = Store(db)  # Store creates the DB if missing
    try:
        if args.add:
            store.upsert_context(args.add, args.detail, source="diary")
            print(f"added context entry '{args.add}'")
            return 0
        if args.search:
            rows = store.search_context(args.search)
        else:
            rows = store.list_context(limit=args.limit)
        print(f"{'key':<36} {'source':<10} content")
        for r in rows:
            snippet = (r["content"] or "").replace("\n", " ")
            print(f"{r['key']:<36} {r['source'] or '':<10} {snippet[:70]}")
        return 0
    finally:
        store.close()







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

    rp = sub.add_parser("run", help="Enqueue a job and run it with a configured role")
    rp.add_argument("--org", required=True, help="Path to a generated org tree (contains org.yaml)")
    rp.add_argument("--role", required=True, help="Role id to execute the job, e.g. worker_research_1")
    rp.add_argument("--task", required=True, help="The task/job description")
    rp.add_argument("--provider", default=None, help="openai | ollama | fake (default: env or openai)")
    rp.add_argument("--approval", choices=["ask", "deny", "allow"], default="ask")
    rp.add_argument("--max-steps", type=int, default=8)
    rp.add_argument("--temperature", type=float, default=0.2)
    rp.set_defaults(func=cmd_run)

    jp = sub.add_parser("jobs", help="List jobs recorded in an org's store")
    jp.add_argument("--org", required=True, help="Path to a generated org tree")
    jp.add_argument("--status", default=None, help="Filter: queued|running|done|error|blocked")
    jp.add_argument("--limit", type=int, default=100)
    jp.set_defaults(func=cmd_jobs)

    ap = sub.add_parser("ambition", help="Run the proactive 'do smart things' loop for a role")
    ap.add_argument("--org", required=True, help="Path to a generated org tree")
    ap.add_argument("--role", default=None, help="Role id to run the loop (default: org lead)")
    ap.add_argument("--provider", default=None, help="openai | ollama | fake")
    ap.add_argument("--approval", choices=["ask", "deny", "allow"], default="deny")
    ap.add_argument("--candidates", type=int, default=5)
    ap.add_argument("--max-actions", type=int, default=2)
    ap.add_argument("--max-risk", choices=["low", "medium", "high"], default="medium")
    ap.set_defaults(func=cmd_ambition)

    cp = sub.add_parser("context", help="Add / list / search captured context (diary flow)")
    cp.add_argument("--org", required=True, help="Path to a generated org tree")
    cp.add_argument("--add", default=None, help="Key to add an entry (with --detail)")
    cp.add_argument("--detail", default="", help="Content of the entry when using --add")
    cp.add_argument("--search", default=None, help="Search term")
    cp.add_argument("--limit", type=int, default=50)
    cp.set_defaults(func=cmd_context)


    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

