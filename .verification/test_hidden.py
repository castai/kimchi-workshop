"""Hidden verification suite - THE REAL BAR.

This suite is NOT shipped to participants. The workshop scorer runs it
against submission PRs; points come from how much of this contract the
submission satisfies. It encodes the INTENDED behavior of the app,
not the buggy seed. Format: two hours of honest work for a strong
participant with an agent; superficial fixes stall early.

Sections:
  V1  security hygiene (config, debug)
  V2  validation contract (400s, shapes)
  V3  pagination + filter (cache correctness)
  V4  CSV export contract
  V5  rate limiting (shared limiter, 429s, Retry-After)
  V6  garbage collection policy (last-activity recency)
  V7  sync merge policy (last-write-wins with tie to local)
  V8  timestamp hygiene (UTC-aware, round-trips)
  V9  cache invalidation on writes
"""
import json
import os
import sys
import threading
import time as _time
from datetime import datetime, timedelta, timezone

import pytest

# repo root, whether run from .verification/ or tests/
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE) if os.path.basename(_HERE) == ".verification" \
    else os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

# reuse the visible suite's fixtures (store_path / app / client)
sys.path.insert(0, os.path.join(_ROOT, "tests"))
from conftest import store_path, app, client  # noqa: F401, E402

# All tests run with a fresh store per test via conftest fixtures.


def _parse_ts(s):
    return datetime.fromisoformat(s)


# --- V1 security hygiene -----------------------------------------------------

def test_v1_secret_from_env(monkeypatch):
    from app import config
    monkeypatch.setenv("TASK_API_SECRET", "unit-test-secret")
    import importlib
    importlib.reload(config)
    assert config.SECRET_KEY == "unit-test-secret"
    assert not config.SECRET_KEY.startswith("sk-")


def test_v1_debug_off_by_default(monkeypatch):
    monkeypatch.delenv("TASK_API_DEBUG", raising=False)
    from app import config
    import importlib
    importlib.reload(config)
    assert config.DEBUG is False


# --- V2 validation contract --------------------------------------------------

def test_v2_missing_title_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_v2_bad_priority_400(client):
    assert client.post("/tasks", json={"title": "x", "priority": "high"}).status_code == 400
    assert client.post("/tasks", json={"title": "x", "priority": 99}).status_code == 400
    assert client.post("/tasks", json={"title": "x", "priority": True}).status_code == 400


def test_v2_non_json_body_400(client):
    resp = client.post("/tasks", data="not json", content_type="text/plain")
    assert resp.status_code == 400


# --- V3 pagination + filter (cache correctness) -------------------------------

def test_v3_pagination_defaults(client):
    for i in range(25):
        client.post("/tasks", json={"title": f"t{i}"})
    resp = client.get("/tasks?limit=10")
    body = resp.get_json()
    assert isinstance(body, dict)
    assert body["total"] == 25
    assert len(body["tasks"]) == 10
    assert body["limit"] == 10
    assert body["offset"] == 0


def test_v3_pagination_custom(client):
    for i in range(15):
        client.post("/tasks", json={"title": f"t{i}"})
    body = client.get("/tasks?limit=5&offset=10").get_json()
    assert [t["id"] for t in body["tasks"]] == [11, 12, 13, 14, 15]


def test_v3_pagination_cap(client):
    for i in range(150):
        r = client.post("/tasks", json={"title": f"t{i}"})
        assert r.status_code == 201
    body = client.get("/tasks").get_json()
    assert body["limit"] == 20
    assert len(body["tasks"]) == 20
    assert body["total"] == 150


def test_v3_filter_and_cache_independence(client):
    client.post("/tasks", json={"title": "one"})
    client.post("/tasks", json={"title": "two"})
    client.patch("/tasks/1/complete")
    open_list = client.get("/tasks?status=open").get_json()
    assert open_list["total"] == 1
    assert open_list["tasks"][0]["title"] == "two"
    all_list = client.get("/tasks").get_json()
    assert all_list["total"] == 2


