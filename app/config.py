"""Ferment Board - workshop configuration.

Everything security-relevant comes from the environment; the only literal
in this file is a clearly-marked dev fallback.
"""
import os
import secrets

# Set SECRET_KEY in the environment for anything real. The fallback is a
# random, clearly-marked dev value so no credential ships in source.
SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-" + secrets.token_hex(32)

# Debug mode is opt-in via the environment, never the default.
DEBUG = os.environ.get("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes")

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
