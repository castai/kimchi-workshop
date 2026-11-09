"""Ferment Board API. Small Flask app used for the workshop challenges."""
import math

from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import (
    CACHE_TTL,
    DEBUG,
    RATE_LIMIT,
    RATE_WINDOW,
    SECRET_KEY,
    STALE_DAYS,
    data_file,
)
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

VALID_STATUSES = ("open", "completed")


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY=SECRET_KEY, DEBUG=DEBUG)

    store = TaskStore(data_file(), stale_days=STALE_DAYS)
    cache = TTLCache(CACHE_TTL)
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    register_error_handlers(app)

    @app.before_request
    def rate_limit():
        # One shared limiter for the whole app: all requests draw from the
        # same window, and hitting the limit is a 429, never a stall.
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            resp = jsonify({"error": "rate_limited", "message": "too many requests"})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(max(1, math.ceil(retry_after)))
            return resp

    @app.after_request
    def invalidate_list_cache(response):
        # Any write can change task lists; never serve a stale cached copy.
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            cache.invalidate_prefix("tasks:list")
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in VALID_STATUSES:
            abort(400, description="status must be 'open' or 'completed'")
        key = f"tasks:list:{status or 'all'}"
        cached = cache.get(key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status)
        cache.set(key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            abort(400, description="title is required and must be a non-empty string")
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError:
            abort(400, description="priority must be an integer between 1 and 5")
        task = store.create_task(title=title, priority=priority)
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
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

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
