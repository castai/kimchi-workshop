"""Ferment Board API. Small Flask app used for the workshop challenges."""
import csv
import io
import math

from flask import Flask, abort, jsonify, request

from app.cache import TTLCache
from app.config import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    cache_ttl,
    data_file,
    rate_limit,
    rate_window,
    stale_days,
)
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
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            response = jsonify({"error": "rate_limited",
                                "message": "Rate limit exceeded"})
            response.status_code = 429
            response.headers["Retry-After"] = str(max(1, math.ceil(retry_after)))
            return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    def cached_tasks(status):
        """Full (filtered) task list, cached per filter."""
        key = f"tasks:list:{status or 'all'}"
        cached = cache.get(key)
        if cached is None:
            cached = store.list_tasks(status=status)
            cache.set(key, cached)
        return cached

    def parse_pagination():
        """Parse ?limit/?offset into (limit, offset); 400 on garbage."""
        def _int_arg(name, default):
            raw = request.args.get(name)
            if raw is None:
                return default
            try:
                value = int(raw)
            except ValueError:
                abort(400)
            if value < 0:
                abort(400)
            return value

        limit = min(_int_arg("limit", DEFAULT_PAGE_LIMIT), MAX_PAGE_LIMIT)
        return limit, _int_arg("offset", 0)

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in ("open", "completed"):
            abort(400)
        paginated = "limit" in request.args or "offset" in request.args
        if status is not None and not paginated:
            # Plain filtered listing (documented: ?status=open|completed).
            return jsonify(cached_tasks(status))
        tasks = cached_tasks(status)
        limit, offset = parse_pagination()
        return jsonify({
            "tasks": tasks[offset:offset + limit],
            "total": len(tasks),
            "limit": limit,
            "offset": offset,
        })

    @app.get("/tasks/export")
    def export_tasks():
        """Full CSV export; always reflects the current store (never cached)."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        columns = ("id", "title", "status",
                   "created_at", "completed_at", "updated_at")
        writer.writerow(columns)
        for task in store.list_tasks():
            writer.writerow([task.get(column, "") for column in columns])
        response = app.response_class(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=tasks.csv"
        return response

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

    @app.patch("/tasks/<int:task_id>")
    def update_task(task_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        fields = {}
        if "title" in payload:
            title = payload["title"]
            if not isinstance(title, str) or not title.strip():
                abort(400)
            fields["title"] = title
        if "priority" in payload:
            try:
                fields["priority"] = validate_priority(payload["priority"])
            except ValueError:
                abort(400)
        if "status" in payload:
            if payload["status"] not in ("open", "completed"):
                abort(400)
            fields["status"] = payload["status"]
        task = store.update_task(task_id, fields)
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
