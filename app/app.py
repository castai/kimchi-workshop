"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import cache_ttl, data_file, rate_limit, rate_window, stale_days
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore


def create_app():
    app = Flask(__name__)
    register_error_handlers(app)
    store = TaskStore(data_file(), stale_days=stale_days())
    cache = TTLCache(cache_ttl())
    # One limiter per app: the sliding window must persist across requests,
    # otherwise the limit can never trip.
    limiter = SlidingWindowLimiter(rate_limit(), rate_window())

    def bust_list_cache():
        """List responses are cached per filter; drop them on any mutation."""
        cache.invalidate_prefix("tasks:list")

    @app.before_request
    def enforce_rate_limit():
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
        tasks = store.list_tasks(status=status)
        cache.set(key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
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
        payload = request.get_json(silent=True)
        incoming = payload.get("tasks") if isinstance(payload, dict) else None
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
