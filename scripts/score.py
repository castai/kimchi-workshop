#!/usr/bin/env python3
"""Score a workshop submission (offline/standalone variant).

Reads the repo state (tests) and prints a leaderboard row per attendee.
Cost is NOT taken from usage CSVs anymore: spend is decided by the Kimchi
API in the leaderboard pipeline (scripts/enrich_costs.py, email -> owner
join). This tool accepts an informational --cost-usd placeholder that earns
no efficiency signal on its own.

    python scripts/score.py --attendee alice --pr https://...
"""
import argparse
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
    ap.add_argument("--cost-usd", type=float, default=0.0,
                    help="informational cost placeholder; the leaderboard "
                         "pipeline decides cost from the Kimchi API")
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
    points = compute_points(
        passed, args.review_score, args.cost_usd, args.budget,
        evidence=False,  # no usage evidence offline; the API path decides
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
        "cost_usd": args.cost_usd,
        "requests": 0,
        "models_used": [],
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
