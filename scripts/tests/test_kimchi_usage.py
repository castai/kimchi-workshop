"""Tests for scripts/kimchi_usage.py (leaderboard API client).

Lives under scripts/tests/ on purpose: the scored challenge suite only runs
pytest tests/ -q, and adding files there would change participants' visible
test counts.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kimchi_usage import (  # noqa: E402
    KimchiUsageError,
    _owner_spend_from,
    _parse_iso,
    _split_window,
    fetch_org_users,
    fetch_owner_costs,
    fetch_tag_usage,
    resolve_api_key,
    resolve_org_id,
)

OWNER_REPORT = {
    "cost": {"items": [
        {"models": [
            {"model": "glm-x", "totalCost": "1.25",
             "castaiApiKeyMetadata": {"ownerType": "USER",
                                      "ownerId": "u-1"}},
            {"model": "glm-big", "totalCost": "10.00",  # service account
             "castaiApiKeyMetadata": {"ownerType": "SERVICE_ACCOUNT",
                                      "ownerId": "sa-9"}},
            {"totalCost": "99.00",  # no owner id: excluded
             "castaiApiKeyMetadata": {"ownerType": "USER", "ownerId": ""}},
        ]},
        {"models": [
            {"model": "glm-y", "totalCost": "0.75",
             "castaiApiKeyMetadata": {
                 "ownerType": "CAST_AI_API_KEY_OWNER_TYPE_USER",
                 "ownerId": "u-1"}},
        ]},
    ]},
    "apiCalls": {"items": [
        {"models": [
            {"model": "glm-x", "totalCount": "3",
             "castaiApiKeyMetadata": {"ownerType": "USER",
                                      "ownerId": "u-1"}},
            {"model": "glm-x", "totalCount": "7",
             "castaiApiKeyMetadata": {"ownerType": "USER",
                                      "ownerId": "u-2"}},
        ]},
    ]},
}

TAG_REPORT = {
    "cost": {"items": [
        {"models": [{"model": "glm-x", "totalCost": "0.50"}]},
        {"models": [{"model": "glm-x", "totalCost": "0.25"},
                    {"model": "minimax-y", "totalCost": "0.10"}]},
    ]},
    "apiCalls": {"items": [
        {"models": [{"model": "glm-x", "totalCount": "10"},
                    {"model": "minimax-y", "totalCount": "4"}]},
    ]},
    "tokens": {"items": []},
}


class OwnerSpendTest(unittest.TestCase):
    def test_user_owners_only_across_sections(self):
        spend = _owner_spend_from(OWNER_REPORT)
        self.assertEqual(set(spend), {"u-1", "u-2"})
        self.assertAlmostEqual(spend["u-1"]["cost_usd"], 2.0)
        self.assertEqual(spend["u-1"]["requests"], 3)
        self.assertEqual(spend["u-2"]["requests"], 7)
        self.assertAlmostEqual(spend["u-2"]["cost_usd"], 0.0)
        self.assertEqual(spend["u-1"]["models_used"], ["glm-x", "glm-y"])
        self.assertEqual(spend["u-2"]["models_used"], ["glm-x"])

    def test_malformed_numbers_are_tolerated(self):
        payload = {"cost": {"items": [{"models": [
            {"totalCost": "not-a-number",
             "castaiApiKeyMetadata": {"ownerType": "USER", "ownerId": "u"}}]}]},
            "apiCalls": {"items": []}}
        spend = _owner_spend_from(payload)
        self.assertEqual(spend["u"]["cost_usd"], 0.0)


class WindowTest(unittest.TestCase):
    def test_parse_iso_handles_z_and_offset(self):
        self.assertEqual(_parse_iso("2026-10-27T00:00:00Z").hour, 0)
        self.assertEqual(_parse_iso("2026-10-27T03:00:00+03:00").hour, 0)

    def test_split_window_halves(self):
        s = _parse_iso("2026-10-27T00:00:00Z")
        e = _parse_iso("2026-10-29T00:00:00Z")
        (s1, e1), (s2, e2) = _split_window(s, e)
        self.assertEqual((e1 - s1), (e2 - s2))
        self.assertEqual(s1, s)
        self.assertEqual(e2, e)


class _FakeHTTP:
    """Callable faking kimchi_usage._get_json with queued results."""

    def __init__(self, payloads):
        self.payloads = payloads  # dict body or KimchiUsageError

    def __call__(self, url, params, api_key, timeout=30, retries=1):
        item = self.payloads.pop(0)
        if isinstance(item, KimchiUsageError):
            raise item
        return item


class FetchOwnerCostsTest(unittest.TestCase):
    def test_row_limit_bisects_and_merges(self):
        err = KimchiUsageError(
            'HTTP 400: {"message":"analytics query result exceeds the row '
            'limit, narrow the time range or filters"}')
        fake = _FakeHTTP([err, OWNER_REPORT, OWNER_REPORT])
        with mock.patch("kimchi_usage._get_json", fake):
            spend = fetch_owner_costs(
                "k", "org", "2026-10-01T00:00:00Z", "2026-10-08T00:00:00Z")
        # two half-window responses merged: u-1 cost doubles
        self.assertAlmostEqual(spend["u-1"]["cost_usd"], 4.0)
        self.assertEqual(len(fake.payloads), 0)

    def test_non_rowlimit_error_propagates(self):
        fake = _FakeHTTP([KimchiUsageError("HTTP 403: forbidden")])
        with mock.patch("kimchi_usage._get_json", fake):
            with self.assertRaises(KimchiUsageError):
                fetch_owner_costs("k", "org", "2026-10-01T00:00:00Z",
                                  "2026-10-02T00:00:00Z")


class FetchOrgUsersTest(unittest.TestCase):
    def test_normalizes_and_skips_incomplete(self):
        fake = _FakeHTTP([{"users": [
            {"user": {"id": "u-1", "email": "  Alice@Example.COM "}},
            {"user": {"id": "u-2", "email": ""}},
            {"user": {"id": "", "email": "x@y.z"}},
        ]}])
        with mock.patch("kimchi_usage._get_json", fake):
            out = fetch_org_users("k", "org")
        self.assertEqual(out["email_to_id"], {"alice@example.com": "u-1"})
        self.assertEqual(out["id_to_email"], {"u-1": "alice@example.com"})


class FetchTagUsageTest(unittest.TestCase):
    def test_aggregates_models_across_buckets(self):
        fake = _FakeHTTP([TAG_REPORT])
        with mock.patch("kimchi_usage._get_json", fake):
            out = fetch_tag_usage("k", "org", "attendee:a",
                                  "2026-10-27T00:00:00Z",
                                  "2026-10-28T00:00:00Z")
        self.assertAlmostEqual(out["cost_usd"], 0.85)
        self.assertEqual(out["requests"], 14)
        self.assertEqual(out["models_used"], ["glm-x", "minimax-y"])
        self.assertEqual(out["rows"], 2)


class ResolutionTest(unittest.TestCase):
    def test_explicit_wins_then_env(self):
        with mock.patch.dict(os.environ, {"KIMCHI_API_KEY": "env-key"}):
            self.assertEqual(resolve_api_key("explicit"), "explicit")
            self.assertEqual(resolve_api_key(), "env-key")

    def test_org_default_chain(self):
        self.assertEqual(resolve_org_id("x"), "x")
        with mock.patch.dict(os.environ, {"KIMCHI_ORG_ID": "env-org"}):
            self.assertEqual(resolve_org_id(), "env-org")
        import kimchi_usage
        self.assertEqual(resolve_org_id(), kimchi_usage.DEFAULT_ORG)


if __name__ == "__main__":
    unittest.main()
