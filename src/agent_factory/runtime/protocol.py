"""Shared helpers for extracting structured JSON from model responses."""

from __future__ import annotations

import json
from typing import Any

# Some local models truncate generation before closing every brace/quote of the
# action-protocol JSON. Try appending a small number of closing characters to
# salvage an otherwise-valid, merely-unterminated object.
_MAX_REPAIR_ATTEMPTS = 4


def _try_repair_truncated_object(fragment: str) -> dict[str, Any] | None:
    open_braces = fragment.count("{") - fragment.count("}")
    if open_braces <= 0 or open_braces > _MAX_REPAIR_ATTEMPTS:
        return None
    # An odd number of unescaped quotes means we're mid-string; close it first.
    if fragment.count('"') % 2:
        fragment += '"'
    fragment += "}" * open_braces
    try:
        value = json.loads(fragment)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Return the first valid JSON object in model text, if one exists."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else cleaned

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try repairing the first (outermost) candidate before considering any
        # nested object, so a truncated outer object isn't shadowed by a
        # complete-looking inner one (e.g. a finished "tool_input" sub-object).
        first_brace = cleaned.find("{")
        if first_brace != -1:
            repaired = _try_repair_truncated_object(cleaned[first_brace:])
            if repaired is not None:
                return repaired

        decoder = json.JSONDecoder()
        for index, character in enumerate(cleaned):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(cleaned[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return None
    return value if isinstance(value, dict) else None

