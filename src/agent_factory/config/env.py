"""Dependency-free ``.env`` loader.

Reads ``KEY=VALUE`` lines from a dotenv file into ``os.environ`` without
overwriting variables already set in the real environment (so a shell export or
a previous file wins). Supports blank lines, ``#`` comments, inline comments
(after a value), an optional leading ``export``, and single/double-quoted
values. Simple ``$VAR`` interpolation of already-known variables is supported.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

_LINE_RE = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$"
)


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    # strip inline comment after a value (only for unquoted values)
    if not (raw.startswith("'") or raw.startswith('"')):
        raw = raw.split("#", 1)[0].strip()
    return raw


def _interpolate(value: str, environ: dict) -> str:
    def _sub(match: re.Match) -> str:
        name = match.group(1) or match.group(2) or ""
        return environ.get(name, "")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", _sub, value)


def load_dotenv(path: str | Path | None = None, *, overwrite: bool = False) -> bool:
    """Load ``KEY=VALUE`` variables from a dotenv file.

    By default this does NOT overwrite variables already in ``os.environ`` —
    pass ``overwrite=True`` to force values from the file to win.
    If ``path`` is None, the working-directory ``.env`` file is used if present.
    Returns True if a file was actually read into the environment.
    """
    dotenv = Path(path) if path is not None else Path.cwd() / ".env"
    if not dotenv.exists() or not dotenv.is_file():
        return False

    environ = dict(os.environ)
    changed = False
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        key, value_raw = match.group(1), match.group(2)
        value = _unquote(value_raw)
        value = _interpolate(value, environ)
        if key in os.environ and not overwrite:
            continue  # real environment wins
        os.environ[key] = value
        environ[key] = value
        changed = True
    return changed


def env_get(*names: str) -> Optional[str]:
    """Fetch the first non-empty environment variable among ``names``.

    Checks both the given casing and its uppercase form because Windows
    normalizes environment variable names to uppercase inside ``os.environ``.
    Returns the stripped value, or None when no name matches.
    """
    for name in names:
        value = os.environ.get(name)
        if value is None:
            value = os.environ.get(name.upper())
        if value is not None and value.strip():
            return value.strip()
    return None