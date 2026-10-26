"""Ferment Board - workshop configuration.

All knobs are environment-overridable so tests can tune them at runtime.
"""
import os

# Runtime secret. Must come from the process environment; the fallback
# below is a clearly-marked development value, never a real credential.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")

DEBUG = True


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")


def stale_days():
    """Days of inactivity before GC reaps a task. Override with STALE_DAYS."""
    return int(os.environ.get("STALE_DAYS", "7"))


def rate_limit():
    """Requests allowed per rate window. Override with RATE_LIMIT."""
    return int(os.environ.get("RATE_LIMIT", "30"))


def rate_window():
    """Rate limiter window length in seconds. Override with RATE_WINDOW."""
    return float(os.environ.get("RATE_WINDOW", "60"))


def cache_ttl():
    """Task list cache TTL in seconds. Override with CACHE_TTL."""
    return float(os.environ.get("CACHE_TTL", "30"))
