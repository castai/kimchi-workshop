"""Ferment Board - workshop configuration.

Seed state: intentionally bad. Do not copy these patterns into anything real.
"""
import os

# Runtime secret. Must come from the process environment; the fallback is a
# clearly-marked development value, never a credential.
SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-insecure-secret-key-change-me"

DEBUG = True

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
