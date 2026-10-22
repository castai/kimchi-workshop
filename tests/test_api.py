"""Tests for the task API.

Three of these fail on the seeded repo on purpose; each failing test
maps to one challenge in workshop/CHALLENGES.md. Fix the app, not the test.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- passing baseline -------------------------------------------------------

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


# --- failing: challenge 1 (The Secret Ingredient) ---------------------------

def test_secret_key_is_not_hardcoded():
    """The secret key must come from the environment, not the source file.

    See workshop/CHALLENGES.md, challenge 2. Runs without the app fixtures
    on purpose: it inspects configuration, not requests.
    """
    from app import config

    assert not config.SECRET_KEY.startswith("sk-"), (
        "SECRET_KEY is hardcoded in app/config.py. Read it from an environment "
        "variable with a safe fallback instead."
    )


# --- failing: challenge 2 (Red to Green) -------------------------------------

def test_create_task_rejects_missing_title(client):
    """POST /tasks without a title must return 400, not crash with a 500.

    See workshop/CHALLENGES.md, challenge 1. There is an unwired helper in
    app/errors.py that would render a clean JSON 400 if it were registered.
    """
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "bad_request"


def test_create_task_rejects_bad_priority(client):
    """Priority must be an integer between 1 and 5; anything else is a 400."""
    resp = client.post("/tasks", json={"title": "x", "priority": "high"})
    assert resp.status_code == 400
    resp = client.post("/tasks", json={"title": "x", "priority": 99})
    assert resp.status_code == 400


# --- failing: challenge 3 (Backlog level 1) ----------------------------------

def test_list_tasks_filters_by_status(client):
    """GET /tasks?status=open returns only open tasks.

    See workshop/CHALLENGES.md, challenge 4 / backlog level 1. The store
    already knows how to filter; the route never asks it to.
    """
    client.post("/tasks", json={"title": "one"})
    client.post("/tasks", json={"title": "two"})
    client.patch("/tasks/1/complete")

    resp = client.get("/tasks?status=open")
    assert resp.status_code == 200
    body = resp.get_json()
    tasks = body["tasks"]
    assert body["total"] == 1
    assert len(tasks) == 1
    assert tasks[0]["title"] == "two"
