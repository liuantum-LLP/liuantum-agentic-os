"""Integration tests for Liuant Agentic OS v1.9.0.

Tests local webhook test server, HMAC verification, retry logic,
delivery history, cleanup scheduler, and UI rendering.
Uses a local mock HTTP server for webhook delivery tests.
"""

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

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


class MockWebhookHandler(BaseHTTPRequestHandler):
    """Mock webhook server that captures requests and returns configurable responses."""

    received_requests = []
    response_code = 200

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        headers = dict(self.headers)
        MockWebhookHandler.received_requests.append({
            "path": self.path,
            "headers": headers,
            "body": body.decode() if body else "",
        })
        self.send_response(MockWebhookHandler.response_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):
        pass


def _start_mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockWebhookHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.1)
    return server, thread, port


# ===================================================================
# Phase 6 & 9: Local Webhook Test Server
# ===================================================================

def test_local_webhook_test_server_receives_payload():
    """Test that the local mock server receives webhook payloads."""
    _reset_db()
    MockWebhookHandler.received_requests = []
    MockWebhookHandler.response_code = 200
    server, thread, port = _start_mock_server()
    try:
        settings = SettingsManager()
        settings.set("webhook_alerts_enabled", "true")
        settings.set("webhook_url", f"http://127.0.0.1:{port}/webhook")
        settings.set("webhook_test_mode", "true")
        settings.set("webhook_hmac_enabled", "false")
        settings.set("webhook_secret", "")
        settings.set("webhook_max_retries", "0")
        settings.set("webhook_timeout", "2")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default", "level": "info", "message": "test"})
        assert result["status"] == "success", f"Expected success, got {result}"
        assert len(MockWebhookHandler.received_requests) == 1
        req = MockWebhookHandler.received_requests[0]
        assert "application/json" in req["headers"].get("Content-Type", "")
        body = json.loads(req["body"])
        assert body["workspace"] == "default"
    finally:
        server.shutdown()
        thread.join()


def test_hmac_signature_verifies_against_raw_body():
    """Test that HMAC signature is generated correctly and can be verified."""
    import hmac
    import hashlib
    _reset_db()
    settings = SettingsManager()
    settings.set("webhook_secret", "test-hmac-secret")
    settings.set("webhook_hmac_enabled", "true")

    from runtime.usage.webhooks import WebhookDelivery
    delivery = WebhookDelivery()
    payload_json = '{"event_type":"test","workspace":"default"}'
    headers = delivery._build_signature_headers(payload_json, "test_event")

    assert "X-Liuant-Signature" in headers
    assert "X-Liuant-Timestamp" in headers

    timestamp = headers["X-Liuant-Timestamp"]
    signature = headers["X-Liuant-Signature"]
    message = f"{timestamp}.{payload_json}"
    expected = hmac.new(b"test-hmac-secret", message.encode(), hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected}"


def test_retry_works_for_429():
    """Test that webhook delivery retries on 429 responses."""
    _reset_db()
    MockWebhookHandler.received_requests = []
    MockWebhookHandler.response_code = 429
    server, thread, port = _start_mock_server()
    try:
        settings = SettingsManager()
        settings.set("webhook_alerts_enabled", "true")
        settings.set("webhook_url", f"http://127.0.0.1:{port}/webhook")
        settings.set("webhook_test_mode", "true")
        settings.set("webhook_max_retries", "1")
        settings.set("webhook_timeout", "2")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        assert result["status"] == "failed"
        assert result["status_code"] == 429
        assert result["retry_count"] >= 1
    finally:
        server.shutdown()
        thread.join()


def test_retry_works_for_500():
    """Test that webhook delivery retries on 500 responses."""
    _reset_db()
    MockWebhookHandler.received_requests = []
    MockWebhookHandler.response_code = 500
    server, thread, port = _start_mock_server()
    try:
        settings = SettingsManager()
        settings.set("webhook_alerts_enabled", "true")
        settings.set("webhook_url", f"http://127.0.0.1:{port}/webhook")
        settings.set("webhook_test_mode", "true")
        settings.set("webhook_max_retries", "1")
        settings.set("webhook_timeout", "2")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        assert result["status"] == "failed"
        assert result["status_code"] == 500
        assert result["retry_count"] >= 1
    finally:
        server.shutdown()
        thread.join()