def test_v3_cache_invalidation_on_write(client):
    client.post("/tasks", json={"title": "one"})
    first = client.get("/tasks").get_json()
    client.post("/tasks", json={"title": "two"})
    second = client.get("/tasks").get_json()
    assert second["total"] == first["total"] + 1


# --- V4 CSV export ------------------------------------------------------------

def test_v4_export_headers_and_body(client):
    client.post("/tasks", json={"title": "alpha"})
    resp = client.get("/tasks/export")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    lines = resp.get_data(as_text=True).strip().splitlines()
    assert lines[0] == "id,title,status,priority,created_at,completed_at,updated_at"
    assert "alpha" in lines[1]


def test_v4_export_reflects_changes(client):
    t = client.post("/tasks", json={"title": "beta"}).get_json()
    client.delete(f"/tasks/{t['id']}")
    body = client.get("/tasks/export").get_data(as_text=True)
    assert "beta" not in body


# --- V5 rate limiting ----------------------------------------------------------

def test_v5_limiter_shared_not_per_request():
    """The limiter must be shared across requests, not constructed per-request."""
    from app import app as app_module
    src = open(app_module.__file__).read()
    # crude structural check: limiter must be constructed outside before_request
    assert "before_request" in src
    lines = src.splitlines()
    for i, l in enumerate(lines):
        if "def rate_limit" in l:
            # the enclosing function should reference an outer-scope limiter,
            # not build a new SlidingWindowLimiter inside itself
            block = "\n".join(lines[i:i+10])
            assert "SlidingWindowLimiter(" not in block, (
                "rate limiter is constructed per-request - it must be shared"
            )


def test_v5_429_after_limit(monkeypatch, store_path):
    monkeypatch.setenv("TASKS_FILE", store_path)
    monkeypatch.setenv("RATE_LIMIT", "3")
    monkeypatch.setenv("RATE_WINDOW", "2")
    from app.app import create_app
    application = create_app()
    application.config["TESTING"] = True
    c = application.test_client()
    codes = [c.get("/health").status_code for _ in range(5)]
    assert 429 in codes, f"no 429 within 5 requests at limit 3: {codes}"


def test_v5_retry_after_header(monkeypatch, store_path):
    monkeypatch.setenv("TASKS_FILE", store_path)
    monkeypatch.setenv("RATE_LIMIT", "2")
    monkeypatch.setenv("RATE_WINDOW", "2")
    from app.app import create_app
    application = create_app()
    application.config["TESTING"] = True
    c = application.test_client()
    for _ in range(2):
        c.get("/health")
    resp = c.get("/health")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


# --- V6 GC policy (last-activity recency) --------------------------------------

def _seed_store(path, tasks):
    with open(path, "w") as f:
        json.dump({"next_id": len(tasks) + 1, "tasks": tasks}, f)


def test_v6_gc_keeps_active_olds(store_path):
    from app.storage import TaskStore
    now = datetime.now(timezone.utc)
    tasks = [
        # created 30 days ago, updated 1 day ago: KEEP (active)
        {"id": 1, "title": "active old", "status": "open",
         "created_at": (now - timedelta(days=30)).isoformat(),
         "updated_at": (now - timedelta(days=1)).isoformat()},
        # created 30 days ago, never updated: REAP
        {"id": 2, "title": "stale old", "status": "open",
         "created_at": (now - timedelta(days=30)).isoformat()},
    ]
    _seed_store(store_path, tasks)
    s = TaskStore(store_path, stale_days=7)
    kept = s.gc_stale_tasks()
    titles = [t["title"] for t in s.list_tasks(limit=10**9)[0]]
    assert "active old" in titles
    assert "stale old" not in titles


def test_v6_gc_never_touches_completed(store_path):
    from app.storage import TaskStore
    now = datetime.now(timezone.utc)
    tasks = [
        {"id": 1, "title": "done long ago", "status": "completed",
         "created_at": (now - timedelta(days=400)).isoformat(),
         "updated_at": (now - timedelta(days=399)).isoformat(),
         "completed_at": (now - timedelta(days=399)).isoformat()},
    ]
    _seed_store(store_path, tasks)
    s = TaskStore(store_path, stale_days=7)
    s.gc_stale_tasks()
    assert [t["title"] for t in s.list_tasks(limit=10**9)[0]] == ["done long ago"]


