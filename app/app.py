"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, STALE_DAYS, data_file
from app.errors import register_error_handlers
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file(), stale_days=STALE_DAYS)
    cache = TTLCache(CACHE_TTL)
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)
    register_error_handlers(app)

    @app.before_request
    def rate_limit():
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            abort(429)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in {"open", "completed"}:
            abort(400)
        cache_key = f"tasks:list:{status or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        try:
            task = store.create_task(
                title=payload.get("title"),
                priority=payload.get("priority", 1),
            )
        except ValueError as exc:
            abort(400, description=str(exc))
        cache.invalidate_prefix("tasks:")
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
        cache.invalidate_prefix("tasks:")
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            cache.invalidate_prefix("tasks:")
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True) or {}
        tasks = store.merge_tasks(payload.get("tasks", []))
        cache.invalidate_prefix("tasks:")
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        cache.invalidate_prefix("tasks:")
        return jsonify({"kept": kept})

    return app
