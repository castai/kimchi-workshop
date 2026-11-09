"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    register_error_handlers(app)

    def bust_list_cache():
        cache.invalidate_prefix("tasks:list")

    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    @app.before_request
    def rate_limit():
        if request.path == "/health":
            return None
        allowed, _retry_after = limiter.try_acquire()
        if not allowed:
            abort(429)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in ("open", "completed"):
            abort(400)
        key = f"tasks:list:{status or 'all'}"
        cached = cache.get(key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status)
        cache.set(key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        title = payload.get("title")
        if not isinstance(title, str):
            abort(400)
        title = title.strip()
        if not title:
            abort(400)
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError:
            abort(400)
        task = store.create_task(title=title, priority=priority)
        bust_list_cache()
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
        bust_list_cache()
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            bust_list_cache()
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        # Sync requires a JSON object: unparseable bodies, wrong content
        # types, and non-object documents are all client errors (400),
        # matching POST /tasks instead of leaking a 415/500.
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        incoming = payload.get("tasks", [])
        if not isinstance(incoming, list):
            abort(400)
        tasks = store.merge_tasks(incoming)
        bust_list_cache()
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        bust_list_cache()
        return jsonify({"kept": kept})

    return app
