#!/usr/bin/env python
"""Validate documentation navigation and release-phase record conventions."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ACTIVE_RELEASE = DOCS / "releases" / "v2.0"
IMPLEMENTATION = ACTIVE_RELEASE / "implementation"

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PHASE_DIR_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-phase-(?P<phase>[0-5])-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
PHASE_HEADINGS = (
    "## Objective",
    "## Delivered",
    "## Files Changed",
    "## Decisions and Contract Deviations",
    "## Verification",
    "## Known Issues and Deferred Work",
    "## Handoff",
    "## Tracker Updates",
)
REQUIRED_PATHS = (
    Path("AGENTS.md"),
    Path("docs/README.md"),
    Path("docs/planning/CURRENT.md"),
    Path("docs/releases/v1.0.0/README.md"),
    Path("docs/releases/v2.0/README.md"),
    Path("docs/releases/v2.0/RELEASE_CHECKLIST_2.0.md"),
    Path("docs/releases/v2.0/implementation/PHASE_TEMPLATE.md"),
    Path("docs/product/PRODUCT.md"),
    Path("docs/product/PRODUCT.html"),
    Path("docs/product/USER_GUIDE.md"),
    Path("docs/product/USER_GUIDE.html"),
)
OBSOLETE_PATHS = (
    Path("docs/planning/upcoming"),
    Path("docs/planning/shipped"),
)


def markdown_files(root: Path) -> list[Path]:
    """Return Markdown documents whose local links form the docs navigation graph."""
    files = list((root / "docs").rglob("*.md"))
    files.extend(path for path in (root / "README.md", root / "AGENTS.md") if path.exists())
    return sorted(files)


def check_links(root: Path, files: list[Path] | None = None) -> list[str]:
    """Return errors for local Markdown links whose targets do not exist."""
    errors: list[str] = []
    for source in files or markdown_files(root):
        text = source.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw_target = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            if not raw_target or raw_target.startswith("#"):
                continue
            parsed = urlsplit(raw_target)
            if parsed.scheme or parsed.netloc:
                continue
            target_text = unquote(parsed.path)
            if not target_text:
                continue
            target = (source.parent / target_text).resolve()
            if not target.exists():
                relative_source = source.relative_to(root).as_posix()
                errors.append(f"{relative_source}: missing link target {target_text}")
    return errors


def check_phase_records(root: Path) -> list[str]:
    """Return errors for malformed or incomplete Release 2.0 phase records."""
    implementation = root / "docs" / "releases" / "v2.0" / "implementation"
    if not implementation.is_dir():
        return ["missing Release 2.0 implementation directory"]

    errors: list[str] = []
    phases: dict[str, str] = {}
    for phase_dir in sorted(path for path in implementation.iterdir() if path.is_dir()):
        match = PHASE_DIR_RE.fullmatch(phase_dir.name)
        if not match:
            errors.append(f"invalid phase directory name: {phase_dir.name}")
            continue
        try:
            date.fromisoformat(match.group("date"))
        except ValueError:
            errors.append(f"invalid phase start date: {phase_dir.name}")

        phase = match.group("phase")
        if phase in phases:
            errors.append(
                f"duplicate Phase {phase} records: {phases[phase]} and {phase_dir.name}"
            )
        else:
            phases[phase] = phase_dir.name

        record = phase_dir / "README.md"
        if not record.is_file():
            errors.append(f"missing phase README: {phase_dir.name}/README.md")
            continue
        text = record.read_text(encoding="utf-8")
        for heading in PHASE_HEADINGS:
            if heading not in text:
                errors.append(f"{phase_dir.name}/README.md: missing heading {heading}")
    return errors


def check_structure(root: Path) -> list[str]:
    """Return errors for missing indexes, obsolete folders, or dated release names."""
    errors = [f"missing required path: {path.as_posix()}" for path in REQUIRED_PATHS if not (root / path).exists()]
    errors.extend(
        f"obsolete documentation path still exists: {path.as_posix()}"
        for path in OBSOLETE_PATHS
        if (root / path).exists()
    )

    releases = root / "docs" / "releases"
    if releases.is_dir():
        dated_release = re.compile(r"^\d{4}-\d{2}-\d{2}-")
        errors.extend(
            f"release folder must be undated: {path.name}"
            for path in releases.iterdir()
            if path.is_dir() and dated_release.match(path.name)
        )

    current = root / "docs" / "planning" / "CURRENT.md"
    if current.is_file():
        text = current.read_text(encoding="utf-8")
        for marker in ("**Release:**", "**Current phase:**", "**Next task:**", "**Blockers:**"):
            if marker not in text:
                errors.append(f"docs/planning/CURRENT.md: missing marker {marker}")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    """Run all documentation validations and return errors."""
    return check_structure(root) + check_phase_records(root) + check_links(root)


def main() -> int:
    errors = validate()
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Documentation structure and links are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
