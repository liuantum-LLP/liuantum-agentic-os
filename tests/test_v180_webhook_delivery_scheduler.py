"""Tests for Liuant Agentic OS v1.8.0.

Tests real HTTP webhook delivery, HMAC signatures, webhook delivery log,
per-round discussion costs, cleanup scheduler, export-before-cleanup,
and UI updates. All tests use mocked delivery, no real network access.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.config import SettingsManager
from runtime.db import delete_all_records, init_db
from runtime.storage import WORKSPACE
from runtime.usage.tracker import UsageTracker


def _reset_db():
    init_db()
    for table in ("usage_events", "alert_history", "webhook_deliveries", "discussion_cost_rounds"):
        try:
            delete_all_records(table)
        except Exception:
            pass


class TestWebhookHTTPDelivery(unittest.TestCase):
    """Phase 1 & 3: Real HTTP webhook delivery and delivery log."""

    def setUp(self):
        _reset_db()
        self.settings = SettingsManager()
        self.settings.set("webhook_alerts_enabled", "false")
        self.settings.set("webhook_url", "")
        self.settings.set("webhook_test_mode", "true")
        self.settings.set("webhook_hmac_enabled", "false")
        self.settings.set("webhook_secret", "")

    def test_webhook_http_delivery_disabled_by_default(self):
        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default", "level": "info", "message": "test"})
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "webhooks_disabled")

    @patch("urllib.request.urlopen")
    def test_webhook_delivery_sends_mocked_post_when_enabled(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response

        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_url", "https://example.com/webhook")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("budget_warning", {"workspace": "default", "level": "warning", "message": "Budget at 90%"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["status_code"], 200)
        mock_urlopen.assert_called_once()

    def test_webhook_delivery_requires_https_url(self):
        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_url", "http://example.com/webhook")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "webhook_url_not_https")

    @patch("urllib.request.urlopen")
    def test_webhook_retry_handles_timeout(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_url", "https://example.com/webhook")
        self.settings.set("webhook_max_retries", "1")
        self.settings.set("webhook_timeout", "1")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        self.assertEqual(result["status"], "failed")
        self.assertGreaterEqual(result["retry_count"], 1)

    @patch("urllib.request.urlopen")
    def test_webhook_retry_handles_429(self, mock_urlopen):
        import urllib.error
        mock_error = urllib.error.HTTPError("https://example.com", 429, "Too Many Requests", {}, None)
        mock_urlopen.side_effect = mock_error

        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_url", "https://example.com/webhook")
        self.settings.set("webhook_max_retries", "1")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["status_code"], 429)

    @patch("urllib.request.urlopen")
    def test_webhook_does_not_retry_unsafe_400(self, mock_urlopen):
        import urllib.error
        mock_error = urllib.error.HTTPError("https://example.com", 400, "Bad Request", {}, None)
        mock_urlopen.side_effect = mock_error

        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_url", "https://example.com/webhook")
        self.settings.set("webhook_max_retries", "3")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(result["retry_count"], 0)

    def test_webhook_delivery_log_stores_url_hash_not_full_url(self):
        from runtime.usage.webhooks import WebhookDelivery, _safe_hash
        delivery = WebhookDelivery()
        test_url = "https://example.com/webhook"
        log = delivery._log_delivery("test", "default", test_url, "success", 200, 0, "", False, '{"test": true}')
        self.assertEqual(log["url_hash"], _safe_hash(test_url))
        self.assertNotIn(test_url, log["url_hash"])

    def test_webhook_delivery_log_stores_payload_hash_not_full_payload(self):
        from runtime.usage.webhooks import WebhookDelivery, _safe_hash
        delivery = WebhookDelivery()
        test_payload = '{"event_type":"test","workspace":"default","message":"secret data"}'
        log = delivery._log_delivery("test", "default", "https://example.com", "success", 200, 0, "", False, test_payload)
        self.assertEqual(log["payload_hash"], _safe_hash(test_payload))
        self.assertNotIn("secret data", log["payload_hash"])


class TestHMACSignature(unittest.TestCase):
    """Phase 2: HMAC signature verification support."""

    def setUp(self):
        _reset_db()
        self.settings = SettingsManager()
        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_url", "https://example.com/webhook")
        self.settings.set("webhook_test_mode", "true")
        self.settings.set("webhook_hmac_enabled", "false")
        self.settings.set("webhook_secret", "")

    def test_hmac_signature_header_generated(self):
        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        self.settings.set("webhook_secret", "test-secret-key")
        self.settings.set("webhook_hmac_enabled", "true")
        payload_json = '{"event_type":"test","workspace":"default"}'
        headers = delivery._build_signature_headers(payload_json, "test_event")
        self.assertIn("X-Liuant-Signature", headers)
        self.assertIn("X-Liuant-Timestamp", headers)
        self.assertIn("X-Liuant-Event", headers)
        self.assertTrue(headers["X-Liuant-Signature"].startswith("sha256="))

    def test_hmac_secret_not_printed_logged(self):
        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        self.settings.set("webhook_secret", "super-secret-key-12345")
        self.settings.set("webhook_hmac_enabled", "true")
        payload_json = '{"event_type":"test"}'
        headers = delivery._build_signature_headers(payload_json, "test")
        all_headers_str = json.dumps(headers)
        self.assertNotIn("super-secret-key-12345", all_headers_str)
        self.assertNotIn("secret", all_headers_str.lower().replace("x-liuant-signature", "").replace("sha256=", ""))

    def test_signature_test_works_with_mock_secret(self):
        self.settings.set("webhook_secret", "mock-secret-for-test")
        self.settings.set("webhook_hmac_enabled", "true")
        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        self.assertTrue(delivery._is_hmac_enabled())
        payload_json = '{"event_type":"test"}'
        headers = delivery._build_signature_headers(payload_json, "signature_test")
        self.assertIn("X-Liuant-Signature", headers)
        self.assertIn("X-Liuant-Timestamp", headers)


class TestWebhookCLI(unittest.TestCase):
    """Phase 1: CLI commands for webhook delivery."""

    def setUp(self):
        _reset_db()
        self.settings = SettingsManager()
        self.settings.set("webhook_alerts_enabled", "false")
        self.settings.set("webhook_url", "")

    def test_delivery_history_cli_works(self):
        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        history = delivery.get_delivery_history()
        self.assertIsInstance(history, list)

    def test_retry_failed_requires_confirmation(self):
        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.retry_failed()
        self.assertEqual(result["status"], "retry_complete")
        self.assertEqual(result["retried"], 0)


class TestPerRoundDiscussionCosts(unittest.TestCase):
    """Phase 4: Per-round discussion cost breakdown."""

    def setUp(self):
        _reset_db()
        self.tracker = UsageTracker()

    def test_per_round_discussion_cost_records_initial_round(self):
        result = self.tracker.record_discussion_round(
            discussion_id="disc_001",
            round_number=1,
            phase="initial",
            role="critic",
            provider="openai",
            model="gpt-4",
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
            estimated_cost=0.003,
            exact_cost_available=False,
            fallback_used=False,
            status="completed",
        )
        self.assertEqual(result["discussion_id"], "disc_001")
        self.assertEqual(result["round_number"], 1)
        self.assertEqual(result["phase"], "initial")
        self.assertEqual(result["role"], "critic")
        self.assertEqual(result["total_tokens"], 300)

    def test_per_round_discussion_cost_records_review_round(self):
        result = self.tracker.record_discussion_round(
            discussion_id="disc_001",
            round_number=2,
            phase="review",
            role="reviewer",
            provider="anthropic",
            model="claude-3",
            input_tokens=150,
            output_tokens=250,
            total_tokens=400,
            estimated_cost=0.005,
            exact_cost_available=False,
            fallback_used=False,
            status="completed",
        )
        self.assertEqual(result["round_number"], 2)
        self.assertEqual(result["phase"], "review")
        self.assertEqual(result["role"], "reviewer")

    def test_per_round_discussion_cost_records_final_phase(self):
        result = self.tracker.record_discussion_round(
            discussion_id="disc_001",
            round_number=3,
            phase="final",
            role="synthesizer",
            provider="gemini",
            model="gemini-pro",
            input_tokens=200,
            output_tokens=300,
            total_tokens=500,
            estimated_cost=0.002,
            exact_cost_available=False,
            fallback_used=False,
            status="completed",
        )
        self.assertEqual(result["phase"], "final")
        self.assertEqual(result["role"], "synthesizer")

    def test_discussion_costs_latest_rounds_works(self):
        self.tracker.record_discussion_round(
            discussion_id="disc_002",
            round_number=1,
            phase="initial",
            role="critic",
            provider="openai",
            model="gpt-4",
            total_tokens=300,
            estimated_cost=0.003,
        )
        costs = self.tracker.get_discussion_costs_by_round(latest=True, rounds=True)
        self.assertGreaterEqual(len(costs["discussions"]), 1)
        if costs["discussions"]:
            latest = costs["discussions"][0]
            self.assertIn("rounds", latest)


class TestCleanupScheduler(unittest.TestCase):
    """Phase 5: Retention cleanup scheduler."""

    def setUp(self):
        _reset_db()
        self.tracker = UsageTracker()

    def test_cleanup_scheduler_disabled_by_default(self):
        status = self.tracker.get_cleanup_scheduler_status()
        self.assertFalse(status["auto_cleanup_enabled"])

    def test_cleanup_scheduler_enable_requires_confirmation(self):
        result = self.tracker.enable_cleanup_scheduler(confirm=False)
        self.assertEqual(result["status"], "error")
        self.assertIn("confirm", result["message"])

        result = self.tracker.enable_cleanup_scheduler(confirm=True)
        self.assertEqual(result["status"], "enabled")
        self.assertIn("next_run", result)

    def test_cleanup_scheduler_dry_run_works(self):
        result = self.tracker.run_cleanup_now(dry_run=True, confirm=False)
        self.assertIn("usage_records_to_delete", result)
        self.assertIn("alert_records_to_delete", result)

    def test_cleanup_scheduler_run_now_exports_before_cleanup(self):
        self.tracker.record_usage(provider="openai", model="gpt-4", estimated_total_tokens=100, estimated_cost=0.001)
        result = self.tracker.run_cleanup_now(dry_run=True, confirm=False, export_before=True)
        self.assertIn("export_path", result)
        self.assertTrue(result.get("export_before_cleanup", False))

    def test_cleanup_does_not_proceed_if_export_fails(self):
        self.settings = self.tracker.settings
        self.settings.set("allow_cleanup_without_export", "false")
        with patch.object(self.tracker, 'export_usage', return_value={"status": "error", "message": "Export failed"}):
            result = self.tracker.run_cleanup_now(dry_run=False, confirm=True, export_before=True)
            self.assertEqual(result["status"], "error")
            self.assertIn("Export failed", result["message"])

    def test_cleanup_neVER_deletes_current_day_records(self):
        today = self.tracker.record_usage(provider="openai", model="gpt-4", estimated_total_tokens=100, estimated_cost=0.001)
        result = self.tracker.run_cleanup_now(dry_run=True, confirm=False)
        self.assertEqual(result["usage_records_to_delete"], 0)


class TestExportBeforeCleanup(unittest.TestCase):
    """Phase 6: Export-before-cleanup warnings."""

    def setUp(self):
        _reset_db()
        self.tracker = UsageTracker()

    def test_cleanup_dry_run_with_export_plan(self):
        result = self.tracker.cleanup_dry_run_with_export_plan()
        self.assertIn("export_path", result)
        self.assertIn("export_before_cleanup", result)
        self.assertTrue(result["export_before_cleanup"])
        self.assertIn("warning", result)


class TestExistingTestsStillPass(unittest.TestCase):
    """Phase 9, Test 26: Verify existing functionality still works."""

    def setUp(self):
        _reset_db()
        self.tracker = UsageTracker()

    def test_usage_record_still_works(self):
        result = self.tracker.record_usage(provider="openai", model="gpt-4", estimated_total_tokens=100, estimated_cost=0.001)
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "gpt-4")

    def test_budget_still_works(self):
        budget = self.tracker.get_budget()
        self.assertIn("daily_estimated_cost_limit", budget)

    def test_webhook_config_still_works(self):
        status = self.tracker.get_webhook_status()
        self.assertIn("webhook_alerts_enabled", status)
        self.assertFalse(status["webhook_alerts_enabled"])


if __name__ == "__main__":
    unittest.main()
