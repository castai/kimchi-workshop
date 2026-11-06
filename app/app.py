"""Ferment Board API. Small Flask app used for the workshop challenges."""
import csv
import io

from flask import Flask, Response, abort, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

DEFAULT_PAGE_SIZE = 50
EXPORT_COLUMNS = (
    "id",
    "title",
    "status",
    "priority",
    "created_at",
    "completed_at",
    "updated_at",
)


def create_app():
    app = Flask(__name__)
    register_error_handlers(app)
    store = TaskStore(data_file())
    cache = TTLCache(CACHE_TTL)
    # One limiter per app instance. Building it inside before_request would
    # reset the event window on every request, so no rate could ever trip.
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    @app.before_request
    def rate_limit():
        # SlidingWindowLimiter docstring: "When the limit is hit, requests
        # receive a 429 rather than blocking." acquire() sleeps; try_acquire()
        # reports, and we reject with the rate_limited shape errors.py already
        # documents, plus a Retry-After header.
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            resp = jsonify({"error": "rate_limited", "message": "rate limit exceeded"})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(max(1, int(retry_after) + 1))
            return resp

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in ("open", "completed"):
            abort(400, description="status must be 'open' or 'completed'")
        limit_raw = request.args.get("limit")
        offset_raw = request.args.get("offset")
        paginated = limit_raw is not None or offset_raw is not None
        if paginated:
            try:
                limit = int(limit_raw) if limit_raw is not None else DEFAULT_PAGE_SIZE
                offset = int(offset_raw) if offset_raw is not None else 0
            except ValueError:
                abort(400, description="limit and offset must be integers")
            if limit < 0 or offset < 0:
                abort(400, description="limit and offset must be non-negative")
        key = "tasks:list" if status is None else f"tasks:list:{status}"
        cached = cache.get(key)
        if cached is None:
            cached = store.list_tasks(status)
            cache.set(key, cached)
        if paginated:
            return jsonify(
                {
                    "tasks": cached[offset : offset + limit],
                    "total": len(cached),
                    "limit": limit,
                    "offset": offset,
                }
            )
        return jsonify(cached)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description="request body must be a JSON object")
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            abort(400, description="title must be a non-empty string")
        try:
            priority = validate_priority(payload.get("priority", 1))
        except ValueError as exc:
            abort(400, description=str(exc))
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
        if not isinstance(payload, dict):
            abort(400, description="request body must be a JSON object")
        incoming = payload.get("tasks", [])
        if not isinstance(incoming, list):
            abort(400, description="tasks must be a list")
        merged = store.merge_tasks(incoming)
        cache.invalidate_prefix("tasks:list")
        return jsonify({"synced": len(merged)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        cache.invalidate_prefix("tasks:list")
        return jsonify({"kept": kept})

    @app.get("/tasks/export")
    def export_tasks():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        for task in store.list_tasks():
            if task.get("deleted_at"):
                # Soft-deleted rows (sync-seeded deletes) are gone for
                # consumers too: the export drops them entirely.
                continue
            writer.writerow([task.get(column, "") for column in EXPORT_COLUMNS])
        return Response(buf.getvalue(), mimetype="text/csv")

    return app
