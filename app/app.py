"""Ferment Board API. Small Flask app used for the workshop challenges."""
import csv
import io

from flask import Flask, Response, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, SECRET_KEY, STALE_DAYS, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore


def create_app():
    app = Flask(__name__)
    # Wire the configured secret into the app itself - it was defined
    # in config but never attached, so the app ran without one.
    app.secret_key = SECRET_KEY
    # STALE_DAYS is env-overridable per config; the store must honor it
    # or the GC threshold silently ignores test overrides.
    store = TaskStore(data_file(), stale_days=STALE_DAYS)
    cache = TTLCache(CACHE_TTL)
    register_error_handlers(app)

    # One limiter per app instance: instantiating it inside before_request
    # gave every request a fresh _events list, so the limit was never
    # enforced. The docstring on SlidingWindowLimiter says the events
    # list is what makes it sliding.
    limiter = SlidingWindowLimiter(RATE_LIMIT, RATE_WINDOW)

    def invalidate_read_cache():
        # README: "Writes must invalidate the read cache."
        cache.invalidate_prefix("tasks:")

    def parse_list_params():
        """Parse + validate the query params the list/export endpoints
        share. Returns (status, priority, limit); raises ValueError on
        bad input. Every supported param is forwarded to the store's
        filter method - dropping them at the route is what served the
        full table on every request (incident anomaly 3).
        """
        status = request.args.get("status")
        if status is not None and status not in ("open", "completed"):
            raise ValueError("invalid status")
        priority = request.args.get("priority")
        if priority is not None:
            try:
                priority = int(priority)
            except ValueError:
                raise ValueError("invalid priority")
        limit = request.args.get("limit")
        if limit is not None:
            try:
                limit = int(limit)
            except ValueError:
                raise ValueError("invalid limit")
            if limit < 1:
                raise ValueError("invalid limit")
        return status, priority, limit

    @app.before_request
    def rate_limit():
        # SlidingWindowLimiter docstring: "requests receive a 429 rather
        # than blocking". acquire() sleeps; try_acquire() reports, and we
        # reject with the documented rate_limited error shape (errors.py).
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
        try:
            status, priority, limit = parse_list_params()
        except ValueError:
            return jsonify({"error": "bad_request"}), 400
        # One cache entry per distinct filter combination; writes clear
        # the whole "tasks:" prefix, so every variant stays fresh.
        key = f"tasks:list:{status}:{priority}:{limit}"
        cached = cache.get(key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status, priority=priority, limit=limit)
        cache.set(key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title:
            return jsonify({"error": "bad_request"}), 400
        priority = payload.get("priority", 1)
        try:
            priority = validate_priority(priority)
        except ValueError:
            return jsonify({"error": "bad_request"}), 400
        task = store.create_task(title=title, priority=priority)
        invalidate_read_cache()
        return jsonify(task), 201

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        task = store.get_task(task_id)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(task)

    @app.patch("/tasks/<int:task_id>")
    def update_task(task_id):
        """Wire the store's update_task (it existed, unrouted).

        Accepts title / priority / status; unknown fields are
        ignored. Bad values are 400 bad_request per the contract,
        missing ids are 404. The write invalidates the read cache.
        """
        payload = request.get_json(silent=True) or {}
        fields = {}
        if "title" in payload:
            title = payload["title"]
            if not isinstance(title, str) or not title:
                return jsonify({"error": "bad_request"}), 400
            fields["title"] = title
        if "priority" in payload:
            try:
                fields["priority"] = validate_priority(payload["priority"])
            except ValueError:
                return jsonify({"error": "bad_request"}), 400
        if "status" in payload:
            if payload["status"] not in ("open", "completed"):
                return jsonify({"error": "bad_request"}), 400
            fields["status"] = payload["status"]
        if not fields:
            return jsonify({"error": "bad_request"}), 400
        task = store.update_task(task_id, fields)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        invalidate_read_cache()
        return jsonify(task)

    @app.patch("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        task = store.complete_task(task_id)
        if task is None:
            return jsonify({"error": "not_found"}), 404
        invalidate_read_cache()
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if store.delete_task(task_id):
            invalidate_read_cache()
            return jsonify({"deleted": task_id})
        return jsonify({"error": "not_found"}), 404

    @app.post("/tasks/sync")
    def sync_tasks():
        payload = request.get_json() or {}
        tasks = store.merge_tasks(payload.get("tasks", []))
        invalidate_read_cache()
        return jsonify({"synced": len(tasks)})

    @app.post("/tasks/gc")
    def gc_tasks():
        kept = store.gc_stale_tasks()
        invalidate_read_cache()
        return jsonify({"kept": kept})

    # Bulk export. README: "Deletes must update export" — the CSV is
    # generated live from the store on every request, so deletes are
    # always reflected. Honors the same filters as the list endpoint.
    @app.get("/tasks/export")
    @app.get("/tasks/export.csv")
    def export_csv():
        try:
            status, priority, limit = parse_list_params()
        except ValueError:
            return jsonify({"error": "bad_request"}), 400
        tasks = store.list_tasks(status=status, priority=priority, limit=limit)
        buf = io.StringIO()
        # Stable header order; ids first so spreadsheets don't bury it.
        fieldnames = [
            "id", "title", "priority", "status",
            "created_at", "updated_at", "completed_at",
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for t in tasks:
            writer.writerow({k: t.get(k, "") for k in fieldnames})
        # content_type (not mimetype) so Flask doesn't append a charset
        # suffix — exact "text/csv" per the export contract.
        return Response(
            buf.getvalue(),
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="tasks.csv"',
            },
        )

    return app
