"""Offline API tests: no Google Cloud calls or credentials required."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as billing_app


class BillingApiTests(unittest.TestCase):
    def setUp(self):
        self.token = patch.dict(os.environ, {"BILLING_READ_TOKEN": "test-only-secret", "MONTHLY_BUDGET": "1000"})
        self.token.start()
        billing_app._cache_value = None
        billing_app._cache_until = 0

    def tearDown(self):
        self.token.stop()
        billing_app._cache_value = None
        billing_app._cache_until = 0

    def test_missing_token_is_rejected(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as result:
            billing_app.authorized(None)
        self.assertEqual(result.exception.status_code, 401)

    def test_bad_token_is_rejected(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as result:
            billing_app.authorized("bad-token")
        self.assertEqual(result.exception.status_code, 401)

    def test_missing_account_prevents_partial_total(self):
        ready = {"status": "ready", "currency": "JPY", "month": 120, "forecast": 200}
        pending = {"status": "pending", "month": None}
        with patch.object(billing_app, "read_account", side_effect=[ready, pending]) as read:
            result = billing_app.billing("test-only-secret")
        self.assertIsNone(result["total_month"])
        self.assertIsNone(result["forecast"])
        self.assertEqual(read.call_count, 2)

    def test_both_accounts_sum_and_cache(self):
        a = {"status": "ready", "currency": "JPY", "month": 100, "forecast": 200}
        b = {"status": "ready", "currency": "JPY", "month": 200, "forecast": 400}
        with patch.object(billing_app, "read_account", side_effect=[a, b]) as read:
            result = billing_app.billing("test-only-secret")
            cached = billing_app.billing("test-only-secret")
        self.assertEqual(result["total_month"], 300)
        self.assertEqual(result["forecast"], 600)
        self.assertFalse(result["over_budget"])
        self.assertEqual(cached, result)
        self.assertEqual(read.call_count, 2)

    def test_budget_warning_when_forecast_exceeds_budget(self):
        a = {"status": "ready", "currency": "JPY", "month": 500, "forecast": 700}
        b = {"status": "ready", "currency": "JPY", "month": 200, "forecast": 500}
        with patch.object(billing_app, "read_account", side_effect=[a, b]):
            result = billing_app.billing("test-only-secret")
        self.assertEqual(result["total_month"], 700)
        self.assertEqual(result["forecast"], 1200)
        self.assertTrue(result["over_budget"])

    def test_cache_does_not_bypass_authentication(self):
        a = {"status": "ready", "currency": "JPY", "month": 100, "forecast": 200}
        with patch.object(billing_app, "read_account", return_value=a):
            billing_app.billing("test-only-secret")
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as error:
                billing_app.billing("wrong")
        self.assertEqual(error.exception.status_code, 401)

    def test_transient_errors_use_short_cache(self):
        with patch.object(billing_app, "read_account", side_effect=RuntimeError("offline")):
            with patch.object(billing_app, "monotonic", return_value=100):
                result = billing_app.billing("test-only-secret")
        self.assertIsNone(result["total_month"])
        self.assertEqual(billing_app._cache_until, 400)

    def test_empty_export_tables_are_pending(self):
        fake_client = MagicMock()
        fake_client.list_tables.return_value = []
        with patch.object(billing_app, "client", return_value=fake_client):
            result = billing_app.read_account("Tesla", "tesla-charge-hub", "gcp_billing_monitor")
        self.assertEqual(result["status"], "pending")
        fake_client.query.assert_not_called()

    def test_query_credits_and_service_breakdown(self):
        fake_client = MagicMock()
        fake_client.list_tables.return_value = [
            SimpleNamespace(table_id="gcp_billing_export_v1_01F37D_543EF8_154579")
        ]
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        previous = (now.replace(day=1) - timedelta(days=1))
        rows = [
            SimpleNamespace(month=now.strftime("%Y-%m"), day=now.strftime("%Y-%m-%d"),
                            currency="JPY", service_name="Compute Engine", net=100),
            SimpleNamespace(month=now.strftime("%Y-%m"), day=now.strftime("%Y-%m-%d"),
                            currency="JPY", service_name="BigQuery", net=-20),
            SimpleNamespace(month=previous.strftime("%Y-%m"), day=previous.strftime("%Y-%m-%d"),
                            currency="JPY", service_name="Compute Engine", net=70),
        ]
        fake_client.query.return_value.result.return_value = rows
        with patch.object(billing_app, "client", return_value=fake_client):
            result = billing_app.read_account("Tesla", "tesla-charge-hub", "gcp_billing_monitor")
        self.assertEqual(result["month"], 80)
        self.assertEqual(result["previous_month"], 70)
        self.assertEqual(sum(x["amount"] for x in result["services"]), 80)
        self.assertIn("UNNEST(credits)", fake_client.query.call_args.args[0])

    def test_mismatched_currency_has_no_total(self):
        a = {"status": "ready", "currency": "JPY", "month": 100, "forecast": 200}
        b = {"status": "ready", "currency": "USD", "month": 200, "forecast": 400}
        with patch.object(billing_app, "read_account", side_effect=[a, b]):
            result = billing_app.billing("test-only-secret")
        self.assertIsNone(result["total_month"])


if __name__ == "__main__":
    unittest.main()
