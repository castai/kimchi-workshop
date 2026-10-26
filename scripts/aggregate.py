#!/usr/bin/env python3
"""Aggregate submission records into leaderboard.json for the UI.

Reads every JSON file in --records (one per accepted submission, written
by CI), keeps the best record per (attendee, event), and writes a
leaderboard.json with per-event rankings the UI can slice by.

    python scripts/aggregate.py --records records/ --out leaderboard.json
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone


def load_records(records_dir):
    records = []
    for path in sorted(glob.glob(os.path.join(records_dir, "*.json"))):
        try:
            with open(path) as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print("skipping unreadable record %s: %s" % (path, e),
                  file=sys.stderr)
    return records


def best_per_attendee_event(records):
    best = {}
    for r in records:
        if r.get("status") not in (None, "accepted"):
            continue
        key = (r.get("attendee"), r.get("event"))
        cur = best.get(key)
        if cur is None or r.get("points", 0) > cur.get("points", 0):
            best[key] = r
    return list(best.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", default="records")
    ap.add_argument("--out", default="leaderboard.json")
    args = ap.parse_args()

    records = load_records(args.records)
    ranked_all = sorted(
        best_per_attendee_event(records),
        key=lambda r: (-r.get("points", 0),
                        r.get("tests_failed", 0),
                        r.get("cost_usd", 0),
                        r.get("attendee", "")),
    )

    events = {}
    for r in ranked_all:
        events.setdefault(r.get("event", "default"), []).append(r)
    for name, rows in events.items():
        for i, row in enumerate(rows, 1):
            row["rank"] = i

    board = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": {
            name: {
                "rows": rows,
                "count": len(rows),
            }
            for name, rows in events.items()
        },
    }
    with open(args.out, "w") as f:
        json.dump(board, f, indent=2)

    for name in sorted(events):
        rows = events[name]
        print("%s: %d participants" % (name, len(rows)))
        for row in rows[:3]:
            print("  #%d %s %.2f pts (%d tests, $%.2f)"
                  % (row["rank"], row["attendee"], row["points"],
                     row.get("tests_passed", 0), row.get("cost_usd", 0)))
    print("-> %s" % args.out)


if __name__ == "__main__":
    import sys
    main()
