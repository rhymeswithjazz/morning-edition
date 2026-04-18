#!/usr/bin/env python3
"""
Builds, commits, and deploys a curated Morning Edition.

Usage:
    python3 scripts/publish-edition.py magazines/YYYY-MM-DD.json
    python3 scripts/publish-edition.py magazines/YYYY-MM-DD.json --dry-run
    python3 scripts/publish-edition.py magazines/YYYY-MM-DD.json --no-push
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MAG_DIR = ROOT / "magazines"

REQUIRED_STORY_FIELDS = {"title", "url", "category", "blurb", "byline"}
REQUIRED_HN_FIELDS = REQUIRED_STORY_FIELDS | {"hn_link"}


def validate_json(json_path):
    data = json.loads(json_path.read_text(encoding="utf-8"))

    if "date" not in data:
        print("Error: JSON missing 'date' field", file=sys.stderr)
        sys.exit(1)

    stories = data.get("stories", [])
    if len(stories) != 20:
        print(f"Error: expected 20 stories, found {len(stories)}", file=sys.stderr)
        sys.exit(1)

    for i, story in enumerate(stories):
        required = REQUIRED_HN_FIELDS if i < 10 else REQUIRED_STORY_FIELDS
        missing = required - set(story.keys())
        if missing:
            print(f"Error: story {i + 1} missing fields: {', '.join(sorted(missing))}", file=sys.stderr)
            sys.exit(1)

    return data


def run_cmd(args, label):
    print(f"  {label}...", file=sys.stderr)
    result = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"  Error: {label} failed (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result


def build(json_path):
    print("Building edition...", file=sys.stderr)
    run_cmd([sys.executable, str(SCRIPTS / "build-edition.py"), str(json_path)], "build-edition.py")
    run_cmd([sys.executable, str(SCRIPTS / "build-index.py")], "build-index.py")
    print("  Build complete", file=sys.stderr)


def git_commit_and_push(date_str, push=True):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A")
    month_name = dt.strftime("%B")
    day = dt.day
    year = dt.year
    msg = f"Morning Edition — {day_name}, {month_name} {day}, {year}"

    print("Publishing...", file=sys.stderr)

    run_cmd(["git", "checkout", "main"], "git checkout main")

    files = [
        f"magazines/{date_str}.json",
        f"magazines/candidates-{date_str}.json",
        f"magazines/{date_str}.html",
        "index.html",
        "archive/index.html",
        "feed.xml",
        "latest/index.html",
    ]
    run_cmd(["git", "add"] + files, "git add")
    run_cmd(["git", "commit", "-m", msg], "git commit")

    if push:
        run_cmd(["git", "push", "origin", "main"], "git push")
        print(f"  Pushed: {msg}", file=sys.stderr)
    else:
        print(f"  Committed (not pushed): {msg}", file=sys.stderr)

    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return sha_result.stdout.strip() if sha_result.returncode == 0 else None


def sync_db(date_str, commit_sha):
    print("Syncing to Supabase...", file=sys.stderr)
    cmd = [sys.executable, str(SCRIPTS / "sync-db.py"), date_str]
    if commit_sha:
        cmd += ["--commit-sha", commit_sha]
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(
            f"  Warning: sync-db exited {result.returncode}; "
            "edition is live, DB will catch up on next run.",
            file=sys.stderr,
        )


def main():
    parser = argparse.ArgumentParser(description="Publish a Morning Edition")
    parser.add_argument("json_file", help="Path to the curated JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Build only, no git operations")
    parser.add_argument("--no-push", action="store_true", help="Commit but do not push")
    args = parser.parse_args()

    json_path = Path(args.json_file).resolve()
    if not json_path.exists():
        print(f"Error: {json_path} not found", file=sys.stderr)
        sys.exit(1)

    data = validate_json(json_path)
    date_str = data["date"]

    build(json_path)

    if not args.dry_run:
        commit_sha = git_commit_and_push(date_str, push=not args.no_push)
        if not args.no_push:
            sync_db(date_str, commit_sha)

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
