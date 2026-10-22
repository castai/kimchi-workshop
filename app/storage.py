"""JSON-file backed task storage for the workshop app."""
import json
import os
import threading
from datetime import datetime, timezone


class TaskStore:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(path):
            self._write({"next_id": 1, "tasks": []})

    def _read(self):
        with open(self.path) as f:
            return json.load(f)

    def _write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def list_tasks(self, status=None):
        data = self._read()
        tasks = data["tasks"]
        if status is not None:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def create_task(self, title, priority=1):
        with self._lock:
            data = self._read()
            task = {
                "id": data["next_id"],
                "title": title,
                "priority": priority,
                "status": "open",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            data["next_id"] += 1
            data["tasks"].append(task)
            self._write(data)
            return task

    def get_task(self, task_id):
        for t in self._read()["tasks"]:
            if t["id"] == task_id:
                return t
        return None

    def complete_task(self, task_id):
        with self._lock:
            data = self._read()
            for t in data["tasks"]:
                if t["id"] == task_id:
                    t["status"] = "completed"
                    t["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._write(data)
                    return t
        return None

    def delete_task(self, task_id):
        with self._lock:
            data = self._read()
            tasks = data["tasks"]
            for i, t in enumerate(tasks):
                if t["id"] == task_id:
                    del tasks[i]
                    self._write(data)
                    return True
        return False
