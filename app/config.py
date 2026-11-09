"""Ferment Board - workshop configuration.

All values are environment-driven with safe local defaults; no real
credentials live in source.
"""
import os

# Runtime secret comes from the environment; the fallback is clearly
# marked as dev-only and is never a real credential.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

# Never run with the debug debugger on by default; override with
# DEBUG=1 for local development.
DEBUG = os.environ.get("DEBUG", "false").strip().lower() in ("1", "true", "yes")

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))

# Pagination: GET /tasks responses are bounded - at most MAX_PAGE_SIZE
# tasks per request (see PRODUCTION-INCIDENT.md: unbounded response size
# drove p99 from 40 ms to 800 ms).
DEFAULT_PAGE_SIZE = int(os.environ.get("DEFAULT_PAGE_SIZE", "100"))
MAX_PAGE_SIZE = int(os.environ.get("MAX_PAGE_SIZE", "100"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
