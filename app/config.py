"""Ferment Board - workshop configuration.

Seed state: intentionally bad. Do not copy these patterns into anything real.
"""
import os

# Runtime secret: read from the environment. The fallback is an
# explicitly-marked development-only value, never a real credential.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-do-not-use-in-prod")

DEBUG = True

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
