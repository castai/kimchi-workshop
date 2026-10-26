#!/usr/bin/env python3
"""Score a workshop submission.

Reads the repo state (tests) and a Kimchi console export (usage CSV) and
prints a leaderboard row per attendee.

    python scripts/score.py --attendee alice --usage export-alice.csv --pr https://...

The usage CSV is the per-attendee export from the Kimchi console
(Usage page -> filter by attendee tag -> Export). The parser tolerates extra
columns and both 'cost_usd' and 'cost' spellings.

Scoring model (full rationale in the private facilitator pack):
    points = output (tests, review score) + efficiency (cost vs budget)
Output first, cost second: the penalty is capped so high output always beats
a cheap no-op, and there is no minimum-spend floor.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_tests():
    """Run pytest quietly; return (passed, failed_or_error) counts."""
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header", "--tb=no"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    out = run.stdout + run.stderr
    def grab(word):
        m = re.search(r"(\d+) " + word, out)
        return int(m.group(1)) if m else 0
    return grab("passed"), grab("failed") + grab("error")


def parse_usage_csv(path):
    """Parse a Kimchi console usage export. Returns metric dict."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}

    def col(*names):
        for n in names:
            for c in rows[0].keys():
                if c.strip().lower().replace(" ", "_") == n:
                    return c
        return None

    c_cost = col("cost_usd", "cost", "spend_usd", "spend")
    c_req = col("requests", "request_count", "api_calls")
    c_model = col("model", "model_name")

    total_cost, total_requests, models = 0.0, 0, set()
    for row in rows:
        if c_cost:
            try:
                total_cost += float(row[c_cost] or 0)
            except ValueError:
                pass
        if c_req:
            try:
                total_requests += int(row[c_req] or 0)
            except ValueError:
                pass
        if c_model and row[c_model]:
            models.add(row[c_model])
    return {
        "cost_usd": round(total_cost, 4),
        "requests": total_requests,
        "models_used": sorted(models),
        "rows": len(rows),
    }


def compute_points(tests_passed, review_score, cost_usd, budget_usd,
                   evidence=True):
    """Points model.

    Efficiency requires usage evidence: a submission with no usage export
    earns zero efficiency (otherwise no-data scores the same as a genuinely
    free run, e.g. the offline Ollama track, which DOES show a zero-cost
    export). Output always dominates: the penalty is capped at the budget.
    """
    output = tests_passed * 10
    output += (review_score / 100.0) * 50 if review_score else 0.0
    if not evidence:
        return round(output, 2)
    if cost_usd <= budget_usd:
        efficiency = (1 - cost_usd / budget_usd) * 20 if budget_usd > 0 else 0
    else:
        efficiency = -(min(cost_usd - budget_usd, budget_usd))
    return round(output + efficiency, 2)


def main():
    ap = argparse.ArgumentParser(description="Score a workshop submission")
    ap.add_argument("--attendee", required=True, help="attendee handle")
    ap.add_argument("--usage", help="Kimchi console usage export CSV for this attendee")
    ap.add_argument("--pr", help="pull request URL (informational)")
    ap.add_argument("--review-score", type=float,
                    default=float(os.environ.get("KIMCHI_REVIEW_SCORE", 0) or 0),
                    help="Kimchi Code Review score for the PR, 0-100")
    ap.add_argument("--budget", type=float, default=2.00,
                    help="efficiency budget in USD (default 2.00)")
    ap.add_argument("--team", help="team name for the submission record")
    ap.add_argument("--notes", help="free-text notes from the attendee")
    ap.add_argument("--submission-dir", default=os.path.join(REPO_ROOT, "submissions"))
    args = ap.parse_args()

    passed, failed = run_tests()
    usage = parse_usage_csv(args.usage)
    cost_usd = usage.get("cost_usd", 0.0)
    has_usage_evidence = bool(usage) and usage.get("rows", 0) > 0
    points = compute_points(
        passed, args.review_score, cost_usd, args.budget,
        evidence=has_usage_evidence,
    )

    record = {
        "attendee": args.attendee,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pr": args.pr,
        "team": args.team,
        "notes": args.notes,
        "tests_passed": passed,
        "tests_failed": failed,
        "review_score": args.review_score,
        "cost_usd": cost_usd,
        "requests": usage.get("requests", 0),
        "models_used": usage.get("models_used", []),
        "points": points,
        "scoring_config": {"budget_usd": args.budget},
    }

    os.makedirs(args.submission_dir, exist_ok=True)
    path = os.path.join(args.submission_dir, f"{args.attendee}.json")
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    print(json.dumps(record, indent=2))
    print(f"\nsubmission saved to {path}")


if __name__ == "__main__":
    main()
