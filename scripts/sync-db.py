#!/usr/bin/env python3
"""Sync a published edition (and its rejected candidates) to Supabase.

Usage:
    python3 scripts/sync-db.py YYYY-MM-DD [--commit-sha SHA] [--dry-run]

Reads magazines/YYYY-MM-DD.json (published) and magazines/candidates-YYYY-MM-DD.json
(fetched), builds edition + story rows, upserts idempotently. Before syncing the
requested date, catches up any earlier editions that are on disk but missing
from the DB.

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


def load_edition_files(date_str):
    edition_path = MAG_DIR / f"{date_str}.json"
    candidates_path = MAG_DIR / f"candidates-{date_str}.json"

    if not edition_path.exists():
        raise FileNotFoundError(f"Edition not found: {edition_path}")

    edition = json.loads(edition_path.read_text(encoding="utf-8"))
    candidates = None
    if candidates_path.exists():
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    return edition, candidates


def build_candidate_index(candidates):
    if not candidates:
        return {}
    index = {}
    for source_key in ("hn", "pinboard"):
        for c in candidates.get("candidates", {}).get(source_key, []):
            index[c["url"]] = c
    return index


def build_rows(date_str, edition, candidates, commit_sha=None):
    published_at = datetime.now(timezone.utc).isoformat()
    fetched_at = (candidates or {}).get("fetched_at")

    edition_row = {
        "date": date_str,
        "fetched_at": fetched_at,
        "published_at": published_at,
        "commit_sha": commit_sha,
    }

    cand_index = build_candidate_index(candidates)
    published_urls = set()
    story_rows = []

    for i, story in enumerate(edition.get("stories", [])):
        url = story["url"]
        published_urls.add(url)
        source = "hn" if i < 10 else "pinboard"
        cand = cand_index.get(url, {})
        story_rows.append({
            "edition_date": date_str,
            "status": "published",
            "source": source,
            "rank": i + 1,
            "url": url,
            "title": story["title"],
            "category": story.get("category"),
            "applies": story.get("applies"),
            "byline": story.get("byline"),
            "blurb": story.get("blurb"),
            "hn_link": story.get("hn_link"),
            "hn_id": cand.get("hn_id"),
            "hn_score": cand.get("score"),
            "hn_comments": cand.get("comments"),
            "hn_author": cand.get("author"),
            "pb_tags": cand.get("tags") or [],
            "pb_description": cand.get("description"),
        })

    for url, cand in cand_index.items():
        if url in published_urls:
            continue
        source = cand.get("source") or ("hn" if "hn_id" in cand else "pinboard")
        story_rows.append({
            "edition_date": date_str,
            "status": "rejected",
            "source": source,
            "rank": None,
            "url": url,
            "title": cand.get("title") or "(untitled)",
            "category": None,
            "applies": None,
            "byline": None,
            "blurb": None,
            "hn_link": None,
            "hn_id": cand.get("hn_id"),
            "hn_score": cand.get("score"),
            "hn_comments": cand.get("comments"),
            "hn_author": cand.get("author"),
            "pb_tags": cand.get("tags") or [],
            "pb_description": cand.get("description"),
        })

    return edition_row, story_rows


def sync_date(client, date_str, commit_sha=None, dry_run=False):
    edition, candidates = load_edition_files(date_str)
    edition_row, story_rows = build_rows(date_str, edition, candidates, commit_sha)

    if dry_run:
        print(f"[dry-run] edition row: {edition_row}")
        print(f"[dry-run] {len(story_rows)} story rows for {date_str}")
        for r in story_rows[:5]:
            rank = r["rank"] if r["rank"] is not None else "-"
            print(f"  {r['status']:9s} rank={rank!s:>2} {r['source']:8s} {r['url']}")
        if len(story_rows) > 5:
            print(f"  ... and {len(story_rows) - 5} more")
        return

    client.table("editions").upsert(edition_row, on_conflict="date").execute()
    client.table("stories").upsert(story_rows, on_conflict="edition_date,url").execute()
    print(f"Synced {date_str}: 1 edition + {len(story_rows)} stories", file=sys.stderr)


def find_unsynced_dates(client, target_date):
    """Edition JSONs on disk with date <= target that are not yet in editions table."""
    resp = client.table("editions").select("date").execute()
    synced = {row["date"] for row in (resp.data or [])}

    dates = []
    for f in sorted(MAG_DIR.glob("????-??-??.json")):
        if f.name.startswith("candidates-"):
            continue
        d = f.stem
        if d > target_date:
            continue
        if d in synced:
            continue
        if d == target_date:
            continue
        dates.append(d)
    return dates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Edition date YYYY-MM-DD")
    parser.add_argument("--commit-sha", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env()

    if args.dry_run:
        sync_date(None, args.date, commit_sha=args.commit_sha, dry_run=True)
        return

    client = get_client()

    catchup = find_unsynced_dates(client, args.date)
    if catchup:
        print(f"Catching up {len(catchup)} prior edition(s)...", file=sys.stderr)
        for d in catchup:
            sync_date(client, d)

    sync_date(client, args.date, commit_sha=args.commit_sha)


if __name__ == "__main__":
    main()
