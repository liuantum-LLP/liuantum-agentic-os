"""Provider health tracking for Liuant Agentic OS v1.6.0.

Tracks provider reliability: last success, last error, error counts,
timeout counts, rate limit counts, latency, and degraded status.
Auto-tracked from real provider calls.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from runtime.config import SettingsManager, utc_now

SENSITIVE_PATTERNS = re.compile(
    r"\b(password|otp|credit.?card|aadhaar|pan|secret|api.?key|token|bearer)\b",
    re.IGNORECASE,
)


def redact_error(text: str) -> str:
    """Redact potential secrets from error messages."""
    if not SENSITIVE_PATTERNS.search(text):
        return text
    for pattern in [
        (r"(?i)(password|otp|secret|api.?key|token)\s*[=:]\s*\S+", r"\1=[REDACTED]"),
        (r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]"),
        (r"sk-[A-Za-z0-9_\-]+", "sk-[REDACTED]"),
    ]:
        text = re.sub(pattern[0], pattern[1], text)
    return text


class ProviderHealthTracker:
    """Tracks provider reliability and health status."""

    def __init__(self) -> None:
        self.settings = SettingsManager()

    def _get_key(self, provider: str) -> str:
        return f"provider_health_{provider.lower()}"

    def _get_health(self, provider: str) -> dict[str, Any]:
        default = {
            "provider": provider,
            "status": "unknown",
            "last_success": None,
            "last_error": None,
            "error_count": 0,
            "timeout_count": 0,
            "rate_limit_count": 0,
            "unavailable_count": 0,
            "degraded_since": None,
            "total_calls": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "last_latency_ms": None,
            "average_latency_ms": None,
            "p50_latency_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "slow_call_count": 0,
            "slow_call_threshold_ms": 5000,
            "fastest_call_ms": None,
            "slowest_call_ms": None,
            "latency_samples": [],
        }
        try:
            val = self.settings.get(self._get_key(provider))
            if val.get("status") == "found":
                import json
                try:
                    data = json.loads(val.get("value", "{}"))
                    # Merge with defaults for any missing keys
                    for k, v in default.items():
                        if k not in data:
                            data[k] = v
                    return data
                except (json.JSONDecodeError, TypeError):
                    pass
        except (ValueError, KeyError):
            pass
        return default

    def _save_health(self, provider: str, data: dict[str, Any]) -> None:
        import json
        # Don't store large latency samples
        if "latency_samples" in data and len(data["latency_samples"]) > 100:
            data["latency_samples"] = data["latency_samples"][-100:]
        self.settings.set(self._get_key(provider), json.dumps(data, default=str))

    def _update_latency(self, health: dict[str, Any], latency_ms: int) -> dict[str, Any]:
        """Update latency metrics including percentiles."""
        health["last_latency_ms"] = latency_ms
        samples = health.get("latency_samples", [])
        samples.append(latency_ms)
        if len(samples) > 200:
            samples = samples[-200:]
        health["latency_samples"] = samples
        health["average_latency_ms"] = round(sum(samples) / len(samples), 1) if samples else None
        health["fastest_call_ms"] = min(samples) if samples else None
        health["slowest_call_ms"] = max(samples) if samples else None
        if latency_ms > 5000:
            health["slow_call_count"] = health.get("slow_call_count", 0) + 1
        # Calculate percentiles
        if samples:
            sorted_samples = sorted(samples)
            n = len(sorted_samples)
            health["p50_latency_ms"] = sorted_samples[int(n * 0.5)] if n > 0 else None
            health["p95_latency_ms"] = sorted_samples[min(int(n * 0.95), n - 1)] if n > 1 else None
            health["p99_latency_ms"] = sorted_samples[min(int(n * 0.99), n - 1)] if n > 1 else None
        return health

    def _update_status(self, health: dict[str, Any]) -> dict[str, Any]:
        """Update provider status based on counts."""
        total = health.get("total_calls", 0)
        if total == 0:
            health["status"] = "unknown"
            return health
        success_rate = health.get("success_count", 0) / max(total, 1)
        health["success_rate"] = round(success_rate * 100, 1)
        if health.get("rate_limit_count", 0) > 0:
            health["status"] = "rate_limited"
        elif health.get("error_count", 0) > 5 or health.get("timeout_count", 0) > 5:
            health["status"] = "error"
        elif health.get("error_count", 0) > 0 or health.get("timeout_count", 0) > 0:
            if health.get("status") == "healthy":
                health["status"] = "degraded"
                if not health.get("degraded_since"):
                    health["degraded_since"] = utc_now()
        else:
            health["status"] = "healthy"
            health["degraded_since"] = None
        return health

    def record_success(self, provider: str, latency_ms: int | None = None) -> dict[str, Any]:
        """Record a successful provider call."""
        health = self._get_health(provider)
        health["total_calls"] = health.get("total_calls", 0) + 1
        health["success_count"] = health.get("success_count", 0) + 1
        health["last_success"] = utc_now()
        if latency_ms is not None:
            health = self._update_latency(health, latency_ms)
        health = self._update_status(health)
        self._save_health(provider, health)
        return health

    def record_error(self, provider: str, error: str = "", latency_ms: int | None = None) -> dict[str, Any]:
        """Record a provider error."""
        health = self._get_health(provider)
        health["total_calls"] = health.get("total_calls", 0) + 1
        health["last_error"] = redact_error(error[:200]) if error else None
        health["error_count"] = health.get("error_count", 0) + 1
        if latency_ms is not None:
            health = self._update_latency(health, latency_ms)
        health = self._update_status(health)
        self._save_health(provider, health)
        return health

    def record_timeout(self, provider: str) -> dict[str, Any]:
        """Record a provider timeout."""
        health = self._get_health(provider)
        health["total_calls"] = health.get("total_calls", 0) + 1
        health["timeout_count"] = health.get("timeout_count", 0) + 1
        if health.get("status") == "healthy":
            health["status"] = "degraded"
            health["degraded_since"] = utc_now()
        health = self._update_status(health)
        self._save_health(provider, health)
        return health

    def record_rate_limit(self, provider: str) -> dict[str, Any]:
        """Record a provider rate limit."""
        health = self._get_health(provider)
        health["total_calls"] = health.get("total_calls", 0) + 1
        health["rate_limit_count"] = health.get("rate_limit_count", 0) + 1
        health["status"] = "rate_limited"
        health = self._update_status(health)
        self._save_health(provider, health)
        return health

    def record_unavailable(self, provider: str) -> dict[str, Any]:
        """Record a provider unavailable/local_unreachable."""
        health = self._get_health(provider)
        health["total_calls"] = health.get("total_calls", 0) + 1
        health["unavailable_count"] = health.get("unavailable_count", 0) + 1
        health["status"] = "local_unreachable"
        health = self._update_status(health)
        self._save_health(provider, health)
        return health

    def get_health(self, provider: str) -> dict[str, Any]:
        """Get health status for a specific provider."""
        health = self._get_health(provider)
        # Don't expose latency samples in API response
        health.pop("latency_samples", None)
        return health

    def get_all_health(self) -> dict[str, Any]:
        """Get health status for all tracked providers."""
        all_settings = self.settings.list()
        health_data = {}
        for s in all_settings:
            key = s.get("key", "")
            if key.startswith("provider_health_"):
                provider = key.replace("provider_health_", "")
                import json
                try:
                    data = json.loads(s.get("value", "{}"))
                    data.pop("latency_samples", None)
                    health_data[provider] = data
                except (json.JSONDecodeError, TypeError):
                    health_data[provider] = {"provider": provider, "status": "unknown"}
        return health_data

    def reset_health(self, provider: str) -> dict[str, Any]:
        """Reset health tracking for a provider."""
        health = {
            "provider": provider,
            "status": "unknown",
            "last_success": None,
            "last_error": None,
            "error_count": 0,
            "timeout_count": 0,
            "rate_limit_count": 0,
            "unavailable_count": 0,
            "degraded_since": None,
            "total_calls": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "last_latency_ms": None,
            "average_latency_ms": None,
            "p50_latency_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "slow_call_count": 0,
            "slow_call_threshold_ms": 5000,
            "fastest_call_ms": None,
            "slowest_call_ms": None,
            "latency_samples": [],
        }
        self._save_health(provider, health)
        health.pop("latency_samples", None)
        return health
