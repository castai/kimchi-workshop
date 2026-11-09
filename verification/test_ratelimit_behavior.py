"""Rate limiting contract: 429 past the limit, /health exempt for probes.

Docstring (app/ratelimit.py): "Allows at most `limit` acquisitions per
`window` seconds. When the limit is hit, requests receive a 429 rather than
blocking."

The limiter is tightened by monkeypatching app.app.RATE_LIMIT (read at
create_app() call time), so this file is safe to run in the same pytest
process as the rest of the verification suite.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_FILE", str(tmp_path / "tasks.json"))
    import app.app as app_module

    monkeypatch.setattr(app_module, "RATE_LIMIT", 3)
    monkeypatch.setattr(app_module, "RATE_WINDOW", 60.0)
    application = app_module.create_app()
    application.config["TESTING"] = True
    return application.test_client()


def test_health_is_exempt_from_rate_limit(client):
    """Probes must never be throttled into restart loops."""
    for _ in range(6):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_fourth_task_request_in_window_is_rate_limited(client):
    for _ in range(3):
        resp = client.post("/tasks", json={"title": "x"})
        assert resp.status_code == 201
    resp = client.post("/tasks", json={"title": "x"})
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate_limited"
