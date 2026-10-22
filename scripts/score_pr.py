#!/usr/bin/env python3
"""Score a submission PR. Runs in the sandboxed CI context.

Parses the PR body block (attendee / event / cost_usd / review_score),
runs the repo's test suite, computes points with the same model as
scripts/score.py, and writes:

    score.json   - machine-readable row for the leaderboard
    summary.md   - human-readable breakdown for the job summary

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
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import compute_points, run_tests  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BUDGET = 2.00


def run_hidden_suite():
    """Run .verification/test_hidden.py if present. Returns (passed, total)."""
    path = os.path.join(REPO_ROOT, ".verification", "test_hidden.py")
    if not os.path.exists(path):
        return 0, 0
    run = subprocess.run(
        [sys.executable, "-m", "pytest", ".verification/", "-q", "--no-header",
         "--tb=no", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    out = run.stdout + run.stderr
    import re
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    m2 = re.search(r"(\d+) failed", out)
    failed = int(m2.group(1)) if m2 else 0
    return passed, passed + failed


def parse_body(body):
    """Pull attendee / event / cost_usd / review_score from the PR body."""
    def grab(key):
        m = re.search(r"(?im)^\s*%s\s*:\s*(.*?)\s*$" % re.escape(key),
                      body or "")
        return m.group(1) if m else None

    attendee = grab("attendee")
    event = grab("event") or "default"
    cost = grab("cost_usd")
    review = grab("review_score")

    cost_usd = None
    if cost:
        try:
            cost_usd = float(cost.strip().strip("$"))
        except ValueError:
            cost_usd = None
    review_score = None
    if review:
        try:
            review_score = float(review)
        except ValueError:
            review_score = None
    return attendee, event, cost_usd, review_score


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

    attendee, event, cost_usd, review_score = parse_body(body)
    if not attendee:
        print("::error::PR body is missing the 'attendee:' line in the "
              "submission block. See the PR template.")
        sys.exit(1)

    passed, failed = run_tests()

    # hidden verification suite: the real bar (V1-V9). If it ran, its
    # pass count feeds the score directly.
    hidden_passed, hidden_total = run_hidden_suite()
    if hidden_total:
        passed = hidden_passed
        failed = hidden_total - hidden_passed

    evidence = cost_usd is not None
    cost_val = cost_usd if cost_usd is not None else 0.0
    review_val = review_score if review_score is not None else 0.0
    points = compute_points(passed, review_val, cost_val, args.budget,
                            evidence=evidence)

    row = {
        "attendee": attendee,
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

    cost_line = ("$%.2f (self-reported from console export)"
                 % cost_val if evidence else
                 "not provided - efficiency points withheld until added")
    review_line = ("%d/100" % review_score if review_score is not None
                   else "not set")

    with open(args.summary, "w") as f:
        f.write("""## Submission score (pending facilitator acceptance)

| Field | Value |
| --- | --- |
| Attendee | `%s` |
| Event | `%s` |
| Tests passing | %d passed, %d failed |
| Review score | %s |
| Cost | %s |
| **Points** | **%.2f** |

Score becomes leaderboard-official when a facilitator adds the
`accepted` label.
""" % (attendee, event, passed, failed, review_line, cost_line, points))

    print("scored pr #%s: attendee=%s event=%s points=%.2f "
          "(tests %d/%d)" % (args.pr, attendee, event, points,
                            passed, passed + failed))


if __name__ == "__main__":
    main()
