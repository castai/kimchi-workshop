#!/usr/bin/env python3
"""Stamp Kimchi-API-verified costs onto leaderboard records, mapped by email.

The API is the deciding factor for cost. Participants are fresh Kimchi
accounts in the workshop org, so within the event window an owner's TOTAL
spend is their workshop spend (facilitator-confirmed assumption). For every
accepted-submission record in --records:

  1. COST (primary) — the record's email is joined through the org roster
     (GET /v1/organizations/{org}/users -> email -> owner id) with org-wide
     per-owner spend in the event window (analytics
     GROUP_BY_API_KEY_OWNER). On a hit the record gets the API cost and
     request count, cost_source=kimchi_api, usage_verified=true; the
     previous (CSV/self-reported) cost is kept as cost_csv_usd. No
     per-record cost call needed — the owner table is fetched once.
  2. IDENTITY cross-check — the attendee tag's spend carries its own owner
     id; if it differs from the email's owner the record is flagged
     tag_email_mismatch (claimed someone else's account / shared key).
  3. FALLBACK — no email match, or no spend: the record keeps its CSV cost,
     marked usage_verified=false, with hints (email_not_in_kimchi when the
     email is absent from the roster). Records with an attendee but no
     email still get tag-scoped spend as their cost — attribution must not
     depend on the email alone. Never a refusal.

Where cost_usd changes, score_breakdown.cost_efficiency and points are
recomputed with the exact v2 formula from .github/workflows/leaderboard.yml
(budget $2, +10..-10) so published points match the API cost that produced
them.

Deliberately fault-tolerant: any API problem degrades to the fallback and
the process still exits 0 — the acceptance flow must never break because
Kimchi had a bad day.

    python scripts/enrich_costs.py --records records/ [--start ISO] [--end ISO]
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kimchi_usage import (  # noqa: E402
    KimchiUsageError,
    fetch_org_users,
    fetch_owner_costs,
    fetch_tag_usage,
    resolve_api_key,
    resolve_org_id,
)

DEFAULT_BUDGET = 2.0
COST_SOURCE_API = "kimchi_api"
COST_SOURCE_CSV = "csv"


def normalize_email(email):
    return (email or "").strip().lower()


def cost_efficiency_points(cost_usd, budget, has_signal):
    """v2 formula from leaderboard.yml: +10 (free) .. -10 (budget over)."""
    if not has_signal:
        return 0
    if budget > 0 and cost_usd <= budget:
        return round(10 - 5 * (cost_usd / budget), 2)
    over = cost_usd - budget
    return round(-min(10, over / 1.0 if budget > 0 else over), 2)


def recompute_points(record, budget):
    """Refresh cost_efficiency + points in place; returns True if changed."""
    breakdown = record.get("score_breakdown")
    if not isinstance(breakdown, dict):
        return False
    has_signal = bool(record.get("usage_verified")
                      or record.get("csv_rows", 0) > 0)
    breakdown["cost_efficiency"] = cost_efficiency_points(
        float(record.get("cost_usd") or 0.0), budget, has_signal)
    record["points"] = round(sum(float(v or 0) for v in breakdown.values()), 2)
    return True


def record_start(record, fallback):
    """Window start for a record's API queries: submitted_at - 7d."""
    for key in ("submitted_at", "accepted_at"):
        raw = record.get(key)
        if not raw:
            continue
        ts = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (dt - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return fallback


def default_window_start(records):
    """--start default: just before the earliest submission on record."""
    stamps = []
    for r in records:
        for key in ("submitted_at", "accepted_at"):
            raw = r.get(key)
            if raw:
                ts = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
                try:
                    stamps.append(datetime.fromisoformat(ts))
                except ValueError:
                    pass
    if stamps:
        earliest = min(stamps)
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=timezone.utc)
        start = earliest - timedelta(days=1)
    else:
        start = datetime.now(timezone.utc) - timedelta(days=30)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_records(records_dir):
    records = []
    for path in sorted(glob.glob(os.path.join(records_dir, "*.json"))):
        try:
            with open(path) as f:
                records.append((path, json.load(f)))
        except (OSError, ValueError) as e:
            print("skipping unreadable record %s: %s" % (path, e),
                  file=sys.stderr)
    return records


