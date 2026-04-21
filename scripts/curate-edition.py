#!/usr/bin/env python3
"""
Calls the Claude API to curate a Morning Edition from pre-fetched candidates.

Reads a candidates JSON file produced by fetch-stories.py, sends the candidates
plus the curation prompt to Claude via a forced tool call, validates the
returned edition against the publish schema, and writes magazines/YYYY-MM-DD.json.

Usage:
    python3 scripts/curate-edition.py magazines/candidates-YYYY-MM-DD.json

Environment:
    ANTHROPIC_API_KEY    Required.
    CURATOR_MODEL        Optional; defaults to claude-sonnet-4-6.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAG_DIR = ROOT / "magazines"
PROMPT_PATH = ROOT / "prompts" / "curation-system.md"

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
REQUEST_TIMEOUT = 120

REQUIRED_STORY_FIELDS = {"title", "url", "category", "blurb", "byline", "applies"}
REQUIRED_HN_FIELDS = REQUIRED_STORY_FIELDS | {"hn_link"}


STORY_PROPERTIES = {
    "title": {"type": "string"},
    "url": {"type": "string"},
    "hn_link": {"type": "string"},
    "category": {"type": "string"},
    "applies": {"type": "boolean"},
    "byline": {"type": "string"},
    "blurb": {"type": "string"},
}

SUBMIT_EDITION_TOOL = {
    "name": "submit_edition",
    "description": "Submit the 20-story curated Morning Edition for today.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Edition date in YYYY-MM-DD format.",
            },
            "stories": {
                "type": "array",
                "description": "The 20 story objects as a native JSON array. Do NOT serialize this to a string.",
                "minItems": 20,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": STORY_PROPERTIES,
                    "required": ["title", "url", "category", "applies", "byline", "blurb"],
                },
            },
        },
        "required": ["date", "stories"],
    },
}


def call_anthropic(api_key, model, system_prompt, candidates_payload):
    body = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "tools": [SUBMIT_EDITION_TOOL],
        "tool_choice": {"type": "tool", "name": "submit_edition"},
        "messages": [
            {
                "role": "user",
                "content": (
                    "Here are today's deduplicated story candidates. "
                    "Curate the 20-story edition and call submit_edition.\n\n"
                    "IMPORTANT: Pass `stories` as a native JSON array of objects, "
                    "not as a JSON-encoded string. Do not serialize the array.\n\n"
                    + candidates_payload
                ),
            }
        ],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_with_retry(api_key, model, system_prompt, candidates_payload):
    for attempt in range(2):
        try:
            return call_anthropic(api_key, model, system_prompt, candidates_payload)
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt == 0:
                print(f"  HTTP {e.code} from Anthropic; retrying in 5s...", file=sys.stderr)
                time.sleep(5)
                continue
            detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            print(f"  Anthropic API error ({e.code}): {detail}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            if attempt == 0:
                print(f"  Network error ({e}); retrying in 5s...", file=sys.stderr)
                time.sleep(5)
                continue
            raise
    raise RuntimeError("unreachable")


def extract_tool_input(response):
    stop_reason = response.get("stop_reason")
    for block in response.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == "submit_edition":
            return block["input"]
    raise RuntimeError(
        f"No submit_edition tool_use block in response (stop_reason={stop_reason!r})"
    )


def _repair_json_string(s):
    """Fix common encoding errors in a model-generated JSON string: unescaped
    double quotes and raw control characters inside string values. Uses a state
    machine that tracks whether we're inside a string and escapes problematic
    chars accordingly."""
    out = []
    in_string = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if not in_string:
            out.append(c)
            if c == '"':
                in_string = True
            i += 1
            continue
        if c == '\\' and i + 1 < n:
            out.append(c)
            out.append(s[i + 1])
            i += 2
            continue
        if c == '"':
            j = i + 1
            while j < n and s[j] in ' \t\r\n':
                j += 1
            if j >= n or s[j] in ',}]:':
                out.append(c)
                in_string = False
            else:
                out.append('\\"')
            i += 1
            continue
        if c == '\n':
            out.append('\\n')
        elif c == '\r':
            out.append('\\r')
        elif c == '\t':
            out.append('\\t')
        elif ord(c) < 0x20:
            out.append(f'\\u{ord(c):04x}')
        else:
            out.append(c)
        i += 1
    return ''.join(out)


def validate_edition(edition, expected_date):
    if not isinstance(edition, dict):
        raise ValueError("Tool output is not an object")

    date = edition.get("date")
    if date != expected_date:
        print(
            f"  Warning: model returned date={date!r}, overriding to {expected_date!r}",
            file=sys.stderr,
        )
        edition["date"] = expected_date

    stories = edition.get("stories")
    if isinstance(stories, str):
        try:
            stories = json.loads(stories)
            edition["stories"] = stories
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  stories string parse failed ({e}); repairing...", file=sys.stderr)
            try:
                stories = json.loads(_repair_json_string(stories))
                edition["stories"] = stories
                print(f"  repair succeeded: {len(stories)} stories", file=sys.stderr)
            except (json.JSONDecodeError, ValueError) as e2:
                print(f"  repair failed: {e2}", file=sys.stderr)
    if not isinstance(stories, list) or len(stories) != 20:
        raise ValueError(f"Expected 20 stories, got {len(stories) if isinstance(stories, list) else 'none'}")

    for i, story in enumerate(stories):
        required = REQUIRED_HN_FIELDS if i < 10 else REQUIRED_STORY_FIELDS
        missing = required - set(story.keys())
        if missing:
            raise ValueError(f"Story {i + 1} missing fields: {', '.join(sorted(missing))}")
        if i >= 10 and "hn_link" in story:
            del story["hn_link"]

    return edition


def main():
    parser = argparse.ArgumentParser(description="Curate a Morning Edition via Claude API")
    parser.add_argument("candidates_file", help="Path to candidates JSON from fetch-stories.py")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY=") and not line.startswith("#"):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("CURATOR_MODEL", DEFAULT_MODEL)

    candidates_path = Path(args.candidates_file).resolve()
    if not candidates_path.exists():
        print(f"Error: {candidates_path} not found", file=sys.stderr)
        sys.exit(1)

    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    date_str = candidates.get("date")
    if not date_str:
        print("Error: candidates file has no 'date' field", file=sys.stderr)
        sys.exit(1)

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    candidates_payload = json.dumps(candidates, ensure_ascii=False, indent=2)

    print(f"Curating edition for {date_str} with {model}...", file=sys.stderr)
    response = call_with_retry(api_key, model, system_prompt, candidates_payload)

    usage = response.get("usage", {})
    print(
        f"  Tokens: input={usage.get('input_tokens')} output={usage.get('output_tokens')}",
        file=sys.stderr,
    )

    edition = None
    for attempt in range(3):
        if attempt > 0:
            print(f"  Retrying API call (attempt {attempt + 1}/3)...", file=sys.stderr)
            response = call_with_retry(api_key, model, system_prompt, candidates_payload)
            usage = response.get("usage", {})
            print(
                f"  Tokens: input={usage.get('input_tokens')} output={usage.get('output_tokens')}",
                file=sys.stderr,
            )
        try:
            edition = extract_tool_input(response)
            edition = validate_edition(edition, date_str)
            break
        except (RuntimeError, ValueError) as e:
            print(f"  Validation error (attempt {attempt + 1}): {e}", file=sys.stderr)
            print(f"  Raw tool input: {json.dumps(edition, ensure_ascii=False)[:500] if isinstance(edition, dict) else repr(edition)[:500]}", file=sys.stderr)
            if attempt == 2:
                raise
    assert edition is not None

    out_path = MAG_DIR / f"{date_str}.json"
    out_path.write_text(
        json.dumps(edition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
