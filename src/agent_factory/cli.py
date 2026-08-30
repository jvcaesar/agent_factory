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
from .config.env import env_get, load_dotenv
from .config.loader import ConfigError, load_org_yaml, validate_org
from .llm import client_for_role
from .runtime import Store, run_job
from .runtime.ambition import run_ambition_loop
from .runtime.insights import build_daily_brief, observe

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


def _multiselect(prompt: str, options: list[str]) -> list[str]:
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
    chosen_labels = _multiselect("Which domains should your workforce cover first?", domain_opts)
    chosen = [key for key, label in DOMAIN_CHOICES if label in chosen_labels]

    print("\nWhich tools does your organization actually use? (empty=all)")
    tool_picks = _multiselect("Tools", TOOL_CHOICES)
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
    if args.pack and args.spec:
        print("--pack and --spec are mutually exclusive.", file=sys.stderr)
        return 2

    pack = None
    if args.pack:
        from .packs import build_answers, get_pack, overridden_archetypes

        try:
            pack = get_pack(args.pack)
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 2
        answers = build_answers(
            pack,
            org_name=args.org_name,
            founder=args.founder,
            north_star=args.north_star,
        )
    elif args.spec:
        answers = _load_spec(Path(args.spec))
    else:
        answers = _interactive()

    errs = answers.validate()
    if errs:
        print("Invalid answers:", "; ".join(errs), file=sys.stderr)
        return 2

    if pack is not None:
        directors, workers, addons = overridden_archetypes(pack)
        org = generate_org(answers, directors=directors, workers=workers, addons=addons)
    else:
        org = generate_org(answers)
    write_org(org, args.out)
    print(f"\nGenerated org '{org.name}' at: {args.out}")
    if pack is not None:
        print(f"  pack: {pack.id}")
    print(f"  roles: {len(org.roles)}  "
          f"lead={answers.use_lead}  risk={org.risk_tier.value}  budget={org.budget_tier}")
    for r in org.roles:
        if r.reports_to is None:
            print(f"  top -> {r.id} ({r.title}, proactivity {r.proactivity_level})")
    return 0


