#!/usr/bin/env python3
"""
Prints URLs from recent Morning Edition JSON files for deduplication.

Usage:
    python3 scripts/recent-urls.py [days]

Defaults to 7 days. Outputs one URL per line.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAG_DIR = ROOT / "magazines"


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    cutoff = datetime.now() - timedelta(days=days)
    urls = []

    for f in sorted(MAG_DIR.glob("????-??-??.json")):
        try:
            dt = datetime.strptime(f.stem, "%Y-%m-%d")
            if dt >= cutoff:
                data = json.loads(f.read_text(encoding="utf-8"))
                for story in data.get("stories", []):
                    if story.get("url"):
                        urls.append(story["url"])
        except (ValueError, json.JSONDecodeError):
            continue

    if urls:
        for url in urls:
            print(url)
        print(f"\n# {len(urls)} URLs from last {days} days", file=sys.stderr)
    else:
        print("# No recent editions found", file=sys.stderr)


if __name__ == "__main__":
    main()
