# Supabase Story Tracking — Design

**Date:** 2026-04-17
**Status:** Draft
**Author:** Ras Fincher

## Goal

Extend the daily magazine pipeline to persist every story — both the 20 published per edition and the candidates that were fetched but rejected — into a Supabase Postgres database. This unlocks:

1. **Analytics / history** (primary) — ad-hoc SQL over the full archive.
2. **Data preservation** — retain rich fetch-time metadata (HN scores, Pinboard tags) that today is discarded.
3. **Editorial memory** — a record of what was rejected and why, not just what shipped.
4. **Optional dedup replacement** — not the driver, but the DB will support it if we want to move off the JSON-scan later.

A public API surface is a *maybe*, not a requirement. The schema is internal-only for now; views and RLS policies can be layered on later without a migration.

## Non-goals

- Re-polling HN/Pinboard for delayed metrics (e.g., "how did this story age?"). Interesting, but a separate feature.
- Replacing the existing JSON files. They remain the source of truth for the site build. The DB is a query surface alongside them, not a replacement.
- Public read access on day one. No RLS policies, no PostgREST views, no API consumers.
- Any change to curation output, rendering, or the HTML pipeline.

## Architecture

### Pipeline changes (summary)

```
fetch-stories.py    →  candidates-YYYY-MM-DD.json     (unchanged)
curate-edition.py   →  YYYY-MM-DD.json                 (unchanged)
publish-edition.py  →  build + commit + push + sync-db (NEW: stop deleting candidates)
sync-db.py          →  upserts editions + stories      (NEW)
backfill-db.py      →  one-shot import of existing JSONs (NEW, run once)
```

### Design principles

- **DB sync happens last and is idempotent.** The edition must publish successfully before the DB is touched. If Supabase is unreachable at 4 AM, the edition ships anyway and the next run (or a manual re-run) catches the DB up. Upserts keyed on `(edition_date, url)` make re-runs safe.
- **Candidates files are retained, not deleted.** They become the durable audit trail of rejects (text-diffable in git) and the input to `sync-db.py`. This also means the entire DB can always be rebuilt from the repo.
- **Service-role key, no RLS.** The DB is internal; only the GitHub Actions runner and local scripts write to it. Defer RLS until/unless a public read path is added.

## Data model

### Table: `editions`

