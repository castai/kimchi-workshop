"""Ferment Board - workshop configuration.

Secrets come from the process environment; the fallback is a clearly
marked dev value that never looks like a credential.
"""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-fallback")

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
