"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, jsonify, request

from app.cache import TTLCache
from app.config import data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
VALID_STATUSES = ("open", "completed")


def create_app():
    # config read per instance (not at import) so env overrides are honored
    import os
    cache_ttl = float(os.environ.get("CACHE_TTL", "30"))
    rate_limit = int(os.environ.get("RATE_LIMIT", "30"))
    rate_window = float(os.environ.get("RATE_WINDOW", "60"))

    app = Flask(__name__)
    store = TaskStore(data_file())
    cache = TTLCache(cache_ttl)
    limiter = SlidingWindowLimiter(rate_limit, rate_window)

    register_error_handlers(app)

    @app.before_request
    def rate_limit():
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            resp = jsonify({"error": "rate_limited"})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(max(1, int(retry_after) + 1))
            return resp

    @app.after_request
    def no_store_headers(resp):
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    def _invalidate_cache():
        cache.invalidate_prefix("tasks:")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in VALID_STATUSES:
            return jsonify({"error": "bad_request",
                            "message": "status must be open or completed"}), 400
        try:
            limit = min(int(request.args.get("limit", DEFAULT_LIMIT)), MAX_LIMIT)
            offset = max(int(request.args.get("offset", 0)), 0)
            if limit < 1:
                raise ValueError
        except ValueError:
            return jsonify({"error": "bad_request",
                            "message": "limit/offset must be positive integers"}), 400

        key = f"tasks:list:{status}:{limit}:{offset}"
        cached = cache.get(key)
        if cached is not None:
            return jsonify(cached)
        tasks, total = store.list_tasks(status=status, limit=limit, offset=offset)
        body = {"tasks": tasks, "total": total, "limit": limit, "offset": offset}
        cache.set(key, body)
        return jsonify(body)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "bad_request",
                            "message": "body must be JSON"}), 400
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "bad_request",
                            "message": "title is required"}), 400
        priority = payload.get("priority", 1)
        try:
            validate_priority(priority)
        except ValueError as e:
            return jsonify({"error": "bad_request", "message": str(e)}), 400
        task = store.create_task(title=title, priority=priority)
        _invalidate_cache()
        return jsonify(task), 201

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        task = store.get_task(task_id)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(task)

    @app.get("/tasks/export")
    def export_tasks():
        import csv
        import io
        tasks, _total = store.list_tasks(limit=10**9, offset=0)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "title", "status", "priority",
                         "created_at", "completed_at", "updated_at"])
        for t in tasks:
            writer.writerow([t["id"], t["title"], t["status"], t["priority"],
                             t.get("created_at", ""), t.get("completed_at", ""),
                             t.get("updated_at", "")])
        return app.response_class(
            buf.getvalue(),
            status=200,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=tasks.csv"},
        )

    @app.patch("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        task = store.complete_task(task_id)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        _invalidate_cache()
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            _invalidate_cache()
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json(silent=True) or {}
        tasks = store.merge_tasks(payload.get("tasks", []))
        _invalidate_cache()
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        _invalidate_cache()
        return jsonify({"kept": kept})

    return app
