"""Ferment Board - workshop configuration.

All knobs are environment-overridable and read at call time via the
accessor functions below, so test fixtures can monkeypatch env vars
after import - the same pattern the visible suite uses for TASKS_FILE
(monkeypatch.setenv, then create_app()). The module-level constants
are kept for import-time consumers and the visible contract test.
"""
import os

# Module-level snapshots (read once at import). Prefer the accessor
# functions below anywhere env changes between import and use.
SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-fallback-not-a-credential"
DEBUG = os.environ.get("DEBUG", "0") == "1"
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def secret_key():
    """SECRET_KEY from the environment, read at call time."""
    return os.environ.get("SECRET_KEY") or "dev-fallback-not-a-credential"


def stale_days():
    """GC threshold in days, read at call time."""
    return int(os.environ.get("STALE_DAYS", "7"))


def rate_limit():
    """Max requests per window, read at call time."""
    return int(os.environ.get("RATE_LIMIT", "30"))


def rate_window():
    """Rate-limit window in seconds, read at call time."""
    return float(os.environ.get("RATE_WINDOW", "60"))


def cache_ttl():
    """Read-cache TTL in seconds, read at call time."""
    return float(os.environ.get("CACHE_TTL", "30"))


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
