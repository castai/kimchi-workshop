"""Ferment Board API. Small Flask app used for the workshop challenges."""
import os

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
        if status is not None and status not in VALID_STATUSES:
            abort(400, "status must be 'open' or 'completed'")
        cache_key = "tasks:list:all" if status is None else f"tasks:list:{status}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, "request body must be a JSON object")
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            abort(400, "title is required")
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError as exc:
            abort(400, str(exc))
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
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400, "request body must be a JSON object")
        tasks = payload.get("tasks")
        if not isinstance(tasks, list) or not all(
            isinstance(t, dict) and isinstance(t.get("id"), int) for t in tasks
        ):
            abort(400, "tasks must be a list of objects with an integer id")
        merged = store.merge_tasks(tasks)
        cache.invalidate_prefix("tasks:list")
        return jsonify({"synced": len(merged)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        cache.invalidate_prefix("tasks:list")
        return jsonify({"kept": kept})

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.environ.get("PORT", "5000")))
