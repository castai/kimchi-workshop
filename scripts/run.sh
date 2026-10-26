#!/usr/bin/env bash
"""Local verification for workshop organizers and attendees.

Runs the seeded test suite and prints a compact summary. Exit code 0 means
all green (you finished the repo); 1 means challenges remain.
"""
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== workshop app test run =="
if command -v python3 >/dev/null 2>&1; then
  python3 -m pytest tests/ -q --no-header --tb=short
else
  echo "python3 not found" >&2
  exit 1
fi
