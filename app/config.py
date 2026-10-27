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
# The public contract names are TASK_API_SECRET / TASK_API_DEBUG;
# the classic SECRET_KEY / DEBUG names are kept as sensible fallbacks.
SECRET_KEY = (
    os.environ.get("TASK_API_SECRET")
    or os.environ.get("SECRET_KEY")
    or ""
)
DEBUG = (os.environ.get("TASK_API_DEBUG") or os.environ.get("DEBUG", "0")) == "1"
STALE_DAYS = float(os.environ.get("STALE_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
RATE_WINDOW = float(os.environ.get("RATE_WINDOW", "60"))
CACHE_TTL = float(os.environ.get("CACHE_TTL", "30"))


def secret_key():
    """Secret from the environment, read at call time.

    Public contract name is TASK_API_SECRET; SECRET_KEY is the
    fallback.
    """
    return os.environ.get("TASK_API_SECRET") or os.environ.get("SECRET_KEY") or ""


def debug():
    """Debug flag from the environment, read at call time.

    Public contract name is TASK_API_DEBUG; DEBUG is the fallback.
    """
    raw = os.environ.get("TASK_API_DEBUG") or os.environ.get("DEBUG", "0")
    return raw == "1"


def stale_days():
    """GC threshold in days, read at call time.

    Fractional values are honored (float) so sub-day thresholds -
    e.g. tests reaping just-created tasks with STALE_DAYS=0.001 -
    don't crash the int() parse.
    """
    return float(os.environ.get("STALE_DAYS", "7"))


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
