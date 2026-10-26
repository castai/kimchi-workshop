"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

VALID_STATUSES = {"open", "completed"}


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    register_error_handlers(app)

    @app.before_request
    def rate_limit():
        limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)
        limiter.acquire()

    def _invalidate_list_cache():
        cache.invalidate("tasks:list")
        cache.invalidate("tasks:list:open")
        cache.invalidate("tasks:list:completed")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in VALID_STATUSES:
            return jsonify({"error": "bad_request"}), 400
        cache_key = f"tasks:list:{status}" if status is not None else "tasks:list"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "bad_request"}), 400
        if "priority" in payload:
            try:
                priority = validate_priority(payload["priority"])
            except ValueError:
                return jsonify({"error": "bad_request"}), 400
        else:
            priority = 1
        task = store.create_task(title=title, priority=priority)
        _invalidate_list_cache()
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
        _invalidate_list_cache()
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            _invalidate_list_cache()
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True) or {}
        tasks = store.merge_tasks(payload.get("tasks", []))
        _invalidate_list_cache()
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        _invalidate_list_cache()
        return jsonify({"kept": kept})

    return app
