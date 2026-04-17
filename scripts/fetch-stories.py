#!/usr/bin/env python3
"""
Fetches candidate stories from Hacker News and Pinboard Popular,
deduplicates against recent editions, and writes a candidates JSON file.

Usage:
    python3 scripts/fetch-stories.py [--date YYYY-MM-DD]

Output: magazines/candidates-YYYY-MM-DD.json
"""

import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAG_DIR = ROOT / "magazines"

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
PINBOARD_RSS_URL = "https://feeds.pinboard.in/rss/popular/"

REQUEST_TIMEOUT = 30
MAX_HN_STORIES = 40
DEDUP_DAYS = 7
HN_WORKERS = 10


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MorningEdition/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MorningEdition/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def get_recent_urls(days=DEDUP_DAYS):
    cutoff = datetime.now() - timedelta(days=days)
    urls = set()
    for f in MAG_DIR.glob("????-??-??.json"):
        if f.name.startswith("candidates-"):
            continue
        try:
            dt = datetime.strptime(f.stem, "%Y-%m-%d")
            if dt >= cutoff:
                data = json.loads(f.read_text(encoding="utf-8"))
                for story in data.get("stories", []):
                    if story.get("url"):
                        urls.add(story["url"])
        except (ValueError, json.JSONDecodeError):
            continue
    return urls


def fetch_hn_item(item_id):
    try:
        return fetch_json(HN_ITEM_URL.format(item_id))
    except Exception as e:
        print(f"  Warning: failed to fetch HN item {item_id}: {e}", file=sys.stderr)
        return None


def fetch_hn_stories():
    print("Fetching HN top stories...", file=sys.stderr)
    try:
        top_ids = fetch_json(HN_TOP_URL)[:MAX_HN_STORIES]
    except Exception as e:
        print(f"  Error fetching HN top stories: {e}", file=sys.stderr)
        # Retry once
        try:
            top_ids = fetch_json(HN_TOP_URL)[:MAX_HN_STORIES]
        except Exception as e2:
            print(f"  Retry failed: {e2}", file=sys.stderr)
            return []

    stories = []
    with ThreadPoolExecutor(max_workers=HN_WORKERS) as pool:
        futures = {pool.submit(fetch_hn_item, sid): sid for sid in top_ids}
        for future in as_completed(futures):
            item = future.result()
            if item and item.get("type") == "story" and not item.get("dead") and not item.get("deleted"):
                hn_id = item["id"]
                url = item.get("url", f"https://news.ycombinator.com/item?id={hn_id}")
                stories.append({
                    "source": "hn",
                    "title": item.get("title", "(untitled)"),
                    "url": url,
                    "hn_id": hn_id,
                    "hn_link": f"https://news.ycombinator.com/item?id={hn_id}",
                    "score": item.get("score", 0),
                    "author": item.get("by", "unknown"),
                    "comments": item.get("descendants", 0),
                    "byline_hint": f"by {item.get('by', 'unknown')} · {item.get('score', 0)} points · {item.get('descendants', 0)} comments",
                })

    stories.sort(key=lambda s: s["score"], reverse=True)
    print(f"  Fetched {len(stories)} HN stories", file=sys.stderr)
    return stories


def fetch_pinboard_stories():
    print("Fetching Pinboard Popular...", file=sys.stderr)
    try:
        xml_text = fetch_text(PINBOARD_RSS_URL)
    except Exception as e:
        print(f"  Error fetching Pinboard RSS: {e}", file=sys.stderr)
        try:
            xml_text = fetch_text(PINBOARD_RSS_URL)
        except Exception as e2:
            print(f"  Retry failed: {e2}", file=sys.stderr)
            return [], "Feed unreachable"

    ns = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rss": "http://purl.org/rss/1.0/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  Error parsing Pinboard XML: {e}", file=sys.stderr)
        return [], "XML parse error"

    stories = []
    for item in root.findall("rss:item", ns):
        url = item.get(f"{{{ns['rdf']}}}about", "")
        if not url:
            link_el = item.find("rss:link", ns)
            url = link_el.text if link_el is not None and link_el.text else ""
        if not url:
            continue

        title_el = item.find("rss:title", ns)
        title = title_el.text.strip() if title_el is not None and title_el.text else "(untitled)"

        desc_el = item.find("rss:description", ns)
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        subject_el = item.find("dc:subject", ns)
        tags = [t.strip() for t in subject_el.text.split()] if subject_el is not None and subject_el.text else []

        tag_str = ", ".join(tags) if tags else "untagged"
        stories.append({
            "source": "pinboard",
            "title": title,
            "url": url,
            "description": description,
            "tags": tags,
            "byline_hint": f"Pinboard Popular · tagged: {tag_str}",
        })

    print(f"  Fetched {len(stories)} Pinboard stories", file=sys.stderr)
    return stories, None


def deduplicate(hn_stories, pb_stories, recent_urls):
    seen = set(recent_urls)

    hn_deduped = []
    for s in hn_stories:
        if s["url"] not in seen:
            seen.add(s["url"])
            hn_deduped.append(s)

    pb_deduped = []
    for s in pb_stories:
        if s["url"] not in seen:
            seen.add(s["url"])
            pb_deduped.append(s)

    return hn_deduped, pb_deduped


def main():
    parser = argparse.ArgumentParser(description="Fetch Morning Edition story candidates")
    parser.add_argument("--date", help="Edition date (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    recent_urls = get_recent_urls()
    print(f"Loaded {len(recent_urls)} recent URLs for dedup", file=sys.stderr)

    hn_raw = fetch_hn_stories()
    pb_raw, pb_error = fetch_pinboard_stories()

    hn_stories, pb_stories = deduplicate(hn_raw, pb_raw, recent_urls)

    candidates = {
        "date": date_str,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "candidates": {
            "hn": hn_stories,
            "pinboard": pb_stories,
        },
        "stats": {
            "hn_fetched": len(hn_raw),
            "hn_after_dedup": len(hn_stories),
            "pinboard_fetched": len(pb_raw),
            "pinboard_after_dedup": len(pb_stories),
        },
    }

    if pb_error:
        candidates["stats"]["pinboard_error"] = pb_error

    out_path = MAG_DIR / f"candidates-{date_str}.json"
    out_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nWrote {out_path}", file=sys.stderr)
    print(str(out_path))


if __name__ == "__main__":
    main()
