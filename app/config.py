"""Ferment Board - workshop configuration.

Secrets and deployment-specific values live in the process environment.
Nothing here may embed a real credential; the only fallback is a
clearly-marked development placeholder.
"""
import os

# Development-only placeholder, used when SECRET_KEY is unset in the
# environment. It is not a credential and must never look like one.
DEV_FALLBACK_SECRET_KEY = "dev-insecure-change-me"

# Debug mode is a deployment decision (env-driven), never a hardcoded flag.
DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}


def secret_key():
    """Secret key, read at call time so env changes are honored."""
    return os.environ.get("SECRET_KEY") or DEV_FALLBACK_SECRET_KEY


# Single source of truth: the module constant reuses secret_key() so the two
# can never drift. Consumers that inspect the module directly still work.
SECRET_KEY = secret_key()


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")


# Workshop tuning knobs. Read at call time so an env override (e.g. set by
# tests right before create_app) is always honored, without re-importing.

def stale_days():
    return int(os.environ.get("STALE_DAYS", "7"))


def rate_limit():
    return int(os.environ.get("RATE_LIMIT", "30"))


def rate_window():
    return float(os.environ.get("RATE_WINDOW", "60"))


def cache_ttl():
    return float(os.environ.get("CACHE_TTL", "30"))
