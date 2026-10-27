"""Ferment Board API. Small Flask app used for the workshop challenges."""
import csv
import io

from flask import Flask, Response, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.errors import register_error_handlers
from app.models import validate_priority
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore

LIST_CACHE_KEY = "tasks:list"


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())
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

    @app.before_request
    def rate_limit():
        limiter.acquire()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status is not None and status not in ("open", "completed"):
            return jsonify({"error": "bad_request"}), 400
        cached = cache.get(LIST_CACHE_KEY) if status is None else None
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status)
        if status is None:
            cache.set(LIST_CACHE_KEY, tasks)
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
    # always reflected.
    @app.get("/tasks/export.csv")
    def export_csv():
        tasks = store.list_tasks()
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
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="tasks.csv"',
            },
        )

    return app
