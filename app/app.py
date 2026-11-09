"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

ALLOWED_STATUS = {"open", "completed"}


def create_app():
    app = Flask(__name__)
    register_error_handlers(app)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)

    @app.before_request
    def rate_limit():
        limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)
        limiter.acquire()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in ALLOWED_STATUS:
            abort(400)
        cache_key = f"tasks:list:{status or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json() or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            abort(400)
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError:
            abort(400)
        task = store.create_task(title=title, priority=priority)
        return jsonify(task), 201

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        task = store.get_task(task_id)
        if task is None:
            abort(404)
        return jsonify(task)

    @app.patch("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        task = store.complete_task(task_id)
        if task is None:
            abort(404)
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            return jsonify({"deleted": task_id})
        abort(404)

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json() or {}
        tasks = store.merge_tasks(payload.get("tasks", []))
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        return jsonify({"kept": kept})

    return app
