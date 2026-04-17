# Supabase Story Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every fetched story (published + rejected candidates) to Supabase so we can query the full archive without clone-and-grep.

**Architecture:** After the daily pipeline publishes an edition, a new post-publish step reads the freshly-written `magazines/YYYY-MM-DD.json` (20 published stories) and `magazines/candidates-YYYY-MM-DD.json` (all fetched candidates), upserts them into two Postgres tables (`editions`, `stories`) via the Supabase Python client. DB writes are idempotent (`on_conflict (edition_date, url)`), run last in the pipeline, and are allowed to fail without failing the publish.

**Tech Stack:** Python 3.12 (stdlib + `supabase>=2.0`), Supabase Postgres, GitHub Actions.

**Testing note:** This project has no test suite. Per the design spec, we do not introduce one for this work. Each task's verification uses `--dry-run` output inspection, manual Supabase queries, or running the modified script end-to-end. Treat `--dry-run` the way you'd treat a passing unit test.

**Design spec:** `docs/superpowers/specs/2026-04-17-supabase-story-tracking-design.md`

---

## File Structure

**New files:**
- `requirements.txt` — single dep: `supabase>=2.0`
- `.env.example` — documents required env vars
- `migrations/0001_init.sql` — schema (editions, stories, constraints, indexes)
- `scripts/_supabase.py` — shared helper: `.env` loader + `get_client()`
- `scripts/sync-db.py` — per-edition sync with catch-up + `--dry-run`
- `scripts/backfill-db.py` — one-shot import of existing published editions

**Modified files:**
- `.gitignore` — ignore `.env`
- `scripts/publish-edition.py` — stop deleting candidates file, invoke `sync-db.py` post-push
- `.github/workflows/daily-edition.yml` — install requirements, pass Supabase secrets
- `CLAUDE.md` — update "No dependencies" note and document new scripts

---

### Task 1: Add dependency declaration and .env plumbing

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Check whether `.gitignore` exists**

Run: `ls -la /Users/ras/Documents/Magazines/.gitignore 2>/dev/null || echo "missing"`

If missing, create it in Step 2. If present, append to it in Step 2.

- [ ] **Step 2: Ensure `.gitignore` ignores `.env` and Python caches**

If `.gitignore` does not exist, create it with this content:

```
.env
__pycache__/
*.pyc
```

If it exists, ensure those three entries are present (append any missing ones). Do not remove existing entries.

- [ ] **Step 3: Create `requirements.txt`**

```
supabase>=2.0
```

- [ ] **Step 4: Create `.env.example`**

```
# Copy to .env for local development. .env is gitignored.
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=REPLACE_WITH_SERVICE_ROLE_KEY
```

- [ ] **Step 5: Install the dependency locally**

Run: `cd /Users/ras/Documents/Magazines && pip install -r requirements.txt`
Expected: `supabase`, `postgrest`, `gotrue`, `realtime`, `storage3`, `supafunc` (and transitives) install without errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore
git commit -m "Add supabase dependency and .env plumbing"
```

---

### Task 2: Write the schema migration

**Files:**
- Create: `migrations/0001_init.sql`

- [ ] **Step 1: Create `migrations/0001_init.sql`**

```sql
-- Morning Edition story tracking schema
-- Apply manually via the Supabase SQL editor.

create table editions (
  date          date primary key,
  fetched_at    timestamptz,
  published_at  timestamptz,
  commit_sha    text
);

create table stories (
  id              bigserial primary key,
  edition_date    date not null references editions(date) on delete cascade,
  status          text not null check (status in ('published','rejected')),
  source          text not null check (source in ('hn','pinboard')),
  rank            int,
  url             text not null,
  title           text not null,
  category        text,
  applies         boolean,
  byline          text,
  blurb           text,
  hn_link         text,
  hn_id           bigint,
  hn_score        int,
  hn_comments     int,
  hn_author       text,
  pb_tags         text[],
  pb_description  text,
  unique (edition_date, url),
  check (status = 'published' or rank is null),
  check (status = 'rejected' or rank is not null)
);

