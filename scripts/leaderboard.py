#!/usr/bin/env python3
"""Rebuild the workshop leaderboard from submissions/*.json.

Each submission is written by scripts/score.py. This script merges them into
a single ranked leaderboard.json, sorted by points. Ties break on fewer
failed tests, then lower cost, then name.

    python scripts/leaderboard.py --submissions submissions/ --out leaderboard.json
"""
import argparse
import json
import os
import glob

COLUMNS = [
    "attendee", "points", "tests_passed", "tests_failed",
    "review_score", "cost_usd", "requests", "pr",
]


def load_submissions(submissions_dir):
    records = []
    for path in sorted(glob.glob(os.path.join(submissions_dir, "*.json"))):
        try:
            with open(path) as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f"skipping unreadable submission {path}: {e}", file=__import__('sys').stderr)
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--submissions", default="submissions")
    ap.add_argument("--out", default="leaderboard.json")
    args = ap.parse_args()

    records = load_submissions(args.submissions)

    # keep the highest-points record per attendee (best run wins)
    best = {}
    for r in records:
        a = r.get("attendee", "unknown")
        if a not in best or r.get("points", 0) > best[a].get("points", 0):
            best[a] = r

    ranked = sorted(
        best.values(),
        key=lambda r: (-r.get("points", 0), r.get("tests_failed", 0),
                        r.get("cost_usd", 0), r.get("attendee", "")),
    )

    board = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "rows": [{k: r.get(k) for k in COLUMNS} for r in ranked],
    }
    with open(args.out, "w") as f:
        json.dump(board, f, indent=2)

    # human-readable table
    print(f"{'rank':<5} {'attendee':<16} {'points':>8} {'passed':>7} {'failed':>7} {'cost $':>8}")
    for i, r in enumerate(ranked, 1):
        print(f"{i:<5} {r.get('attendee', '?'):<16} {r.get('points', 0):>8.2f} "
              f"{r.get('tests_passed', 0):>7} {r.get('tests_failed', 0):>7} "
              f"{r.get('cost_usd', 0.0):>8.4f}")
    print(f"\n{len(ranked)} attendees on the board -> {args.out}")


if __name__ == "__main__":
    main()
