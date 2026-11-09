"""JSON-file backed task storage for the workshop app."""
import json
import os
import threading
from datetime import datetime, timedelta, timezone


class TaskStore:
    def __init__(self, path, stale_days=7, cache_ttl=30):
        self.path = path
        self.stale_days = stale_days
        self._lock = threading.RLock()
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

    def _now(self):
        return datetime.utcnow()

    def gc_stale_tasks(self):
        """Remove tasks that have been open too long (over STALE_DAYS days).

        Age is measured since LAST ACTIVITY: updated_at or completed_at,
        whichever exists (falling back to created_at). An actively updated
        task therefore survives; a never-touched old task is reaped. Tasks
        that are not open are never removed.
        """
        with self._lock:
            data = self._read()
            cutoff = self._now() - timedelta(days=self.stale_days)
            kept = []
            for t in data["tasks"]:
                if t["status"] != "open":
                    kept.append(t)
                    continue
                last_activity = (
                    t.get("updated_at") or t.get("completed_at") or t.get("created_at")
                )
                if _parse(last_activity) >= cutoff:
                    kept.append(t)
            data["tasks"] = kept
            self._write(data)
            return len(kept)

    def merge_tasks(self, incoming):
        """Merge tasks from a sync payload (id, title, priority, status).

        Keep whichever task has the later updated_at; on equal
        timestamps, keep local.
        """
        with self._lock:
            data = self._read()
            by_id = {t["id"]: t for t in data["tasks"]}
            for inc in incoming:
                tid = inc["id"]
                if tid in by_id:
                    local = by_id[tid]
                    if _parse(inc.get("updated_at", "")) > _parse(local.get("updated_at", "")):
                        local.update(inc)
                        by_id[tid] = local
                else:
                    by_id[tid] = dict(inc)
            data["tasks"] = list(by_id.values())
            self._write(data)
            return data["tasks"]

    def list_tasks(self, status=None):
        data = self._read()
        tasks = data["tasks"]
        if status is not None:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def create_task(self, title, priority=1, now=None):
        now = now or self._now()
        with self._lock:
            data = self._read()
            task = {
                "id": data["next_id"],
                "title": title,
                "priority": priority,
                "status": "open",
                "created_at": _iso(now),
                "updated_at": _iso(now),
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

    def update_task(self, task_id, fields, now=None):
        with self._lock:
            data = self._read()
            for t in data["tasks"]:
                if t["id"] == task_id:
                    t.update(fields)
                    self._write(data)
                    return t
        return None

    def complete_task(self, task_id, now=None):
        now = now or self._now()
        with self._lock:
            data = self._read()
            for t in data["tasks"]:
                if t["id"] == task_id:
                    t["status"] = "completed"
                    t["completed_at"] = _iso(now)
                    t["updated_at"] = _iso(now)
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


def _iso(dt):
    return dt.isoformat()


def _parse(s):
    """Parse an ISO-8601 timestamp to a naive UTC datetime.

    Naive strings are taken as UTC. Aware timestamps (including a
    trailing "Z") are converted to UTC and made naive so comparisons
    never mix naive and aware values. Empty input maps to datetime.min.
    """
    if not s:
        return datetime.min
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
