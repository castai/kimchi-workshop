"""Regression tests for the task-api policy fixes.

These live OUTSIDE tests/ (the read-only contract suite) and pin the
policies the module docstrings specify: GC by last activity, sync merge
tie-breaks, write-through cache invalidation, request validation, and
rate limiting behavior.

Run with: python -m pytest regression_tests/ -q
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone


def _utcnow_naive():
    """Naive UTC timestamp, matching the store's timestamp format."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def store_file(tmp_path, monkeypatch):
    path = str(tmp_path / "tasks.json")
    monkeypatch.setenv("TASKS_FILE", path)
    return path


@pytest.fixture
def factory(store_file, monkeypatch):
    """Build fresh app instances with per-test env overrides."""

    def build(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        from app.app import create_app

        application = create_app()
        application.config["TESTING"] = True
        return application.test_client()

    return build


def _write_store(path, tasks, next_id=None):
    with open(path, "w") as f:
        json.dump(
            {"next_id": next_id or max((t["id"] for t in tasks), default=0) + 1,
             "tasks": tasks},
            f,
        )


def _read_store(path):
    with open(path) as f:
        return json.load(f)


# --- rate limiting -----------------------------------------------------------

def test_health_is_exempt_from_rate_limit(factory):
    client = factory(RATE_LIMIT="1", RATE_WINDOW="60")
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_rate_limit_returns_429_with_retry_after(factory):
    client = factory(RATE_LIMIT="2", RATE_WINDOW="60")
    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks").status_code == 200
    resp = client.get("/tasks")
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate_limited"
    assert int(resp.headers["Retry-After"]) >= 1


# --- request validation ------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"title": 123},
        {"title": None},
        {"title": "x", "priority": "high"},
        {"title": "x", "priority": 99},
        {"title": "x", "priority": 3.5},
        {"title": "x", "priority": True},
        {"title": "x", "priority": None},
    ],
)
def test_create_rejects_invalid_input(factory, payload):
    resp = factory().post("/tasks", json=payload)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_create_accepts_valid_input(factory):
    resp = factory().post("/tasks", json={"title": "ship it", "priority": 5})
    assert resp.status_code == 201
    task = resp.get_json()
    assert task["status"] == "open"
    assert task["priority"] == 5


def test_status_filter_is_validated(factory):
    client = factory()
    assert client.get("/tasks?status=bogus").status_code == 400
    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks?status=open").status_code == 200
    assert client.get("/tasks?status=completed").status_code == 200


# --- cache invalidation ------------------------------------------------------

def test_every_write_invalidates_the_list_cache(factory, store_file):
    client = factory()
    client.post("/tasks", json={"title": "a"})
    assert len(client.get("/tasks").get_json()) == 1  # caches "all"
    client.post("/tasks", json={"title": "b"})
    assert [t["title"] for t in client.get("/tasks").get_json()] == ["a", "b"]

    client.patch("/tasks/1/complete")
    assert client.get("/tasks?status=open").get_json()[0]["title"] == "b"
    assert client.get("/tasks?status=completed").get_json()[0]["title"] == "a"

    client.delete("/tasks/2")
    assert [t["id"] for t in client.get("/tasks").get_json()] == [1]


def test_sync_and_gc_invalidate_the_list_cache(factory, store_file):
    two_days_ago = (_utcnow_naive() - timedelta(days=2)).isoformat()
    _write_store(store_file, [
        {"id": 1, "title": "old", "priority": 1, "status": "open",
         "created_at": two_days_ago, "updated_at": two_days_ago},
    ])
    client = factory(STALE_DAYS="1")
    assert [t["id"] for t in client.get("/tasks").get_json()] == [1]  # caches
    client.post("/tasks/sync", json={"tasks": [
        {"id": 9, "title": "synced", "priority": 1, "status": "open",
         "updated_at": two_days_ago}]})
    assert any(t["id"] == 9 for t in client.get("/tasks").get_json())
    client.post("/tasks/gc")
    assert client.get("/tasks").get_json() == []


