"""Offline API tests: no Google Cloud calls or credentials required."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_mismatched_currency_has_no_total(self):
        a = {"status": "ready", "currency": "JPY", "month": 100, "forecast": 200}
        b = {"status": "ready", "currency": "USD", "month": 200, "forecast": 400}
        with patch.object(billing_app, "read_account", side_effect=[a, b]):
            result = billing_app.billing("test-only-secret")
        self.assertIsNone(result["total_month"])


if __name__ == "__main__":
    unittest.main()
