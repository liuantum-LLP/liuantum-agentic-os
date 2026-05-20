"""Usage and cost tracking for Liuant Agentic OS v1.6.0.

Tracks provider calls, token estimates, and costs across chat, text, agent,
and discussion features. Supports local (zero-cost) and cloud providers.
Adds budgeting, alerts, export, anomaly detection, workspace tracking,
trends, and alert history.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from runtime.config import SettingsManager, utc_now
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.storage import WORKSPACE

LOCAL_PROVIDERS = {"ollama", "lmstudio", "local_hash_embedding", "whisper_local", "piper_local", "coqui_local"}

PRICING_TABLE = {
    "openai": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
    "openrouter": {"input_per_1k": 0.001, "output_per_1k": 0.005},
    "anthropic": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "gemini": {"input_per_1k": 0.00035, "output_per_1k": 0.00105},
    "groq": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
    "mistral": {"input_per_1k": 0.0001, "output_per_1k": 0.0003},
    "together": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
    "fireworks": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
}

DEFAULT_BUDGETS = {
    "daily_estimated_cost_limit": 0.0,
    "monthly_estimated_cost_limit": 0.0,
    "per_provider_limit": 0.0,
    "per_role_limit": 0.0,
    "discussion_mode_cost_warning_threshold": 0.50,
    "cloud_model_warning_enabled": True,
    "budget_blocking_enabled": False,
}


class UsageTracker:
    """Tracks API usage and estimated costs."""

    def __init__(self) -> None:
        self.settings = SettingsManager()

    def _get_budget(self, key: str) -> float:
        try:
            val = self.settings.get(key)
            if val.get("status") == "found":
                try:
                    return float(val.get("value", 0.0))
                except (ValueError, TypeError):
                    return 0.0
        except (ValueError, KeyError):
            pass
        return DEFAULT_BUDGETS.get(key, 0.0)

    def _set_budget(self, key: str, value: float) -> dict[str, Any]:
        return self.settings.set(key, str(value))

    def _get_workspace(self, workspace: str | None = None) -> str:
        """Resolve workspace name for usage tracking."""
        if workspace == "current":
            try:
                ws = self.settings.get("active_workspace")
                if ws.get("status") == "found":
                    return ws.get("value", "default")
            except (ValueError, KeyError):
                pass
            return "default"
        if workspace == "all":
            return ""
        return workspace or "default"

    def record_usage(
        self,
        provider: str,
        model: str,
        model_role: str = "default",
        feature: str = "chat",
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        estimated_total_tokens: int = 0,
        estimated_cost: float = 0.0,
        estimated: bool = True,
        fallback_used: bool = False,
        status: str = "completed",
        discussion_id: str | None = None,
        workspace_name: str | None = None,
        latency_ms: int | None = None,
    ) -> dict[str, Any]:
        """Record a single usage event."""
        is_local = provider.lower() in LOCAL_PROVIDERS
        if is_local:
            estimated_cost = 0.0

        ws = self._get_workspace(workspace_name)

        row = {
            "id": f"usage_{utc_now().replace(':', '-').replace('.', '-')}",
            "provider": provider,
            "model": model,
            "model_role": model_role,
            "feature": feature,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_total_tokens,
            "estimated_cost": round(estimated_cost, 6),
            "estimated": estimated,
            "fallback_used": fallback_used,
            "status": status,
            "discussion_id": discussion_id,
            "is_local": is_local,
            "timestamp": utc_now(),
            "workspace_name": ws,
            "latency_ms": latency_ms,
        }
        insert_record("usage_events", row)
        return row

    def get_summary(self, workspace: str | None = None) -> dict[str, Any]:
        """Get overall usage summary, optionally filtered by workspace."""
        events = list_records("usage_events")
        ws = self._get_workspace(workspace)
        if ws:
            events = [e for e in events if e.get("workspace_name", "default") == ws]
        if not events:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_estimated_cost": 0.0,
                "by_provider": {},
                "by_role": {},
                "by_feature": {},
                "local_calls": 0,
                "cloud_calls": 0,
                "workspace": ws or "all",
            }

        total_tokens = sum(e.get("estimated_total_tokens", 0) for e in events)
        total_cost = sum(e.get("estimated_cost", 0.0) for e in events)
        local_calls = sum(1 for e in events if e.get("is_local"))
        cloud_calls = len(events) - local_calls

        by_provider: dict[str, dict[str, Any]] = {}
        by_role: dict[str, dict[str, Any]] = {}
        by_feature: dict[str, dict[str, Any]] = {}

        for e in events:
            p = e.get("provider", "unknown")
            r = e.get("model_role", "default")
            f = e.get("feature", "chat")
            tokens = e.get("estimated_total_tokens", 0)
            cost = e.get("estimated_cost", 0.0)

            by_provider.setdefault(p, {"calls": 0, "tokens": 0, "cost": 0.0})
            by_provider[p]["calls"] += 1
            by_provider[p]["tokens"] += tokens
            by_provider[p]["cost"] += cost

            by_role.setdefault(r, {"calls": 0, "tokens": 0, "cost": 0.0})
            by_role[r]["calls"] += 1
            by_role[r]["tokens"] += tokens
            by_role[r]["cost"] += cost

            by_feature.setdefault(f, {"calls": 0, "tokens": 0, "cost": 0.0})
            by_feature[f]["calls"] += 1
            by_feature[f]["tokens"] += tokens
            by_feature[f]["cost"] += cost

        return {
            "total_calls": len(events),
            "total_tokens": total_tokens,
            "total_estimated_cost": round(total_cost, 6),
            "by_provider": by_provider,
            "by_role": by_role,
            "by_feature": by_feature,
            "local_calls": local_calls,
            "cloud_calls": cloud_calls,
            "workspace": ws or "all",
        }

    def get_today(self, workspace: str | None = None) -> dict[str, Any]:
        """Get today's usage, optionally filtered by workspace."""
        events = list_records("usage_events")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_events = [e for e in events if (e.get("timestamp", "") or "").startswith(today)]
        ws = self._get_workspace(workspace)
        if ws:
            today_events = [e for e in today_events if e.get("workspace_name", "default") == ws]
        return self._summarize_events(today_events)

    def get_by_provider(self, workspace: str | None = None) -> dict[str, dict[str, Any]]:
        """Get usage grouped by provider, optionally filtered by workspace."""
        events = list_records("usage_events")
        ws = self._get_workspace(workspace)
        if ws:
            events = [e for e in events if e.get("workspace_name", "default") == ws]
        by_provider: dict[str, dict[str, Any]] = {}
        for e in events:
            p = e.get("provider", "unknown")
            by_provider.setdefault(p, {"calls": 0, "tokens": 0, "cost": 0.0})
            by_provider[p]["calls"] += 1
            by_provider[p]["tokens"] += e.get("estimated_total_tokens", 0)
            by_provider[p]["cost"] += e.get("estimated_cost", 0.0)
        return by_provider

    def get_by_role(self, workspace: str | None = None) -> dict[str, dict[str, Any]]:
        """Get usage grouped by model role, optionally filtered by workspace."""
        events = list_records("usage_events")
        ws = self._get_workspace(workspace)
        if ws:
            events = [e for e in events if e.get("workspace_name", "default") == ws]
        by_role: dict[str, dict[str, Any]] = {}
        for e in events:
            r = e.get("model_role", "default")
            by_role.setdefault(r, {"calls": 0, "tokens": 0, "cost": 0.0})
            by_role[r]["calls"] += 1
            by_role[r]["tokens"] += e.get("estimated_total_tokens", 0)
            by_role[r]["cost"] += e.get("estimated_cost", 0.0)
        return by_role

    def reset(self) -> dict[str, Any]:
        """Reset all usage data."""
        from runtime.db import delete_all_records
        try:
            delete_all_records("usage_events")
        except Exception:
            for e in list_records("usage_events"):
                from runtime.db import delete_record
                delete_record("usage_events", e.get("id", ""))
        return {"status": "reset", "message": "All usage data cleared."}

    def estimate_cost(self, provider: str, input_tokens: int, output_tokens: int, model: str | None = None) -> dict[str, Any]:
        """Estimate cost for a provider call."""
        is_local = provider.lower() in LOCAL_PROVIDERS
        if is_local:
            return {"estimated_cost": 0.0, "estimated": False, "local": True}

        model_lower = (model or "").lower()
        if provider.lower() in {"amazon_bedrock", "bedrock"}:
            if "nova-micro" in model_lower:
                rates = {"input_per_1k": 0.000035, "output_per_1k": 0.00014}
            elif "nova-pro" in model_lower:
                rates = {"input_per_1k": 0.0008, "output_per_1k": 0.0032}
            else:
                # Default/Lite rate
                rates = {"input_per_1k": 0.00006, "output_per_1k": 0.00024}
        else:
            rates = PRICING_TABLE.get(provider.lower(), {"input_per_1k": 0.001, "output_per_1k": 0.005})

        cost = (input_tokens / 1000) * rates["input_per_1k"] + (output_tokens / 1000) * rates["output_per_1k"]
        return {"estimated_cost": round(cost, 6), "estimated": True, "local": False}

    def _summarize_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        total_tokens = sum(e.get("estimated_total_tokens", 0) for e in events)
        total_cost = sum(e.get("estimated_cost", 0.0) for e in events)
        return {
            "calls": len(events),
            "tokens": total_tokens,
            "estimated_cost": round(total_cost, 6),
            "local_calls": sum(1 for e in events if e.get("is_local")),
            "cloud_calls": sum(1 for e in events if not e.get("is_local")),
        }

    # ------------------------------------------------------------------
    # Budget management (v1.5.0)
    # ------------------------------------------------------------------

    def get_budget(self) -> dict[str, Any]:
        """Get current budget settings."""
        return {
            "daily_estimated_cost_limit": self._get_budget("daily_estimated_cost_limit"),
            "monthly_estimated_cost_limit": self._get_budget("monthly_estimated_cost_limit"),
            "per_provider_limit": self._get_budget("per_provider_limit"),
            "per_role_limit": self._get_budget("per_role_limit"),
            "discussion_mode_cost_warning_threshold": self._get_budget("discussion_mode_cost_warning_threshold"),
            "cloud_model_warning_enabled": bool(self._get_budget("cloud_model_warning_enabled")),
            "budget_blocking_enabled": bool(self._get_budget("budget_blocking_enabled")),
        }

    def set_budget(self, **kwargs: float | bool) -> dict[str, Any]:
        """Set one or more budget values."""
        results = {}
        for key, value in kwargs.items():
            if key in DEFAULT_BUDGETS:
                results[key] = self._set_budget(key, float(value))
        return {"status": "updated", "budgets": results}

    def reset_budget(self) -> dict[str, Any]:
        """Reset all budget settings to defaults."""
        for key, default in DEFAULT_BUDGETS.items():
            self._set_budget(key, float(default))
        return {"status": "reset", "message": "Budget settings reset to defaults."}

    def check_budget_alerts(self) -> dict[str, Any]:
        """Check current usage against budget limits and return alerts."""
        today = self.get_today()
        events = list_records("usage_events")
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_events = [e for e in events if (e.get("timestamp", "") or "") >= month_start.strftime("%Y-%m-%dT")]

        daily_cost = today.get("estimated_cost", 0.0)
        monthly_cost = sum(e.get("estimated_cost", 0.0) for e in month_events)
        daily_limit = self._get_budget("daily_estimated_cost_limit")
        monthly_limit = self._get_budget("monthly_estimated_cost_limit")

        alerts: list[dict[str, Any]] = []

        if daily_limit > 0:
            daily_pct = (daily_cost / daily_limit) * 100
            if daily_pct >= 100:
                alerts.append({"level": "critical", "type": "daily_limit_exceeded", "message": f"Daily cost ${daily_cost:.4f} exceeds limit ${daily_limit:.2f} ({daily_pct:.0f}%)", "pct": round(daily_pct, 1)})
            elif daily_pct >= 90:
                alerts.append({"level": "warning", "type": "daily_90", "message": f"Daily cost at 90% of limit (${daily_cost:.4f}/${daily_limit:.2f})", "pct": round(daily_pct, 1)})
            elif daily_pct >= 70:
                alerts.append({"level": "info", "type": "daily_70", "message": f"Daily cost at 70% of limit (${daily_cost:.4f}/${daily_limit:.2f})", "pct": round(daily_pct, 1)})

        if monthly_limit > 0:
            monthly_pct = (monthly_cost / monthly_limit) * 100
            if monthly_pct >= 100:
                alerts.append({"level": "critical", "type": "monthly_limit_exceeded", "message": f"Monthly cost ${monthly_cost:.4f} exceeds limit ${monthly_limit:.2f} ({monthly_pct:.0f}%)", "pct": round(monthly_pct, 1)})
            elif monthly_pct >= 90:
                alerts.append({"level": "warning", "type": "monthly_90", "message": f"Monthly cost at 90% of limit (${monthly_cost:.4f}/${monthly_limit:.2f})", "pct": round(monthly_pct, 1)})
            elif monthly_pct >= 70:
                alerts.append({"level": "info", "type": "monthly_70", "message": f"Monthly cost at 70% of limit (${monthly_cost:.4f}/${monthly_limit:.2f})", "pct": round(monthly_pct, 1)})

        blocking = alerts and any(a["level"] == "critical" for a in alerts) and bool(self._get_budget("budget_blocking_enabled"))

        return {
            "daily_cost": round(daily_cost, 6),
            "daily_limit": daily_limit,
            "monthly_cost": round(monthly_cost, 6),
            "monthly_limit": monthly_limit,
            "alerts": alerts,
            "blocking": blocking,
        }

    def should_block_cloud(self) -> bool:
        """Check if cloud provider calls should be blocked based on budget."""
        if not bool(self._get_budget("budget_blocking_enabled")):
            return False
        alerts = self.check_budget_alerts()
        return alerts.get("blocking", False)

    # ------------------------------------------------------------------
    # Export (v1.5.0)
    # ------------------------------------------------------------------

    def export_usage(self, fmt: str = "csv", workspace: str | None = None) -> dict[str, Any]:
        """Export usage data in CSV, JSON, or Markdown format."""
        events = list_records("usage_events")
        ws = self._get_workspace(workspace)
        if ws:
            events = [e for e in events if e.get("workspace_name", "default") == ws]
        output_dir = WORKSPACE / "outputs" / "usage"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if fmt == "csv":
            filepath = output_dir / f"usage_{timestamp}.csv"
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["timestamp", "provider", "model", "model_role", "feature", "estimated_input_tokens", "estimated_output_tokens", "estimated_total_tokens", "estimated_cost", "estimated", "fallback_used", "status", "discussion_id", "is_local", "workspace_name", "latency_ms"])
            for e in events:
                writer.writerow([
                    e.get("timestamp", ""),
                    e.get("provider", ""),
                    e.get("model", ""),
                    e.get("model_role", ""),
                    e.get("feature", ""),
                    e.get("estimated_input_tokens", 0),
                    e.get("estimated_output_tokens", 0),
                    e.get("estimated_total_tokens", 0),
                    e.get("estimated_cost", 0.0),
                    e.get("estimated", True),
                    e.get("fallback_used", False),
                    e.get("status", ""),
                    e.get("discussion_id", ""),
                    e.get("is_local", False),
                    e.get("workspace_name", "default"),
                    e.get("latency_ms", ""),
                ])
            filepath.write_text(buf.getvalue(), encoding="utf-8")
            return {"status": "exported", "format": "csv", "path": str(filepath), "records": len(events)}

        if fmt == "json":
            filepath = output_dir / f"usage_{timestamp}.json"
            filepath.write_text(json.dumps(events, indent=2, default=str), encoding="utf-8")
            return {"status": "exported", "format": "json", "path": str(filepath), "records": len(events)}

        if fmt == "markdown":
            filepath = output_dir / f"usage_{timestamp}.md"
            lines = ["# Usage Report", f"Generated: {utc_now()}", f"Workspace: {ws or 'all'}", "", "## Events", ""]
            lines.append("| Timestamp | Provider | Model | Role | Feature | Tokens | Cost | Estimated | Fallback | Status | Workspace |")
            lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
            for e in events:
                lines.append(
                    f"| {e.get('timestamp', '')} | {e.get('provider', '')} | {e.get('model', '')} | {e.get('model_role', '')} | {e.get('feature', '')} | {e.get('estimated_total_tokens', 0)} | ${e.get('estimated_cost', 0.0):.6f} | {'Yes' if e.get('estimated', True) else 'No'} | {'Yes' if e.get('fallback_used', False) else 'No'} | {e.get('status', '')} | {e.get('workspace_name', 'default')} |"
                )
            summary = self.get_summary(workspace=workspace)
            lines.extend(["", "## Summary", "", f"- Total calls: {summary['total_calls']}", f"- Total tokens: {summary['total_tokens']}", f"- Total estimated cost: ${summary['total_estimated_cost']:.6f}", f"- Local calls: {summary['local_calls']}", f"- Cloud calls: {summary['cloud_calls']}", f"- Workspace: {summary.get('workspace', 'all')}", ""])
            filepath.write_text("\n".join(lines), encoding="utf-8")
            return {"status": "exported", "format": "markdown", "path": str(filepath), "records": len(events)}

        return {"status": "error", "message": f"Unsupported format: {fmt}. Use csv, json, or markdown."}

    # ------------------------------------------------------------------
    # Cost anomaly detection (v1.5.0)
    # ------------------------------------------------------------------

    def detect_anomalies(self) -> dict[str, Any]:
        """Detect cost anomalies and return warnings."""
        events = list_records("usage_events")
        if not events:
            return {"anomalies": [], "warnings": []}

        warnings: list[dict[str, Any]] = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_events = [e for e in events if (e.get("timestamp", "") or "").startswith(today)]

        # Sudden cost spike: today's cost > 3x average daily cost
        if len(events) > 7:
            daily_costs: dict[str, float] = {}
            for e in events:
                ts = (e.get("timestamp", "") or "")[:10]
                if ts:
                    daily_costs[ts] = daily_costs.get(ts, 0.0) + e.get("estimated_cost", 0.0)
            avg_daily = sum(daily_costs.values()) / max(len(daily_costs), 1)
            today_cost = sum(e.get("estimated_cost", 0.0) for e in today_events)
            if avg_daily > 0 and today_cost > avg_daily * 3:
                warnings.append({"type": "cost_spike", "level": "warning", "message": f"Today's cost ${today_cost:.4f} is {today_cost/avg_daily:.1f}x the daily average ${avg_daily:.4f}"})

        # Too many discussion calls
        discussion_today = [e for e in today_events if e.get("feature") == "discussion"]
        if len(discussion_today) > 10:
            warnings.append({"type": "discussion_spike", "level": "warning", "message": f"{len(discussion_today)} discussion calls today. This may increase costs significantly."})

        # Fallback causing cloud provider use
        fallback_cloud = [e for e in today_events if e.get("fallback_used") and not e.get("is_local")]
        if fallback_cloud:
            warnings.append({"type": "fallback_cloud", "level": "info", "message": f"{len(fallback_cloud)} cloud fallback(s) today. Check provider configuration."})

        # Repeated provider errors
        error_events = [e for e in today_events if e.get("status") in ("error", "failed")]
        if len(error_events) > 5:
            warnings.append({"type": "repeated_errors", "level": "warning", "message": f"{len(error_events)} provider errors today. Check provider health."})

        # Unusually high token usage
        today_tokens = sum(e.get("estimated_total_tokens", 0) for e in today_events)
        if today_tokens > 100000:
            warnings.append({"type": "high_tokens", "level": "info", "message": f"{today_tokens} tokens used today. This is unusually high."})

        return {"anomalies": warnings, "warnings": warnings}

    # ------------------------------------------------------------------
    # Usage trends (v1.6.0)
    # ------------------------------------------------------------------

    def get_trends(self, days: int = 7) -> dict[str, Any]:
        """Get daily usage trends for the last N days."""
        events = list_records("usage_events")
        now = datetime.now(timezone.utc)
        daily: dict[str, dict[str, Any]] = {}

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            daily[day] = {"date": day, "calls": 0, "tokens": 0, "cost": 0.0, "local_calls": 0, "cloud_calls": 0}

        for e in events:
            ts = (e.get("timestamp", "") or "")[:10]
            if ts in daily:
                daily[ts]["calls"] += 1
                daily[ts]["tokens"] += e.get("estimated_total_tokens", 0)
                daily[ts]["cost"] += e.get("estimated_cost", 0.0)
                if e.get("is_local"):
                    daily[ts]["local_calls"] += 1
                else:
                    daily[ts]["cloud_calls"] += 1

        rows = sorted(daily.values(), key=lambda x: x["date"])
        for r in rows:
            r["cost"] = round(r["cost"], 6)

        return {"period": f"last_{days}_days", "days": days, "daily": rows}

    def get_monthly_trends(self, months: int = 3) -> dict[str, Any]:
        """Get monthly usage trends for the last N months."""
        events = list_records("usage_events")
        now = datetime.now(timezone.utc)
        monthly: dict[str, dict[str, Any]] = {}

        for i in range(months):
            m = now.replace(day=1) - timedelta(days=i * 28)
            key = m.strftime("%Y-%m")
            monthly[key] = {"month": key, "calls": 0, "tokens": 0, "cost": 0.0, "local_calls": 0, "cloud_calls": 0}

        for e in events:
            ts = (e.get("timestamp", "") or "")[:7]
            if ts in monthly:
                monthly[ts]["calls"] += 1
                monthly[ts]["tokens"] += e.get("estimated_total_tokens", 0)
                monthly[ts]["cost"] += e.get("estimated_cost", 0.0)
                if e.get("is_local"):
                    monthly[ts]["local_calls"] += 1
                else:
                    monthly[ts]["cloud_calls"] += 1

        rows = sorted(monthly.values(), key=lambda x: x["month"])
        for r in rows:
            r["cost"] = round(r["cost"], 6)

        return {"period": f"last_{months}_months", "months": months, "monthly": rows}

    # ------------------------------------------------------------------
    # Alert history (v1.6.0)
    # ------------------------------------------------------------------

    def record_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        """Record a budget alert to history."""
        row = {
            "id": f"alert_{utc_now().replace(':', '-').replace('.', '-')}",
            "level": alert.get("level", "info"),
            "type": alert.get("type", ""),
            "message": alert.get("message", ""),
            "pct": alert.get("pct", 0.0),
            "daily_cost": alert.get("daily_cost", 0.0),
            "daily_limit": alert.get("daily_limit", 0.0),
            "monthly_cost": alert.get("monthly_cost", 0.0),
            "monthly_limit": alert.get("monthly_limit", 0.0),
            "workspace_name": self._get_workspace(),
            "dismissed": False,
            "timestamp": utc_now(),
        }
        insert_record("alert_history", row)
        return row

    def get_alert_history(self, include_dismissed: bool = False) -> list[dict[str, Any]]:
        """Get alert history."""
        alerts = list_records("alert_history")
        if not include_dismissed:
            alerts = [a for a in alerts if not a.get("dismissed")]
        return sorted(alerts, key=lambda x: x.get("timestamp", ""), reverse=True)

    def dismiss_alert(self, alert_id: str) -> dict[str, Any]:
        """Dismiss an alert."""
        try:
            update_record("alert_history", alert_id, {"dismissed": True, "updated_at": utc_now()})
            return {"status": "dismissed", "alert_id": alert_id}
        except Exception:
            return {"status": "error", "message": f"Alert {alert_id} not found."}

    # ------------------------------------------------------------------
    # Webhook alerts (v1.7.0)
    # ------------------------------------------------------------------

    WEBHOOK_DEFAULTS = {
        "webhook_alerts_enabled": "false",
        "webhook_url": "",
        "webhook_test_mode": "true",
        "webhook_requires_approval": "true",
        "webhook_allowed_event_types": "budget_warning,budget_exceeded,provider_degraded,provider_rate_limited,cost_anomaly",
    }

    def _get_webhook_setting(self, key: str) -> str:
        try:
            val = self.settings.get(key)
            if val:
                return str(val.get("value", ""))
        except (ValueError, KeyError):
            pass
        return self.WEBHOOK_DEFAULTS.get(key, "")

    def get_webhook_status(self) -> dict[str, Any]:
        """Get webhook alert configuration status."""
        enabled = self._get_webhook_setting("webhook_alerts_enabled").lower() == "true"
        url = self._get_webhook_setting("webhook_url")
        test_mode = self._get_webhook_setting("webhook_test_mode").lower() != "false"
        requires_approval = self._get_webhook_setting("webhook_requires_approval").lower() != "false"
        allowed_types = self._get_webhook_setting("webhook_allowed_event_types")
        return {
            "webhook_alerts_enabled": enabled,
            "webhook_url": url,
            "webhook_test_mode": test_mode,
            "webhook_requires_approval": requires_approval,
            "webhook_allowed_event_types": [t.strip() for t in allowed_types.split(",") if t.strip()],
            "webhook_secret_configured": bool(self._get_webhook_setting("webhook_secret")),
        }

    def set_webhook_url(self, url: str, confirm: bool = False) -> dict[str, Any]:
        """Set webhook URL with confirmation."""
        if not confirm:
            return {"status": "error", "message": "Webhook URL requires --confirm true."}
        if not url.startswith("https://"):
            return {"status": "error", "message": "Webhook URL must use HTTPS."}
        self.settings.set("webhook_url", url)
        return {"status": "updated", "webhook_url": url}

    def enable_webhooks(self, confirm: bool = False) -> dict[str, Any]:
        """Enable webhook alerts with confirmation."""
        if not confirm:
            return {"status": "error", "message": "Enabling webhooks requires --confirm true."}
        url = self._get_webhook_setting("webhook_url")
        if not url:
            return {"status": "error", "message": "Set webhook URL first with set-url."}
        self.settings.set("webhook_alerts_enabled", "true")
        self.settings.set("webhook_test_mode", "true")
        return {"status": "enabled", "test_mode": True, "message": "Webhooks enabled in test mode. Production requires approval."}

    def disable_webhooks(self) -> dict[str, Any]:
        """Disable webhook alerts."""
        self.settings.set("webhook_alerts_enabled", "false")
        return {"status": "disabled"}

    def send_webhook_test(self, event_type: str = "budget_warning") -> dict[str, Any]:
        """Send a test webhook payload."""
        enabled = self._get_webhook_setting("webhook_alerts_enabled").lower() == "true"
        url = self._get_webhook_setting("webhook_url")
        if not enabled or not url:
            return {"status": "error", "message": "Webhooks not enabled or URL not set."}
        payload = self._build_webhook_payload(event_type, level="info", message="Test webhook from Liuant Agentic OS", workspace=self._get_workspace())
        payload["test_mode"] = True
        payload["event_type"] = event_type
        return {"status": "test_payload_ready", "payload": payload, "url": url, "message": "Test payload generated. Delivery requires HTTP client."}

    def _build_webhook_payload(self, event_type: str, level: str, message: str, workspace: str = "default", provider: str = "", model: str = "", estimated_cost: float = 0.0) -> dict[str, Any]:
        """Build a safe webhook payload with no secrets, prompts, or raw errors."""
        return {
            "event_type": event_type,
            "workspace": workspace,
            "level": level,
            "message": message[:500],
            "provider": provider[:50] if provider else "",
            "model": model[:100] if model else "",
            "estimated_cost": round(estimated_cost, 6),
            "timestamp": utc_now(),
            "source": "liuant-agentic-os",
        }

    # ------------------------------------------------------------------
    # Discussion cost-per-role (v1.7.0)
    # ------------------------------------------------------------------

    def get_discussion_costs(self, workspace: str | None = None) -> dict[str, Any]:
        """Get discussion cost breakdown by role."""
        events = list_records("usage_events")
        ws = self._get_workspace(workspace)
        if ws:
            events = [e for e in events if e.get("workspace_name", "default") == ws]
        discussion_events = [e for e in events if e.get("feature") == "discussion"]
        if not discussion_events:
            return {"discussions": [], "total_cost": 0.0, "total_tokens": 0}

        discussions: dict[str, dict[str, Any]] = {}
        for e in discussion_events:
            disc_id = e.get("discussion_id", "unknown")
            if disc_id not in discussions:
                discussions[disc_id] = {"discussion_id": disc_id, "roles": {}, "final": {}, "total_tokens": 0, "total_cost": 0.0, "timestamp": e.get("timestamp", "")}
            role = e.get("model_role", "unknown")
            cost = e.get("estimated_cost", 0.0)
            tokens = e.get("estimated_total_tokens", 0)
            if role == "discussion" or "," in str(role):
                discussions[disc_id]["total_tokens"] += tokens
                discussions[disc_id]["total_cost"] += cost
            else:
                if role not in discussions[disc_id]["roles"]:
                    discussions[disc_id]["roles"][role] = {"tokens": 0, "estimated_cost": 0.0, "provider": e.get("provider", ""), "model": e.get("model", "")}
                discussions[disc_id]["roles"][role]["tokens"] += tokens
                discussions[disc_id]["roles"][role]["estimated_cost"] += cost

        for d in discussions.values():
            d["total_cost"] = round(d["total_cost"], 6)

        rows = sorted(discussions.values(), key=lambda x: x["timestamp"], reverse=True)
        total_cost = round(sum(d["total_cost"] for d in rows), 6)
        total_tokens = sum(d["total_tokens"] for d in rows)

        return {"discussions": rows, "total_cost": total_cost, "total_tokens": total_tokens}

    # ------------------------------------------------------------------
    # Usage retention policies (v1.7.0)
    # ------------------------------------------------------------------

    RETENTION_DEFAULTS = {
        "usage_retention_days": 90,
        "alert_retention_days": 90,
        "provider_health_retention_days": 90,
        "auto_cleanup_enabled": False,
    }

    def _get_retention(self, key: str) -> int | bool:
        try:
            val = self.settings.get(key)
            if val.get("status") == "found":
                v = val.get("value", "")
                if key == "auto_cleanup_enabled":
                    return v.lower() == "true"
                return int(v)
        except (ValueError, KeyError, TypeError):
            pass
        return self.RETENTION_DEFAULTS.get(key, 90)

    def get_retention(self) -> dict[str, Any]:
        """Get current retention settings."""
        return {
            "usage_retention_days": self._get_retention("usage_retention_days"),
            "alert_retention_days": self._get_retention("alert_retention_days"),
            "provider_health_retention_days": self._get_retention("provider_health_retention_days"),
            "auto_cleanup_enabled": self._get_retention("auto_cleanup_enabled"),
        }

    def set_retention(self, days: int = 90) -> dict[str, Any]:
        """Set retention days for all tables."""
        self.settings.set("usage_retention_days", str(days))
        self.settings.set("alert_retention_days", str(days))
        self.settings.set("provider_health_retention_days", str(days))
        return {"status": "updated", "retention_days": days}

    def cleanup_dry_run(self) -> dict[str, Any]:
        """Show records that would be deleted without deleting."""
        usage_days = self._get_retention("usage_retention_days")
        alert_days = self._get_retention("alert_retention_days")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=usage_days)).strftime("%Y-%m-%d")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        usage_events = list_records("usage_events")
        usage_candidates = [e for e in usage_events if (e.get("timestamp", "") or "")[:10] < cutoff and (e.get("timestamp", "") or "")[:10] < today]

        alert_events = list_records("alert_history")
        alert_cutoff = (datetime.now(timezone.utc) - timedelta(days=alert_days)).strftime("%Y-%m-%d")
        alert_candidates = [a for a in alert_events if (a.get("timestamp", "") or "")[:10] < alert_cutoff and (a.get("timestamp", "") or "")[:10] < today]

        return {
            "usage_records_to_delete": len(usage_candidates),
            "alert_records_to_delete": len(alert_candidates),
            "total_records_to_delete": len(usage_candidates) + len(alert_candidates),
            "cutoff_date": cutoff,
            "message": "Run cleanup --confirm true to delete these records.",
        }

    def cleanup_confirm(self) -> dict[str, Any]:
        """Delete old records past retention period."""
        usage_days = self._get_retention("usage_retention_days")
        alert_days = self._get_retention("alert_retention_days")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=usage_days)).strftime("%Y-%m-%d")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        deleted_usage = 0
        deleted_alerts = 0

        usage_events = list_records("usage_events")
        for e in usage_events:
            ts = (e.get("timestamp", "") or "")[:10]
            if ts < cutoff and ts < today:
                from runtime.db import delete_record
                try:
                    delete_record("usage_events", e.get("id", ""))
                    deleted_usage += 1
                except Exception:
                    pass

        alert_events = list_records("alert_history")
        alert_cutoff = (datetime.now(timezone.utc) - timedelta(days=alert_days)).strftime("%Y-%m-%d")
        for a in alert_events:
            ts = (a.get("timestamp", "") or "")[:10]
            if ts < alert_cutoff and ts < today:
                from runtime.db import delete_record
                try:
                    delete_record("alert_history", a.get("id", ""))
                    deleted_alerts += 1
                except Exception:
                    pass

        return {
            "status": "cleaned",
            "usage_records_deleted": deleted_usage,
            "alert_records_deleted": deleted_alerts,
            "total_deleted": deleted_usage + deleted_alerts,
        }

    # ------------------------------------------------------------------
    # Per-round discussion cost breakdown (v1.8.0)
    # ------------------------------------------------------------------

    def record_discussion_round(
        self,
        discussion_id: str,
        round_number: int,
        phase: str,
        role: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0.0,
        exact_cost_available: bool = False,
        fallback_used: bool = False,
        status: str = "completed",
        workspace_name: str | None = None,
    ) -> dict[str, Any]:
        """Record a per-round discussion cost entry."""
        ws = self._get_workspace(workspace_name)
        row = {
            "id": f"dcr_{utc_now().replace(':', '-').replace('.', '-')}",
            "discussion_id": discussion_id,
            "round_number": round_number,
            "phase": phase,
            "role": role,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": round(estimated_cost, 6),
            "exact_cost_available": exact_cost_available,
            "fallback_used": fallback_used,
            "status": status,
            "timestamp": utc_now(),
            "workspace_name": ws,
        }
        insert_record("discussion_cost_rounds", row)
        return row

    def get_discussion_costs_by_round(self, discussion_id: str | None = None, workspace: str | None = None, latest: bool = False, rounds: bool = False) -> dict[str, Any]:
        """Get discussion cost breakdown by round."""
        from runtime.db import list_records as db_list
        all_rounds = db_list("discussion_cost_rounds")
        ws = self._get_workspace(workspace)
        if ws:
            all_rounds = [r for r in all_rounds if r.get("workspace_name", "default") == ws]

        if discussion_id:
            all_rounds = [r for r in all_rounds if r.get("discussion_id") == discussion_id]
        elif latest:
            if all_rounds:
                latest_disc_id = all_rounds[0].get("discussion_id")
                all_rounds = [r for r in all_rounds if r.get("discussion_id") == latest_disc_id]

        if not all_rounds:
            return {"discussions": [], "total_cost": 0.0, "total_tokens": 0}

        discussions: dict[str, dict[str, Any]] = {}
        for r in all_rounds:
            disc_id = r.get("discussion_id", "unknown")
            if disc_id not in discussions:
                discussions[disc_id] = {
                    "discussion_id": disc_id,
                    "rounds": {},
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "timestamp": r.get("timestamp", ""),
                }
            round_num = r.get("round_number", 0)
            phase = r.get("phase", "unknown")
            key = f"round_{round_num}_{phase}"
            if key not in discussions[disc_id]["rounds"]:
                discussions[disc_id]["rounds"][key] = {
                    "round_number": round_num,
                    "phase": phase,
                    "roles": {},
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            role = r.get("role", "unknown")
            if role not in discussions[disc_id]["rounds"][key]["roles"]:
                discussions[disc_id]["rounds"][key]["roles"][role] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                    "provider": r.get("provider", ""),
                    "model": r.get("model", ""),
                    "fallback_used": r.get("fallback_used", False),
                }
            discussions[disc_id]["rounds"][key]["roles"][role]["input_tokens"] += r.get("input_tokens", 0)
            discussions[disc_id]["rounds"][key]["roles"][role]["output_tokens"] += r.get("output_tokens", 0)
            discussions[disc_id]["rounds"][key]["roles"][role]["total_tokens"] += r.get("total_tokens", 0)
            discussions[disc_id]["rounds"][key]["roles"][role]["estimated_cost"] += r.get("estimated_cost", 0.0)
            discussions[disc_id]["rounds"][key]["total_tokens"] += r.get("total_tokens", 0)
            discussions[disc_id]["rounds"][key]["total_cost"] += r.get("estimated_cost", 0.0)
            discussions[disc_id]["total_tokens"] += r.get("total_tokens", 0)
            discussions[disc_id]["total_cost"] += r.get("estimated_cost", 0.0)

        for d in discussions.values():
            d["total_cost"] = round(d["total_cost"], 6)
            for rnd in d["rounds"].values():
                rnd["total_cost"] = round(rnd["total_cost"], 6)
                for role_data in rnd["roles"].values():
                    role_data["estimated_cost"] = round(role_data["estimated_cost"], 6)

        result_rows = sorted(discussions.values(), key=lambda x: x["timestamp"], reverse=True)
        total_cost = round(sum(d["total_cost"] for d in result_rows), 6)
        total_tokens = sum(d["total_tokens"] for d in result_rows)

        if not rounds:
            for d in result_rows:
                d.pop("rounds", None)

        return {"discussions": result_rows, "total_cost": total_cost, "total_tokens": total_tokens}

    # ------------------------------------------------------------------
    # Cleanup scheduler (v1.8.0)
    # ------------------------------------------------------------------

    CLEANUP_SCHEDULER_DEFAULTS = {
        "auto_cleanup_enabled": "false",
        "cleanup_schedule": "weekly",
        "cleanup_day": "Sunday",
        "cleanup_time": "03:00",
        "export_before_cleanup": "true",
        "allow_cleanup_without_export": "false",
        "cleanup_last_run": "",
        "cleanup_next_run": "",
    }

    def _get_scheduler_setting(self, key: str) -> str:
        try:
            val = self.settings.get(key)
            if val.get("status") == "found":
                return str(val.get("value", ""))
        except (ValueError, KeyError):
            pass
        return self.CLEANUP_SCHEDULER_DEFAULTS.get(key, "")

    def get_cleanup_scheduler_status(self) -> dict[str, Any]:
        """Get cleanup scheduler status."""
        return {
            "auto_cleanup_enabled": self._get_scheduler_setting("auto_cleanup_enabled").lower() == "true",
            "cleanup_schedule": self._get_scheduler_setting("cleanup_schedule"),
            "cleanup_day": self._get_scheduler_setting("cleanup_day"),
            "cleanup_time": self._get_scheduler_setting("cleanup_time"),
            "export_before_cleanup": self._get_scheduler_setting("export_before_cleanup").lower() != "false",
            "allow_cleanup_without_export": self._get_scheduler_setting("allow_cleanup_without_export").lower() == "true",
            "cleanup_last_run": self._get_scheduler_setting("cleanup_last_run"),
            "cleanup_next_run": self._get_scheduler_setting("cleanup_next_run"),
        }

    def enable_cleanup_scheduler(self, confirm: bool = False) -> dict[str, Any]:
        """Enable cleanup scheduler with confirmation."""
        if not confirm:
            return {"status": "error", "message": "Enabling cleanup scheduler requires --confirm true."}
        self.settings.set("auto_cleanup_enabled", "true")
        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(days=7)).strftime("%Y-%m-%dT03:00:00Z")
        self.settings.set("cleanup_next_run", next_run)
        return {"status": "enabled", "next_run": next_run, "message": "Cleanup scheduler enabled. Runs weekly on Sunday at 03:00 UTC."}

    def disable_cleanup_scheduler(self) -> dict[str, Any]:
        """Disable cleanup scheduler."""
        self.settings.set("auto_cleanup_enabled", "false")
        self.settings.set("cleanup_next_run", "")
        return {"status": "disabled"}

    def run_cleanup_now(self, dry_run: bool = False, confirm: bool = False, export_before: bool = True) -> dict[str, Any]:
        """Run cleanup immediately."""
        if not dry_run and not confirm:
            return {"status": "error", "message": "Cleanup requires --confirm true. Use --dry-run to preview."}

        export_path = ""
        if export_before:
            export_result = self.export_usage(fmt="json")
            if export_result.get("status") == "exported":
                export_path = export_result.get("path", "")
            else:
                allow_without = self._get_scheduler_setting("allow_cleanup_without_export").lower() == "true"
                if not allow_without:
                    return {"status": "error", "message": "Export failed and allow_cleanup_without_export is false. Cleanup aborted."}

        if dry_run:
            dry_result = self.cleanup_dry_run()
            dry_result["export_path"] = export_path
            dry_result["export_before_cleanup"] = export_before
            return dry_result

        cleanup_result = self.cleanup_confirm()
        self.settings.set("cleanup_last_run", utc_now())
        next_run = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT03:00:00Z")
        self.settings.set("cleanup_next_run", next_run)
        cleanup_result["export_path"] = export_path
        cleanup_result["export_before_cleanup"] = export_before
        cleanup_result["next_run"] = next_run
        return cleanup_result

    def cleanup_dry_run_with_export_plan(self) -> dict[str, Any]:
        """Show cleanup plan with export details."""
        base = self.cleanup_dry_run()
        output_dir = WORKSPACE / "outputs" / "usage"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_path = str(output_dir / f"usage_{timestamp}.json")

        usage_events = list_records("usage_events")
        alert_events = list_records("alert_history")
        usage_days = self._get_retention("usage_retention_days")
        alert_days = self._get_retention("alert_retention_days")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=usage_days)).strftime("%Y-%m-%d")
        alert_cutoff = (datetime.now(timezone.utc) - timedelta(days=alert_days)).strftime("%Y-%m-%d")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        usage_candidates = [e for e in usage_events if (e.get("timestamp", "") or "")[:10] < cutoff and (e.get("timestamp", "") or "")[:10] < today]
        alert_candidates = [a for a in alert_events if (a.get("timestamp", "") or "")[:10] < alert_cutoff and (a.get("timestamp", "") or "")[:10] < today]

        oldest_usage = min((e.get("timestamp", "")[:10] for e in usage_candidates if e.get("timestamp")), default="N/A")
        newest_usage = max((e.get("timestamp", "")[:10] for e in usage_candidates if e.get("timestamp")), default="N/A")
        oldest_alert = min((a.get("timestamp", "")[:10] for a in alert_candidates if a.get("timestamp")), default="N/A")
        newest_alert = max((a.get("timestamp", "")[:10] for a in alert_candidates if a.get("timestamp")), default="N/A")

        base.update({
            "export_path": export_path,
            "export_before_cleanup": True,
            "usage_records_oldest": oldest_usage,
            "usage_records_newest": newest_usage,
            "alert_records_oldest": oldest_alert,
            "alert_records_newest": newest_alert,
            "warning": "Deletion is local and irreversible unless exported.",
        })
        return base
