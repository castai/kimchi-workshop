"""Ferment Board API. Small Flask app used for the workshop challenges."""
import math

from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

VALID_STATUSES = ("open", "completed")


def create_app():
    app = Flask(__name__)
    register_error_handlers(app)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    @app.before_request
    def rate_limit():
        if request.path == "/health":
            return None  # probes must never be throttled
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            retry = str(math.ceil(retry_after))
            resp = jsonify({
                "error": "rate_limited",
                "message": f"rate limited; retry after {retry}s",
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = retry
            return resp

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in VALID_STATUSES:
            abort(400, description=f"status must be one of: {', '.join(VALID_STATUSES)}")
        key = f"tasks:list:{status or 'all'}"
        cached = cache.get(key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status)
        cache.set(key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description="request body must be a JSON object")
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            abort(400, description="title is required and must be a non-empty string")
        title = title.strip()  # normalize before storing
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError as e:
            abort(400, description=str(e))
        task = store.create_task(title=title, priority=priority)
        cache.invalidate_prefix("tasks:list")
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
        cache.invalidate_prefix("tasks:list")
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            cache.invalidate_prefix("tasks:list")
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True)
        tasks_in = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks_in, list) or not all(
            isinstance(t, dict) and "id" in t for t in tasks_in
        ):
            abort(
                400,
                description="request body must be a JSON object with a tasks list, "
                "each item an object with an id",
            )
        tasks = store.merge_tasks(tasks_in)
        cache.invalidate_prefix("tasks:list")
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        cache.invalidate_prefix("tasks:list")
        return jsonify({"kept": kept})

    return app
