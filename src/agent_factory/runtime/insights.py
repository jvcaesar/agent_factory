"""M4 — Insights: observers (watchdogs) and the daily "what to do" brief.

* **Observer/watchdog** — a low-cost scan agent that looks across jobs, recent
  events (approval denials, errors), captured context, and existing insights,
  then reports friction, access gaps, contradictions, blockers, and
  opportunities in a small JSON protocol. Each finding is persisted to the
  ``insights`` store.
* **Daily brief ("insight → action")** — turns the open insights and job state
  into a concrete "what to do today" plan that routes actions to roles and
  names first steps. Not a dashboard: it says *what to do next*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import Org, Role
from ..llm.base import ChatMessage, LLMClient
from .protocol import extract_json_object
from .state import Store

VALID_LEVELS = ("info", "low", "warning", "critical")
VALID_KINDS = ("friction", "access_gap", "contradiction", "blocker", "opportunity")
VALID_INSIGHT_STATUSES = ("open", "accepted", "dismissed")


def _sanitize_prompt_text(value: str | None, *, limit: int = 4000) -> str:
    """Normalize text before injecting it into an LLM prompt."""
    if value is None:
        return "(none yet)"
    text = str(value).replace("\x00", "")
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text or "(none yet)"


@dataclass
class Observation:
    level: str
    kind: str
    title: str
    detail: str = ""
    suggestion: str = ""

    def slug(self) -> str:
        fingerprint = "|".join(
            part.strip() for part in (self.kind, self.title, self.detail, self.suggestion)
        )
        s = re.sub(r"[^a-z0-9]+", "-", fingerprint.lower()).strip("-")
        return s[:96] or "insight"


def _norm(value: str, allowed: tuple[str, ...], default: str) -> str:
    value = (value or default).strip().lower()
    return value if value in allowed else default


def parse_observations(text: str, max_count: int | None = None) -> list[Observation]:
    """Parse an observer response into a list of :class:`Observation`."""
    data = extract_json_object(text)
    if not data:
        return []
    raw = data.get("observations", [])
    if not isinstance(raw, list):
        return []
    results = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        results.append(
            Observation(
                level=_norm(str(item.get("level", "info")), VALID_LEVELS, "info"),
                kind=_norm(str(item.get("kind", "friction")), VALID_KINDS, "friction"),
                title=title,
                detail=str(item.get("detail", "")).strip(),
                suggestion=str(item.get("suggestion", "")).strip(),
            )
        )
    return results[:max_count] if max_count is not None else results


def _state_summary(store: Store) -> str:
    """A compact, prompt-friendly snapshot of jobs/events/insights."""
    stats = store.stats()
    lines = [
        f"Job counts: {stats['jobs']} total "
        f"(queued={stats['queued']}, running={stats['running']}, "
        f"done={stats['done']}, error={stats['error']}, blocked={stats['blocked']}).",
        f"Open insights: {stats['open_insights']}.",
    ]
    recent = store.list_jobs(limit=10)
    if recent:
        lines.append("Recent jobs:")
        for j in recent:
            tail = f" — {j['error'][:80]}" if j["error"] else ""
            lines.append(f"  #{j['id']} [{j['role']}] {j['status']}: {j['task'][:60]}{tail}")
    denials = [e for e in store.recent_events(limit=200) if e["type"] == "approval"]
    if denials:
        lines.append(f"Recent approval denials: {len(denials)} "
                     f"(last: {denials[-1]['detail'][:80]}).")
    return "\n".join(lines)


def _observe_prompt(org: Org, role: Role, summary: str, context_text: str, max_count: int) -> str:
    template = (
        "You are the {role_title} (role `{role_id}`) in the workforce {org_name}.\n"
        "Your job is to WATCH and surface actionable findings - not to do the work.\n"
        "\n"
        "NORTH STAR: {north_star}\n"
        "\n"
        "STATE OF THE WORKFORCE\n"
        "{summary}\n"
        "\n"
        "CAPTURED CONTEXT (diary / prior results)\n"
        "{context_text}\n"
        "\n"
        "FIND WHAT\n"
        "- friction = repeated work, stuck jobs;\n"
        "- access_gap = a role needs a tool it does not have;\n"
        "- blocker = a job or process is stuck and needs a human or fixer;\n"
        "- contradiction = two pieces of context/goals now conflict;\n"
        "- opportunity = a clear next step that advances a quarterly target.\n"
        "\n"
        "Be concrete and specific. Report up to {max_count} findings, ordered by impact.\n"
        "\n"
        "Respond with EXACTLY ONE JSON object and no other prose:\n"
        '{{"type": "observations", "observations": ['
        '{{"level": "info|low|warning|critical", "kind": "friction|access_gap|'
        'contradiction|blocker|opportunity", "title": "<short title>", '
        '"detail": "<what you found>", "suggestion": "<what to do about it>"}}]}}'
    )
    return template.format(
        role_title=role.title,
        role_id=role.id,
        org_name=org.name,
        north_star=org.north_star,
        summary=summary,
        context_text=context_text or "(none yet)",
        max_count=max_count,
    )
def observe(
    org: Org,
    role: Role,
    store: Store,
    llm: LLMClient,
    *,
    temperature: float = 0.2,
    max_count: int = 5,
) -> list[Observation]:
    """Run one observer pass: scan state, parse findings, and persist insights."""
    summary = _sanitize_prompt_text(_state_summary(store))
    context_text = _sanitize_prompt_text(store.context_blob())
    messages = [ChatMessage("user", _observe_prompt(org, role, summary, context_text, max_count))]
    result = llm.complete(messages, temperature=temperature)
    observations = parse_observations(result.text, max_count=max_count)
    seen: set[str] = set()
    for obs in observations:
        key = obs.slug()
        if key in seen:
            continue
        seen.add(key)
        store.add_insight(
            org.name,
            role.id,
            level=obs.level,
            kind=obs.kind,
            title=obs.title,
            detail=obs.detail,
            suggestion=obs.suggestion,
        )
    return observations


def _brief_prompt(org: Org, role: Role, summary: str, open_insights: list, context_text: str) -> str:
    rows = []
    for i in open_insights:
        rows.append(
            f"- [{i['level']}/{i['kind']}] {i['title']}. "
            f"({i['detail'] or 'no detail'}) Suggestion: {i['suggestion'] or '--'}"
        )
    insight_block = "\n".join(rows) or "- (no open insights)"
    template = (
        "You are {role_title} (role `{role_id}`) acting as the founder's "
        "morning brief for the workforce \"{org_name}\".\n"
        "\n"
        "STATE OF THE WORKFORCE\n"
        "{summary}\n"
        "\n"
        "OPEN INSIGHTS\n"
        "{insight_block}\n"
        "\n"
        "CAPTURED CONTEXT\n"
        "{context_text}\n"
        "\n"
        "Produce a short, prioritized \"what should I do today\" plan that "
        "turns the insights into ACTION (not a dashboard). For each top "
        "priority item, say:\n"
        "  * WHAT (one actionable step),\n"
        "  * WHO (which role or the human), and\n"
        "  * FIRST STEP (a concrete next action).\n"
        "\n"
        "Be specific and concise. Plain text is fine."
    )
    return template.format(
        role_title=role.title,
        role_id=role.id,
        org_name=org.name,
        summary=summary,
        insight_block=insight_block,
        context_text=context_text or "(none yet)",
    )


def build_daily_brief(
    org: Org,
    role: Role,
    store: Store,
    llm: LLMClient,
    *,
    temperature: float = 0.2,
) -> str:
    """Generate a "what to do today" brief from open insights + state."""
    open_items = store.list_insights(status="open", limit=20)
    summary = _sanitize_prompt_text(_state_summary(store))
    context_text = _sanitize_prompt_text(store.context_blob())
    prompt = _brief_prompt(org, role, summary, open_items, context_text)
    result = llm.complete([ChatMessage("user", prompt)], temperature=temperature)
    return result.text.strip()
