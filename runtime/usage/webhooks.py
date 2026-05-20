"""Webhook alert delivery for Liuant Agentic OS v1.8.0.

Implements real HTTP webhook delivery with retry logic, HMAC signatures,
and delivery logging. Webhooks are disabled by default and require explicit
user enablement and approval.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from runtime.config import SettingsManager, utc_now
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.storage import WORKSPACE


def _safe_hash(value: str) -> str:
    """Create a safe hash of a value without storing the original."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _redact_error(error: str) -> str:
    """Redact sensitive information from error messages."""
    sensitive_patterns = [
        ("Bearer\\s+[A-Za-z0-9._\\-]+", "Bearer [REDACTED]"),
        ("sk-[A-Za-z0-9_\\-]+", "sk-[REDACTED]"),
        ("(?i)(password|secret|api.?key|token)\\s*[=:]\\s*\\S+", "\\1=[REDACTED]"),
    ]
    import re
    for pattern, replacement in sensitive_patterns:
        error = re.sub(pattern, replacement, error)
    return error[:200]


class WebhookDelivery:
    """Handles webhook alert delivery with retry logic and HMAC signatures."""

    def __init__(self) -> None:
        self.settings = SettingsManager()

    def _get_setting(self, key: str) -> str:
        try:
            val = self.settings.get(key)
            if val:
                return str(val.get("value", ""))
        except (ValueError, KeyError):
            pass
        return ""

    def _is_enabled(self) -> bool:
        return self._get_setting("webhook_alerts_enabled").lower() == "true"

    def _get_url(self) -> str:
        return self._get_setting("webhook_url")

    def _is_test_mode(self) -> bool:
        return self._get_setting("webhook_test_mode").lower() != "false"

    def _get_secret(self) -> str:
        return self._get_setting("webhook_secret")

    def _is_hmac_enabled(self) -> bool:
        return self._get_setting("webhook_hmac_enabled").lower() != "false" and bool(self._get_secret())

    def _get_max_retries(self) -> int:
        try:
            return int(self._get_setting("webhook_max_retries") or "3")
        except ValueError:
            return 3

    def _get_timeout(self) -> int:
        try:
            return int(self._get_setting("webhook_timeout") or "10")
        except ValueError:
            return 10

    def _build_signature_headers(self, payload_json: str, event_type: str) -> dict[str, str]:
        """Build HMAC signature headers. Never logs or exposes the secret."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Liuant-Agentic-OS/1.8.0",
            "X-Liuant-Event": event_type,
        }
        if self._is_hmac_enabled():
            secret = self._get_secret()
            timestamp = str(int(time.time()))
            message = f"{timestamp}.{payload_json}"
            signature = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Liuant-Timestamp"] = timestamp
            headers["X-Liuant-Signature"] = f"sha256={signature}"
        return headers

    def _log_delivery(self, event_type: str, workspace: str, url: str, status: str, status_code: int = 0, retry_count: int = 0, error: str = "", test_mode: bool = False, payload_json: str = "") -> dict[str, Any]:
        """Record delivery result. Stores hashes, not full URL or payload."""
        row = {
            "id": f"wh_{utc_now().replace(':', '-').replace('.', '-')}",
            "event_type": event_type,
            "workspace": workspace,
            "url_hash": _safe_hash(url),
            "status": status,
            "status_code": status_code,
            "retry_count": retry_count,
            "error_redacted": _redact_error(error) if error else "",
            "created_at": utc_now(),
            "delivered_at": utc_now() if status == "success" else None,
            "payload_hash": _safe_hash(payload_json) if payload_json else "",
            "test_mode": test_mode,
            "timestamp": utc_now(),
        }
        insert_record("webhook_deliveries", row)
        return row

    def send(self, event_type: str, payload: dict[str, Any], test_mode: bool = False) -> dict[str, Any]:
        """Send webhook with retry logic. Skips if disabled or URL missing."""
        if not self._is_enabled():
            return {"status": "skipped", "reason": "webhooks_disabled"}
        url = self._get_url()
        if not url:
            return {"status": "skipped", "reason": "webhook_url_missing"}
        if not url.startswith("https://"):
            is_localhost = url.startswith("http://127.0.0.1") or url.startswith("http://localhost")
            is_test_flag = os.environ.get("LIUANT_WEBHOOK_TEST_ALLOW_HTTP_LOCALHOST", "").lower() == "true"
            if not (is_localhost and (test_mode or self._is_test_mode() or is_test_flag)):
                return {"status": "skipped", "reason": "webhook_url_not_https"}
        if test_mode and not self._is_test_mode():
            return {"status": "skipped", "reason": "production_event_rejected_in_test_mode"}

        payload_json = json.dumps(payload, default=str)
        max_retries = self._get_max_retries()
        timeout = self._get_timeout()
        retry_count = 0
        last_error = ""
        last_status = 0

        for attempt in range(max_retries + 1):
            try:
                headers = self._build_signature_headers(payload_json, event_type)
                req = urllib.request.Request(url, data=payload_json.encode(), headers=headers, method="POST")
                resp = urllib.request.urlopen(req, timeout=timeout)
                status_code = resp.getcode()
                self._log_delivery(event_type, payload.get("workspace", "default"), url, "success", status_code, retry_count, "", test_mode, payload_json)
                return {"status": "success", "status_code": status_code, "retry_count": retry_count}
            except urllib.error.HTTPError as exc:
                last_status = exc.code
                last_error = str(exc)
                # Retry only for 429 or 5xx
                if exc.code == 429 or exc.code >= 500:
                    if attempt < max_retries:
                        backoff = min(2 ** attempt, 60)
                        time.sleep(backoff)
                        retry_count += 1
                        continue
                # 4xx (except 429) - do not retry
                self._log_delivery(event_type, payload.get("workspace", "default"), url, "failed", last_status, retry_count, last_error, test_mode, payload_json)
                return {"status": "failed", "status_code": last_status, "retry_count": retry_count, "error": _redact_error(last_error)}
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    backoff = min(2 ** attempt, 60)
                    time.sleep(backoff)
                    retry_count += 1
                    continue
                self._log_delivery(event_type, payload.get("workspace", "default"), url, "failed", 0, retry_count, last_error, test_mode, payload_json)
                return {"status": "failed", "status_code": 0, "retry_count": retry_count, "error": _redact_error(last_error)}

        self._log_delivery(event_type, payload.get("workspace", "default"), url, "failed", last_status, retry_count, last_error, test_mode, payload_json)
        return {"status": "failed", "status_code": last_status, "retry_count": retry_count, "error": _redact_error(last_error)}

    def send_test(self, event_type: str = "budget_warning") -> dict[str, Any]:
        """Send a test webhook payload."""
        if not self._is_enabled() or not self._get_url():
            return {"status": "error", "message": "Webhooks not enabled or URL not set."}
        payload = {
            "event_type": event_type,
            "workspace": "default",
            "level": "info",
            "message": "Test webhook from Liuant Agentic OS",
            "provider": "",
            "model": "",
            "estimated_cost": 0.0,
            "timestamp": utc_now(),
            "source": "liuant-agentic-os",
            "test_mode": True,
        }
        return self.send(event_type, payload, test_mode=True)

    def get_delivery_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent delivery history."""
        records = list_records("webhook_deliveries")
        return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)[:limit]

    def get_failed_deliveries(self) -> list[dict[str, Any]]:
        """Get failed deliveries that could be retried."""
        records = list_records("webhook_deliveries")
        return [r for r in records if r.get("status") == "failed"]

    def retry_failed(self) -> dict[str, Any]:
        """Retry all failed deliveries."""
        failed = self.get_failed_deliveries()
        retried = 0
        for delivery in failed:
            # Reconstruct minimal payload for retry
            payload = {
                "event_type": delivery.get("event_type", "unknown"),
                "workspace": delivery.get("workspace", "default"),
                "level": "warning",
                "message": "Retried webhook alert",
                "timestamp": utc_now(),
                "source": "liuant-agentic-os",
            }
            result = self.send(delivery.get("event_type", "unknown"), payload)
            if result.get("status") == "success":
                retried += 1
        return {"status": "retry_complete", "retried": retried, "total_failed": len(failed)}
