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
        return datetime.now(timezone.utc)

    def gc_stale_tasks(self):
        """Remove OPEN tasks whose LAST ACTIVITY is older than STALE_DAYS days.

        Policy: only open tasks are ever reaped - completed tasks are
        never touched. Age is measured since last activity: updated_at or
        completed_at, whichever exists (falling back to created_at for a
        task never touched since creation). An actively-updated task
        survives; a task strictly older than the window is reaped; a task
        exactly at the boundary, or with no timestamps at all, is kept.
        """
        with self._lock:
            data = self._read()
            cutoff = self._now() - timedelta(days=self.stale_days)
            kept = []
            for t in data["tasks"]:
                if t.get("status") != "open":
                    kept.append(t)
                    continue
                stamps = [
                    _parse(t[key])
                    for key in ("updated_at", "completed_at", "created_at")
                    if t.get(key)
                ]
                if not stamps:
                    kept.append(t)
                    continue
                if max(stamps) >= cutoff:
                    kept.append(t)
            data["tasks"] = kept
            self._write(data)
            return len(kept)

    def merge_tasks(self, incoming):
        """Merge tasks from a sync payload (id, title, priority, status).

        Policy: keep whichever copy has the later updated_at; on equal
        timestamps, keep the local task.
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
                else:
                    by_id[tid] = dict(inc)
            data["tasks"] = list(by_id.values())
            self._write(data)
            return data["tasks"]

    def list_tasks(self, status=None, limit=None, offset=0):
        """List tasks, optionally filtered and paginated.

        status filters by task status; limit/offset are applied after
        filtering (limit=None returns everything from offset on). Returns
        the matching tasks as a list.
        """
        data = self._read()
        tasks = data["tasks"]
        if status is not None:
            tasks = [t for t in tasks if t.get("status") == status]
        if offset:
            tasks = tasks[offset:]
        if limit is not None:
            tasks = tasks[:limit]
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
        """Apply field updates and stamp last activity.

        Only known task fields (title, priority, status) are applied.
        updated_at always reflects the update; moving a task to
        "completed" also stamps completed_at. Returns the updated task,
        or None when the id is unknown.
        """
        now = now or self._now()
        with self._lock:
            data = self._read()
            for t in data["tasks"]:
                if t["id"] == task_id:
                    t.update({k: v for k, v in fields.items()
                              if k in ("title", "priority", "status")})
                    t["updated_at"] = _iso(now)
                    if t.get("status") == "completed" and not t.get("completed_at"):
                        t["completed_at"] = _iso(now)
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
    """Parse an ISO timestamp and normalize it to timezone-aware UTC.

    Naive inputs are interpreted as UTC so comparisons never mix aware
    and naive values (the TypeError class from the incident).
    """
    if not s or not isinstance(s, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