def enrich_record(record, roster, owner_spend, now_iso, budget, verify,
                  api_key, org_id, base_url, fallback_start):
    """Apply total-cost/identity/fallback logic to one record in place.

    roster: {"email_to_id": ..., "id_to_email": ...} from the org users API
    owner_spend: org-wide per-owner spend in the window (the cost source)
    verify: also run the tag-owner identity cross-check
    Returns True if the record changed.
    """
    before = json.dumps(record, sort_keys=True)
    email = normalize_email(record.get("email"))
    attendee = record.get("attendee")
    tag = "attendee:%s" % attendee if attendee else None
    window_end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    window_start = record_start(record, fallback_start)

    # 1. COST: email -> owner id -> total spend in the window (fresh
    #    participant accounts make owner-total = workshop spend)
    uid = roster["email_to_id"].get(email) if email else None
    spend = owner_spend.get(uid) if uid else None
    if spend is not None:
        if record.get("cost_csv_usd") is None and record.get("cost_usd") is not None:
            record["cost_csv_usd"] = record.get("cost_usd")
        record["cost_usd"] = round(float(spend["cost_usd"]), 4)
        record["requests"] = int(spend["requests"])
        record["cost_source"] = COST_SOURCE_API
        record["usage_verified"] = True
        record["api_owner_id"] = uid
        record["api_usage_fetched_at"] = now_iso
    elif tag and api_key:
        # no email to join (or not in the roster) — fall back to the
        # attendee tag so attribution does not depend on the email alone
        try:
            usage = fetch_tag_usage(api_key, org_id, tag, window_start,
                                    window_end, base_url)
        except KimchiUsageError as e:
            print("tag usage unavailable for %s: %s" % (attendee, e),
                  file=sys.stderr)
            usage = None
        if usage and usage["rows"] > 0:
            if record.get("cost_csv_usd") is None and record.get("cost_usd") is not None:
                record["cost_csv_usd"] = record.get("cost_usd")
            record["cost_usd"] = round(float(usage["cost_usd"]), 4)
            record["requests"] = int(usage["requests"])
            record["cost_source"] = COST_SOURCE_API
            record["usage_verified"] = True
            record["api_usage_fetched_at"] = now_iso
            record["cost_source_detail"] = "attendee_tag"
        else:
            record["usage_verified"] = False
            if record.get("cost_usd") is not None:
                record["cost_source"] = COST_SOURCE_CSV
            if email and uid is None:
                record["email_not_in_kimchi"] = True
    else:
        record["usage_verified"] = False
        if record.get("cost_usd") is not None:
            record["cost_source"] = COST_SOURCE_CSV
        if email and uid is None:
            record["email_not_in_kimchi"] = True

    # 2. IDENTITY cross-check: the tag's spend owner must be the email's
    #    owner — catches claiming someone else's account or a shared key
    if verify and tag and api_key and uid is not None:
        try:
            tag_owners = fetch_owner_costs(
                api_key, org_id, window_start, window_end, base_url,
                tags=[tag])
            tag_uid = max(tag_owners, key=lambda u: tag_owners[u]["cost_usd"]) \
                if tag_owners else None
        except KimchiUsageError as e:
            print("tag owner lookup failed for %s: %s" % (attendee, e),
                  file=sys.stderr)
            tag_uid = None
        if tag_uid is not None:
            record["tag_owner_id"] = tag_uid
            record["tag_email_mismatch"] = bool(tag_uid != uid)

    if record.get("cost_source") == COST_SOURCE_API:
        recompute_points(record, budget)
    return json.dumps(record, sort_keys=True) != before


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--records", default="records")
    ap.add_argument("--start", help="analytics window start (default: 1 day "
                                    "before earliest record)")
    ap.add_argument("--end", help="analytics window end (default: now)")
    ap.add_argument("--org", help="organization id (default: KIMCHI_ORG_ID "
                                  "or workshop default)")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the email/owner identity check")
    ap.add_argument("--base-url", default="https://api.cast.ai")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.records):
        print("::error::records dir not found: %s" % args.records,
              file=sys.stderr)
        return 1

    api_key = resolve_api_key()
    if not api_key:
        print("::warning::KIMCHI_API_KEY not set — leaving records "
              "unverified (CSV costs stand)")
        return 0

    records = load_records(args.records)
    if not records:
        print("no records to enrich in %s" % args.records)
        return 0

    org_id = resolve_org_id(args.org)
    start = args.start or default_window_start([r for _, r in records])
    end = args.end or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        roster = fetch_org_users(api_key, org_id, args.base_url)
        owner_spend = fetch_owner_costs(api_key, org_id, start, end,
                                        args.base_url)
    except KimchiUsageError as e:
        print("::warning::Kimchi API unavailable (%s) — leaving records "
              "unverified (CSV costs stand)" % e)
        return 0

    verified = fallback = mismatched = 0
    for path, record in records:
        try:
            changed = enrich_record(
                record, roster, owner_spend, now_iso, args.budget,
                not args.no_verify, api_key, org_id, args.base_url, start)
        except Exception as e:  # never let one bad record kill the run
            print("::warning::could not enrich %s: %s" % (path, e),
                  file=sys.stderr)
            continue
        if not changed:
            continue
        if record.get("usage_verified"):
            verified += 1
        else:
            fallback += 1
        if record.get("tag_email_mismatch"):
            mismatched += 1
        with open(path, "w") as f:
            json.dump(record, f, indent=2)

    print("enriched %d records: %d api-verified, %d fallback, "
          "%d identity mismatches" % (len(records), verified, fallback,
                                      mismatched))
    return 0


if __name__ == "__main__":
    sys.exit(main())
