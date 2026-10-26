#!/usr/bin/env python3
"""Score a submission PR. Runs in the sandboxed CI context.

Parses the PR body block (attendee / email / event / cost_usd),
runs the repo's visible test suite, computes points with the same model
as scripts/score.py, and writes:

    score.json   - machine-readable row for the leaderboard
    summary.md   - human-readable breakdown for the job summary

The production-stage suite runs in a SEPARATE job
(.github/workflows/production.yml); its score is merged by the
leaderboard aggregation script, not here.

Usage (all metadata passed explicitly so nothing trusts the network):

    python scripts/score_pr.py --pr 12 --author alice-gh \
        --url https://github.com/.../pull/12 --body-file body.md \
        --out score.json --summary summary.md

The output row is status "pending" until a facilitator adds the
`accepted` label, which triggers the leaderboard workflow.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import compute_points, run_tests  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BUDGET = 2.00
REQUIRED_FIELDS = ("attendee", "email", "event", "cost_usd")


def parse_body(body):
    """Pull attendee / email / event / cost_usd from the PR body.

    Returns a dict of found fields (values as strings) plus a list of
    missing required fields.
    """
    def grab(key):
        m = re.search(r"(?im)^\s*%s\s*:\s*(.*?)\s*$" % re.escape(key),
                      body or "")
        return m.group(1) if m else None

    found = {
        "attendee": grab("attendee"),
        "email": grab("email"),
        "event": grab("event"),
        "cost_usd": grab("cost_usd"),
    }

    missing = [k for k in REQUIRED_FIELDS if not found.get(k)]

    cost_usd = None
    raw_cost = found.get("cost_usd")
    if raw_cost is not None:
        try:
            cost_usd = float(raw_cost.strip().lstrip("$"))
        except (ValueError, AttributeError):
            cost_usd = None
            if "cost_usd" not in missing:
                missing.append("cost_usd")

    found["cost_usd"] = cost_usd
    found["event"] = found.get("event") or "default"
    return found, missing


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--author", required=True, help="PR author login")
    ap.add_argument("--url", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--out", default="score.json")
    ap.add_argument("--summary", default="summary.md")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET)
    args = ap.parse_args()

    body = ""
    with open(args.body_file) as f:
        body = f.read()

    fields, missing = parse_body(body)

    if missing:
        lines = [
            "## Submission incomplete",
            "",
            "The PR body is missing required fields from the template block:",
            "",
        ]
        for k in missing:
            lines.append("- `%s`" % k)
        lines.extend([
            "",
            "Fill them in and push - the workflow re-runs on update.",
            "Submissions without all fields are not scored.",
        ])
        with open(args.summary, "w") as f:
            f.write("\n".join(lines))
        print("::error::missing required fields: %s" % ", ".join(missing))
        sys.exit(1)

    attendee = fields["attendee"]
    email = fields["email"]
    event = fields["event"]
    cost_usd = fields["cost_usd"]

    passed, failed = run_tests()

    # The production scenario is a separate CI job; its score merges at the
    # leaderboard aggregation step. This job is the visible-suite gate.
    evidence = True
    cost_val = cost_usd
    review_val = 0.0  # Kimchi review posts separately; leaderboard merges it
    points = compute_points(passed, review_val, cost_val, args.budget,
                            evidence=evidence)

    row = {
        "attendee": attendee,
        "email": email,
        "github": args.author,
        "event": event,
        "pr": args.pr,
        "pr_url": args.url,
        "pr_title": args.title,
        "status": "pending",
        "tests_passed": passed,
        "tests_failed": failed,
        "review_score": review_val,
        "cost_usd": round(cost_val, 4),
        "cost_self_reported": evidence,
        "requests": 0,
        "models_used": [],
        "points": points,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "scoring_config": {"budget_usd": args.budget},
    }
    with open(args.out, "w") as f:
        json.dump(row, f, indent=2)

    with open(args.summary, "w") as f:
        f.write("""## Submission score (pending facilitator acceptance)

| Field | Value |
| --- | --- |
| Attendee | `%s` |
| Email | `%s` |
| Event | `%s` |
| Tests passing | %d passed, %d failed |
| Review score | (pending Kimchi review) |
| Cost | $%.2f (self-reported) |
| **Points** | **%.2f** |

The production scenario runs as a separate check; its result merges here
when both artifacts are available at leaderboard time.

Score becomes leaderboard-official when a facilitator adds the
`accepted` label.
""" % (attendee, email, event, passed, failed, cost_val, points))

    print("scored pr #%s: attendee=%s event=%s points=%.2f "
          "(tests %d/%d)" % (args.pr, attendee, event, points,
                             passed, passed + failed))


if __name__ == "__main__":
    main()
