#!/usr/bin/env python3
"""
Regenerates index.html, feed.xml, and latest redirect
from whatever .html files exist in magazines/.
Run after adding a new edition.
"""

import html
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAG_DIR = ROOT / "magazines"
DOMAIN = "https://daily.rhymeswithjazz.com"


# Matches a <article class="story...">...</article> block. Captures the
# full inner HTML for downstream extraction.
STORY_RE = re.compile(
    r'<article\s+class="(?P<classes>story[^"]*)"[^>]*data-source="(?P<source>[^"]+)"[^>]*>(?P<body>.*?)</article>',
    re.DOTALL,
)
H3_LINK_RE = re.compile(r'<h3[^>]*>\s*<a\s+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>\s*</h3>', re.DOTALL)
BLURB_RE = re.compile(r'<p\s+class="blurb"[^>]*>(?P<text>.*?)</p>', re.DOTALL)


def get_editions():
    """Find all YYYY-MM-DD.html files, sorted newest first."""
    files = sorted(MAG_DIR.glob("????-??-??.html"), reverse=True)
    editions = []
    for f in files:
        date_str = f.stem
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        content = f.read_text(encoding="utf-8")
        title_match = re.search(r"<title>(.*?)</title>", content)
        title = html.unescape(title_match.group(1)) if title_match else f"Morning Edition — {date_str}"

        stories = []
        for m in STORY_RE.finditer(content):
            body = m.group("body")
            classes = m.group("classes")
            source = m.group("source")

            h3 = H3_LINK_RE.search(body)
            if not h3:
                continue
            headline = html.unescape(re.sub(r"<[^>]+>", "", h3.group("title")).strip())
            url = html.unescape(h3.group("url"))

            blurb = ""
            b = BLURB_RE.search(body)
            if b:
                blurb = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", b.group("text"))).strip()
                blurb = html.unescape(blurb)

            stories.append({
                "headline": headline,
                "url": url,
                "blurb": blurb,
                "applies": "applies" in classes.split(),
                "source": "pinboard" if source == "pb" else "hn",
            })

        # Fallback: handle legacy (pre-Digest) editions whose markup used
        # <section class="spread...">. Best-effort metadata extraction so the
        # archive and feed still work.
        if not stories:
            for m in re.finditer(
                r'<section\s+class="spread[^"]*">.*?<h2[^>]*>(.*?)</h2>.*?<a\s+class="read-link"\s+href="([^"]+)"',
                content,
                re.DOTALL,
            ):
                headline = html.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
                url = html.unescape(m.group(2))
                stories.append({"headline": headline, "url": url, "blurb": "", "applies": False, "source": "hn"})

            for i, m in enumerate(BLURB_RE.finditer(content)):
                if i < len(stories):
                    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group("text"))).strip()
                    stories[i]["blurb"] = html.unescape(txt)

            for j, m in enumerate(re.finditer(r'class="spread[^"]*"', content)):
                spread_start = m.start()
                next_spread = content.find('class="spread', spread_start + 1)
                section = content[spread_start:next_spread] if next_spread > 0 else content[spread_start:]
                if j < len(stories):
                    stories[j]["applies"] = "applies-tag" in section
                    stories[j]["source"] = "pinboard" if "source-pinboard" in section else "hn"

        editions.append({
            "date": dt,
            "date_str": date_str,
            "filename": f.name,
            "title": title,
            "path": f"magazines/{f.name}",
            "stories": stories,
        })
    return editions


def build_index(editions):
    """Copy the latest edition to index.html as the homepage."""
    if editions:
        latest_html = (MAG_DIR / editions[0]["filename"]).read_text(encoding="utf-8")
        (ROOT / "index.html").write_text(latest_html, encoding="utf-8")
        print(f"  index.html: latest edition ({editions[0]['date_str']})")
    else:
        html_doc = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Edition — Daily Tech Magazine</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
  body { font-family: 'Inter', system-ui, sans-serif; background: #fbf8f1; color: #1a1a17;
         display: flex; justify-content: center; align-items: center;
         min-height: 100vh; text-align: center; padding: 2rem; }
