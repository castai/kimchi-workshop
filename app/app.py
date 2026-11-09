"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import (
    cache_ttl,
    data_file,
    rate_limit,
    rate_window,
    secret_key,
    stale_days,
)
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

VALID_STATUSES = ("open", "completed")
LIST_CACHE_PREFIX = "tasks:list"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secret_key()
    store = TaskStore(data_file(), stale_days=stale_days())
    cache = TTLCache(cache_ttl())
    # One limiter per app instance, so the window actually fills up across
    # requests instead of resetting on every call.
    limiter = SlidingWindowLimiter(rate_limit(), rate_window())
    register_error_handlers(app)

    def invalidate_list_cache():
        """Every write to the store must drop the read cache."""
        cache.invalidate_prefix(LIST_CACHE_PREFIX)

    @app.before_request
    def enforce_rate_limit():
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            abort(
                429,
                description=f"rate limit exceeded; retry after {retry_after:.1f}s",
            )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in VALID_STATUSES:
            abort(
                400,
                description=f"status must be one of: {', '.join(VALID_STATUSES)}",
            )
        cache_key = f"{LIST_CACHE_PREFIX}:{status or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            abort(400, description="title is required and must be a non-empty string")
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError as exc:
            abort(400, description=str(exc))
        task = store.create_task(title=title, priority=priority)
        invalidate_list_cache()
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
        invalidate_list_cache()
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            invalidate_list_cache()
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True) or {}
        incoming = payload.get("tasks", [])
        if not isinstance(incoming, list) or not all(
            isinstance(t, dict) for t in incoming
        ):
            abort(400, description="tasks must be a list of task objects")
        tasks = store.merge_tasks(incoming)
        invalidate_list_cache()
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        invalidate_list_cache()
        return jsonify({"kept": kept})

    return app