def test_gc_never_crashes_on_malformed_tasks(factory, store_file):
    now = _utcnow_naive().isoformat()
    _write_store(store_file, [
        {"id": 1, "title": "no-status-field", "created_at": now},
        {"id": 2, "title": "normal", "priority": 1, "status": "open",
         "created_at": now, "updated_at": now},
    ])
    resp = factory().post("/tasks/gc")
    assert resp.status_code == 200
    assert [t["id"] for t in _read_store(store_file)["tasks"]] == [1, 2]


# --- GC policy ---------------------------------------------------------------

def test_gc_reaps_by_last_activity(factory, store_file):
    now = _utcnow_naive()
    old = (now - timedelta(days=10)).isoformat()
    recent = (now - timedelta(days=1)).isoformat()
    _write_store(store_file, [
        {"id": 1, "title": "never-touched", "priority": 1, "status": "open",
         "created_at": old, "updated_at": old},
        {"id": 2, "title": "actively-updated", "priority": 1, "status": "open",
         "created_at": old, "updated_at": recent},
        {"id": 3, "title": "completed", "priority": 1, "status": "completed",
         "created_at": old, "updated_at": old, "completed_at": old},
    ])
    resp = factory(STALE_DAYS="7").post("/tasks/gc")
    kept = [t["id"] for t in _read_store(store_file)["tasks"]]
    assert kept == [2, 3]
    assert resp.get_json() == {"kept": 2}


def test_stale_days_env_override_is_honored(factory, store_file):
    now = _utcnow_naive()
    _write_store(store_file, [
        {"id": 1, "title": "two-days-old", "priority": 1, "status": "open",
         "created_at": (now - timedelta(days=2)).isoformat(),
         "updated_at": (now - timedelta(days=2)).isoformat()},
    ])
    factory(STALE_DAYS="1").post("/tasks/gc")
    assert _read_store(store_file)["tasks"] == []


# --- sync merge policy -------------------------------------------------------

def test_merge_keeps_local_on_older_and_equal_timestamps(factory, store_file):
    older = (_utcnow_naive() - timedelta(hours=2)).isoformat()
    _write_store(store_file, [
        {"id": 1, "title": "local", "priority": 1, "status": "open",
         "created_at": older, "updated_at": older},
    ])
    client = factory()
    client.post("/tasks/sync", json={"tasks": [
        {"id": 1, "title": "incoming-older", "updated_at": older},
        {"id": 1, "title": "incoming-same-stamp", "updated_at": older},
    ]})
    tasks = _read_store(store_file)["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "local"  # older ignored, equal stamp keeps local


def test_merge_applies_newer_incoming(factory, store_file):
    now = _utcnow_naive()
    older = (now - timedelta(hours=2)).isoformat()
    _write_store(store_file, [
        {"id": 1, "title": "local", "priority": 1, "status": "open",
         "created_at": older, "updated_at": older},
    ])
    factory().post("/tasks/sync", json={"tasks": [
        {"id": 1, "title": "incoming-newer", "updated_at": now.isoformat()}]})
    assert _read_store(store_file)["tasks"][0]["title"] == "incoming-newer"


def test_sync_rejects_items_without_integer_id(factory):
    client = factory()
    assert client.post("/tasks/sync", json={"tasks": [{}]}).status_code == 400
    assert client.post(
        "/tasks/sync", json={"tasks": [{"id": True}]}).status_code == 400
    assert client.post(
        "/tasks/sync", json={"tasks": "not-a-list"}).status_code == 400
    resp = client.post("/tasks/sync", json={"tasks": [{"id": 5, "title": "x"}]})
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 1}


# --- update_task bumps updated_at --------------------------------------------

def test_update_task_moves_updated_at(store_file):
    from app.storage import TaskStore

    store = TaskStore(store_file)
    task = store.create_task("before")
    store.update_task(task["id"], {"title": "after"})
    updated = store.get_task(task["id"])
    assert updated["title"] == "after"
    assert updated["updated_at"] >= updated["created_at"]


# --- configuration -----------------------------------------------------------

def test_secret_key_is_not_a_literal_credential():
    from app import config

    assert not config.SECRET_KEY.startswith("sk-")
    assert config.secret_key() == config.SECRET_KEY  # single source of truth


def test_secret_key_env_override_is_read_at_call_time(monkeypatch):
    from app import config

    monkeypatch.setenv("SECRET_KEY", "custom-value")
    assert config.secret_key() == "custom-value"
