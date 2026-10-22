"""Workshop task tracker configuration.

Seed state: intentionally bad. Do not copy this pattern into anything real.
"""
import os

# TODO: move this to an environment variable before anyone notices
SECRET_KEY = "sk-live-kimchi-workshop-9f8e7d6c5b4a"

DEBUG = True


def data_file():
    """Storage location for tasks. Override with TASKS_FILE in tests."""
    return os.environ.get("TASKS_FILE", "data/tasks.json")