</style>
</head>
<body><p>No editions yet. Check back tomorrow morning.</p></body>
</html>"""
        (ROOT / "index.html").write_text(html_doc, encoding="utf-8")
        print("  index.html: placeholder (no editions)")


def build_archive(editions):
    """Generate the archive listing at archive/index.html."""
    archive_dir = ROOT / "archive"
    archive_dir.mkdir(exist_ok=True)

    rows = ""
    for i, ed in enumerate(editions):
        day_name = ed["date"].strftime("%A")
        month_day = ed["date"].strftime("%B %-d, %Y")
        applies_count = sum(1 for s in ed["stories"] if s.get("applies"))
        story_count = len(ed["stories"])
        latest_badge = (
            '<span class="latest-badge">Latest</span>'
            if i == 0 else ""
        )
        meta_line = ""
        if story_count:
            meta_line = f'<div class="edition-meta">{story_count} stories · {applies_count} flagged for you</div>'

        rows += f"""
    <a href="/{ed['path']}" class="edition-row">
      <div class="edition-date"><span class="day">{day_name}</span><span class="md">{month_day}</span></div>
      <div class="edition-body">
        <div class="edition-title">Morning Edition{latest_badge}</div>
        {meta_line}
      </div>
      <span class="edition-arrow">&rarr;</span>
    </a>"""

    archive_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Previous Issues — Morning Edition</title>
<meta name="description" content="Archive of all Morning Edition issues. A daily curated magazine from Hacker News and Pinboard Popular.">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="alternate" type="application/rss+xml" title="Morning Edition RSS" href="{DOMAIN}/feed.xml">
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
  }}
  html {{ font-size: 17px; -webkit-text-size-adjust: 100%; }}
  body {{
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg);
    color: var(--ink);
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: inherit; text-decoration: none; }}

  .page {{ max-width: 38rem; margin: 0 auto; padding: 1.25rem 1.25rem 4rem; }}

  .masthead {{
    padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--ink);
    margin-bottom: 1.5rem;
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

  .nav-links {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.25rem;
    margin-bottom: 2rem;
    font-size: 0.85rem;
  }}
  .nav-links a {{
    color: var(--accent);
    border-bottom: 1px solid var(--accent);
    padding-bottom: 1px;
  }}

  .editions {{
    display: flex;
    flex-direction: column;
  }}
  .edition-row {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.75rem 1rem;
    padding: 1.1rem 0;
    border-top: 1px solid var(--rule);
    color: var(--ink);
    align-items: center;
  }}
  .edition-row:first-child {{ border-top: none; }}
  .edition-row:hover {{ background: rgba(138,58,26,0.04); }}
  .edition-date {{
    grid-row: 1;
    grid-column: 1;
    display: flex;
    flex-direction: column;
    font-size: 0.72rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.1rem;
  }}
  .edition-date .day {{ font-weight: 600; color: var(--accent); }}
  .edition-date .md {{ color: var(--muted); margin-top: 0.15rem; }}
  .edition-body {{
    grid-row: 2;
    grid-column: 1;
  }}
  .edition-title {{
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 700;
    font-size: 1.25rem;
    line-height: 1.15;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }}
  .edition-meta {{
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 0.2rem;
  }}
  .edition-arrow {{
    grid-row: 1 / span 2;
    grid-column: 2;
    font-size: 1.15rem;
    color: var(--muted);
    align-self: center;
  }}
  .edition-row:hover .edition-arrow {{ color: var(--accent); transform: translateX(2px); }}
  .latest-badge {{
    background: var(--accent);
    color: var(--bg);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 3px;
    font-family: 'Inter', system-ui, sans-serif;
  }}

  .empty {{
    padding: 4rem 0;
    text-align: center;
    color: var(--muted);
    font-size: 1rem;
  }}

  .colophon {{
    margin-top: 3rem;
    padding-top: 1.25rem;
    border-top: 1px solid var(--ink);
    font-size: 0.78rem;
    color: var(--muted);
    line-height: 1.6;
  }}
  .colophon a {{ color: var(--accent); }}

  @media (min-width: 640px) {{
    html {{ font-size: 18px; }}
    .page {{ padding: 2rem 1.75rem 5rem; }}
    .masthead h1 {{ font-size: 2.6rem; }}
    .edition-row {{
      grid-template-columns: 12rem 1fr auto;
      padding: 1.25rem 0;
    }}
    .edition-date {{ grid-row: 1; grid-column: 1; align-self: center; }}
    .edition-body {{ grid-row: 1; grid-column: 2; }}
    .edition-arrow {{ grid-row: 1; grid-column: 3; }}
  }}
</style>
</head>
<body>
<div class="page">

  <header class="masthead">
    <div class="kicker">Archive</div>
    <h1>Previous <em>Issues</em></h1>
    <p class="sub">Every Morning Edition, newest first. {len(editions)} issues so far.</p>
  </header>

  <nav class="nav-links">
    <a href="/">← Latest issue</a>
    <a href="/feed.xml">Subscribe via RSS →</a>
  </nav>

  <div class="editions">
    {rows if rows else '<div class="empty">No editions yet. Check back tomorrow morning.</div>'}
  </div>

  <footer class="colophon">
    Morning Edition · daily.rhymeswithjazz.com<br>
    Curated by Claude · <a href="/">Home</a> · <a href="/feed.xml">RSS</a>
  </footer>

</div>
</body>
</html>"""
    (archive_dir / "index.html").write_text(archive_html, encoding="utf-8")
    print(f"  archive/index.html: {len(editions)} editions listed")