def cmd_packs(args: argparse.Namespace) -> int:
    from .packs import get_pack, list_packs

    if args.show:
        try:
            pack = get_pack(args.show)
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 2
        print(yaml.safe_dump(pack.spec, sort_keys=False, allow_unicode=True))
        return 0
    for p in list_packs():
        print(f"{p.id:<16}{p.name:<28}{p.description}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    org_yaml = root / "org.yaml"
    if not org_yaml.exists():
        print(f"No org.yaml found under {root}", file=sys.stderr)
        return 2
    org = load_org_yaml(org_yaml)
    errors = validate_org(org, root)
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
    errors = validate_org(org, root)
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
        llm = client_for_role(
            role,
            provider_override=args.provider,
            model_override=args.model,
        )
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
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — report and exit for run
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
    errors = validate_org(org, root)
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
        # Build a per-agent client so the lead and each worker can use
        # different providers/models (from their role YAML + .env).
        role_client = lambda r: client_for_role(
            r,
            provider_override=args.provider,
            model_override=args.model,
        )
        approval_fn = _approval_policy(args)
        proposals, executed = run_ambition_loop(
            org,
            role,
            role_client(role),
            store,
            root=root,
            approval_fn=approval_fn,
            role_client=role_client,
            max_candidates=args.candidates,
            max_actions=args.max_actions,
            max_risk=args.max_risk,
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — integrity from ambition loop
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







def cmd_probe(args) -> int:
    """Ping every LLM configured via the environment and report reachability."""
    import os
    import time

    from .llm.base import ChatMessage
    from .llm.factory import get_client
    from .llm.models import (
        model_for_tier,
        resolve_default_provider,
        split_provider_model,
    )

    pairs: set[tuple[str, str]] = set()

    default_provider = resolve_default_provider()

    # Every model actually configured via generic/per-role MODEL_* env vars.
    entries = []
    for suffix in ("default", "fast", "smart", "big"):
        value = env_get(f"MODEL_{suffix}")
        if value:
            entries.append(split_provider_model(value))
    for key, value in os.environ.items():
        if not key.upper().startswith("MODEL_") or not value.strip():
            continue
        tail = key.upper()[len("MODEL_"):]
        if tail in ("DEFAULT", "FAST", "SMART", "BIG"):
            continue
        entries.append(split_provider_model(value))

    if entries:
        for prefix, model in entries:
            pairs.add((prefix or default_provider, model))
    else:
        # Nothing configured: fall back to built-in defaults of the provider.
        for tier in ("fast", "smart", "big"):
            model = model_for_tier(default_provider, tier)
            if model:
                pairs.add((default_provider, model))

    if args.only:
        pairs = {(p, m) for p, m in pairs if p == args.only}

    ordered = sorted(pairs)
    print(f"Probing {len(ordered)} configured provider/model pair(s)...\n")
    failures = 0
    for prov, model in ordered:
        started = time.time()
        try:
            client = get_client(prov, model=model)
            result = client.complete(
                [ChatMessage(role="user", content="Reply with the single word: OK.")],
                max_tokens=200,
            )
            elapsed = time.time() - started
            note = (
                " [reasoning-fallback]"
                if getattr(client, "used_reasoning_fallback", False)
                else ""
            )
            reply = result.text.strip().replace("\n", " ")[:60]
            print(f"[OK]   {prov:<7} {model:<20} {elapsed:5.1f}s{note}  -> {reply!r}")
        except Exception as exc:  # noqa: BLE001 — probe reports everything
            failures += 1
            reason = str(exc).replace("\n", " ")[:100]
            print(f"[FAIL] {prov:<7} {model:<20} -> {reason}")

    ok = len(ordered) - failures
    print(f"\n{ok}/{len(ordered)} reachable.")
    return 0 if failures == 0 else 1


def cmd_observe(args: argparse.Namespace) -> int:
    root = Path(args.org)
    org = load_org_yaml(root / "org.yaml")
    role_id = args.role or next(
        (r.id for r in org.roles if r.id == "observer"), None
    ) or next((r.id for r in org.roles if r.reports_to is None), None)
    if role_id is None:
        print("No observer/lead role found; pass --role.", file=sys.stderr)
        return 2
    role = org.role(role_id)

    db = root / ".agentfactory" / "jobs.db"
    store = Store(db)
    try:
        llm = client_for_role(role, provider_override=args.provider, model_override=args.model)
        findings = observe(org, role, store, llm, max_count=args.limit)
    except Exception as exc:  # noqa: BLE001
        print(f"Observe failed for role {role.id!r}: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()

    print(f"Observer {role.id} surfaced {len(findings)} finding(s):")
    for f in findings:
        print(f"  [{f.level}/{f.kind}] {f.title}")
        if f.detail:
            print(f"      detail: {f.detail}")
        if f.suggestion:
            print(f"      suggest: {f.suggestion}")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    root = Path(args.org)
    org = load_org_yaml(root / "org.yaml")
    role_id = args.role or next(
        (r.id for r in org.roles if r.reports_to is None), None
    )
    if role_id is None:
        print("No lead role found; pass --role.", file=sys.stderr)
        return 2
    role = org.role(role_id)

    db = root / ".agentfactory" / "jobs.db"
    store = Store(db)
    try:
        llm = client_for_role(role, provider_override=args.provider, model_override=args.model)
        brief = build_daily_brief(org, role, store, llm)
    except Exception as exc:  # noqa: BLE001
        print(f"Brief failed for role {role.id!r}: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()

    print(brief)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.org)
    org = load_org_yaml(root / "org.yaml")
    db = root / ".agentfactory" / "jobs.db"
    if not db.exists():
        print(f"No job store at {db} — run a job first.", file=sys.stderr)
        return 2
    store = Store(db)
    try:
        stats = store.stats()
        print(f"Mission control — {org.name}")
        print(f"  Jobs: {stats['jobs']} total  "
              f"(queued={stats['queued']}, running={stats['running']}, "
              f"done={stats['done']}, error={stats['error']}, blocked={stats['blocked']})")
        print(f"  Open insights: {stats['open_insights']}")

        recent_jobs = store.list_jobs(limit=args.limit)
        if recent_jobs:
            print("\n  Recent jobs:")
            for j in recent_jobs:
                print(f"    #{j['id']} [{j['role']}] {j['status']}: {j['task'][:60]}")
        else:
            print("\n  Recent jobs: none")

        open_insights = store.list_insights(status="open", limit=args.limit)
        if open_insights:
            print("\n  Open insights:")
            for i in open_insights:
                print(f"    [{i['level']}/{i['kind']}] {i['title']}")
        else:
            print("\n  Open insights: none")

        approvals = [e for e in store.recent_events(limit=200) if e["type"] == "approval"]
        if approvals:
            print(f"\n  Recent approval events: {len(approvals)}")
        else:
            print("\n  Recent approval events: none")
        return 0
    finally:
        store.close()
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="agent_factory", description="Generate and manage AI agent workforces.")
    sub = parser.add_subparsers(dest="command", required=True)

    bp = sub.add_parser("bootstrap", help="Interview -> generated org chart")
    bp.add_argument("--spec", help="Load answers from a YAML spec file (non-interactive)")
    bp.add_argument("--pack", default=None, help="Generate from a built-in role pack (business_ops|engineering|research)")
    bp.add_argument("--name", "--org-name", dest="org_name", default=None, help="Override pack org name")
    bp.add_argument("--founder", default=None, help="Override pack founder name")
    bp.add_argument("--north-star", dest="north_star", default=None, help="Override pack north star")
    bp.add_argument("--out", default="orgs/MyOrg", help="Output directory for the generated org")
    bp.set_defaults(func=cmd_bootstrap)

    pk = sub.add_parser("packs", help="List built-in role packs")
    pk.add_argument("--show", default=None, help="Print the spec YAML for a pack")
    pk.set_defaults(func=cmd_packs)

    vp = sub.add_parser("validate", help="Validate a generated org tree")
    vp.add_argument("--root", default="orgs/MyOrg", help="Root directory of the org")
    vp.set_defaults(func=cmd_validate)

    rp = sub.add_parser("run", help="Enqueue a job and run it with a configured role")
    rp.add_argument("--org", required=True, help="Path to a generated org tree (contains org.yaml)")
    rp.add_argument("--role", required=True, help="Role id to execute the job, e.g. worker_research_1")
    rp.add_argument("--task", required=True, help="The task/job description")
    rp.add_argument("--provider", default=None, help="openai | ollama | fake (default: env or openai)")
    rp.add_argument("--model", default=None, help="Override the resolved model; optional provider/model prefix")
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
    ap.add_argument("--model", default=None, help="Override the resolved model; optional provider/model prefix")
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

    prp = sub.add_parser("probe", help="Ping every LLM configured via .env and report reachability")
    prp.add_argument("--only", choices=["openai", "ollama"], default=None, help="Limit to one provider")
    prp.set_defaults(func=cmd_probe)

    op = sub.add_parser("observe", help="Run an observer to surface friction/access gaps/blockers as insights")
    op.add_argument("--org", required=True, help="Path to a generated org tree")
    op.add_argument("--role", default=None, help="Role id of the observer (default: observer or lead)")
    op.add_argument("--provider", default=None, help="openai | ollama | fake")
    op.add_argument("--model", default=None, help="Override the resolved model; optional provider/model prefix")
    op.add_argument("--limit", type=int, default=5, help="Max findings per pass")
    op.set_defaults(func=cmd_observe)

    bf = sub.add_parser("brief", help="Generate a 'what should I do today' plan from insights")
    bf.add_argument("--org", required=True, help="Path to a generated org tree")
    bf.add_argument("--role", default=None, help="Role id for the brief (default: org lead)")
    bf.add_argument("--provider", default=None, help="openai | ollama | fake")
    bf.add_argument("--model", default=None, help="Override the resolved model; optional provider/model prefix")
    bf.set_defaults(func=cmd_brief)

    st = sub.add_parser("status", help="Mission-control report for an org")
    st.add_argument("--org", required=True, help="Path to a generated org tree")
    st.add_argument("--limit", type=int, default=20)
    st.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

