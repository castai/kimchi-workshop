"""Tests for scripts/enrich_costs.py (email-mapped API cost stamping).

Semantics: tag-scoped API spend decides the cost; the email join verifies
identity (email_verified / tag_email_mismatch); records without tag spend
fall back to CSV with hint flags (forgot_tag / email_not_in_kimchi).
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
    mask_email,
    normalize_email,
    recompute_points,
)

ROSTER = {
    "email_to_id": {"alice@example.com": "uid-alice"},
    "id_to_email": {"uid-alice": "alice@example.com",
                    "uid-someone": "someone.else@cast.ai"},
}
ORG_SPEND = {"uid-alice": {"cost_usd": 12.0, "requests": 100}}
TAG_USAGE = {"cost_usd": 0.50, "requests": 42,
             "models_used": ["glm-x"], "rows": 1}
TAG_OWNERS = {"uid-alice": {"cost_usd": 0.50, "requests": 42}}
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


def enrich(record, verify=True, tag_usage=TAG_USAGE, tag_owners=TAG_OWNERS,
           roster=ROSTER, org_spend=ORG_SPEND, api_key="k"):
    # org_spend (the forgot-tag hint lookup) is passed into enrich_record
    # directly; only the per-record tag queries go through the module
    # functions mocked here.
    with mock.patch("enrich_costs.fetch_tag_usage",
                    return_value=tag_usage), \
         mock.patch("enrich_costs.fetch_owner_costs",
                    return_value=tag_owners):
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
        self.assertTrue(recompute_points(record, 2.0))
        # 10 - 5*(1.11/2) = 7.225 -> 7.22 (float repr)
        self.assertEqual(record["score_breakdown"]["cost_efficiency"], 7.22)
        # 27+16+6+8+10+8+7+0+7.22
        self.assertEqual(record["points"], 89.22)


class MaskTest(unittest.TestCase):
    def test_mask_email(self):
        self.assertEqual(mask_email("matas@cast.ai"), "mat***@cast.ai")
        self.assertEqual(mask_email(""), "")
        self.assertEqual(mask_email("no-at-sign"), "")


class EnrichRecordTest(unittest.TestCase):
    def test_tag_spend_decides_cost_and_email_verifies(self):
        record = base_record()
        self.assertTrue(enrich(record))
        self.assertEqual(record["cost_usd"], 0.5)         # API, not CSV
        self.assertEqual(record["cost_csv_usd"], 1.11)    # audit trail
        self.assertEqual(record["requests"], 42)
        self.assertEqual(record["models_used"], ["glm-x"])
        self.assertEqual(record["cost_source"], "kimchi_api")
        self.assertTrue(record["usage_verified"])
        self.assertTrue(record["email_verified"])
        self.assertFalse(record["tag_email_mismatch"])  # explicit, not absent
        # points recomputed with the API cost: 10 - 5*(0.5/2) = 8.75
        self.assertEqual(record["score_breakdown"]["cost_efficiency"], 8.75)
        # 27+16+6+8+10+8+7+0+8.75
        self.assertEqual(record["points"], 90.75)

    def test_email_mismatch_flagged_but_cost_still_verified(self):
        record = base_record(email="claimed@somewhere.else")
        self.assertTrue(enrich(record))
        self.assertEqual(record["cost_usd"], 0.5)
        self.assertTrue(record["usage_verified"])
        self.assertFalse(record["email_verified"])
        self.assertTrue(record["tag_email_mismatch"])
        self.assertEqual(record["api_email_masked"], "ali***@example.com")

    def test_no_verify_skips_identity_flags(self):
        record = base_record()
        self.assertTrue(enrich(record, verify=False))
        self.assertTrue(record["usage_verified"])
        self.assertNotIn("email_verified", record)
        self.assertNotIn("api_owner_id", record)

    def test_no_tag_spend_falls_back_to_csv(self):
        empty = {"cost_usd": 0.0, "requests": 0, "models_used": [], "rows": 0}
        record = base_record()
        self.assertTrue(enrich(record, tag_usage=empty, tag_owners={}))
        self.assertEqual(record["cost_usd"], 1.11)
        self.assertFalse(record["usage_verified"])
        self.assertEqual(record["cost_source"], "csv")
        # breakdown untouched: no points recompute without an API match
        self.assertEqual(record["score_breakdown"]["cost_efficiency"], 2.22)
        self.assertEqual(record["points"], 84.22)

    def test_forgot_tag_hint_when_email_owner_spent(self):
        empty = {"cost_usd": 0.0, "requests": 0, "models_used": [], "rows": 0}
        record = base_record()
        self.assertTrue(enrich(record, tag_usage=empty, tag_owners={}))
        self.assertTrue(record["forgot_tag"])

    def test_email_not_in_kimchi_hint(self):
        empty = {"cost_usd": 0.0, "requests": 0, "models_used": [], "rows": 0}
        record = base_record(email="ghost@nowhere.test", attendee="bob")
        self.assertTrue(enrich(record, tag_usage=empty, tag_owners={}))
        self.assertTrue(record["email_not_in_kimchi"])
        self.assertNotIn("forgot_tag", record)

    def test_missing_attendee_and_email_is_tolerated(self):
        record = base_record(attendee=None, email=None)
        empty = {"cost_usd": 0.0, "requests": 0, "models_used": [], "rows": 0}
        self.assertTrue(enrich(record, tag_usage=empty, tag_owners={}))
        self.assertFalse(record["usage_verified"])

    def test_api_failure_on_tag_query_degrades(self):
        from kimchi_usage import KimchiUsageError
        record = base_record()
        with mock.patch("enrich_costs.fetch_tag_usage",
                        side_effect=KimchiUsageError("boom")), \
             mock.patch("enrich_costs.fetch_owner_costs",
                        return_value={}):
            changed = enrich_record(record, ROSTER, ORG_SPEND, NOW, 2.0,
                                    True, "k", "org", None, "start")
        self.assertTrue(changed)
        self.assertFalse(record["usage_verified"])
        self.assertEqual(record["cost_source"], "csv")


class MainTest(unittest.TestCase):
    def test_end_to_end_over_tmp_records_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = base_record()
            bob = base_record(attendee="bob", email="bob@x.io",
                              cost_usd=0.75, csv_rows=1)
            for name, rec in (("alice.json", good), ("bob.json", bob)):
                with open(os.path.join(tmp, name), "w") as f:
                    json.dump(rec, f)

            empty = {"cost_usd": 0.0, "requests": 0, "models_used": [],
                     "rows": 0}
            with mock.patch("enrich_costs.resolve_api_key",
                            return_value="k"), \
                 mock.patch("enrich_costs.fetch_org_users",
                            return_value=ROSTER), \
                 mock.patch("enrich_costs.fetch_owner_costs",
                            return_value=ORG_SPEND), \
                 mock.patch("enrich_costs.fetch_tag_usage",
                            side_effect=lambda k, o, tag, s, e, b=None: (
                                TAG_USAGE if "alice" in tag else empty)):
                rc = main(["--records", tmp])
            self.assertEqual(rc, 0)

            rows = {os.path.basename(p): r for p, r in load_records(tmp)}
            alice = rows["alice.json"]
            self.assertEqual(alice["cost_usd"], 0.5)
            self.assertTrue(alice["usage_verified"])
            self.assertTrue(alice["email_verified"])
            bob_r = rows["bob.json"]
            self.assertEqual(bob_r["cost_usd"], 0.75)  # untouched fallback
            self.assertTrue(bob_r["email_not_in_kimchi"])
            self.assertNotIn("forgot_tag", bob_r)

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
