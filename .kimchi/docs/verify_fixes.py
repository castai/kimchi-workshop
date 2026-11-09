"""Verify behaviors beyond the visible suite: 429s, cache freshness,
status-filter validation, gc and merge policies, config contract."""
import importlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, "/home/nvarga/kimchi-workshop")

import app.app as appmod

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("  -> " + str(detail)) if not cond else "")


def fresh_app(rate_limit=30, stale_days=7, cache_ttl=30):
    appmod.RATE_LIMIT = rate_limit
    appmod.RATE_WINDOW = 60
    appmod.CACHE_TTL = cache_ttl
    appmod.STALE_DAYS = stale_days
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)
    os.environ["TASKS_FILE"] = path
    app = appmod.create_app()
    app.config["TESTING"] = True
    return app, path


# --- 1. cache freshness: writes invalidate the cached list ------------------
app, path = fresh_app(cache_ttl=60)  # long TTL: only invalidation can save us
c = app.test_client()
c.post("/tasks", json={"title": "one"})
c.get("/tasks")  # warm the list cache with 1 task
c.post("/tasks", json={"title": "two"})
listing = c.get("/tasks").get_json()
check("cache invalidated on POST", len(listing) == 2, listing)

task_id = listing[0]["id"]
c.patch(f"/tasks/{task_id}/complete")
statuses = [t["status"] for t in c.get("/tasks").get_json() if t["id"] == task_id]
check("cache invalidated on PATCH", statuses == ["completed"], statuses)

c.get("/tasks?status=open")  # warm the filtered cache too
c.delete(f"/tasks/{task_id}")
check("cache invalidated on DELETE (filtered)",
      len(c.get("/tasks?status=open").get_json()) == 1)
check("cache invalidated on DELETE (all)", len(c.get("/tasks").get_json()) == 1)

# --- 2. status filter validation --------------------------------------------
r = c.get("/tasks?status=banana")
check("invalid status -> 400 bad_request",
      r.status_code == 400 and r.get_json()["error"] == "bad_request",
      (r.status_code, r.get_json()))
check("valid status -> 200", c.get("/tasks?status=open").status_code == 200)
check("no status -> 200", c.get("/tasks").status_code == 200)

# --- 3. title/priority validation edge cases ---------------------------------
r = c.post("/tasks", json={"title": "   "})
check("whitespace title -> 400", r.status_code == 400, r.status_code)
r = c.post("/tasks", json={"title": 42})
check("non-string title -> 400", r.status_code == 400, r.status_code)
r = c.post("/tasks", data="", content_type="application/json")
check("empty body -> 400", r.status_code == 400, r.status_code)
r = c.post("/tasks", json={"title": "ok", "priority": True})
check("bool priority -> 400", r.status_code == 400, r.status_code)
r = c.post("/tasks", json={"title": "ok", "priority": 3})
check("valid priority -> 201", r.status_code == 201, r.status_code)

# --- 4. rate limiting: shared limiter, 429 + Retry-After ---------------------
app, path = fresh_app(rate_limit=3)
c = app.test_client()
codes = [c.get("/health").status_code for _ in range(3)]
r = c.get("/health")
check("first 3 within limit", codes == [200, 200, 200], codes)
check("4th request -> 429 rate_limited",
      r.status_code == 429 and r.get_json()["error"] == "rate_limited",
      (r.status_code, r.get_json()))
check("Retry-After header >= 1s", int(r.headers.get("Retry-After", "0")) >= 1,
      dict(r.headers))

# --- 5. gc policy: age since last activity -----------------------------------
store = appmod.TaskStore(path, stale_days=7)
old = (datetime.utcnow() - timedelta(days=10)).isoformat()
recent = (datetime.utcnow() - timedelta(hours=1)).isoformat()
seed = {"next_id": 5, "tasks": [
    {"id": 1, "title": "old never touched", "priority": 1, "status": "open",
     "created_at": old, "updated_at": old},
    {"id": 2, "title": "old but actively updated", "priority": 1, "status": "open",
     "created_at": old, "updated_at": recent},
    {"id": 3, "title": "completed long ago", "priority": 1, "status": "completed",
     "created_at": old, "completed_at": old},
    {"id": 4, "title": "open with recent completed_at", "priority": 1, "status": "open",
     "created_at": old, "completed_at": recent},
]}
with open(path, "w") as f:
    json.dump(seed, f)
kept = store.gc_stale_tasks()
titles = sorted(t["title"] for t in json.load(open(path))["tasks"])
check("gc reaps never-touched old task", "old never touched" not in titles, titles)
check("gc keeps actively-updated task", "old but actively updated" in titles, titles)
check("gc keeps completed tasks", "completed long ago" in titles, titles)
check("gc treats completed_at as last activity",
      "open with recent completed_at" in titles, titles)
check("gc kept count", kept == 3, kept)

# --- 6. merge policy: later updated_at wins, ties keep local -----------------
with open(path, "w") as f:
    json.dump({"next_id": 2, "tasks": [
        {"id": 1, "title": "local", "priority": 2, "status": "open",
         "updated_at": "2026-11-09T12:00:00"},
    ]}, f)
store.merge_tasks([{"id": 1, "title": "older incoming",
                    "updated_at": "2026-11-08T00:00:00"}])
t = [x for x in json.load(open(path))["tasks"] if x["id"] == 1][0]
check("older incoming does not clobber local", t["title"] == "local", t)
store.merge_tasks([{"id": 1, "title": "newer incoming",
                    "updated_at": "2026-11-09T13:00:00"}])
t = [x for x in json.load(open(path))["tasks"] if x["id"] == 1][0]
check("newer incoming wins", t["title"] == "newer incoming", t)
store.merge_tasks([{"id": 1, "title": "equal incoming",
                    "updated_at": "2026-11-09T13:00:00"}])
t = [x for x in json.load(open(path))["tasks"] if x["id"] == 1][0]
check("equal timestamps keep local", t["title"] == "newer incoming", t)

# --- 7. config contract -------------------------------------------------------
import app.config as config

os.environ.pop("SECRET_KEY", None)
os.environ.pop("FLASK_DEBUG", None)
config = importlib.reload(config)
check("SECRET_KEY is not a literal sk- credential",
      not config.SECRET_KEY.startswith("sk-"), config.SECRET_KEY[:20])
check("DEBUG defaults to off", config.DEBUG is False, config.DEBUG)
os.environ["SECRET_KEY"] = "from-env"
os.environ["FLASK_DEBUG"] = "1"
config = importlib.reload(config)
check("SECRET_KEY honors env var", config.SECRET_KEY == "from-env", config.SECRET_KEY)
check("DEBUG opt-in via env", config.DEBUG is True, config.DEBUG)

failed = [name for name, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
