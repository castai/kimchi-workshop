"""Ferment Board - workshop configuration.

Seed state: intentionally bad. Do not copy these patterns into anything real.
"""
import os

# Secrets live in the environment (TASK_API_SECRET); the fallback below is a
# clearly-marked non-secret for local development only.
SECRET_KEY = os.environ.get("TASK_API_SECRET", "dev-only-not-a-real-secret")

# Debug toggle is environment-driven too (TASK_API_DEBUG), defaulting to off.
DEBUG = os.environ.get("TASK_API_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