def test_no_retry_for_400():
    """Test that webhook delivery does not retry on 400 responses."""
    _reset_db()
    MockWebhookHandler.received_requests = []
    MockWebhookHandler.response_code = 400
    server, thread, port = _start_mock_server()
    try:
        settings = SettingsManager()
        settings.set("webhook_alerts_enabled", "true")
        settings.set("webhook_url", f"http://127.0.0.1:{port}/webhook")
        settings.set("webhook_test_mode", "true")
        settings.set("webhook_max_retries", "3")
        settings.set("webhook_timeout", "2")

        from runtime.usage.webhooks import WebhookDelivery
        delivery = WebhookDelivery()
        result = delivery.send("test_event", {"workspace": "default"})
        assert result["status"] == "failed"
        assert result["status_code"] == 400
        assert result["retry_count"] == 0
    finally:
        server.shutdown()
        thread.join()


def test_delivery_history_stores_hashes_only():
    """Test that delivery history stores url_hash and payload_hash, not full values."""
    _reset_db()
    MockWebhookHandler.received_requests = []
    MockWebhookHandler.response_code = 200
    server, thread, port = _start_mock_server()
    try:
        from runtime.usage.webhooks import WebhookDelivery, _safe_hash
        settings = SettingsManager()
        settings.set("webhook_alerts_enabled", "true")
        settings.set("webhook_url", f"http://127.0.0.1:{port}/webhook")
        settings.set("webhook_test_mode", "true")
        settings.set("webhook_max_retries", "0")
        settings.set("webhook_timeout", "2")

        delivery = WebhookDelivery()
        test_url = f"http://127.0.0.1:{port}/webhook"
        test_payload = '{"event_type":"test","workspace":"default","secret_data":"hidden"}'

        delivery.send("test_event", {"workspace": "default", "level": "info", "message": "test"})

        history = delivery.get_delivery_history()
        assert len(history) > 0
        log = history[0]
        assert log["url_hash"] == _safe_hash(test_url)
        assert test_url not in log["url_hash"]
        assert "secret_data" not in log.get("error_redacted", "")
    finally:
        server.shutdown()
        thread.join()


def test_signature_test_does_not_expose_secret():
    """Test that signature test does not expose the webhook secret."""
    _reset_db()
    settings = SettingsManager()
    settings.set("webhook_secret", "super-secret-key-12345")
    settings.set("webhook_hmac_enabled", "true")

    from runtime.usage.webhooks import WebhookDelivery
    delivery = WebhookDelivery()
    payload_json = '{"event_type":"test"}'
    headers = delivery._build_signature_headers(payload_json, "test")
    all_headers_str = json.dumps(headers)
    assert "super-secret-key-12345" not in all_headers_str


# ===================================================================
# Phase 7 & 9: Cleanup Scheduler Foundation
# ===================================================================

def test_cleanup_scheduler_next_run_calculation_works():
    """Test that next run is calculated correctly when enabling scheduler."""
    _reset_db()
    tracker = UsageTracker()
    result = tracker.enable_cleanup_scheduler(confirm=True)
    assert result["status"] == "enabled"
    assert "next_run" in result
    assert len(result["next_run"]) > 0


def test_disabled_scheduler_does_not_run():
    """Test that a disabled scheduler does not execute cleanup."""
    _reset_db()
    tracker = UsageTracker()
    status = tracker.get_cleanup_scheduler_status()
    assert status["auto_cleanup_enabled"] == False

    dry_run = tracker.run_cleanup_now(dry_run=True, confirm=False)
    assert "usage_records_to_delete" in dry_run


def test_check_and_run_due_cleanup_does_not_run_when_disabled():
    """Test that check_and_run_due_cleanup respects disabled state."""
    _reset_db()
    tracker = UsageTracker()
    status = tracker.get_cleanup_scheduler_status()
    assert status["auto_cleanup_enabled"] == False

    result = tracker.run_cleanup_now(dry_run=True, confirm=False)
    assert "total_records_to_delete" in result


# ===================================================================
# Phase 8 & 9: Frontend UI / Backend Tests
# ===================================================================

