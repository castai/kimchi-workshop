"""Tests for scripts/enrich_costs.py (email-mapped API cost stamping).

Semantics: participants are fresh Kimchi accounts, so an owner's TOTAL spend
in the window is their workshop spend — cost comes from the email -> owner
join (fetched once, org-wide). The attendee tag provides the identity
cross-check (tag owner vs email owner) and a cost fallback when no email
can be joined.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from enrich_costs import (  # noqa: E402
    cost_efficiency_points,
    enrich_record,
    load_records,
    main,
    normalize_email,
    recompute_points,
)

ROSTER = {
    "email_to_id": {"alice@example.com": "uid-alice"},
    "id_to_email": {"uid-alice": "alice@example.com"},
}
ORG_SPEND = {"uid-alice": {"cost_usd": 12.3456, "requests": 300,
                           "models_used": ["glm-x", "glm-y"]}}
TAG_USAGE = {"cost_usd": 0.50, "requests": 42,
             "models_used": ["glm-x"], "rows": 1}
TAG_OWNERS_SAME = {"uid-alice": {"cost_usd": 0.50, "requests": 42,
                                 "models_used": ["glm-x"]}}
TAG_OWNERS_OTHER = {"uid-someone": {"cost_usd": 0.50, "requests": 42,
                                    "models_used": ["glm-x"]}}
NOW = "2026-11-06T12:00:00+00:00"


def base_record(**over):
    record = {
        "attendee": "alice",
        "email": "alice@example.com",
        "cost_usd": 1.11,
        "csv_rows": 3,
        "requests": 7,
        "score_breakdown": {
            "visible_tests": 27, "production_tests": 16, "models_used": 6,
            "request_count": 8, "cost_efficiency": 2.22, "time_to_accept": 10,
            "commit_discipline": 8, "code_quality": 7, "full_clear_bonus": 0,
        },
        "points": 84.22,
    }
    record.update(over)
    return record


def enrich(record, verify=True, tag_owners=TAG_OWNERS_SAME,
           tag_usage=TAG_USAGE, roster=ROSTER, org_spend=ORG_SPEND,
           api_key="k"):
    """org_spend is passed straight in (fetched once per run); the per-record
    tag queries go through the module functions mocked here."""
    with mock.patch("enrich_costs.fetch_owner_costs",
                    return_value=tag_owners), \
         mock.patch("enrich_costs.fetch_tag_usage",
                    return_value=tag_usage):
        changed = enrich_record(record, roster, org_spend, NOW, 2.0,
                                verify, api_key, "org", None, "start")
    return changed


class FormulaTest(unittest.TestCase):
    def test_v2_cost_band_matches_leaderboard_yml(self):
        self.assertEqual(cost_efficiency_points(0.0, 2.0, True), 10.0)
        self.assertEqual(cost_efficiency_points(2.0, 2.0, True), 5.0)
        self.assertEqual(cost_efficiency_points(1.0, 2.0, True), 7.5)
        self.assertEqual(cost_efficiency_points(4.0, 2.0, True), -2.0)
        self.assertEqual(cost_efficiency_points(12.0, 2.0, True), -10.0)
        self.assertEqual(cost_efficiency_points(5.0, 2.0, False), 0)

    def test_recompute_updates_breakdown_and_points(self):
        record = base_record()  # cost_usd stays 1.11
        record["usage_verified"] = True
        record["requests"] = 300
        record["models_used"] = ["glm-x", "glm-y"]
        self.assertTrue(recompute_points(record, 2.0))
        # models 2 -> 4 pts; requests 300 -> log2(301)*1.77 -> 10 pts;
        # 10 - 5*(1.11/2) = 7.225 -> 7.22 (float repr)
        self.assertEqual(record["score_breakdown"]["models_used"], 4)
        self.assertEqual(record["score_breakdown"]["request_count"], 10)
        self.assertEqual(record["score_breakdown"]["cost_efficiency"], 7.22)
        # 27+16+4+10+10+8+7+0+7.22
        self.assertEqual(record["points"], 89.22)


class EnrichRecordTest(unittest.TestCase):
    def test_email_join_decides_cost_from_owner_total(self):
        record = base_record()
        self.assertTrue(enrich(record))
        self.assertEqual(record["cost_usd"], 12.3456)   # owner total
        self.assertEqual(record["cost_csv_usd"], 1.11)  # audit trail
        self.assertEqual(record["requests"], 300)
        self.assertEqual(record["models_used"], ["glm-x", "glm-y"])
        self.assertEqual(record["cost_source"], "kimchi_api")
        self.assertTrue(record["usage_verified"])
        self.assertEqual(record["api_owner_id"], "uid-alice")
        # full breakdown recompute: models 2 -> 4 pts, requests 300 -> 10,
        # cost 12.3456 vs $2 budget -> capped at -10
        self.assertEqual(record["score_breakdown"]["models_used"], 4)
        self.assertEqual(record["score_breakdown"]["request_count"], 10)
        self.assertEqual(record["score_breakdown"]["cost_efficiency"], -10)
        # 27+16+4+10-10+10+8+7+0
        self.assertEqual(record["points"], 72.0)

    def test_matching_tag_owner_is_not_flagged(self):
        record = base_record()
        self.assertTrue(enrich(record, tag_owners=TAG_OWNERS_SAME))
        self.assertEqual(record["tag_owner_id"], "uid-alice")
        self.assertFalse(record["tag_email_mismatch"])

    def test_identity_mismatch_flagged_but_cost_still_verified(self):
        record = base_record()
        self.assertTrue(enrich(record, tag_owners=TAG_OWNERS_OTHER))
        self.assertEqual(record["cost_usd"], 12.3456)  # email join wins
        self.assertTrue(record["usage_verified"])
        self.assertTrue(record["tag_email_mismatch"])
        self.assertEqual(record["tag_owner_id"], "uid-someone")

    def test_no_verify_skips_identity_check(self):
        record = base_record()
        self.assertTrue(enrich(record, verify=False))
        self.assertTrue(record["usage_verified"])
        self.assertNotIn("tag_owner_id", record)
        self.assertNotIn("tag_email_mismatch", record)

    def test_unknown_email_with_no_tag_spend_falls_back_to_csv(self):
        empty_tag = {"cost_usd": 0.0, "requests": 0, "models_used": [],
                     "rows": 0}
        record = base_record(email="nobody@nowhere.test", attendee="bob")
        self.assertTrue(enrich(record, tag_owners={}, tag_usage=empty_tag))
        self.assertEqual(record["cost_usd"], 1.11)
        self.assertFalse(record["usage_verified"])
        self.assertEqual(record["cost_source"], "csv")
        # breakdown untouched: no points recompute without an API match
        self.assertEqual(record["score_breakdown"]["cost_efficiency"], 2.22)
        self.assertEqual(record["points"], 84.22)
        self.assertTrue(record["email_not_in_kimchi"])

    def test_no_email_but_tagged_spend_still_gets_api_cost(self):
        record = base_record(email=None)
        self.assertTrue(enrich(record, tag_owners={}))
        self.assertEqual(record["cost_usd"], 0.5)  # tag-scoped fallback
        self.assertEqual(record["cost_source_detail"], "attendee_tag")
        self.assertTrue(record["usage_verified"])

    def test_email_in_roster_but_zero_spend_falls_back(self):
        empty_tag = {"cost_usd": 0.0, "requests": 0, "models_used": [],
                     "rows": 0}
        record = base_record()
        self.assertTrue(enrich(record, org_spend={}, tag_usage=empty_tag))
        self.assertFalse(record["usage_verified"])
        self.assertEqual(record["cost_source"], "csv")
        self.assertNotIn("email_not_in_kimchi", record)  # known, just idle

    def test_missing_attendee_and_email_is_tolerated(self):
        record = base_record(attendee=None, email=None)
        empty_tag = {"cost_usd": 0.0, "requests": 0, "models_used": [],
                     "rows": 0}
        self.assertTrue(enrich(record, tag_owners={}, tag_usage=empty_tag))
        self.assertFalse(record["usage_verified"])

    def test_api_failure_on_tag_check_degrades_gracefully(self):
        from kimchi_usage import KimchiUsageError
        record = base_record()
        with mock.patch("enrich_costs.fetch_owner_costs",
                        side_effect=KimchiUsageError("boom")):
            changed = enrich_record(record, ROSTER, ORG_SPEND, NOW, 2.0,
                                    True, "k", "org", None, "start")
        self.assertTrue(changed)
        # cost still verified via the email join; only the check failed
        self.assertTrue(record["usage_verified"])
        self.assertEqual(record["cost_usd"], 12.3456)


class MainTest(unittest.TestCase):
    def test_end_to_end_over_tmp_records_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = base_record()
            bob = base_record(attendee="bob", email="bob@x.io",
                              cost_usd=0.75, csv_rows=1)
            for name, rec in (("alice.json", good), ("bob.json", bob)):
                with open(os.path.join(tmp, name), "w") as f:
                    json.dump(rec, f)

            empty_tag = {"cost_usd": 0.0, "requests": 0, "models_used": [],
                         "rows": 0}
            with mock.patch("enrich_costs.resolve_api_key",
                            return_value="k"), \
                 mock.patch("enrich_costs.fetch_org_users",
                            return_value=ROSTER), \
                 mock.patch("enrich_costs.fetch_owner_costs",
                            side_effect=lambda *a, **kw: (
                                TAG_OWNERS_SAME if kw.get("tags")
                                else ORG_SPEND)), \
                 mock.patch("enrich_costs.fetch_tag_usage",
                            side_effect=lambda k, o, tag, s, e, b=None: (
                                TAG_USAGE if "alice" in tag else empty_tag)):
                rc = main(["--records", tmp])
            self.assertEqual(rc, 0)

            rows = {os.path.basename(p): r for p, r in load_records(tmp)}
            alice = rows["alice.json"]
            self.assertEqual(alice["cost_usd"], 12.3456)
            self.assertTrue(alice["usage_verified"])
            self.assertFalse(alice["tag_email_mismatch"])
            bob_r = rows["bob.json"]
            self.assertEqual(bob_r["cost_usd"], 0.75)  # untouched fallback
            self.assertTrue(bob_r["email_not_in_kimchi"])

    def test_missing_records_dir_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = main(["--records", os.path.join(tmp, "nope")])
        self.assertEqual(rc, 1)

    def test_no_api_key_leaves_records_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.json")
            with open(path, "w") as f:
                json.dump(base_record(), f)
            with mock.patch("enrich_costs.resolve_api_key",
                            return_value=None):
                rc = main(["--records", tmp])
            self.assertEqual(rc, 0)
            with open(path) as f:
                self.assertNotIn("usage_verified", json.load(f))


if __name__ == "__main__":
    unittest.main()
