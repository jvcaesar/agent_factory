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
import html
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
<meta name="theme-color" content="#17191B">
<title>{title}</title>
<style>
:root{{
  /* The Forge Palette (docs/product/forge_palette.md) — dark industrial theme */
    --bg:#1E2022; --bg2:#17191B; --card:#26292C; --card2:#2B2F33; --ink:#F4F5F6;
    --muted:#9BA3AE; --accent:#EAA115; --accent2:#F0C244; --cyan:#8ED1C2;
    --line:#3B4045; --ok:#6FCF97; --warn:#EAA115; --err:#E5484D;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth;scroll-padding-top:92px}}
body{{font-family:"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;
    background:var(--bg);color:var(--ink);line-height:1.7;font-size:16px}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;opacity:.18;
    background-image:linear-gradient(var(--line) 1px,transparent 1px),
        linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:48px 48px;
    mask-image:linear-gradient(to bottom,#000,transparent 70%);z-index:-1}}
a{{color:var(--accent2);text-decoration:none;transition:color .2s ease}}
a:hover{{color:#fff;text-decoration:underline}}
code{{font-family:"Cascadia Code",Consolas,Menlo,monospace;font-size:.88em;
    background:#151719;color:#F0C244;padding:.12em .45em;border-radius:4px}}
.progress{{position:fixed;top:0;left:0;width:100%;height:3px;background:transparent;z-index:100}}
.progress span{{display:block;width:0;height:100%;background:var(--accent2);box-shadow:0 0 12px var(--accent)}}
.top{{position:sticky;top:0;z-index:50;background:rgba(23,25,27,.94);
    backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}}
.top-in{{max-width:1240px;margin:0 auto;padding:14px 28px;display:flex;
    align-items:center;justify-content:space-between;gap:24px}}
.brand{{display:flex;align-items:center;gap:12px;color:var(--ink);font-weight:700;letter-spacing:.04em}}
.brand:hover{{text-decoration:none;color:var(--accent2)}}
.brand-mark{{width:30px;height:30px;border:2px solid var(--accent);display:grid;
    place-items:center;color:var(--accent);font-size:13px;transform:rotate(45deg)}}
.brand-mark span{{transform:rotate(-45deg)}}
.top-links{{display:flex;gap:18px;font-size:14px;align-items:center}}
.top-links a{{color:var(--muted)}}
.top-links a:hover{{color:var(--accent2)}}
.layout{{max-width:1240px;margin:0 auto;display:grid;grid-template-columns:230px minmax(0,860px);
    gap:48px;padding:42px 28px 100px}}
.sidebar{{position:sticky;top:88px;height:max-content;max-height:calc(100vh - 110px);overflow:auto;
    border-left:2px solid var(--line);padding:8px 0 0 18px}}
.sidebar-label{{color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;margin-bottom:12px}}
.sidebar a{{display:block;color:var(--muted);font-size:13px;line-height:1.4;padding:7px 0}}
.sidebar a:hover{{color:var(--ink);text-decoration:none;transform:translateX(3px)}}
.content{{min-width:0;animation:rise .55s ease both}}
.hero{{border-bottom:1px solid var(--line);padding:8px 0 34px;margin-bottom:42px;position:relative}}
.hero::after{{content:"";position:absolute;right:0;bottom:-1px;width:100px;height:3px;background:var(--accent)}}
.eyebrow{{color:var(--accent);font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;margin-bottom:12px}}
h1,h2,h3{{line-height:1.2;scroll-margin-top:100px}}
h1{{font-size:clamp(34px,5vw,56px);font-weight:800;letter-spacing:-.02em;margin-bottom:10px}}
h2{{font-size:30px;font-weight:700;margin:54px 0 14px;padding-top:12px;border-top:1px solid var(--line)}}
h3{{font-size:20px;font-weight:600;margin:30px 0 8px;color:var(--accent2)}}
p,ul,ol{{margin-bottom:14px}}
ul,ol{{padding-left:24px}}
table{{border-collapse:collapse;width:100%;margin:22px 0;display:block;overflow-x:auto}}
th,td{{border:1px solid var(--line);padding:11px 14px;text-align:left;min-width:130px}}
th{{background:var(--card2);color:var(--accent2)}}
tr{{transition:background .2s ease}}
tr:hover{{background:rgba(234,161,21,.08)}}
pre{{position:relative;background:#111315;color:#e6edf3;border:1px solid var(--line);
    border-radius:6px;padding:20px;overflow-x:auto;margin:20px 0;font-size:.9em;line-height:1.55}}
.copy{{position:absolute;top:9px;right:9px;border:1px solid var(--line);background:var(--card2);
    color:var(--muted);border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer}}
.copy:hover{{color:var(--ink);border-color:var(--accent)}}
blockquote{{border-left:3px solid var(--accent);background:rgba(234,161,21,.08);padding:14px 18px;color:var(--muted);
    margin:20px 0;border-radius:0 5px 5px 0}}
hr{{border:none;border-top:1px solid var(--line);margin:30px 0}}
footer{{margin-top:80px;padding:28px;border-top:1px solid var(--line);
  color:var(--muted);font-size:14px;text-align:center}}
@keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
@media (max-width:820px){{
    .layout{{display:block;padding:30px 20px 72px}}
    .sidebar{{position:relative;top:auto;max-height:none;overflow:visible;border-left:0;border-bottom:1px solid var(--line);padding:0 0 14px;margin-bottom:30px;display:flex;gap:12px;overflow-x:auto}}
    .sidebar-label{{display:none}}
    .sidebar a{{white-space:nowrap;padding:4px 0}}
    .top-in{{padding:12px 20px}}
    .top-links a:nth-child(n+2){{display:none}}
}}
@media (prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;animation:none!important;transition:none!important}}}}
</style>
</head>
<body>
<div class="progress"><span id="progress-bar"></span></div>
<header class="top"><div class="top-in">
    <a class="brand" href="{user_guide_href}"><span class="brand-mark"><span>AF</span></span> AGENT FACTORY</a>
    <nav class="top-links"><a href="{user_guide_href}">Guide</a><a href="{architecture_href}">Architecture</a><a href="{roadmap_href}">Roadmap</a></nav>
</div></header>
<div class="layout">
<aside class="sidebar"><div class="sidebar-label">On this page</div>{nav}</aside>
<main class="content"><div class="hero"><div class="eyebrow">Agent Factory / documentation</div><h1>{title}</h1></div>{content}</main>
</div>
<footer>Agent Factory — open source — docs: <a href="{user_guide_href}">User Guide</a> |
<a href="{architecture_href}">Architecture</a> | <a href="{roadmap_href}">Roadmap</a> |
<a href="{md_name}">this page (markdown)</a></footer>
<script>
const bar=document.getElementById('progress-bar');
const updateProgress=()=>{{const max=document.documentElement.scrollHeight-innerHeight;bar.style.width=(max>0?(scrollY/max)*100:0)+'%';}};
addEventListener('scroll',updateProgress,{{passive:true}}); updateProgress();
document.querySelectorAll('pre').forEach((block)=>{{
    const button=document.createElement('button');button.className='copy';button.textContent='Copy';
    button.addEventListener('click',async()=>{{try{{const code=block.querySelector('code');await navigator.clipboard.writeText((code?code.innerText:block.innerText).trim());button.textContent='Copied';setTimeout(()=>button.textContent='Copy',1200);}}catch{{button.textContent='Select manually';}}}});
    block.appendChild(button);
}});
</script>
</body>
</html>
"""


def _title_from_md(md_text: str) -> str:
    """Pull the first H1 from the Markdown, else fall back to the filename."""
    m = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return m.group(1).strip() if m else "Agent Factory"


def _sidebar_nav(body: str) -> str:
    """Build a compact sidebar from the rendered document's h2 headings."""
    links = []
    for match in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body):
        heading = re.sub(r"<[^>]+>", "", match.group(2))
        heading = html.unescape(heading)
        if heading.lower() == "table of contents":
            continue
        links.append(f'<a href="#{match.group(1)}">{heading}</a>')
    return "".join(links) or '<span style="color:var(--muted);font-size:13px">Overview</span>'


def _remove_first_h1(body: str) -> str:
    """Keep the document title in the shared hero instead of rendering it twice."""
    return re.sub(r"<h1(?:\s[^>]*)?>.*?</h1>\s*", "", body, count=1, flags=re.DOTALL)


def build_one(md_path: Path, html_path: Path) -> str:
    """Convert a single Markdown file to its HTML representation."""
    import markdown as md

    md_text = md_path.read_text(encoding="utf-8")
    body = md.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc", "smarty", "attr_list"],
    )
    body = _remove_first_h1(body)
    out_dir = html_path.resolve().parent
    footer_hrefs = {
        f"{name}_href": os.path.relpath(target, out_dir).replace(os.sep, "/")
        for name, target in _FOOTER_TARGETS.items()
    }
    nav = _sidebar_nav(body)
    html = _SHELL.format(
        title=_title_from_md(md_text),
        content=body,
        nav=nav,
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
