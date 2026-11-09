"""Ferment Board API. Small Flask app used for the workshop challenges."""
import math

from flask import Flask, abort, g, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

# Shared cache key for the full task list. Centralised so every write path
# invalidates the same entry the read path serves from.
TASKS_LIST_KEY = "tasks:list"

# Status values accepted on ?status= and stored on tasks.
ALLOWED_STATUSES = ("open", "completed")


def _validate_title(title):
    """A title is a non-empty string. Reject None, blanks, and non-strings."""
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    if not title.strip():
        raise ValueError("title must not be empty")
    return title


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    # One limiter per app, shared across requests so the sliding window
    # actually spans the process lifetime (per-request instantiation
    # would let any caller bypass the limit).
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    register_error_handlers(app)

    @app.before_request
    def rate_limit():
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            # Defer to app/errors.py for the response shape; it is the
            # single source of truth for error envelopes.
            g.retry_after = math.ceil(retry_after)
            abort(429, description="rate limit exceeded")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in ALLOWED_STATUSES:
            abort(400, description="invalid status filter")

        cache_key = TASKS_LIST_KEY if status is None else f"{TASKS_LIST_KEY}:{status}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)

        tasks = store.list_tasks(status=status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        # silent=True: the contract says 400 for invalid input; a bad
        # Content-Type would otherwise leak as 415 instead.
        payload = request.get_json(silent=True) or {}
        try:
            title = _validate_title(payload.get("title"))
            priority = validate_priority(payload.get("priority", 1))
        except ValueError as exc:
            abort(400, description=str(exc))

        task = store.create_task(title=title, priority=priority)
        cache.invalidate_prefix(TASKS_LIST_KEY)
        return jsonify(task), 201

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        task = store.get_task(task_id)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(task)

    @app.patch("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        task = store.complete_task(task_id)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        cache.invalidate_prefix(TASKS_LIST_KEY)
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            cache.invalidate_prefix(TASKS_LIST_KEY)
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True) or {}
        tasks = store.merge_tasks(payload.get("tasks", []))
        cache.invalidate_prefix(TASKS_LIST_KEY)
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        cache.invalidate_prefix(TASKS_LIST_KEY)
        return jsonify({"kept": kept})

    return app
