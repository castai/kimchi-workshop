"""Ferment Board - workshop configuration.

Everything on the config surface - including the secret and the debug
flag - is resolved from the process environment at call time, so tests
and deploys can tune behavior without code changes or import-order
sensitivity.
"""
import os


def __getattr__(name):
    """Resolve module attributes dynamically from the environment.

    SECRET_KEY must come from the process environment; the fallback is a
    clearly-marked development value, never a real credential. DEBUG is
    off unless explicitly enabled via the environment.
    """
    if name == "SECRET_KEY":
        return os.environ.get("SECRET_KEY", "dev-insecure-secret-key")
    if name == "DEBUG":
        return os.environ.get("DEBUG", "0").lower() in ("1", "true", "yes", "on")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Pagination surface: the list endpoint never returns the whole table.
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")


def stale_days():
    """Days of inactivity before GC reaps a task. Override with STALE_DAYS."""
    return int(os.environ.get("STALE_DAYS", "7"))


def rate_limit():
    """Requests allowed per rate window. Override with RATE_LIMIT."""
    return int(os.environ.get("RATE_LIMIT", "200"))


def rate_window():
    """Rate limiter window length in seconds. Override with RATE_WINDOW."""
    return float(os.environ.get("RATE_WINDOW", "60"))


def cache_ttl():
    """Task list cache TTL in seconds. Override with CACHE_TTL."""
    return float(os.environ.get("CACHE_TTL", "30"))
