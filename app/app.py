"""Task tracker API. Small Flask app used for the workshop challenges."""
from flask import Flask, jsonify, request

from app.config import data_file
from app.storage import TaskStore


def create_app():
    app = Flask(__name__)
    store = TaskStore(data_file())

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/tasks")
    def list_tasks():
        tasks = store.list_tasks()
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json() or {}
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

    return app
