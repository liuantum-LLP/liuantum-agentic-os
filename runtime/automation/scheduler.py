from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.action_log import log_external_action
from runtime.automation.manager import AutomationManager
from runtime.automation.schedule_utils import is_due, parse_dt
from runtime.db import get_record, list_records


class SchedulerEngine:
    def status(self) -> dict[str, Any]:
        automations = AutomationManager().list()
        enabled = [row for row in automations if row.get("enabled")]
        due = self.list_due()
        next_due = sorted([row.get("next_run_at") for row in enabled if row.get("next_run_at")])[:1]
        ticks = [row for row in list_records("action_logs") if row.get("action_type") == "scheduler_tick"]
        return {
            "enabled": True,
            "mode": "local",
            "running": False,
            "due_count": len(due),
            "enabled_automation_count": len(enabled),
            "last_tick_at": ticks[0]["created_at"] if ticks else None,
            "next_due_at": next_due[0] if next_due else None,
            "warnings": ["Local MVP scheduler uses manual tick/run-due; no production daemon is installed."],
        }

    def list_due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        return [row for row in AutomationManager().list() if is_due(row, current)]

    def run_due(self, now: datetime | None = None, limit: int = 5) -> dict[str, Any]:
        due = self.list_due(now)[:limit]
        results = [AutomationManager().run(row["id"], reason="scheduled") for row in due]
        log_external_action("scheduler_run_due", "completed", {"due_count": len(due), "run_count": len(results), "limit": limit})
        return {"status": "completed", "due_count": len(due), "run_count": len(results), "runs": results}

    def tick(self) -> dict[str, Any]:
        result = self.run_due()
        log_external_action("scheduler_tick", "completed", {"run_count": result["run_count"], "due_count": result["due_count"]})
        return {"status": "completed", "scheduler": self.status(), "result": result}

    def runs(self) -> list[dict[str, Any]]:
        return list_records("automation_runs")

    def run_show(self, run_id: str) -> dict[str, Any]:
        row = get_record("automation_runs", run_id)
        if not row:
            raise ValueError(f"Automation run not found: {run_id}")
        return row


def due_sort_key(row: dict[str, Any]) -> datetime:
    return parse_dt(row.get("next_run_at")) or datetime.max.replace(tzinfo=timezone.utc)