| column         | type          | notes                                           |
| -------------- | ------------- | ----------------------------------------------- |
| `date`         | `date`        | Primary key. E.g. `2026-04-17`.                 |
| `fetched_at`   | `timestamptz` | From `candidates-*.json` `fetched_at` field.    |
| `published_at` | `timestamptz` | Time `sync-db.py` runs (i.e., post-push).       |
| `commit_sha`   | `text`        | Git SHA of the publish commit. Nullable (backfill rows can't reliably tie to a specific commit). |

### Table: `stories`

| column           | type      | notes                                                    |
| ---------------- | --------- | -------------------------------------------------------- |
| `id`             | `bigserial` | Primary key.                                           |
| `edition_date`   | `date`    | FK → `editions(date)`, `on delete cascade`.              |
| `status`         | `text`    | Check constraint: `'published' \| 'rejected'`.           |
| `source`         | `text`    | Check constraint: `'hn' \| 'pinboard'`.                  |
| `rank`           | `int`     | 1..20 when `status='published'`, NULL otherwise.         |
| `url`            | `text`    | Not null. Story canonical URL.                           |
| `title`          | `text`    | Not null.                                                |
| `category`       | `text`    | Curator output. NULL for rejected rows.                  |
| `applies`        | `boolean` | Curator output. NULL for rejected rows.                  |
| `byline`         | `text`    | Curator output. NULL for rejected rows.                  |
| `blurb`          | `text`    | Curator output. NULL for rejected rows.                  |
| `hn_link`        | `text`    | Curator output for HN published rows. NULL otherwise.    |
| `hn_id`          | `bigint`  | Fetch-time metadata. Always captured when present.       |
| `hn_score`       | `int`     | Fetch-time metadata.                                     |
| `hn_comments`    | `int`     | Fetch-time metadata.                                     |
| `hn_author`      | `text`    | Fetch-time metadata.                                     |
| `pb_tags`        | `text[]`  | Fetch-time metadata. Empty array when absent.            |
| `pb_description` | `text`    | Fetch-time metadata.                                     |

**Constraints:**
- `unique (edition_date, url)` — idempotency key for upserts.
- `check (status in ('published','rejected'))`
- `check (source in ('hn','pinboard'))`
- `check (status = 'published' or rank is null)` — only published rows have a rank.
- `check (status = 'rejected' or rank is not null)` — every published row has a rank.

**Indexes:**
- `(status, edition_date desc)` — "most recent N published stories"
- `(source, edition_date desc)` — "Pinboard picks over time"
- `gin (pb_tags)` — tag-based queries

## Write points

### `publish-edition.py` changes

1. **Remove the candidates-file deletion.** The `cleanup_candidates(date_str)` call and `--keep-candidates` flag go away; candidates files are now always retained. `git add` the candidates file alongside the edition and html.
2. **After successful `git push`**, capture the pushed commit SHA (`git rev-parse HEAD`) and invoke `sync-db.py` with the date and SHA. Sync failure logs a warning but does **not** fail the publish.

### `scripts/sync-db.py` (new)

```
python3 scripts/sync-db.py YYYY-MM-DD [--commit-sha SHA] [--dry-run]
```

Behavior:
1. Read `magazines/YYYY-MM-DD.json` (published) and `magazines/candidates-YYYY-MM-DD.json` (raw fetch). Both required unless `--dry-run`.
2. Upsert the `editions` row: `(date, fetched_at, published_at=now(), commit_sha)`.
3. For each of the 20 published stories:
   - Build a row with `status='published'`, `rank=i+1`, curator fields populated.
   - Match back to the candidates file by URL to pull fetch-time metadata (`hn_score`, `hn_comments`, `pb_tags`, etc.). If no match, those columns are NULL.
4. For each candidate whose URL is not in the published set:
   - Build a row with `status='rejected'`, `rank=NULL`, curator fields NULL, fetch-time metadata populated.
5. Bulk upsert all rows into `stories` with `on_conflict=(edition_date,url)` updating all columns. This makes re-runs idempotent.
6. `--dry-run` prints the rows it would upsert and exits without a network call.

### `scripts/backfill-db.py` (new, one-shot)

```
python3 scripts/backfill-db.py [--dry-run]
```

Iterates every `magazines/????-??-??.json`, upserts an `editions` row (`commit_sha=NULL`, `fetched_at` from file mtime as a fallback), and inserts the 20 published stories per edition. **No rejects are backfilled** — historical candidates files are already deleted and cannot be recovered. Run once after schema creation, then never again.

## Dependencies & configuration

- Add `requirements.txt` at repo root: `supabase>=2.0`.
- The GitHub Actions workflow installs deps before running the pipeline: `pip install -r requirements.txt`.
- New repo secrets (already-created Supabase project):
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- Local dev: confirm with user how they manage local secrets. Default plan: a gitignored `.env` file loaded by a tiny `os.environ` shim at the top of `sync-db.py` / `backfill-db.py`, or just `export` in the shell before running.

## Schema migration

Supabase project is already created. One-time setup:

1. Apply `migrations/0001_init.sql` (new file, committed to repo) via the Supabase SQL editor. Contains: the two `create table` statements, constraints, indexes.
2. Run `python3 scripts/backfill-db.py` locally to import the ~5 existing published editions.
3. Next scheduled pipeline run picks up `sync-db.py` automatically.

The `migrations/` directory is a plain convention for this repo (not a formal migration tool). If we ever need a second migration we add `0002_*.sql` and apply it manually through the same SQL editor.

## Failure modes

| Scenario                                      | Behavior                                                      |
| --------------------------------------------- | ------------------------------------------------------------- |
| Supabase unreachable during scheduled run     | Edition publishes; `sync-db.py` logs a warning and exits 0. Slack notification is **not** sent (edition itself is fine). DB catches up on next day's run via a "catch up any unsynced editions" check at the top of `sync-db.py`. |
| `sync-db.py` partial failure mid-upsert       | Not a concern — a single `upsert` call per table is atomic.  |
| Re-running sync-db.py on the same date        | Idempotent — upserts update existing rows.                    |
| Local run with stale secrets                  | `sync-db.py` fails fast with a clear error; publish step still completes. |
| Candidates file missing                       | `sync-db.py` syncs published stories only and logs that rejects were unavailable for that date. |

## Catch-up logic

At the top of `sync-db.py`, query `select date from editions order by date desc limit 1`. If the most recent DB edition is older than the most recent `magazines/*.json` on disk by more than 1 day, sync the intervening editions in order before syncing the requested date. This handles the "Supabase was down yesterday" case without manual intervention.

## Testing strategy

- **`--dry-run` on sync-db.py** — print rows, no network. Primary pre-merge test.
- **Idempotency check** — run `sync-db.py` twice against the same date; row counts in `stories` should be unchanged after the second run.
- **Backfill dry-run** — `backfill-db.py --dry-run` over the existing editions, spot-check counts (expect 5 editions × 20 stories = 100 rows).
- **Manual post-merge verification** — after first real scheduled run, query `select count(*) from stories where edition_date = current_date;` and confirm 60-ish rows (20 published + ~40 rejects).

Unit tests are not part of this spec — the existing project has no test suite and this work doesn't justify introducing one. If future work adds a test harness, `sync-db.py`'s pure "JSON → rows" transform is the natural first target.

## Open questions

None blocking. The local-secrets mechanism (`.env` vs shell export) is the only open detail, and it doesn't affect schema or architecture — decided at implementation time.
