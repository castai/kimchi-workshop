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
        """Remove tasks that have been open too long (over STALE_DAYS days).

        Intended policy: age since LAST ACTIVITY. The materialized
        last_activity_at field is authoritative when present; otherwise
        fall back through updated_at / completed_at / created_at.
        """
        with self._lock:
            data = self._read()
            cutoff = self._now() - timedelta(days=self.stale_days)
            kept = []
            for t in data["tasks"]:
                if t["status"] != "open":
                    kept.append(t)
                    continue
                if _parse(_last_activity_iso(t)) >= cutoff:
                    kept.append(t)
            data["tasks"] = kept
            self._write(data)
            return len(kept)

    def merge_tasks(self, incoming):
        """Merge tasks from a sync payload (id, title, priority, status).

        BUG: blindly overwrites the local task when incoming is older -
        last-writer-wins by incoming. The intended policy: keep whichever
        task has the later updated_at; on equal timestamps, keep local.
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
                        local["last_activity_at"] = _last_activity_iso(local)
                else:
                    merged = dict(inc)
                    merged["last_activity_at"] = _last_activity_iso(merged)
                    by_id[tid] = merged
            data["tasks"] = list(by_id.values())
            self._write(data)
            return data["tasks"]

    def list_tasks(self, status=None, priority=None, limit=None, offset=None, assignee=None):
        """List tasks with optional server-side filtering and pagination.

        The route layer forwards every supported query param here -
        dropping them at the route is what made /tasks serve the full
        table on every request (incident anomaly 3). Pagination is
        limit + offset, offset applied first.
        """
        data = self._read()
        tasks = data["tasks"]
        if status is not None:
            tasks = [t for t in tasks if t.get("status") == status]
        if priority is not None:
            tasks = [t for t in tasks if t.get("priority") == priority]
        if assignee is not None:
            tasks = [t for t in tasks if t.get("assignee") == assignee]
        if offset is not None:
            tasks = tasks[offset:]
        if limit is not None:
            tasks = tasks[:limit]
        return tasks

    def create_task(self, title, priority=1, assignee=None, now=None):
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
                "last_activity_at": _iso(now),
            }
            if assignee:
                task["assignee"] = assignee
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
        """Update mutable fields and bump updated_at.

        updated_at is the activity marker GC keys on - an edit that
        doesn't refresh it leaves the task looking stale, so actively
        edited tasks get reaped mid-edit. Status changes keep the
        completed_at lifecycle consistent (set on complete, cleared on
        reopen).
        """
        now = now or self._now()
        with self._lock:
            data = self._read()
            for t in data["tasks"]:
                if t["id"] == task_id:
                    t.update(fields)
                    if fields.get("status") == "completed" and not t.get("completed_at"):
                        t["completed_at"] = _iso(now)
                    elif fields.get("status") == "open":
                        t.pop("completed_at", None)
                    t["updated_at"] = _iso(now)
                    t["last_activity_at"] = _iso(now)
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
                    t["last_activity_at"] = _iso(now)
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


def _last_activity_iso(t):
    """Most recent of the task's activity timestamps, as an ISO string.

    'Age since last activity' means the MAX of the present stamps -
    an or-chain picks updated_at even when completed_at is more
    recent, wrongly reaping an active task (verified: an open task
    updated 20 days ago but completed yesterday was reaped).
    """
    stamps = [s for s in (
        t.get("last_activity_at"), t.get("updated_at"),
        t.get("completed_at"), t.get("created_at"),
    ) if s]
    if not stamps:
        return ""
    return max(stamps, key=_parse)


def _parse(s):
    # Every timestamp that enters a comparison must be tz-aware: _now()
    # returns aware (now(timezone.utc)), so a naive string - externally
    # seeded data, sync payloads, or pre-tz files - would raise
    # TypeError on comparison. Normalize naive input to UTC.
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
