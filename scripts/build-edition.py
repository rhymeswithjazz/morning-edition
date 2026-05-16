#!/usr/bin/env python3
"""
Renders a Morning Edition HTML magazine from a curated JSON file.

Usage:
    python3 scripts/build-edition.py magazines/2026-04-16.json

Input: a JSON file with date and 20 curated stories.
Output: magazines/YYYY-MM-DD.html alongside the JSON.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent.parent


def render_story(story, index, source):
    """Render a single story article. `source` is "hn" or "pb"."""
    e = escape
    num = f"{index + 1:02d}"
    headline = e(story["title"])
    url = e(story["url"])
    blurb = e(story["blurb"])
    byline = e(story.get("byline", ""))
    category = e(story["category"])
    applies = bool(story.get("applies"))

    applies_html = '<span class="applies">Applies to you</span>' if applies else ""
    classes = "story applies" if applies else "story"

    hn_link_html = ""
    if story.get("hn_link"):
        hn_link_html = f'<a href="{e(story["hn_link"])}">HN discussion</a>'

    return f"""
  <article class="{classes}" id="s{index + 1}" data-source="{source}">
    <div class="topline">
      <span class="num">No.&nbsp;{num}</span><span class="cat">{category}</span>{applies_html}
    </div>
    <h3><a href="{url}">{headline}</a></h3>
    <div class="byline">{byline}</div>
    <p class="blurb">{blurb}</p>
    <div class="links">
      <a href="{url}">Read article</a>
      {hn_link_html}
    </div>
  </article>"""


def render_toc(stories):
    """Render the at-a-glance contents list."""
    items = []
    for i, s in enumerate(stories):
        title = escape(s["title"])
        items.append(f'      <li><a href="#s{i + 1}">{title}</a></li>')
    return "\n".join(items)


def render_magazine(data):
    """Render the full HTML magazine from structured data."""
    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A")
    month_day_year = dt.strftime("%B %-d, %Y")

    stories = data["stories"]
    hn_stories = stories[:10]
    pb_stories = stories[10:20]

    hn_html = "".join(render_story(s, i, "hn") for i, s in enumerate(hn_stories))
    pb_html = "".join(render_story(s, i + 10, "pb") for i, s in enumerate(pb_stories))
    toc_html = render_toc(stories)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Edition — {month_day_year}</title>
<meta name="description" content="20 curated stories from Hacker News + Pinboard Popular for {month_day_year}.">
<meta property="og:title" content="Morning Edition — {month_day_year}">
<meta property="og:description" content="20 curated stories from Hacker News + Pinboard Popular">
<meta property="og:type" content="article">
<meta property="og:url" content="https://daily.rhymeswithjazz.com/magazines/{date_str}.html">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="alternate" type="application/rss+xml" title="Morning Edition RSS" href="https://daily.rhymeswithjazz.com/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..900;1,9..144,400..900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
  :root {{
    --bg: #fbf8f1;
    --ink: #1a1a17;
    --muted: #6e695e;
    --rule: #d9d2c1;
    --accent: #8a3a1a;
    --applies-bg: #faecd0;
    --applies-ink: #6a3e00;
  }}
  html {{ font-size: 17px; -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--ink);
    font-family: 'Inter', system-ui, sans-serif;
    line-height: 1.6;
    font-feature-settings: "kern" 1, "liga" 1;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: inherit; }}

  .page {{
    max-width: 38rem;
    margin: 0 auto;
    padding: 1.25rem 1.25rem 4rem;
  }}

  /* Masthead */
  .masthead {{
    padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--ink);
    margin-bottom: 2rem;
  }}
  .masthead .kicker {{
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }}
  .masthead h1 {{
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 800;
    font-size: 2rem;
    line-height: 1;
    letter-spacing: -0.025em;
  }}
  .masthead h1 em {{ font-style: italic; font-weight: 700; }}
  .masthead .sub {{
    color: var(--muted);
    font-size: 0.92rem;
    margin-top: 0.65rem;
    line-height: 1.5;
  }}

  /* Table of contents */
  .toc {{
    background: #f3eedf;
    border: 1px solid var(--rule);
    padding: 1rem 1.1rem;
    margin-bottom: 2.25rem;
    border-radius: 4px;
  }}
  .toc h2 {{
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.6rem;
  }}
  .toc ol {{ list-style: none; counter-reset: tocnum; }}
  .toc li {{
    counter-increment: tocnum;
    padding: 0.32rem 0;
    border-bottom: 1px dotted var(--rule);
    font-size: 0.92rem;
    line-height: 1.4;
    display: flex;
    gap: 0.65rem;
    align-items: baseline;
  }}
  .toc li:last-child {{ border-bottom: none; }}
  .toc li::before {{
    content: counter(tocnum, decimal-leading-zero);
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    font-size: 0.78rem;
    flex-shrink: 0;
    min-width: 1.5rem;
  }}
  .toc li a {{ color: var(--ink); text-decoration: none; }}
  .toc li a:hover {{ color: var(--accent); }}

  /* Section heading */
  .section {{
    margin: 2.5rem 0 1.5rem;
    text-align: center;
  }}
  .section .rule {{ display: flex; align-items: center; gap: 0.85rem; }}
  .section .rule::before, .section .rule::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--ink);
  }}
  .section h2 {{
    font-family: 'Fraunces', Georgia, serif;
    font-style: italic;
    font-weight: 600;
    font-size: 1.05rem;
    letter-spacing: 0.01em;
    color: var(--ink);
    white-space: nowrap;
  }}
  .section .count {{
    display: block;
    margin-top: 0.4rem;
    font-size: 0.7rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
  }}

  /* Story */
  .story {{
    padding-bottom: 2rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid var(--rule);
    scroll-margin-top: 1rem;
  }}
  .story:last-of-type,
  .story:has(+ .section) {{ border-bottom: none; }}

  .story .topline {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.75rem;
    font-size: 0.7rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.65rem;
  }}
  .story .num {{
    color: var(--accent);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }}
  .story .cat {{ color: var(--accent); font-weight: 600; }}
  .story .applies {{
    background: var(--applies-bg);
    color: var(--applies-ink);
    padding: 2px 7px;
    border-radius: 3px;
    letter-spacing: 0.14em;
    font-weight: 600;
  }}

  .story h3 {{
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 700;
    font-size: 1.45rem;
    line-height: 1.15;
    letter-spacing: -0.015em;
    margin-bottom: 0.6rem;
  }}
  .story h3 a {{ text-decoration: none; color: var(--ink); }}
  .story h3 a:hover {{ color: var(--accent); }}

  .story .byline {{
    font-size: 0.88rem;
    color: var(--muted);
    margin-bottom: 0.85rem;
    font-style: italic;
  }}

  .story .blurb {{
    font-size: 1.02rem;
    line-height: 1.65;
    color: var(--ink);
    margin-bottom: 0.95rem;
  }}

  .story .links {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem 1.25rem;
    font-size: 0.82rem;
  }}
  .story .links a {{
    color: var(--accent);
    text-decoration: none;
    border-bottom: 1px solid var(--accent);
    padding-bottom: 1px;
  }}
  .story .links a:hover {{ background: var(--accent); color: var(--bg); }}

  /* Footer */
  .colophon {{
    margin-top: 3rem;
    padding-top: 1.25rem;
    border-top: 1px solid var(--ink);
    font-size: 0.78rem;
    color: var(--muted);
    line-height: 1.6;
  }}
  .colophon a {{ color: var(--accent); }}

  /* Tablet */
  @media (min-width: 640px) {{
    html {{ font-size: 18px; }}
    .page {{ padding: 2rem 1.75rem 5rem; }}
    .masthead h1 {{ font-size: 2.6rem; }}
    .story h3 {{ font-size: 1.7rem; }}
    .story .blurb {{ font-size: 1.05rem; }}
  }}

  /* Desktop */
  @media (min-width: 960px) {{
    .page {{ padding: 3rem 2rem 6rem; max-width: 40rem; }}
    .masthead h1 {{ font-size: 3rem; }}
    .story h3 {{ font-size: 1.85rem; }}
  }}
</style>
</head>
<body>
<div class="page">

  <header class="masthead">
    <div class="kicker">{day_name} · {month_day_year}</div>
    <h1>Morning <em>Edition</em></h1>
    <p class="sub">Twenty stories from Hacker News and Pinboard Popular, curated for tech-leaning readers who care about Claude Code, the Apple ecosystem, and privacy.</p>
  </header>

  <div class="toc">
    <h2>In this issue</h2>
    <ol>
{toc_html}
    </ol>
  </div>

  <div class="section">
    <div class="rule"><h2>From Hacker News</h2></div>
    <span class="count">Stories 1 – 10</span>
  </div>
{hn_html}

  <div class="section">
    <div class="rule"><h2>From Pinboard Popular</h2></div>
    <span class="count">Stories 11 – 20</span>
  </div>
{pb_html}

  <footer class="colophon">
    Morning Edition · daily.rhymeswithjazz.com<br>
    Curated by Claude · <a href="/archive/">Previous issues</a> · <a href="/feed.xml">RSS</a>
  </footer>

</div>
</body>
</html>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/build-edition.py <path-to-json>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    html = render_magazine(data)

    out_path = json_path.with_suffix(".html")
    out_path.write_text(html, encoding="utf-8")
    print(f"  {out_path.name}: {len(data['stories'])} stories rendered")


if __name__ == "__main__":
    main()