def _xml_escape(text):
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _build_feed_description(ed):
    """Build rich HTML description for an RSS item from extracted stories."""
    stories = ed.get("stories", [])
    if not stories:
        return f"20 curated stories for {ed['date'].strftime('%B %-d, %Y')}."

    hn_stories = [s for s in stories if s.get("source") != "pinboard"]
    pb_stories = [s for s in stories if s.get("source") == "pinboard"]

    html_parts = []

    if hn_stories:
        html_parts.append("<h3>From Hacker News</h3><ol>")
        for s in hn_stories:
            flag = " ⚡" if s.get("applies") else ""
            blurb = s.get("blurb", "")
            blurb_html = f"<br/><small>{_xml_escape(blurb)}</small>" if blurb else ""
            html_parts.append(
                f'<li><a href="{_xml_escape(s["url"])}">'
                f'{_xml_escape(s["headline"])}</a>{flag}{blurb_html}</li>'
            )
        html_parts.append("</ol>")

    if pb_stories:
        html_parts.append("<h3>Pinboard Picks</h3><ol>")
        for s in pb_stories:
            flag = " ⚡" if s.get("applies") else ""
            blurb = s.get("blurb", "")
            blurb_html = f"<br/><small>{_xml_escape(blurb)}</small>" if blurb else ""
            html_parts.append(
                f'<li><a href="{_xml_escape(s["url"])}">'
                f'{_xml_escape(s["headline"])}</a>{flag}{blurb_html}</li>'
            )
        html_parts.append("</ol>")

    html_parts.append(
        f'<p><a href="{DOMAIN}/{ed["path"]}">Read the full magazine edition →</a></p>'
    )
    return "\n".join(html_parts)


def build_feed(editions):
    """Generate RSS feed.xml with rich story descriptions."""
    items = ""
    for ed in editions[:20]:  # last 20 editions in feed
        pub_date = ed["date"].strftime("%a, %d %b %Y 07:00:00 +0000")
        description = _build_feed_description(ed)
        items += f"""
    <item>
      <title>{_xml_escape(ed['title'])}</title>
      <link>{DOMAIN}/{ed['path']}</link>
      <guid>{DOMAIN}/{ed['path']}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{description}]]></description>
    </item>"""

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Morning Edition</title>
    <link>{DOMAIN}</link>
    <description>A daily curated magazine from Hacker News and Pinboard Popular.</description>
    <language>en-us</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{DOMAIN}/feed.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>{DOMAIN}/favicon.svg</url>
      <title>Morning Edition</title>
      <link>{DOMAIN}</link>
    </image>
    {items}
  </channel>
</rss>"""
    (ROOT / "feed.xml").write_text(xml, encoding="utf-8")
    print(f"  feed.xml: {min(len(editions), 20)} items")


def build_latest_redirect(editions):
    """Generate latest/index.html redirect to most recent edition."""
    latest_dir = ROOT / "latest"
    latest_dir.mkdir(exist_ok=True)

    if editions:
        target = f"/{editions[0]['path']}"
    else:
        target = "/"

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0;url={target}">
<link rel="canonical" href="{DOMAIN}{target}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<title>Redirecting to latest edition...</title>
</head>
<body><a href="{target}">Latest edition</a></body>
</html>"""
    (latest_dir / "index.html").write_text(html_doc, encoding="utf-8")
    print(f"  latest/index.html -> {target}")


if __name__ == "__main__":
    print("Building Morning Edition site...")
    editions = get_editions()
    build_index(editions)
    build_archive(editions)
    build_feed(editions)
    build_latest_redirect(editions)
    print("Done.")
