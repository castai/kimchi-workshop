#!/usr/bin/env python3
"""Build docs/config.json for the leaderboard UI.

The UI (docs/index.html) fetches config.json which points it at the right
leaderboard.json for this repo deployment. Run by CI alongside aggregate.py
before the Pages deploy:

    python scripts/build_ui_config.py --repo owner/name \
        [--default-event berlin-2026-10-22]

If --default-event is omitted, the most recent event by submitted_at wins.
"""
import argparse
import json
import os
from datetime import datetime, timezone


def newest_event(board):
    best, best_ts = None, ""
    for name, ev in (board.get("events") or {}).items():
        ts = max((r.get("submitted_at") or "") for r in ev.get("rows", []))
        if ts > best_ts:
            best, best_ts = name, ts
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--default-event")
    ap.add_argument("--board", default="leaderboard.json")
    ap.add_argument("--out", default="docs/config.json")
    args = ap.parse_args()

    board = {}
    if os.path.exists(args.board):
        with open(args.board) as f:
            board = json.load(f)

    default_event = args.default_event or newest_event(board) or ""
    config = {
        "repo": "github.com/" + args.repo,
        "repo_url": "https://github.com/" + args.repo,
        "default_event": default_event,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(config, f, indent=2)
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
