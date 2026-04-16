#!/usr/bin/env python3
"""
Regenerates index.html, feed.xml, and latest redirect
from whatever .html files exist in magazines/.
Run after adding a new edition.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAG_DIR = ROOT / "magazines"
DOMAIN = "https://daily.rhymeswithjazz.com"


def get_editions():
    """Find all YYYY-MM-DD.html files, sorted newest first."""
    files = sorted(MAG_DIR.glob("????-??-??.html"), reverse=True)
    editions = []
    for f in files:
        date_str = f.stem
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # Extract title from <title> tag
            content = f.read_text(encoding="utf-8")
            title_match = re.search(r"<title>(.*?)</title>", content)
            title = title_match.group(1) if title_match else f"Morning Edition — {date_str}"
            # Extract story headlines and links from spread sections only
            # (skip section-divider h2 by requiring a read-link in the same spread)
            stories = []
            for m in re.finditer(
                r'<section\s+class="spread[^"]*">.*?<h2[^>]*>(.*?)</h2>.*?<a\s+class="read-link"\s+href="([^"]+)"',
                content,
                re.DOTALL,
            ):
                headline = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                url = m.group(2)
                stories.append({"headline": headline, "url": url})

            # Extract blurbs paired with headlines
            for i, m in enumerate(re.finditer(
                r'<p\s+class="blurb"[^>]*>(.*?)</p>',
                content,
                re.DOTALL,
            )):
                if i < len(stories):
                    blurb = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                    blurb = re.sub(r"\s+", " ", blurb)
                    stories[i]["blurb"] = blurb

            # Detect which stories have "Directly Applies" tags
            applies_positions = set()
            for j, m in enumerate(re.finditer(r'class="spread[^"]*"', content)):
                spread_start = m.start()
                next_spread = content.find('class="spread', spread_start + 1)
                section = content[spread_start:next_spread] if next_spread > 0 else content[spread_start:]
                if "applies-tag" in section:
                    applies_positions.add(j)

            for j, s in enumerate(stories):
                s["applies"] = j in applies_positions

            # Detect Pinboard stories (have source-pinboard badge)
            for j, m in enumerate(re.finditer(r'class="spread[^"]*"', content)):
                spread_start = m.start()
                next_spread = content.find('class="spread', spread_start + 1)
                section = content[spread_start:next_spread] if next_spread > 0 else content[spread_start:]
                if j < len(stories):
                    stories[j]["source"] = "pinboard" if "source-pinboard" in section else "hn"

            editions.append({
                "date": dt,
                "date_str": date_str,
                "filename": f.name,
                "title": title,
                "path": f"magazines/{f.name}",
                "stories": stories,
            })
        except ValueError:
            continue
    return editions


def build_index(editions):
    """Copy the latest edition to index.html as the homepage."""
    if editions:
        latest_html = (MAG_DIR / editions[0]["filename"]).read_text(encoding="utf-8")
        (ROOT / "index.html").write_text(latest_html, encoding="utf-8")
        print(f"  index.html: latest edition ({editions[0]['date_str']})")
    else:
        # Placeholder when no editions exist
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Edition — Daily Tech Magazine</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
  body { font-family: sans-serif; background: #0a0a0a; color: #fafaf9;
         display: flex; justify-content: center; align-items: center;
         min-height: 100vh; text-align: center; }
</style>
</head>
<body><p>No editions yet. Check back tomorrow morning.</p></body>
</html>"""
        (ROOT / "index.html").write_text(html, encoding="utf-8")
        print("  index.html: placeholder (no editions)")