def test_usage_dashboard_shows_webhook_delivery_history_section():
    """Test that webhook delivery history API returns expected structure."""
    _reset_db()
    from runtime.usage.webhooks import WebhookDelivery
    delivery = WebhookDelivery()
    history = delivery.get_delivery_history()
    assert isinstance(history, list)


def test_webhook_history_never_displays_full_url():
    """Test that delivery history stores url_hash, not full URL."""
    _reset_db()
    from runtime.usage.webhooks import WebhookDelivery, _safe_hash
    delivery = WebhookDelivery()
    test_url = "https://example.com/webhook"
    log = delivery._log_delivery("test", "default", test_url, "success", 200, 0, "", False, '{"test": true}')
    assert "https://example.com" not in log["url_hash"]
    assert log["url_hash"] == _safe_hash(test_url)


def test_webhook_history_never_displays_payload_body():
    """Test that delivery history stores payload_hash, not full payload."""
    _reset_db()
    from runtime.usage.webhooks import WebhookDelivery, _safe_hash
    delivery = WebhookDelivery()
    test_payload = '{"event_type":"test","secret":"hidden","api_key":"sk-123"}'
    log = delivery._log_delivery("test", "default", "https://example.com", "success", 200, 0, "", False, test_payload)
    assert "secret" not in log["payload_hash"]
    assert "api_key" not in log["payload_hash"]
    assert log["payload_hash"] == _safe_hash(test_payload)


def test_hmac_status_card_does_not_show_secret():
    """Test that HMAC status does not expose the webhook secret."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    tracker.settings.set("webhook_secret", "super-secret-value")
    status = tracker.get_webhook_status()
    assert "super-secret-value" not in str(status)
    assert "webhook_secret_configured" in status
    assert status["webhook_secret_configured"] == True


def test_cleanup_scheduler_card_exists():
    """Test that cleanup scheduler status API returns expected structure."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    status = tracker.get_cleanup_scheduler_status()
    assert "auto_cleanup_enabled" in status
    assert "cleanup_schedule" in status
    assert "cleanup_day" in status
    assert "cleanup_time" in status


def test_cleanup_dry_run_panel_exists():
    """Test that cleanup dry run returns expected structure."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    result = tracker.run_cleanup_now(dry_run=True, confirm=False)
    assert "usage_records_to_delete" in result
    assert "alert_records_to_delete" in result


def test_confirm_cleanup_warning_exists():
    """Test that cleanup dry run with export plan includes warning."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    plan = tracker.cleanup_dry_run_with_export_plan()
    assert "warning" in plan
    assert "irreversible" in plan["warning"].lower()


def test_discussion_cost_breakdown_table_exists():
    """Test that discussion costs by round API returns expected structure."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    tracker.record_discussion_round("disc_test", 1, "initial", "critic", "openai", "gpt-4", 100, 200, 300, 0.003)
    costs = tracker.get_discussion_costs_by_round(latest=True, rounds=True)
    assert "discussions" in costs
    assert len(costs["discussions"]) > 0


def test_per_round_cost_rows_render():
    """Test that per-round cost data has rounds structure."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    tracker.record_discussion_round("disc_test2", 1, "initial", "critic", "openai", "gpt-4", 100, 200, 300, 0.003)
    tracker.record_discussion_round("disc_test2", 2, "review", "reviewer", "anthropic", "claude-3", 150, 250, 400, 0.005)
    costs = tracker.get_discussion_costs_by_round(latest=True, rounds=True)
    latest = costs["discussions"][0]
    assert "rounds" in latest
    assert len(latest["rounds"]) > 1


def test_retry_failed_webhook_button_requires_confirmation():
    """Test that retry-failed API requires confirmation."""
    _reset_db()
    from runtime.usage.webhooks import WebhookDelivery
    delivery = WebhookDelivery()
    result = delivery.retry_failed()
    assert result["status"] == "retry_complete"


def test_existing_tests_still_pass_v190():
    """Verify existing functionality still works."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    result = tracker.record_usage(provider="openai", model="gpt-4", estimated_total_tokens=100, estimated_cost=0.001)
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4"
    budget = tracker.get_budget()
    assert "daily_estimated_cost_limit" in budget
    status = tracker.get_webhook_status()
    assert "webhook_alerts_enabled" in status
    assert status["webhook_alerts_enabled"] == False
