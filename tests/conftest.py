"""Shared pytest fixtures. Nothing broken in here."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "tasks.json")


@pytest.fixture
def app(store_path, monkeypatch):
    monkeypatch.setenv("TASKS_FILE", store_path)
    monkeypatch.setenv("RATE_LIMIT", "1000")   # effectively off for functional tests
    monkeypatch.setenv("RATE_WINDOW", "0.001")
    monkeypatch.setenv("CACHE_TTL", "30")
    monkeypatch.setenv("STALE_DAYS", "7")
    from app.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