create index stories_status_date_idx on stories (status, edition_date desc);
create index stories_source_date_idx on stories (source, edition_date desc);
create index stories_pb_tags_idx on stories using gin (pb_tags);
```

- [ ] **Step 2: Commit**

```bash
git add migrations/0001_init.sql
git commit -m "Add initial schema migration for story tracking"
```

---

### Task 3: Apply migration to Supabase (manual, one-time)

This step requires the user. Pause and prompt them.

- [ ] **Step 1: Prompt the user to apply the migration**

Tell the user:

> Open the Supabase SQL editor for your project, paste the contents of `migrations/0001_init.sql`, and run it. Confirm both tables (`editions`, `stories`) exist in the Table Editor, then reply "applied" so I can continue.

Wait for explicit confirmation before proceeding to Task 4.

---

### Task 4: Create the shared Supabase helper

**Files:**
- Create: `scripts/_supabase.py`

- [ ] **Step 1: Create `scripts/_supabase.py`**

```python
"""Shared Supabase client and .env loading for pipeline DB scripts.

Intentionally minimal — no python-dotenv dependency. Parses KEY=VALUE lines
from a repo-root .env file, ignoring comments and blank lines, and only
sets variables that aren't already in the environment.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Load repo-root .env if present. Existing env vars win."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def get_client():
    """Build a Supabase client using service-role credentials from the env."""
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set "
            "(export them, or add to .env at repo root)."
        )
    return create_client(url, key)
```

- [ ] **Step 2: Verify the helper imports cleanly**

Run: `cd /Users/ras/Documents/Magazines && python3 -c "import sys; sys.path.insert(0, 'scripts'); import _supabase; _supabase.load_env(); print('ok')"`
Expected: prints `ok` with no exception.

- [ ] **Step 3: Commit**

```bash
git add scripts/_supabase.py
git commit -m "Add shared Supabase client helper"
```

---

### Task 5: Create `sync-db.py`

**Files:**
- Create: `scripts/sync-db.py`

- [ ] **Step 1: Create `scripts/sync-db.py`**

```python
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
```

- [ ] **Step 2: Dry-run against the most recent edition on disk**

Run: `cd /Users/ras/Documents/Magazines && ls magazines/????-??-??.json | grep -v candidates | tail -1`

Note the date (call it `$RECENT`), then:

Run: `cd /Users/ras/Documents/Magazines && python3 scripts/sync-db.py $RECENT --dry-run`

Expected: prints an edition row dict, then "N story rows for $RECENT" where N is at least 20 (plus rejects if a candidates file exists for that date), then up to 5 sample rows with status `published`/`rejected` and ranks 1–5.

If a candidates file does NOT exist for that date, N will be exactly 20 — that's still a valid dry-run.

- [ ] **Step 3: Commit**

```bash
git add scripts/sync-db.py
git commit -m "Add sync-db.py for Supabase story tracking"
```

---

### Task 6: Create `backfill-db.py`

**Files:**
- Create: `scripts/backfill-db.py`

- [ ] **Step 1: Create `scripts/backfill-db.py`**

```python
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
```

- [ ] **Step 2: Dry-run the backfill**

Run: `cd /Users/ras/Documents/Magazines && python3 scripts/backfill-db.py --dry-run`

Expected: one `[dry-run] YYYY-MM-DD: 20 stories` line per edition JSON on disk, then a `Done: N editions, N*20 stories` summary.

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill-db.py
git commit -m "Add backfill-db.py for importing existing editions"
```

---

### Task 7: Run the backfill (manual, one-time)

This step requires the user's Supabase credentials in a local `.env`.

- [ ] **Step 1: Prompt the user to populate `.env`**

Tell the user:

> Copy `.env.example` to `.env` and fill in the real `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (from the Supabase dashboard → Project Settings → API → `service_role` key). Reply when it's in place.

Wait for confirmation.

- [ ] **Step 2: Run the backfill for real**

Run: `cd /Users/ras/Documents/Magazines && python3 scripts/backfill-db.py`

Expected: one `Backfilled YYYY-MM-DD` line per edition, then `Done: N editions, N*20 stories`.

- [ ] **Step 3: Verify in Supabase**

Prompt the user to run this query in the Supabase SQL editor:

```sql
select edition_date, count(*)
from stories
group by edition_date
order by edition_date;
```

Expected: one row per backfilled date, `count` = 20 for each. Wait for confirmation.

No commit for this task (no code change).

---

### Task 8: Wire `sync-db.py` into `publish-edition.py`

**Files:**
- Modify: `.gitignore`
- Modify: `scripts/publish-edition.py`

Read the current file first. The changes are:

1. **Stop ignoring candidates files** — the existing `.gitignore` has `magazines/candidates-*.json`, which would make the next step silently fail.
2. **Add candidates file to the `git add` list** (inside `git_commit_and_push`).
3. **Have `git_commit_and_push` return the pushed commit SHA** (from `git rev-parse HEAD`).
4. **Add a new `sync_db(date_str, commit_sha)` function** that invokes `scripts/sync-db.py` and tolerates failure.
5. **Remove `cleanup_candidates` and its call** (plus the `--keep-candidates` flag).
6. **In `main()`, call `sync_db()` after `git_commit_and_push()` returns** (skip when `--dry-run` or `--no-push`).

- [ ] **Step 0: Remove `magazines/candidates-*.json` from `.gitignore`**

Open `.gitignore` and delete the line `magazines/candidates-*.json`. Leave all other entries alone. Verify:

Run: `grep -c 'candidates' /Users/ras/Documents/Magazines/.gitignore || echo "clean"`
Expected: `clean` (or `0`).

- [ ] **Step 1: Read the current file**

Run: `cat /Users/ras/Documents/Magazines/scripts/publish-edition.py`

Note the exact line numbers for: the `files = [...]` list inside `git_commit_and_push`, the `cleanup_candidates` function, the `--keep-candidates` arg, and the `if not args.dry_run:` block in `main`.

- [ ] **Step 2: Replace `git_commit_and_push` with this version**

```python
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
```

- [ ] **Step 3: Add `sync_db` helper immediately after `git_commit_and_push`**

```python
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
```

- [ ] **Step 4: Delete `cleanup_candidates` entirely**

Remove the whole function (approx 5 lines: `def cleanup_candidates(date_str):` through the `print` inside it).

- [ ] **Step 5: Update `main()` — remove `--keep-candidates`, call `sync_db`**

Replace the `main()` function with this version:

```python
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
```

- [ ] **Step 6: Smoke-test with `--dry-run`**

Run: `cd /Users/ras/Documents/Magazines && python3 scripts/publish-edition.py magazines/2026-04-16.json --dry-run`

Expected: `Building edition...`, `Build complete`, then `Done!`. No git operations, no DB call. Exit code 0. (If the only available edition has a different date, substitute it.)

- [ ] **Step 7: Commit**

```bash
git add .gitignore scripts/publish-edition.py
git commit -m "Retain candidates files and sync editions to Supabase"
```

---

### Task 9: Update GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/daily-edition.yml`

Changes:
1. After `setup-python`, install requirements.
2. Pass Supabase secrets to the Publish step.

- [ ] **Step 1: Add a dependency-install step after setup-python (line 19 in current file)**

Insert between the `setup-python` step and the `Configure git` step:

```yaml
      - name: Install Python dependencies
        run: pip install -r requirements.txt
```

- [ ] **Step 2: Add Supabase secrets to the Publish step's env**

Modify the existing Publish step (currently lines 36–39) so it has an `env:` block:

```yaml
      - name: Publish
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          DATE=$(date -u +%F)
          python3 scripts/publish-edition.py "magazines/${DATE}.json"
```

- [ ] **Step 3: Prompt the user to add GitHub repo secrets**

Tell the user:

> In the repo's GitHub Settings → Secrets and variables → Actions, add two new repository secrets: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (same values as your local `.env`). Reply when done.

Wait for confirmation.

- [ ] **Step 4: Verify the YAML parses**

Run: `cd /Users/ras/Documents/Magazines && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/daily-edition.yml'))"`

If `yaml` isn't installed, skip and trust git review; otherwise expected: exits 0 with no output.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily-edition.yml
git commit -m "Install deps and pass Supabase secrets in daily workflow"
```

---

### Task 10: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

Two documentation updates: the "No dependencies" line is now wrong, and the new scripts need a mention.

- [ ] **Step 1: Replace the "No dependencies" line**

Find: `No dependencies beyond Python 3 standard library.`

Replace with: `Dependencies: `requirements.txt` has a single line, `supabase>=2.0`, needed only by `scripts/sync-db.py` and `scripts/backfill-db.py`. Everything else (fetch, curate, build, publish) is Python 3 stdlib.`

- [ ] **Step 2: Add the two new scripts to the Architecture bullet list**

After the `scripts/recent-urls.py` bullet, add:

```markdown
- **scripts/sync-db.py** — Post-publish step. Reads `magazines/YYYY-MM-DD.json` + `magazines/candidates-YYYY-MM-DD.json`, upserts to Supabase (`editions` + `stories` tables). Idempotent via `(edition_date, url)`. Failures do not fail the publish. Supports `--dry-run`. Requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.
- **scripts/backfill-db.py** — One-shot helper for importing existing published editions into Supabase (published stories only; historical rejects are gone). Run once after the initial schema is created.
```

- [ ] **Step 3: Add Supabase secrets to the "Required repo secrets" line**

Find: `Required repo secrets: `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`.`

Replace with: `Required repo secrets: `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Document Supabase integration in CLAUDE.md"
```

---

### Task 11: End-to-end verification (manual, no commit)

- [ ] **Step 1: Trigger a manual workflow run**

Prompt the user:

> In the GitHub Actions tab, trigger the "Daily Morning Edition" workflow manually (workflow_dispatch). Watch the run. Expected outcome: all steps green, including the new "Install Python dependencies" step, the "Publish" step completes, and the run includes `Syncing to Supabase...` + `Synced YYYY-MM-DD: 1 edition + N stories` in the Publish step log.

- [ ] **Step 2: Verify the new row in Supabase**

Prompt the user to run:

```sql
select edition_date, status, count(*)
from stories
where edition_date = current_date
group by edition_date, status;
```

Expected: two rows for today, `published` = 20 and `rejected` = some number in the 30–60 range (depending on that day's HN/Pinboard dedup).

If the counts are off, review the Publish step log — common causes are candidates file missing from git add (Task 8 Step 2) or secrets not set on the repo (Task 9 Step 3).

---

## Verification Summary

After all tasks complete, you should have:

- `requirements.txt`, `.env.example`, updated `.gitignore`
- `migrations/0001_init.sql` applied to Supabase
- `scripts/_supabase.py`, `scripts/sync-db.py`, `scripts/backfill-db.py`
- `scripts/publish-edition.py` modified (retains candidates, invokes sync-db)
- `.github/workflows/daily-edition.yml` modified (installs deps, passes secrets)
- Updated `CLAUDE.md`
- Every backfilled edition in the `editions` table
- Every subsequent daily run writing both published and rejected stories to `stories`
- A failing DB sync does not fail the edition publish

That's the complete change set.
