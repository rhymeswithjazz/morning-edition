#!/usr/bin/env python3
"""One-shot backfill of existing published editions into Supabase.

Usage:
    python3 scripts/backfill-db.py [--dry-run]

Walks every magazines/YYYY-MM-DD.json file, upserts the corresponding
editions row and its 20 published stories. Historical candidates files
were already deleted, so no rejected rows are backfilled — fetch-time
metadata columns (hn_score, pb_tags, etc.) are NULL/empty for backfilled
rows.

Environment:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _supabase import get_client, load_env

ROOT = Path(__file__).resolve().parent.parent
MAG_DIR = ROOT / "magazines"


def build_rows(edition_json_path):
    data = json.loads(edition_json_path.read_text(encoding="utf-8"))
    date_str = data["date"]
    mtime = datetime.fromtimestamp(
        edition_json_path.stat().st_mtime, tz=timezone.utc
    ).isoformat()

    edition_row = {
        "date": date_str,
        "fetched_at": mtime,
        "published_at": mtime,
        "commit_sha": None,
    }

    story_rows = []
    for i, story in enumerate(data.get("stories", [])):
        source = "hn" if i < 10 else "pinboard"
        story_rows.append({
            "edition_date": date_str,
            "status": "published",
            "source": source,
            "rank": i + 1,
            "url": story["url"],
            "title": story["title"],
            "category": story.get("category"),
            "applies": story.get("applies"),
            "byline": story.get("byline"),
            "blurb": story.get("blurb"),
            "hn_link": story.get("hn_link"),
            "hn_id": None,
            "hn_score": None,
            "hn_comments": None,
            "hn_author": None,
            "pb_tags": [],
            "pb_description": None,
        })
    return edition_row, story_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env()
    client = None if args.dry_run else get_client()

    files = sorted(
        f for f in MAG_DIR.glob("????-??-??.json")
        if not f.name.startswith("candidates-")
    )

    total_editions = 0
    total_stories = 0

    for f in files:
        edition_row, story_rows = build_rows(f)
        if args.dry_run:
            print(f"[dry-run] {edition_row['date']}: {len(story_rows)} stories")
        else:
            client.table("editions").upsert(edition_row, on_conflict="date").execute()
            client.table("stories").upsert(story_rows, on_conflict="edition_date,url").execute()
            print(f"Backfilled {edition_row['date']}", file=sys.stderr)
        total_editions += 1
        total_stories += len(story_rows)

    print(f"\nDone: {total_editions} editions, {total_stories} stories", file=sys.stderr)


if __name__ == "__main__":
    main()
