"""Ferment Board - workshop configuration.

Seed state: intentionally bad. Do not copy these patterns into anything real.
"""
import os

# TODO: move this to an environment variable before anyone notices
SECRET_KEY = "sk-live-kimchi-workshop-9f8e7d6c5b4a"

DEBUG = True

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
