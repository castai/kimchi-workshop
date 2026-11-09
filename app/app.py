"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, jsonify, request

from app.cache import TTLCache
from app.config import (
    CACHE_TTL,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    RATE_LIMIT,
    RATE_WINDOW,
    data_file,
)
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

TASK_STATUSES = ("open", "completed")
LIST_CACHE_PREFIX = "tasks:list"


def _parse_paging_args():
    """Parse ?limit and ?offset. Returns (limit, offset) or None if invalid."""
    try:
        limit = int(request.args.get("limit", DEFAULT_PAGE_SIZE))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return None
    if limit < 1 or offset < 0:
        return None
    return min(limit, MAX_PAGE_SIZE), offset


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    # One limiter per app instance: a fresh limiter per request would
    # never actually limit anything.
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    @app.before_request
    def rate_limit():
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            return (
                jsonify({"error": "rate_limited"}),
                429,
                {"Retry-After": str(int(retry_after) + 1)},
            )

    register_error_handlers(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in TASK_STATUSES:
            return jsonify({"error": "bad_request"}), 400
        paging = _parse_paging_args()
        if paging is None:
            return jsonify({"error": "bad_request"}), 400
        limit, offset = paging

        cache_key = LIST_CACHE_PREFIX if status is None else f"{LIST_CACHE_PREFIX}:{status}"
        tasks = cache.get(cache_key)
        if tasks is None:
            tasks = store.list_tasks(status=status)
            cache.set(cache_key, tasks)
        # Bounded response: never serialize the whole table (see
        # PRODUCTION-INCIDENT.md - unbounded GET /tasks pushed p99
        # from 40 ms to 800 ms).
        return jsonify(tasks[offset : offset + limit])

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "bad_request"}), 400
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError:
            return jsonify({"error": "bad_request"}), 400
        task = store.create_task(title=title, priority=priority)
        cache.invalidate_prefix(LIST_CACHE_PREFIX)
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
        cache.invalidate_prefix(LIST_CACHE_PREFIX)
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            cache.invalidate_prefix(LIST_CACHE_PREFIX)
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True) or {}
        incoming = payload.get("tasks", [])
        if not isinstance(incoming, list) or any(
            not isinstance(t, dict) or "id" not in t for t in incoming
        ):
            return jsonify({"error": "bad_request"}), 400
        tasks = store.merge_tasks(incoming)
        cache.invalidate_prefix(LIST_CACHE_PREFIX)
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        cache.invalidate_prefix(LIST_CACHE_PREFIX)
        return jsonify({"kept": kept})

    return app
