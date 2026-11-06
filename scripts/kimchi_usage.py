#!/usr/bin/env python3
"""Kimchi usage API client — org users (emails) and per-owner spend.

Powers the leaderboard's "API is the deciding factor" cost verification:

  1. GET {base}/v1/organizations/{org}/users
       -> members with emails (RBAC: ORGANIZATION_MANAGEMENT / IAM / READ)
  2. GET {base}/ai-optimizer/v1beta/organizations/{org}:generateAnalyticsReport
       ?groupBy=ANALYTICS_GROUP_BY_API_KEY_OWNER
       &sections=ANALYTICS_SECTION_COST,ANALYTICS_SECTION_API_CALLS
       &startTime=...&endTime=...&omitZeroEntries=true
       -> per-owner spend; USER owners join to (1) by ownerId == user.id

Join = email -> user id -> owner spend. Tag-filtered queries
(attendee:<handle>) are also supported for cross-checks and fallbacks; the
aggregation matches the console CSV exporter so numbers reconcile.

CLI (for facilitator dry-runs):

    python scripts/kimchi_usage.py users
    python scripts/kimchi_usage.py owners --start 2026-10-27T00:00:00Z
    python scripts/kimchi_usage.py tag --tag attendee:alice --start ...

Credentials: KIMCHI_API_KEY env, else ~/.config/kimchi/config.json (never
logged). Org: KIMCHI_ORG_ID env, else DEFAULT_ORG. Stdlib only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_BASE_URL = "https://api.cast.ai"
DEFAULT_ORG = "f3e6b119-888a-42bd-aa90-5cca48078a4e"
DEFAULT_WINDOW_DAYS = 30
USER_SUFFIX = "USER"  # matches "USER" and "CAST_AI_API_KEY_OWNER_TYPE_USER"


class KimchiUsageError(RuntimeError):
    """Raised when the Kimchi/CAST AI API cannot be queried."""


def resolve_api_key(explicit=None):
    """API key precedence: argument > KIMCHI_API_KEY env > local CLI config."""
    if explicit:
        return explicit
    env = os.environ.get("KIMCHI_API_KEY", "").strip()
    if env:
        return env
    cfg_path = os.path.expanduser("~/.config/kimchi/config.json")
    try:
        with open(cfg_path) as f:
            return (json.load(f).get("apiKey") or "").strip() or None
    except (OSError, ValueError):
        return None


def resolve_org_id(explicit=None):
    return (explicit or os.environ.get("KIMCHI_ORG_ID", "").strip()
            or DEFAULT_ORG)


def _get_json(url, params, api_key, timeout=30, retries=1):
    """GET with Bearer auth; one retry on 429/5xx; JSON only."""
    full = url
    if params:
        full += "?" + urllib.parse.urlencode(params, doseq=True)
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(full, headers={
            "Authorization": "Bearer %s" % api_key,
            "User-Agent": "kimchi-workshop-leaderboard/1.0",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            last_err = KimchiUsageError("HTTP %s from %s: %s"
                                        % (e.code, url.split("?")[0], body))
            if e.code in (429,) or e.code >= 500:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last_err
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = KimchiUsageError("request to %s failed: %s"
                                        % (url.split("?")[0], e))
            if attempt < retries:
                time.sleep(1.5)
                continue
            raise last_err
    raise last_err  # pragma: no cover - loop always raises or returns


def _parse_iso(ts):
    ts = (ts or "").strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _analytics_url(base_url, org_id):
    return ("%s/ai-optimizer/v1beta/organizations/%s:generateAnalyticsReport"
            % (base_url.rstrip("/"), org_id))


def fetch_org_users(api_key, org_id, base_url=None):
    """Map normalized email -> user id (and id -> email) for the org.

    Only members with both an id and an email are returned.
    """
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    url = "%s/v1/organizations/%s/users" % (base, org_id)
    data = _get_json(url, None, api_key)
    email_to_id, id_to_email = {}, {}
    for membership in data.get("users", []):
        user = membership.get("user") or {}
        uid, email = user.get("id"), (user.get("email") or "").strip().lower()
        if uid and email:
            email_to_id[email] = uid
            id_to_email[uid] = email
    return {"email_to_id": email_to_id, "id_to_email": id_to_email}


def _is_user_owner(meta):
    """ownerType may be spelled 'USER' or the full enum name."""
    return bool(meta.get("ownerId")) and (
        (meta.get("ownerType") or "").upper().endswith(USER_SUFFIX))


def _owner_spend_from(data):
    """Extract {owner_id: {cost_usd, requests, models_used}} from a report
    payload."""
    spend = {}
    for bucket in (data.get("cost") or {}).get("items", []):
        for m in bucket.get("models", []):
            meta = m.get("castaiApiKeyMetadata") or {}
            if not _is_user_owner(meta):
                continue
            acc = spend.setdefault(meta["ownerId"], {
                "cost_usd": 0.0, "requests": 0, "models_used": set()})
            try:
                acc["cost_usd"] += float(m.get("totalCost") or 0)
            except (TypeError, ValueError):
                pass
            if m.get("model"):
                acc["models_used"].add(m["model"])
    for bucket in (data.get("apiCalls") or {}).get("items", []):
        for m in bucket.get("models", []):
            meta = m.get("castaiApiKeyMetadata") or {}
            if not _is_user_owner(meta):
                continue
            acc = spend.setdefault(meta["ownerId"], {
                "cost_usd": 0.0, "requests": 0, "models_used": set()})
            try:
                acc["requests"] += int(m.get("totalCount") or 0)
            except (TypeError, ValueError):
                pass
            if m.get("model"):
                acc["models_used"].add(m["model"])
    for acc in spend.values():
        acc["models_used"] = sorted(acc["models_used"])
    return spend


def _split_window(start, end):
    mid = start + (end - start) / 2
    return (start, mid), (mid, end)


def fetch_owner_costs(api_key, org_id, start, end, base_url=None, tags=None):
    """Spend per user owner over [start, end), optionally scoped to tags.

    With tags=None this is org-wide (used to detect participants who forgot
    their attendee tag). With a tag it answers "who owns this workshop
    spend" — the join point between Kimchi identity and the leaderboard.

    The analytics endpoint caps result rows; if the window is too wide the
    API says so in a 400. We bisect the window (down to one hour) and merge,
    so callers always get a complete answer or a clean error.
    """
    params = {
        "groupBy": ["ANALYTICS_GROUP_BY_API_KEY_OWNER"],
        "sections": ["ANALYTICS_SECTION_COST", "ANALYTICS_SECTION_API_CALLS"],
        "omitZeroEntries": "true",
    }
    if tags:
        params["tags"] = list(tags)

    def _query(start_dt, end_dt, depth=0):
        p = dict(params)
        p["startTime"] = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        p["endTime"] = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            return _owner_spend_from(
                _get_json(_analytics_url(base_url or DEFAULT_BASE_URL,
                                         org_id), p, api_key))
        except KimchiUsageError as e:
            span = end_dt - start_dt
            if "row limit" not in str(e).lower() or span <= timedelta(hours=1) \
                    or depth > 12:
                raise
            (s1, e1), (s2, e2) = _split_window(start_dt, end_dt)
            left = _query(s1, e1, depth + 1)
            right = _query(s2, e2, depth + 1)
            for oid, acc in right.items():
                cur = left.setdefault(oid, {"cost_usd": 0.0, "requests": 0,
                                            "models_used": []})
                cur["cost_usd"] += acc["cost_usd"]
                cur["requests"] += acc["requests"]
                merged = set(cur.get("models_used", []))
                merged.update(acc.get("models_used", []))
                cur["models_used"] = sorted(merged)
            return left

    return _query(_parse_iso(start), _parse_iso(end))


def fetch_tag_usage(api_key, org_id, tag, start, end, base_url=None):
    """Usage for one tag (e.g. attendee:<handle>), same aggregation as the
    console CSV exporter: per-model rows summed across time buckets."""
    params = {
        "tags": [tag],
        "groupBy": ["ANALYTICS_GROUP_BY_MODEL"],
        "sections": ["ANALYTICS_SECTION_COST",
                     "ANALYTICS_SECTION_API_CALLS",
                     "ANALYTICS_SECTION_TOKENS"],
        "omitZeroEntries": "true",
        "startTime": _parse_iso(start).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endTime": _parse_iso(end).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    data = _get_json(_analytics_url(base_url or DEFAULT_BASE_URL, org_id),
                     params, api_key)

    models = {}
    for section, pick in (("cost", lambda m: float(m.get("totalCost") or 0)),
                          ("apiCalls", lambda m: int(m.get("totalCount") or 0))):
        for bucket in (data.get(section) or {}).get("items", []):
            for m in bucket.get("models", []):
                name = m.get("model")
                if not name:
                    continue
                acc = models.setdefault(name, {"cost_usd": 0.0, "requests": 0})
                try:
                    acc["cost_usd" if section == "cost" else "requests"] += \
                        pick(m)
                except (TypeError, ValueError):
                    pass
    return {
        "cost_usd": round(sum(v["cost_usd"] for v in models.values()), 6),
        "requests": sum(v["requests"] for v in models.values()),
        "models_used": sorted(models),
        "rows": len(models),
    }


def _default_start():
    return (datetime.now(timezone.utc)
            - timedelta(days=DEFAULT_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["users", "owners", "tag"])
    ap.add_argument("--org", help="organization id (default: KIMCHI_ORG_ID "
                                  "or workshop default)")
    ap.add_argument("--tag", help="tag for the `tag` command")
    ap.add_argument("--start", help="window start ISO (default: 30d ago)")
    ap.add_argument("--end", help="window end ISO (default: now)")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = ap.parse_args(argv)

    api_key = resolve_api_key()
    if not api_key:
        print("::error::no API key (set KIMCHI_API_KEY or run kimchi login)",
              file=sys.stderr)
        return 2
    org_id = resolve_org_id(args.org)
    start = args.start or _default_start()
    end = args.end or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        if args.command == "users":
            out = fetch_org_users(api_key, org_id, args.base_url)
            out["members"] = len(out["email_to_id"])
            out.pop("id_to_email")  # keep stdout compact
        elif args.command == "owners":
            spend = fetch_owner_costs(api_key, org_id, start, end,
                                      args.base_url)
            out = {"owners": len(spend), "window": [start, end],
                   "total_cost_usd": round(
                       sum(v["cost_usd"] for v in spend.values()), 4)}
        else:
            if not args.tag:
                print("::error::--tag is required for the tag command",
                      file=sys.stderr)
                return 2
            out = fetch_tag_usage(api_key, org_id, args.tag, start, end,
                                  args.base_url)
    except KimchiUsageError as e:
        print("::error::%s" % e, file=sys.stderr)
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