def build_archive(editions):
    """Generate the archive listing at archive/index.html."""
    archive_dir = ROOT / "archive"
    archive_dir.mkdir(exist_ok=True)

    rows = ""
    for i, ed in enumerate(editions):
        day_name = ed["date"].strftime("%A")
        month_day = ed["date"].strftime("%B %-d, %Y")
        latest_badge = (
            '<span style="background:#fb923c;color:white;padding:0.2rem 0.6rem;'
            'border-radius:100px;font-size:0.7rem;font-weight:700;letter-spacing:0.1em;'
            'text-transform:uppercase;margin-left:0.75rem;">Latest</span>'
            if i == 0 else ""
        )
        rows += f"""
    <a href="/{ed['path']}" class="edition-row">
      <span class="edition-date">{day_name}<br><strong>{month_day}</strong></span>
      <span class="edition-title">{ed['title']}{latest_badge}</span>
      <span class="edition-arrow">&rarr;</span>
    </a>"""

    html = f"""<!DOCTYPE html>
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
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,100..900;1,9..144,100..900&family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html {{ font-size: 18px; }}
  body {{
    font-family: 'Inter', sans-serif;
    background: #0a0a0a;
    color: #fafaf9;
    min-height: 100vh;
  }}
  .header {{
    padding: clamp(3rem, 10vw, 6rem) clamp(2rem, 6vw, 5rem);
    max-width: 52rem;
    margin: 0 auto;
  }}
  .header .label {{
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #fb923c;
    margin-bottom: 1.5rem;
  }}
  .header h1 {{
    font-family: 'Fraunces', serif;
    font-size: clamp(2.5rem, 7vw, 5rem);
    font-weight: 900;
    font-style: italic;
    line-height: 1;
    margin-bottom: 1rem;
  }}
  .header p {{
    font-size: 1.1rem;
    color: #a8a29e;
    line-height: 1.6;
    max-width: 36rem;
  }}
  .header .nav-links {{
    margin-top: 1.5rem;
    display: flex;
    gap: 1.5rem;
  }}
  .header .nav-links a {{
    font-size: 0.85rem;
    text-decoration: none;
    font-weight: 600;
  }}
  .header .home-link {{ color: #a8a29e; }}
  .header .home-link:hover {{ color: #fb923c; }}
  .header .rss-link {{ color: #fb923c; }}
  .header .rss-link:hover {{ text-decoration: underline; }}
  .editions {{
    max-width: 52rem;
    margin: 0 auto;
    padding: 0 clamp(2rem, 6vw, 5rem) 4rem;
  }}
  .edition-row {{
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 1.5rem 0;
    border-top: 1px solid #292524;
    text-decoration: none;
    color: #fafaf9;
    transition: background 0.15s;
  }}
  .edition-row:hover {{
    background: rgba(251,146,60,0.04);
  }}
  .edition-date {{
    font-size: 0.85rem;
    color: #78716c;
    min-width: 10rem;
    line-height: 1.4;
  }}
  .edition-date strong {{
    color: #a8a29e;
    font-weight: 600;
  }}
  .edition-title {{
    flex: 1;
    font-family: 'Fraunces', serif;
    font-size: 1.15rem;
    font-weight: 600;
    display: flex;
    align-items: center;
  }}
  .edition-arrow {{
    font-size: 1.2rem;
    color: #57534e;
    transition: color 0.15s, transform 0.15s;
  }}
  .edition-row:hover .edition-arrow {{
    color: #fb923c;
    transform: translateX(4px);
  }}
  .empty {{
    padding: 4rem 0;
    text-align: center;
    color: #57534e;
    font-size: 1.1rem;
  }}
  .footer {{
    max-width: 52rem;
    margin: 0 auto;
    padding: 3rem clamp(2rem, 6vw, 5rem);
    border-top: 1px solid #1c1917;
    font-size: 0.8rem;
    color: #57534e;
  }}
  @media (max-width: 640px) {{
    .edition-row {{ flex-wrap: wrap; gap: 0.5rem; }}
    .edition-date {{ min-width: 100%; }}
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="label">Archive</div>
    <h1>Previous Issues</h1>
    <p>Every Morning Edition, from newest to oldest.</p>
    <div class="nav-links">
      <a class="home-link" href="/">&larr; Latest Issue</a>
      <a class="rss-link" href="/feed.xml">Subscribe via RSS &rarr;</a>
    </div>
  </div>
  <div class="editions">
    {rows if rows else '<div class="empty">No editions yet. Check back tomorrow morning.</div>'}
  </div>
  <div class="footer">
    <p>Curated daily from Hacker News + Pinboard Popular</p>
  </div>
</body>
</html>"""
    (archive_dir / "index.html").write_text(html, encoding="utf-8")
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

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0;url={target}">
<link rel="canonical" href="{DOMAIN}{target}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<title>Redirecting to latest edition...</title>
</head>
<body><a href="{target}">Latest edition</a></body>
</html>"""
    (latest_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"  latest/index.html -> {target}")


if __name__ == "__main__":
    print("Building Morning Edition site...")
    editions = get_editions()
    build_index(editions)
    build_archive(editions)
    build_feed(editions)
    build_latest_redirect(editions)
    print("Done.")
