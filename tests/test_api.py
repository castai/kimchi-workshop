"""Contract tests for the task API.

These describe how the service is supposed to behave (see
PRODUCTION-INCIDENT.md). Fix the app, not the tests.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- baseline behaviour ------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_create_and_get_task(client):
    resp = client.post("/tasks", json={"title": "write the workshop brief"})
    assert resp.status_code == 201
    task = resp.get_json()
    assert task["title"] == "write the workshop brief"
    assert task["status"] == "open"

    resp = client.get(f"/tasks/{task['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "write the workshop brief"


def test_complete_task(client):
    task = client.post("/tasks", json={"title": "ship it"}).get_json()
    resp = client.patch(f"/tasks/{task['id']}/complete")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_delete_task(client):
    task = client.post("/tasks", json={"title": "gone soon"}).get_json()
    assert client.delete(f"/tasks/{task['id']}").status_code == 200
    assert client.get(f"/tasks/{task['id']}").status_code == 404


def test_unknown_task_404(client):
    assert client.get("/tasks/999").status_code == 404


# --- configuration contract ---------------------------------------------------

def test_secret_key_comes_from_environment():
    """Runtime configuration must not embed credentials in source."""
    from app import config

    assert not config.SECRET_KEY.startswith("sk-"), (
        "SECRET_KEY appears to be a literal credential. It should come "
        "from the process environment, with a clearly-marked dev fallback."
    )


# --- request validation contract ----------------------------------------------

def test_create_task_requires_title(client):
    """POST /tasks without a title is a client error, not a server crash."""
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "bad_request"


def test_create_task_validates_priority(client):
    """Priority is an integer in the range 1-5; anything else is a 400."""
    resp = client.post("/tasks", json={"title": "x", "priority": "high"})
    assert resp.status_code == 400
    resp = client.post("/tasks", json={"title": "x", "priority": 99})
    assert resp.status_code == 400


# --- query contract -------------------------------------------------------------

def test_list_tasks_status_filter(client):
    """GET /tasks respects ?status=open|completed and returns only matches."""
    client.post("/tasks", json={"title": "one"})
    client.post("/tasks", json={"title": "two"})
    client.patch("/tasks/1/complete")

    resp = client.get("/tasks?status=open")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "two"
