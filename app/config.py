"""Ferment Board - workshop configuration."""
import os

# Read from the environment; the fallback is for local development only.
SECRET_KEY = os.environ.get("TASK_API_SECRET", "dev-only-insecure-fallback")

# Debug is a deployment concern, not a source constant.
DEBUG = os.environ.get("TASK_API_DEBUG", "false").lower() == "true"

# Workshop tuning knobs (all overridable by env for tests)
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
