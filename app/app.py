"""Ferment Board API. Small Flask app used for the workshop challenges."""
from flask import Flask, jsonify, request

from app.cache import TTLCache
from app.config import CACHE_TTL, RATE_LIMIT, RATE_WINDOW, data_file
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore


def create_app():
    app = Flask(__name__)
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
        status = request.args.get('status', default=None, type=str) 
        cache_key = "tasks:list"
        if status is not None:
            cache_key = cache_key + ":" + str(status)
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached)
        tasks = store.list_tasks(status=status)
        cache.set(cache_key, tasks)
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json() or {}
        if "title" not in payload:
            return jsonify({"error":"bad_request"}), 400
        try:
            priority = int(payload.get("priority",1))
        except:
            return jsonify({"error":"bad_request"}), 400
        if priority < 1 or priority > 5:
            return jsonify({"error":"bad_request"}), 400
        task = store.create_task(
            title=payload["title"],
            priority=payload.get("priority", 1),
        )
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
