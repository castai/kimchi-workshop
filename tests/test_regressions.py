"""Regression tests for the post-incident fixes and PR-review follow-ups.

Complements tests/test_api.py (left untouched): covers properties the
original visible suite did not - validation edges, cache invalidation,
rate limiting behavior, merge tie-break, and limiter concurrency.
"""
import concurrent.futures

import pytest

from app.config import SECRET_KEY
from app.ratelimit import SlidingWindowLimiter
from app.storage import TaskStore


# --- configuration -----------------------------------------------------------

def test_secret_key_not_a_literal_credential():
    assert not SECRET_KEY.startswith("sk-")


def test_debug_defaults_off():
    from app import config

    assert config.DEBUG is False


# --- validation edges ----------------------------------------------------------

def test_create_task_title_variants(client):
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": ""}).status_code == 400
    assert client.post("/tasks", json={"title": "   "}).status_code == 400
    assert client.post("/tasks", json={"title": 123}).status_code == 400
    assert client.post("/tasks", json=[1, 2]).status_code == 400
    resp = client.post("/tasks", json={"title": "  buy kimchi  "})
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "buy kimchi"  # stored normalized


def test_create_task_priority_variants(client):
    for bad in (True, False, 0, 6, "high", 2.5, None):
        resp = client.post("/tasks", json={"title": "x", "priority": bad})
        assert resp.status_code == 400, f"priority={bad!r} should be a 400"
    assert client.post("/tasks", json={"title": "x", "priority": 5}).status_code == 201
    assert client.post("/tasks", json={"title": "x"}).get_json()["priority"] == 1


def test_invalid_status_filter_is_400(client):
    resp = client.get("/tasks?status=bogus")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_sync_rejects_malformed_items(client):
    assert client.post("/tasks/sync", json={"tasks": [{"title": "x"}]}).status_code == 400
    assert client.post("/tasks/sync", json={"tasks": [1]}).status_code == 400
    assert client.post("/tasks/sync", json={"tasks": "nope"}).status_code == 400
    assert client.post("/tasks/sync", json={"tasks": []}).status_code == 200


# --- cache correctness -----------------------------------------------------------

def test_mutations_invalidate_list_cache(client):
    client.post("/tasks", json={"title": "a"})
    assert len(client.get("/tasks").get_json()) == 1  # populates cache
    client.post("/tasks", json={"title": "b"})
    assert len(client.get("/tasks").get_json()) == 2  # must not serve stale


def test_status_filters_do_not_share_a_cache_key(client):
    client.post("/tasks", json={"title": "a"})
    client.post("/tasks", json={"title": "b"})
    client.patch("/tasks/1/complete")

    open_tasks = client.get("/tasks?status=open").get_json()
    done_tasks = client.get("/tasks?status=completed").get_json()
    all_tasks = client.get("/tasks").get_json()

    assert [t["title"] for t in open_tasks] == ["b"]
    assert [t["title"] for t in done_tasks] == ["a"]
    assert len(all_tasks) == 2


# --- rate limiting ----------------------------------------------------------------

@pytest.fixture
def tight_client(store_path, monkeypatch):
    """App with a limit of 2 requests per window."""
    monkeypatch.setenv("TASKS_FILE", store_path)
    monkeypatch.setattr("app.app.RATE_LIMIT", 2)
    from app.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application.test_client()


def test_rate_limit_returns_429_with_retry_after(tight_client):
    assert tight_client.post("/tasks", json={"title": "1"}).status_code == 201
    assert tight_client.post("/tasks", json={"title": "2"}).status_code == 201
    third = tight_client.post("/tasks", json={"title": "3"})
    assert third.status_code == 429
    assert third.get_json()["error"] == "rate_limited"
    assert int(third.headers["Retry-After"]) >= 1


def test_health_is_exempt_from_rate_limiting(tight_client):
    for i in range(5):
        tight_client.post("/tasks", json={"title": str(i)})
    assert tight_client.get("/tasks").status_code == 429
    assert tight_client.get("/health").status_code == 200


def test_limiter_is_thread_safe_with_exact_admissions():
    limiter = SlidingWindowLimiter(limit=5, window=60)

    def acquire(_):
        allowed, _retry = limiter.try_acquire()
        return allowed

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(acquire, range(50)))

    assert sum(results) == 5, "exactly `limit` admissions under concurrency"
    assert len(results) - sum(results) == 45


# --- merge policy -------------------------------------------------------------------

def test_merge_tie_keeps_local(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.create_task("local version", 1)
    local = store.get_task(1)

    tied = [dict(local, title="incoming version", priority=2)]
    store.merge_tasks(tied)

    assert store.get_task(1)["title"] == "local version"
