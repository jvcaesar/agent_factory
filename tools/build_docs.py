#!/usr/bin/env python
"""Regenerate the HTML docs from their Markdown sources.

Rebuilds docs/product/PRODUCT.html and docs/product/USER_GUIDE.html (and any
future ``*.md`` paired with a ``*.html``, anywhere under docs/) from the
matching Markdown source, so the rendered HTML can never silently drift from
the canonical Markdown.

Run with:

    python tools/build_docs.py          # rebuild all
    python tools/build_docs.py --check  # exit non-zero if a rebuild would differ (CI)

Requires the ``markdown`` package (in the ``dev`` extra).
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"

# Footer links, resolved relative to each generated file's own directory
# (docs have moved into topic subfolders — the shared shell can't hardcode
# same-directory hrefs anymore).
_FOOTER_TARGETS = {
    "user_guide": DOCS / "product" / "USER_GUIDE.html",
    "architecture": DOCS / "architecture" / "ARCHITECTURE.md",
    "roadmap": DOCS / "planning" / "ROADMAP.md",
}

# The CSS + shell shared by every generated page. Kept deliberately
# self-contained (no external CDN links) so the docs render offline.
_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
:root{{
  /* The Forge Palette (docs/product/forge_palette.md) — dark industrial theme */
  --bg:#1E2022; --bg2:#17191B; --card:#26292C; --card2:#2B2F33; --ink:#F4F5F6;
  --muted:#9BA3AE; --accent:#EAA115; --accent2:#F0C244; --cyan:#F0C244;
  --line:#33373C; --ok:#6FCF97; --warn:#EAA115; --err:#E5484D;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;
  background:radial-gradient(1200px 600px at 80% -10%,#1e1b4b 0%,transparent 60%),
             radial-gradient(900px 500px at -10% 30%,#172554 0%,transparent 55%),
             var(--bg);
  color:var(--ink);line-height:1.7;font-size:16px}}
a{{color:var(--accent);text-decoration:none}}
a:hover{{text-decoration:underline}}
code{{font-family:"Cascadia Code",Consolas,Menlo,monospace;font-size:.88em;
  background:#1c2440;color:#a5b4fc;padding:.12em .45em;border-radius:6px}}
main{{max-width:1060px;margin:0 auto;padding:0 28px 100px}}
nav.top{{position:sticky;top:0;z-index:50;background:rgba(11,15,26,.85);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
nav.top .in{{max-width:1060px;margin:0 auto;padding:12px 28px;display:flex;
  align-items:center;gap:20px;flex-wrap:wrap}}
section{{margin-top:80px}}
h1,h2,h3{{line-height:1.2}}
h1{{font-size:38px;font-weight:800;margin-bottom:10px}}
h2{{font-size:28px;font-weight:700;margin-bottom:12px}}
h3{{font-size:20px;font-weight:600;margin-bottom:8px}}
p,ul,ol{{margin-bottom:14px}}
ul,ol{{padding-left:24px}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid var(--line);padding:10px 14px;text-align:left}}
th{{background:var(--card2)}}
pre{{background:#0d1117;color:#e6edf3;border-radius:12px;padding:18px 20px;
  overflow-x:auto;margin:16px 0;font-size:.9em;line-height:1.5}}
blockquote{{border-left:3px solid var(--accent);padding-left:16px;color:var(--muted);
  margin:16px 0}}
hr{{border:none;border-top:1px solid var(--line);margin:30px 0}}
footer{{margin-top:80px;padding:28px;border-top:1px solid var(--line);
  color:var(--muted);font-size:14px;text-align:center}}
</style>
</head>
<body>
<main>
{content}
</main>
<footer>Agent Factory — open source — docs: <a href="{user_guide_href}">User Guide</a> |
<a href="{architecture_href}">Architecture</a> | <a href="{roadmap_href}">Roadmap</a> |
<a href="{md_name}">this page (markdown)</a></footer>
</body>
</html>
"""


def _title_from_md(md_text: str) -> str:
    """Pull the first H1 from the Markdown, else fall back to the filename."""
    m = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return m.group(1).strip() if m else "Agent Factory"


def build_one(md_path: Path, html_path: Path) -> str:
    """Convert a single Markdown file to its HTML representation."""
    import markdown as md

    md_text = md_path.read_text(encoding="utf-8")
    body = md.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc", "smarty", "attr_list"],
    )
    out_dir = html_path.resolve().parent
    footer_hrefs = {
        f"{name}_href": os.path.relpath(target, out_dir).replace(os.sep, "/")
        for name, target in _FOOTER_TARGETS.items()
    }
    html = _SHELL.format(
        title=_title_from_md(md_text),
        content=body,
        md_name=md_path.name,
        **footer_hrefs,
    )
    return html


def targets():
    """Yield (md, html) pairs for every Markdown that has a matching HTML."""
    for md in sorted(DOCS.rglob("*.md")):
        html = md.with_suffix(".html")
        if html.exists():
            yield md, html


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="don't write; exit non-zero if any HTML is out of date",
    )
    args = parser.parse_args()

    dirty = []
    for md, html in targets():
        rendered = build_one(md, html)
        existing = html.read_text(encoding="utf-8") if html.exists() else ""
        if rendered == existing:
            print(f"ok        {html.name}")
            continue
        dirty.append(html.name)
        if args.check:
            diff = difflib.unified_diff(
                existing.splitlines(),
                rendered.splitlines(),
                fromfile=f"{html.name} (on disk)",
                tofile=f"{html.name} (rebuilt)",
                lineterm="",
            )
            print("\n".join(diff[:40]))
        else:
            html.write_text(rendered, encoding="utf-8")
            print(f"rebuilt   {html.name}")

    if dirty:
        if args.check:
            print(f"\nFAILED: {len(dirty)} doc(s) out of date: {', '.join(dirty)}")
            print("Run `python tools/build_docs.py` to regenerate.")
            return 1
    elif not args.check:
        print("All docs up to date.")
    else:
        print("All docs up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
