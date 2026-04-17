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

# ── Spread style definitions ──

HN_STYLES = [
    {"class": "spread-hero", "name": "HERO"},
    {"class": "spread-midnight", "name": "MIDNIGHT"},
    {"class": "spread-rose", "name": "ROSE ALERT"},
    {"class": "spread-terminal", "name": "TERMINAL"},
    {"class": "spread-academic", "name": "ACADEMIC"},
    {"class": "spread-electric", "name": "ELECTRIC BLUE"},
    {"class": "spread-apple", "name": "APPLE"},
    {"class": "spread-newsprint", "name": "NEWSPRINT"},
    {"class": "spread-gradient", "name": "GRADIENT"},
    {"class": "spread-bigstat", "name": "BIG-STAT"},
]

PB_STYLES = [
    {"class": "spread-cork", "name": "CORK BOARD"},
    {"class": "spread-teal", "name": "DEEP TEAL"},
    {"class": "spread-blueprint", "name": "BLUEPRINT"},
    {"class": "spread-sakura", "name": "SAKURA"},
    {"class": "spread-obsidian", "name": "OBSIDIAN"},
    {"class": "spread-copper", "name": "COPPER"},
    {"class": "spread-forest", "name": "FOREST"},
    {"class": "spread-graph", "name": "GRAPH PAPER"},
    {"class": "spread-infrared", "name": "INFRARED"},
    {"class": "spread-frosted", "name": "FROSTED"},
]


def render_spread(story, index, style, is_pinboard):
    """Render a single story spread section."""
    num = f"{index + 1:02d}"
    e = escape

    category_tag = f'<span class="category-tag">{e(story["category"])}</span>'
    applies_tag = (
        '<span class="applies-tag">Directly Applies to You</span>'
        if story.get("applies")
        else ""
    )
    pinboard_badge = (
        '<span class="source-pinboard">Pinboard</span>' if is_pinboard else ""
    )

    byline = e(story.get("byline", ""))
    blurb = e(story["blurb"])
    headline = e(story["title"])
    url = e(story["url"])

    discuss_html = ""
    if story.get("hn_link"):
        discuss_html = (
            f'<a class="discuss-link" href="{e(story["hn_link"])}">HN Discussion →</a>'
        )

    # Big-stat style has different structure
    if style["class"] == "spread-bigstat":
        return f"""
<section class="spread {style['class']}">
  <div class="spread-inner">
    <div class="tag-row">{category_tag}{applies_tag}</div>
    <div class="stat-num">{num}</div>
    <h2>{headline}</h2>
    <div class="byline">{byline}</div>
    <p class="blurb">{blurb}</p>
    <div class="action-row"><a class="read-link" href="{url}">Read Article →</a>{discuss_html}</div>
  </div>
</section>"""

    return f"""
<section class="spread {style['class']}">
  <div class="ghost-num">{num}</div>
  <div class="spread-inner">
    <div class="tag-row">{category_tag}{applies_tag}{pinboard_badge}</div>
    <h2>{headline}</h2>
    <div class="byline">{byline}</div>
    <p class="blurb">{blurb}</p>
    <div class="action-row"><a class="read-link" href="{url}">Read Article →</a>{discuss_html}</div>
  </div>
</section>"""


