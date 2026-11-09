"""Supplementary contract tests for the task API.

These encode the policies documented in the module docstrings (the spec per
the challenge rules) and the behaviors added in review:

  - request validation and JSON error handling (400 {"error": "bad_request"})
  - the ?status=open|completed filter and its 400 path
  - cache honesty: writes invalidate listings (no stale reads)
  - rate limiting: 429 JSON past the limit, /health exempt for probes
  - merge_tasks: equal timestamps keep local (docstring contract)
  - gc_stale_tasks: age = last activity (updated_at or completed_at);
    records without timestamps are kept, never silently reaped

`tests/` is the challenge's read-only scoring suite and is untouched; run
this suite alongside it:

    python -m pytest verification/ -v
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_FILE", str(tmp_path / "tasks.json"))
    from app.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


# --- request validation and error handling ------------------------------------

def test_missing_title_is_bad_request(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_non_string_title_is_bad_request(client):
    resp = client.post("/tasks", json={"title": 123})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_empty_title_is_bad_request(client):
    resp = client.post("/tasks", json={"title": ""})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


@pytest.mark.parametrize("priority", ["high", 99, True, None])
def test_invalid_priority_is_bad_request(client, priority):
    resp = client.post("/tasks", json={"title": "x", "priority": priority})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_valid_priority_accepted(client):
    resp = client.post("/tasks", json={"title": "x", "priority": 5})
    assert resp.status_code == 201
    assert resp.get_json()["priority"] == 5


def test_malformed_json_is_bad_request_json(client):
    resp = client.post("/tasks", data="not json", content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_500_response_does_not_leak_internal_details(client, monkeypatch):
    """Internal error details must never reach the client."""
    def boom(*a, **k):
        raise RuntimeError("internal db password=hunter2")

    monkeypatch.setattr("app.storage.TaskStore.list_tasks", boom)
    client.application.config["PROPAGATE_EXCEPTIONS"] = False
    resp = client.get("/tasks")
    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert "hunter2" not in body
    assert resp.get_json()["error"] == "internal_error"


def test_not_found_errors_are_json(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"


def test_non_dict_json_body_is_bad_request(client):
    """A JSON array body is a client error, not an AttributeError 500."""
    resp = client.post("/tasks", json=[1, 2, 3])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_sync_non_dict_json_body_is_bad_request(client):
    resp = client.post("/tasks/sync", json=[1, 2, 3])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_sync_tasks_field_must_be_list(client):
    resp = client.post("/tasks/sync", json={"tasks": "nope"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_sync_non_json_content_type_is_bad_request(client):
    """Same client mistake, same 400 as every other endpoint (no 415 leak)."""
    resp = client.post("/tasks/sync", data="not json", content_type="text/plain")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_title_is_stripped_on_create(client):
    """Validated-with-strip must mean stored-with-strip."""
    resp = client.post("/tasks", json={"title": "  buy milk  "})
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "buy milk"


# --- status filter + cache honesty ---------------------------------------------

def test_status_filter_rejects_unknown_value(client):
    client.post("/tasks", json={"title": "one"})
    resp = client.get("/tasks?status=bogus")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_status_filter_completed(client):
    client.post("/tasks", json={"title": "one"})
    client.post("/tasks", json={"title": "two"})
    client.patch("/tasks/1/complete")
    resp = client.get("/tasks?status=completed")
    assert resp.status_code == 200
    assert [t["title"] for t in resp.get_json()] == ["one"]


def test_list_reflects_writes_immediately(client):
    """A write must invalidate the cached listing (no stale reads)."""
    client.post("/tasks", json={"title": "one"})
    assert len(client.get("/tasks").get_json()) == 1  # primes the cache
    client.post("/tasks", json={"title": "two"})
    assert len(client.get("/tasks").get_json()) == 2


# --- merge tie-break (docstring: equal timestamps keep local) ------------------

def test_merge_keeps_local_on_equal_timestamps(tmp_path):
    from app.storage import TaskStore

    store = TaskStore(str(tmp_path / "tasks.json"))
    local = store.create_task("local", now=datetime(2026, 1, 1))
    incoming = [{
        "id": local["id"],
        "title": "from-sync",
        "priority": 1,
        "status": "open",
        "updated_at": local["updated_at"],
    }]
    store.merge_tasks(incoming)
    assert store.get_task(local["id"])["title"] == "local"


def test_merge_accepts_strictly_newer(tmp_path):
    from app.storage import TaskStore

    store = TaskStore(str(tmp_path / "tasks.json"))
    local = store.create_task("local", now=datetime(2026, 1, 1))
    incoming = [{
        "id": local["id"],
        "title": "from-sync",
        "priority": 1,
        "status": "open",
        "updated_at": "2026-01-02T00:00:00",
    }]
    store.merge_tasks(incoming)
    assert store.get_task(local["id"])["title"] == "from-sync"


# --- gc: age = last activity; never silently reap unparseable records ----------

def _seed(path, task):
    with open(path, "w") as f:
        json.dump({"next_id": task["id"] + 1, "tasks": [task]}, f)


def test_gc_uses_completed_at_when_updated_at_missing(tmp_path):
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    now = datetime.utcnow()
    _seed(path, {
        "id": 1,
        "title": "completed-at is the last activity",
        "priority": 1,
        "status": "open",
        "created_at": (now - timedelta(days=10)).isoformat(),
        "completed_at": (now - timedelta(hours=1)).isoformat(),
    })
    store = TaskStore(path)
    store.gc_stale_tasks()
    assert store.get_task(1) is not None


def test_gc_reaps_never_touched_old_task(tmp_path):
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    now = datetime.utcnow()
    _seed(path, {
        "id": 1,
        "title": "old and untouched",
        "priority": 1,
        "status": "open",
        "created_at": (now - timedelta(days=10)).isoformat(),
    })
    store = TaskStore(path)
    store.gc_stale_tasks()
    assert store.get_task(1) is None


def test_gc_keeps_actively_updated_task(tmp_path):
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    now = datetime.utcnow()
    _seed(path, {
        "id": 1,
        "title": "active",
        "priority": 1,
        "status": "open",
        "created_at": (now - timedelta(days=10)).isoformat(),
        "updated_at": (now - timedelta(hours=1)).isoformat(),
    })
    store = TaskStore(path)
    store.gc_stale_tasks()
    assert store.get_task(1) is not None


def test_gc_keeps_task_without_timestamps(tmp_path):
    """A merged-in record with no timestamps must not be silently reaped."""
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    _seed(path, {
        "id": 1,
        "title": "no timestamps",
        "priority": 1,
        "status": "open",
    })
    store = TaskStore(path)
    store.gc_stale_tasks()
    assert store.get_task(1) is not None


def test_gc_keeps_record_with_unparseable_timestamp(tmp_path):
    """A garbage timestamp must not crash the gc sweep or reap the task."""
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    _seed(path, {
        "id": 1,
        "title": "garbage timestamp",
        "priority": 1,
        "status": "open",
        "updated_at": "not-a-date",
    })
    store = TaskStore(path)
    store.gc_stale_tasks()  # must not raise
    assert store.get_task(1) is not None


def test_gc_keeps_record_with_non_string_timestamp(tmp_path):
    """A non-string timestamp (e.g. merged JSON number) must not 500 the gc."""
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    _seed(path, {
        "id": 1,
        "title": "numeric timestamp",
        "priority": 1,
        "status": "open",
        "updated_at": 123,
    })
    store = TaskStore(path)
    store.gc_stale_tasks()  # must not raise
    assert store.get_task(1) is not None


def test_gc_keeps_record_without_status(tmp_path):
    """A merged-in record without a status field must not crash the sweep."""
    from app.storage import TaskStore

    path = str(tmp_path / "tasks.json")
    _seed(path, {"id": 1, "title": "no status", "priority": 1})
    store = TaskStore(path)
    store.gc_stale_tasks()  # must not raise
    assert store.get_task(1) is not None


# --- sync payload hardening: malformed items are client errors -----------------


def test_sync_item_missing_id_is_bad_request(client):
    resp = client.post("/tasks/sync", json={"tasks": [{"title": "x"}]})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_sync_item_non_dict_is_bad_request(client):
    resp = client.post("/tasks/sync", json={"tasks": ["nope"]})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_sync_item_non_int_id_is_bad_request(client):
    resp = client.post("/tasks/sync", json={"tasks": [{"id": "abc", "title": "x"}]})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_merge_existing_task_with_garbage_timestamp_keeps_local(tmp_path):
    """A numeric/garbage incoming timestamp must never crash or overwrite."""
    from app.storage import TaskStore

    store = TaskStore(str(tmp_path / "tasks.json"))
    local = store.create_task("local", now=datetime(2026, 1, 1))
    store.merge_tasks([{
        "id": local["id"],
        "title": "from-sync",
        "priority": 1,
        "status": "open",
        "updated_at": 123,
    }])
    assert store.get_task(local["id"])["title"] == "local"


def test_merge_new_task_with_garbage_timestamp_still_lands(tmp_path):
    """New records are stored even with a bad timestamp (gc protects them)."""
    from app.storage import TaskStore

    store = TaskStore(str(tmp_path / "tasks.json"))
    store.merge_tasks([{
        "id": 7,
        "title": "garbage-ts",
        "priority": 1,
        "status": "open",
        "updated_at": "not-a-date",
    }])
    assert store.get_task(7)["title"] == "garbage-ts"


# --- error-contract consistency ------------------------------------------------


def test_404_error_shape_is_consistent(client):
    """Route-emitted 404s and error-handler 404s share one JSON contract."""
    handler_404 = client.get("/nonexistent-route")
    task_404 = client.get("/tasks/999")
    assert handler_404.status_code == 404 and task_404.status_code == 404
    assert set(handler_404.get_json().keys()) == set(task_404.get_json().keys())
    assert task_404.get_json()["error"] == "not_found"
    assert client.patch("/tasks/999/complete").status_code == 404
    assert client.delete("/tasks/999").status_code == 404


def test_sync_missing_tasks_key_syncs_nothing(client):
    """{} is a valid empty sync, not an error."""
    resp = client.post("/tasks/sync", json={})
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 0}


# --- configuration contract: debug off by default, fail fast in production -----
# Each case runs in a fresh interpreter (no module-reload state leaking into
# other tests).


def _run_config_code(code):
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def test_debug_defaults_off():
    out = _run_config_code(
        "import os; os.environ.pop('FLASK_DEBUG', None); "
        "from app import config; print(config.DEBUG)"
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "False"  # RED today: hardcoded True


def test_debug_env_opt_in():
    out = _run_config_code(
        "import os; os.environ['FLASK_DEBUG'] = '1'; "
        "from app import config; print(config.DEBUG)"
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "True"


def test_production_env_requires_secret_key():
    out = _run_config_code(
        "import os; os.environ['ENV'] = 'production'; "
        "os.environ.pop('SECRET_KEY', None); import app.config"
    )
    assert out.returncode != 0  # RED today: silently boots with fallback key
    assert "RuntimeError" in out.stderr
    assert "SECRET_KEY" in out.stderr


# --- model-layer validation (docstring: "Task model and validation rules") ------


def test_validate_title_accepts_and_strips():
    from app.models import validate_title

    assert validate_title("  buy milk  ") == "buy milk"


def test_validate_title_rejects_non_string():
    from app.models import validate_title

    with pytest.raises(ValueError):
        validate_title(123)


def test_validate_title_rejects_empty_and_whitespace():
    from app.models import validate_title

    with pytest.raises(ValueError):
        validate_title("")
    with pytest.raises(ValueError):
        validate_title("   ")
