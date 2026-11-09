"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

LIST_CACHE_PREFIX = "tasks:list"
VALID_STATUSES = ("open", "completed")


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    # One limiter for the whole app: the window must span requests.
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    register_error_handlers(app)

    @app.before_request
    def rate_limit():
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            response = jsonify({"error": "rate_limited"})
            response.status_code = 429
            response.headers["Retry-After"] = str(int(retry_after) + 1)
            return response

    def invalidate_list_cache():
        """Drop cached list responses after any mutation."""
        cache.invalidate_prefix(LIST_CACHE_PREFIX)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in VALID_STATUSES:
            return jsonify({"error": "bad_request"}), 400
        cache_key = f"{LIST_CACHE_PREFIX}:{status or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "bad_request"}), 400
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "bad_request"}), 400
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError:
            return jsonify({"error": "bad_request"}), 400
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
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "bad_request"}), 400
        incoming = payload.get("tasks", [])
        if not isinstance(incoming, list) or not all(
            isinstance(t, dict) and "id" in t for t in incoming
        ):
            return jsonify({"error": "bad_request"}), 400
        tasks = store.merge_tasks(incoming)
        invalidate_list_cache()
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        invalidate_list_cache()
        return jsonify({"kept": kept})

    return app