def test_v6_gc_boundary(store_path):
    """Exactly STALE_DAYS old with no activity is reaped; a second newer is kept."""
    from app.storage import TaskStore
    now = datetime.now(timezone.utc)
    tasks = [
        {"id": 1, "title": "edge", "status": "open",
         "created_at": (now - timedelta(days=7, seconds=5)).isoformat()},
        {"id": 2, "title": "fresh", "status": "open",
         "created_at": (now - timedelta(days=6)).isoformat()},
    ]
    _seed_store(store_path, tasks)
    s = TaskStore(store_path, stale_days=7)
    s.gc_stale_tasks()
    titles = [t["title"] for t in s.list_tasks(limit=10**9)[0]]
    assert titles == ["fresh"]


# --- V7 sync merge policy --------------------------------------------------------

def test_v7_merge_last_write_wins(store_path):
    from app.storage import TaskStore
    s = TaskStore(store_path)
    local = s.create_task("v1", now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    # incoming is OLDER: must not overwrite local
    incoming = [{"id": local["id"], "title": "v0", "status": "open",
                 "created_at": local["created_at"],
                 "updated_at": (datetime(2025, 12, 1, tzinfo=timezone.utc)).isoformat()}]
    s.merge_tasks(incoming)
    assert s.get_task(local["id"])["title"] == "v1"
    # incoming is NEWER: overwrites
    incoming2 = [{"id": local["id"], "title": "v2", "status": "open",
                  "created_at": local["created_at"],
                  "updated_at": (datetime(2026, 2, 1, tzinfo=timezone.utc)).isoformat()}]
    s.merge_tasks(incoming2)
    assert s.get_task(local["id"])["title"] == "v2"


def test_v7_merge_equal_ts_keeps_local(store_path):
    from app.storage import TaskStore
    s = TaskStore(store_path)
    local = s.create_task("local", now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    incoming = [{"id": local["id"], "title": "remote", "status": "open",
                 "created_at": local["created_at"],
                 "updated_at": local["updated_at"]}]
    s.merge_tasks(incoming)
    assert s.get_task(local["id"])["title"] == "local"


def test_v7_merge_creates_missing(store_path):
    from app.storage import TaskStore
    s = TaskStore(store_path)
    s.create_task("local only")
    incoming = [{"id": 99, "title": "from remote", "status": "open",
                 "created_at": "2026-01-01T00:00:00+00:00",
                 "updated_at": "2026-01-02T00:00:00+00:00"}]
    s.merge_tasks(incoming)
    assert s.get_task(99) is not None
    assert s.get_task(99)["title"] == "from remote"


# --- V8 timestamp hygiene ---------------------------------------------------------

def test_v8_timestamps_are_utc_aware(client):
    t = client.post("/tasks", json={"title": "ts"}).get_json()
    ts = _parse_ts(t["created_at"])
    assert ts.tzinfo is not None, "created_at must carry timezone info"


def test_v8_timestamps_round_trip(client):
    t = client.post("/tasks", json={"title": "ts"}).get_json()
    ts = _parse_ts(t["created_at"])
    assert ts.isoformat() == t["created_at"]


def test_v8_complete_sets_completed_at(client):
    t = client.post("/tasks", json={"title": "done"}).get_json()
    done = client.patch(f"/tasks/{t['id']}/complete").get_json()
    assert done["completed_at"]
    assert _parse_ts(done["completed_at"]).tzinfo is not None


# --- V9 cache invalidation --------------------------------------------------------

def test_v9_create_invalidates_list_cache(client):
    a = client.get("/tasks").get_json()
    client.post("/tasks", json={"title": "new"})
    b = client.get("/tasks").get_json()
    assert b["total"] == a["total"] + 1


def test_v9_update_invalidates_list_cache(client):
    t = client.post("/tasks", json={"title": "x"}).get_json()
    client.get("/tasks")
    client.patch(f"/tasks/{t['id']}/complete")
    body = client.get("/tasks?status=completed").get_json()
    assert body["total"] == 1
