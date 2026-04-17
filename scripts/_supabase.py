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