def render_magazine(data):
    """Render the full HTML magazine from structured data."""
    date_str = data["date"]
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A")
    month_day_year = dt.strftime("%B %-d, %Y")
    year = dt.strftime("%Y")

    hn_stories = data["stories"][:10]
    pb_stories = data["stories"][10:20]

    # Build spread sections
    hn_spreads = ""
    for i, story in enumerate(hn_stories):
        hn_spreads += render_spread(story, i, HN_STYLES[i], False)

    pb_spreads = ""
    for i, story in enumerate(pb_stories):
        pb_spreads += render_spread(story, i + 10, PB_STYLES[i], True)

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
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,100..900;1,9..144,100..900&family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

  :root {{
    --ff-display: 'Fraunces', serif;
    --ff-body: 'Inter', sans-serif;
  }}

  html {{ font-size: 18px; scroll-behavior: smooth; }}
  body {{ font-family: var(--ff-body); line-height: 1.6; }}

  .cover {{
    min-height: 100vh;
    background: #0a0a0a;
    color: #fafaf9;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 4rem 2rem;
    text-align: center;
    position: relative;
    overflow: hidden;
  }}
  .cover::before {{
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 30% 50%, rgba(251,146,60,0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 70% 80%, rgba(139,92,246,0.06) 0%, transparent 50%);
    animation: drift 20s ease-in-out infinite alternate;
  }}
  @keyframes drift {{
    from {{ transform: translate(0, 0) rotate(0deg); }}
    to {{ transform: translate(-3%, 2%) rotate(2deg); }}
  }}
  .cover-content {{ position: relative; z-index: 1; }}
  .cover .edition-label {{
    font-family: var(--ff-body);
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #fb923c;
    margin-bottom: 2rem;
  }}
  .cover h1 {{
    font-family: var(--ff-display);
    font-size: clamp(3.5rem, 10vw, 8rem);
    font-weight: 900;
    line-height: 0.95;
    margin-bottom: 1.5rem;
    font-style: italic;
  }}
  .cover .date {{
    font-family: var(--ff-body);
    font-size: 1.2rem;
    font-weight: 300;
    color: #a8a29e;
    letter-spacing: 0.1em;
  }}
  .cover .story-count {{
    margin-top: 2rem;
    font-size: 0.85rem;
    color: #78716c;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }}
  .cover .archive-link {{
    display: inline-block;
    margin-top: 1.5rem;
    font-size: 0.85rem;
    color: #a8a29e;
    text-decoration: none;
    font-weight: 400;
    letter-spacing: 0.05em;
    transition: color 0.15s;
  }}
  .cover .archive-link:hover {{ color: #fb923c; }}

  .spread {{
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: clamp(3rem, 8vw, 6rem) clamp(2rem, 6vw, 5rem);
    position: relative;
    overflow: hidden;
  }}
  .spread-inner {{
    max-width: 48rem;
    margin: 0 auto;
    width: 100%;
    position: relative;
    z-index: 1;
  }}
  .ghost-num {{
    position: absolute;
    font-family: var(--ff-display);
    font-weight: 900;
    font-size: clamp(10rem, 30vw, 22rem);
    line-height: 1;
    opacity: 0.06;
    pointer-events: none;
    z-index: 0;
    right: 5%;
    top: 50%;
    transform: translateY(-50%);
  }}
  .tag-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin-bottom: 1.5rem;
  }}
  .action-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
    align-items: center;
  }}
  .category-tag {{
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 0.25rem 0.75rem;
    border-radius: 100px;
  }}
  .applies-tag {{
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.25rem 0.75rem;
    border-radius: 100px;
    background: #fbbf24;
    color: #1c1917;
  }}
  .spread h2 {{
    font-family: var(--ff-display);
    font-size: clamp(1.8rem, 5vw, 3rem);
    font-weight: 800;
    line-height: 1.15;
    margin-bottom: 1rem;
  }}
  .byline {{
    font-size: 0.85rem;
    margin-bottom: 1.5rem;
    opacity: 0.7;
  }}
  .blurb {{
    font-size: 1.05rem;
    line-height: 1.7;
    margin-bottom: 2rem;
    max-width: 38rem;
  }}
  .read-link {{
    display: inline-block;
    font-weight: 600;
    font-size: 0.9rem;
    text-decoration: none;
    padding: 0.6rem 1.5rem;
    border-radius: 100px;
    transition: transform 0.15s, box-shadow 0.15s;
  }}
  .read-link:hover {{ transform: translateY(-2px); }}
  .discuss-link {{
    display: inline-block;
    font-weight: 500;
    font-size: 0.85rem;
    text-decoration: none;
    opacity: 0.7;
  }}
  .discuss-link:hover {{ opacity: 1; }}
  .source-pinboard {{
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    background: rgba(255,255,255,0.1);
  }}

  .section-divider {{
    min-height: 60vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 4rem 2rem;
    background: linear-gradient(135deg, #1a1025, #0f172a);
    color: #fafaf9;
  }}
  .section-divider .emoji {{ font-size: 3rem; margin-bottom: 1.5rem; }}
  .section-divider h2 {{
    font-family: var(--ff-display);
    font-size: clamp(2.5rem, 7vw, 4.5rem);
    font-weight: 900;
    font-style: italic;
    margin-bottom: 1rem;
  }}
  .section-divider p {{
    font-size: 1.1rem;
    color: #a8a29e;
  }}

  .footer {{
    background: #0a0a0a;
    color: #57534e;
    padding: 3rem clamp(2rem, 6vw, 5rem);
    text-align: center;
    font-size: 0.85rem;
    line-height: 1.8;
  }}

  /* ── 1. HERO ── */
  .spread-hero {{ background: #fffbeb; color: #1c1917; }}
  .spread-hero .ghost-num {{ color: #fb923c; }}
  .spread-hero .category-tag {{ background: #fed7aa; color: #9a3412; }}
  .spread-hero .read-link {{ background: #fb923c; color: white; }}
  .spread-hero .discuss-link {{ color: #9a3412; }}

  /* ── 2. MIDNIGHT ── */
  .spread-midnight {{ background: #1a1025; color: #e8e0f0; }}
  .spread-midnight .ghost-num {{ color: #8b5cf6; }}
  .spread-midnight .category-tag {{ background: rgba(139,92,246,0.2); color: #c4b5fd; }}
  .spread-midnight .read-link {{ background: #8b5cf6; color: white; }}
  .spread-midnight .discuss-link {{ color: #c4b5fd; }}

  /* ── 3. ROSE ALERT ── */
  .spread-rose {{ background: #fef2f2; color: #1c1917; position: relative; }}
  .spread-rose::after {{
    content: 'ALERT';
    position: absolute;
    font-family: var(--ff-display);
    font-weight: 900;
    font-size: clamp(8rem, 25vw, 18rem);
    color: rgba(239,68,68,0.04);
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%) rotate(-12deg);
    pointer-events: none;
  }}
  .spread-rose .ghost-num {{ color: #ef4444; }}
  .spread-rose .category-tag {{ background: #fecaca; color: #991b1b; }}
  .spread-rose .read-link {{ background: #ef4444; color: white; }}
  .spread-rose .discuss-link {{ color: #991b1b; }}

  /* ── 4. TERMINAL ── */
  .spread-terminal {{ background: #0c0c0c; color: #4ade80; font-family: 'Courier New', monospace; }}
  .spread-terminal .ghost-num {{ color: #4ade80; }}
  .spread-terminal h2 {{ font-family: 'Courier New', monospace; }}
  .spread-terminal .category-tag {{ background: rgba(74,222,128,0.15); color: #4ade80; border: 1px solid #4ade80; }}
  .spread-terminal .read-link {{ background: #4ade80; color: #0c0c0c; font-family: 'Courier New', monospace; }}
  .spread-terminal .discuss-link {{ color: #4ade80; }}
  .spread-terminal .blurb::after {{ content: '\u2588'; animation: blink 1s step-end infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}

  /* ── 5. ACADEMIC ── */
  .spread-academic {{ background: #f5f0e8; color: #292524; }}
  .spread-academic h2 {{ font-style: italic; }}
  .spread-academic .blurb::first-letter {{
    font-family: var(--ff-display);
    font-size: 3.5rem;
    font-weight: 900;
    float: left;
    line-height: 0.8;
    margin-right: 0.5rem;
    margin-top: 0.15rem;
    color: #78716c;
  }}
  .spread-academic .ghost-num {{ color: #a8a29e; }}
  .spread-academic .category-tag {{ background: #d6d3d1; color: #44403c; }}
  .spread-academic .read-link {{ background: #57534e; color: white; }}
  .spread-academic .discuss-link {{ color: #57534e; }}

  /* ── 6. ELECTRIC BLUE ── */
  .spread-electric {{ background: #0f172a; color: #e0f2fe; }}
  .spread-electric .ghost-num {{ color: #06b6d4; }}
  .spread-electric .category-tag {{ background: rgba(6,182,212,0.15); color: #67e8f9; }}
  .spread-electric .read-link {{ background: #06b6d4; color: #0f172a; }}
  .spread-electric .discuss-link {{ color: #67e8f9; }}

  /* ── 7. APPLE ── */
  .spread-apple {{ background: linear-gradient(180deg, #ffffff, #f5f5f7); color: #1d1d1f; }}
  .spread-apple .ghost-num {{
    background: linear-gradient(135deg, #ff3b30, #ff9500, #ffcc00, #34c759, #007aff, #5856d6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    opacity: 0.12;
  }}
  .spread-apple .category-tag {{ background: #e8e8ed; color: #1d1d1f; }}
  .spread-apple .read-link {{ background: #007aff; color: white; }}
  .spread-apple .discuss-link {{ color: #007aff; }}

  /* ── 8. NEWSPRINT ── */
  .spread-newsprint {{
    background: #fefce8;
    color: #1c1917;
    background-image: radial-gradient(circle, #d4d4d4 0.5px, transparent 0.5px);
    background-size: 12px 12px;
  }}
  .spread-newsprint h2 {{ text-transform: uppercase; letter-spacing: 0.02em; }}
  .spread-newsprint .ghost-num {{ color: #a16207; }}
  .spread-newsprint .category-tag {{ background: #fde68a; color: #92400e; }}
  .spread-newsprint .read-link {{ background: #a16207; color: white; }}
  .spread-newsprint .discuss-link {{ color: #92400e; }}

  /* ── 9. GRADIENT ── */
  .spread-gradient {{ background: linear-gradient(135deg, #fecdd3, #c4b5fd, #a78bfa); color: #1c1917; }}
  .spread-gradient .ghost-num {{ color: rgba(0,0,0,0.08); }}
  .spread-gradient .category-tag {{ background: rgba(255,255,255,0.4); color: #581c87; }}
  .spread-gradient .read-link {{ background: #7c3aed; color: white; }}
  .spread-gradient .discuss-link {{ color: #581c87; }}

  /* ── 10. BIG-STAT ── */
  .spread-bigstat {{ background: #18181b; color: #fafaf9; text-align: center; }}
  .spread-bigstat .spread-inner {{ display: flex; flex-direction: column; align-items: center; }}
  .spread-bigstat .stat-num {{
    font-family: var(--ff-display);
    font-weight: 900;
    font-size: clamp(5rem, 18vw, 12rem);
    line-height: 1;
    background: linear-gradient(135deg, #fb923c, #f43f5e, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 1.5rem;
  }}
  .spread-bigstat .category-tag {{ background: rgba(251,146,60,0.15); color: #fb923c; }}
  .spread-bigstat .read-link {{ background: linear-gradient(135deg, #fb923c, #f43f5e); color: white; }}
  .spread-bigstat .discuss-link {{ color: #fb923c; }}

  /* ── 11. CORK BOARD ── */
  .spread-cork {{
    background: #fef3c7;
    color: #1c1917;
    background-image: repeating-linear-gradient(0deg, transparent, transparent 20px, rgba(217,119,6,0.05) 20px, rgba(217,119,6,0.05) 21px),
                       repeating-linear-gradient(90deg, transparent, transparent 20px, rgba(217,119,6,0.05) 20px, rgba(217,119,6,0.05) 21px);
  }}
  .spread-cork .ghost-num {{ color: #d97706; }}
  .spread-cork .category-tag {{ background: #fde68a; color: #92400e; }}
  .spread-cork .read-link {{ background: #d97706; color: white; }}
  .spread-cork .source-pinboard {{ background: rgba(217,119,6,0.15); color: #92400e; }}

  /* ── 12. DEEP TEAL ── */
  .spread-teal {{ background: #042f2e; color: #ccfbf1; }}
  .spread-teal .ghost-num {{ color: #14b8a6; }}
  .spread-teal .category-tag {{ background: rgba(20,184,166,0.15); color: #5eead4; }}
  .spread-teal .read-link {{ background: #14b8a6; color: #042f2e; }}
  .spread-teal .source-pinboard {{ background: rgba(20,184,166,0.15); color: #5eead4; }}

  /* ── 13. BLUEPRINT ── */
  .spread-blueprint {{
    background: #172554;
    color: #dbeafe;
    background-image:
      linear-gradient(rgba(59,130,246,0.1) 1px, transparent 1px),
      linear-gradient(90deg, rgba(59,130,246,0.1) 1px, transparent 1px);
    background-size: 24px 24px;
  }}
  .spread-blueprint .ghost-num {{ color: #3b82f6; }}
  .spread-blueprint .category-tag {{ background: rgba(59,130,246,0.2); color: #93c5fd; }}
  .spread-blueprint .read-link {{ background: #3b82f6; color: white; }}
  .spread-blueprint .source-pinboard {{ background: rgba(59,130,246,0.15); color: #93c5fd; }}

  /* ── 14. SAKURA ── */
  .spread-sakura {{ background: linear-gradient(135deg, #fff1f2, #faf5ff); color: #1c1917; }}
  .spread-sakura .ghost-num {{ color: #ec4899; }}
  .spread-sakura .category-tag {{ background: #fce7f3; color: #9d174d; }}
  .spread-sakura .read-link {{ background: #ec4899; color: white; }}
  .spread-sakura .source-pinboard {{ background: rgba(236,72,153,0.1); color: #9d174d; }}

  /* ── 15. OBSIDIAN ── */
  .spread-obsidian {{ background: #1c1917; color: #e7e5e4; }}
  .spread-obsidian .ghost-num {{ color: #a855f7; }}
  .spread-obsidian h2 {{ text-shadow: 0 0 30px rgba(168,85,247,0.3); }}
  .spread-obsidian .category-tag {{ background: rgba(168,85,247,0.15); color: #c084fc; }}
  .spread-obsidian .read-link {{ background: #a855f7; color: white; }}
  .spread-obsidian .source-pinboard {{ background: rgba(168,85,247,0.15); color: #c084fc; }}

  /* ── 16. COPPER ── */
  .spread-copper {{ background: linear-gradient(180deg, #1c1917, #292524); color: #fde68a; }}
  .spread-copper .ghost-num {{ color: #d97706; }}
  .spread-copper h2 {{ color: #fbbf24; }}
  .spread-copper .category-tag {{ background: rgba(251,191,36,0.15); color: #fbbf24; }}
  .spread-copper .read-link {{ background: #d97706; color: #1c1917; }}
  .spread-copper .source-pinboard {{ background: rgba(217,119,6,0.15); color: #fbbf24; }}

  /* ── 17. FOREST ── */
  .spread-forest {{ background: #052e16; color: #dcfce7; }}
  .spread-forest .ghost-num {{ color: #22c55e; }}
  .spread-forest .category-tag {{ background: rgba(34,197,94,0.15); color: #86efac; }}
  .spread-forest .read-link {{ background: #22c55e; color: #052e16; }}
  .spread-forest .source-pinboard {{ background: rgba(34,197,94,0.15); color: #86efac; }}

  /* ── 18. GRAPH PAPER ── */
  .spread-graph {{
    background: #fafafa;
    color: #1c1917;
    background-image:
      linear-gradient(rgba(0,0,0,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,0,0,0.04) 1px, transparent 1px);
    background-size: 20px 20px;
  }}
  .spread-graph .ghost-num {{ color: #a8a29e; }}
  .spread-graph .category-tag {{ background: #e7e5e4; color: #44403c; }}
  .spread-graph .read-link {{ background: #44403c; color: white; }}
  .spread-graph .source-pinboard {{ background: rgba(0,0,0,0.06); color: #44403c; }}

  /* ── 19. INFRARED ── */
  .spread-infrared {{ background: #1a0a0a; color: #fecaca; }}
  .spread-infrared .ghost-num {{ color: #ef4444; text-shadow: 0 0 40px rgba(239,68,68,0.3); }}
  .spread-infrared h2 {{ text-shadow: 0 0 20px rgba(239,68,68,0.2); }}
  .spread-infrared .category-tag {{ background: rgba(239,68,68,0.15); color: #fca5a5; }}
  .spread-infrared .read-link {{ background: #ef4444; color: white; }}
  .spread-infrared .source-pinboard {{ background: rgba(239,68,68,0.15); color: #fca5a5; }}

  /* ── 20. FROSTED ── */
  .spread-frosted {{
    background: linear-gradient(135deg, #e2e8f0, #f1f5f9, #e2e8f0);
    color: #1e293b;
  }}
  .spread-frosted .spread-inner {{
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(20px);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.8);
    padding: 3rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.08);
  }}
  .spread-frosted .ghost-num {{ color: #94a3b8; }}
  .spread-frosted .category-tag {{ background: rgba(100,116,139,0.1); color: #475569; }}
  .spread-frosted .read-link {{ background: #475569; color: white; }}
  .spread-frosted .source-pinboard {{ background: rgba(100,116,139,0.1); color: #475569; }}

  @media (max-width: 640px) {{
    .spread {{ padding: clamp(2rem, 6vw, 4rem) 1.5rem; }}
    .ghost-num {{ font-size: clamp(6rem, 20vw, 10rem); }}
    .spread-frosted .spread-inner {{ padding: 1.5rem; }}
  }}
</style>
</head>
<body>

<section class="cover">
  <div class="cover-content">
    <div class="edition-label">Morning Edition</div>
    <h1>{dt.strftime('%B')} {dt.day},<br>{year}</h1>
    <div class="date">{day_name}</div>
    <div class="story-count">20 stories from Hacker News + Pinboard Popular</div>
    <a class="archive-link" href="/archive/">Previous Issues →</a>
  </div>
</section>

{hn_spreads}

<section class="section-divider">
  <div class="emoji">\U0001F4CC</div>
  <h2>Pinboard Picks</h2>
  <p>10 exclusives from Pinboard Popular</p>
</section>

{pb_spreads}

<footer class="footer">
  <p>Morning Edition — {day_name}, {month_day_year}</p>
  <p>Curated from Hacker News + Pinboard Popular</p>
  <p style="margin-top:1rem;"><a href="/archive/" style="color:#a8a29e;text-decoration:none;">Previous Issues →</a></p>
</footer>

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
