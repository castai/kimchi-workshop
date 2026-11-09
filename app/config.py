"""Ferment Board - workshop configuration.

Values come from the environment where possible; the SECRET_KEY dev fallback
is intentionally non-production and must never be used in real deployments.
"""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-me")

DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
