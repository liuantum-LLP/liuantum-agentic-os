from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.agents import AgentRunner
from runtime.approvals import ApprovalManager
from runtime.connectors.email.base_email import EmailDraft
from runtime.connectors.email.draft_store import EmailDraftStore
from runtime.db import delete_record, get_record, insert_record, list_records, update_record
from runtime.exports import outputs_dir, write_text
from runtime.workflows import SocialContentWorkflow
from runtime.automation.schedule_utils import calculate_next_run, human_readable_schedule, validate_schedule


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AutomationDefinition:
    name: str
    agent_slug: str
    trigger_type: str
    schedule_text: str
    task_prompt: str
    connector_ids_json: list[str] = field(default_factory=list)
    schedule: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    workspace_name: str = "default"
    allowed_outputs: list[str] = field(default_factory=lambda: ["local_report"])
    external_actions_allowed: bool = False
    next_run_at: str | None = None
    run_count: int = 0
    failure_count: int = 0
    enabled: bool = True
    requires_approval: bool = True
    last_run_at: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutomationManager:
    trigger_types = ("manual", "interval", "daily", "weekly", "monthly", "cron_like", "scheduled", "webhook", "email_received", "social_comment_received", "file_changed")

    def list(self) -> list[dict[str, Any]]:
        return [self._normalize(row) for row in list_records("automations")]

    def show(self, automation_id: str) -> dict[str, Any]:
        row = get_record("automations", automation_id)
        if not row:
            raise ValueError(f"Automation not found: {automation_id}")
        return self._normalize(row)

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        trigger_type = data.get("trigger_type", "manual")
        if trigger_type == "scheduled":
            trigger_type = "daily"
        if trigger_type not in self.trigger_types:
            raise ValueError(f"Unsupported trigger_type: {trigger_type}")
        developer_mode = data.get("permission_mode") == "developer"
        schedule_type = trigger_type if trigger_type in {"manual", "interval", "daily", "weekly", "monthly", "cron_like"} else "manual"
        schedule = validate_schedule(schedule_type, data.get("schedule", {}), developer_mode=developer_mode)
        automation = AutomationDefinition(
            name=data["name"],
            agent_slug=data.get("agent_slug", "automation-builder-agent"),
            trigger_type=trigger_type,
            schedule=schedule,
            schedule_text=data.get("schedule_text") or _schedule_text(trigger_type, schedule),
            task_prompt=data["task_prompt"],
            connector_ids_json=data.get("connector_ids_json", []),
            description=data.get("description", ""),
            workspace_name=data.get("workspace_name", "default"),
            allowed_outputs=data.get("allowed_outputs", ["local_report"]),
            external_actions_allowed=False,
            enabled=data.get("enabled", True),
            requires_approval=data.get("requires_approval", True),
        )
        row = automation.to_dict()
        row["next_run_at"] = calculate_next_run(row)
        return insert_record("automations", row)

    def create_daily(self, name: str, time_of_day: str, agent_slug: str, task_prompt: str, timezone_name: str = "Asia/Kolkata", **extra: Any) -> dict[str, Any]:
        return self.create({**extra, "name": name, "trigger_type": "daily", "schedule": {"time_of_day": time_of_day, "timezone": timezone_name}, "agent_slug": agent_slug, "task_prompt": task_prompt})

    def create_weekly(self, name: str, day: str, time_of_day: str, agent_slug: str, task_prompt: str, timezone_name: str = "Asia/Kolkata", **extra: Any) -> dict[str, Any]:
        return self.create({**extra, "name": name, "trigger_type": "weekly", "schedule": {"days_of_week": [day.lower()], "time_of_day": time_of_day, "timezone": timezone_name}, "agent_slug": agent_slug, "task_prompt": task_prompt})

    def create_interval(self, name: str, minutes: int, agent_slug: str, task_prompt: str, **extra: Any) -> dict[str, Any]:
        return self.create({**extra, "name": name, "trigger_type": "interval", "schedule": {"interval_minutes": minutes, "timezone": extra.get("timezone", "Asia/Kolkata")}, "agent_slug": agent_slug, "task_prompt": task_prompt})

    def run(self, automation_id: str, reason: str = "manual") -> dict[str, Any]:
        automation = self.show(automation_id)
        started_at = utc_now()
        run = insert_record("automation_runs", {
            "id": str(uuid4()),
            "automation_id": automation_id,
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "output_summary": "",
            "output_path": "",
            "agent_run_id": None,
            "approvals_json": [],
            "errors_json": [],
            "reason": reason,
            "created_at": started_at,
            "updated_at": started_at,
        })
        approvals: list[str] = []
        errors: list[dict[str, str]] = []
        status = "completed"
        try:
            safety = inspect_task_safety(automation.get("task_prompt", ""))
            if safety["blocked"]:
                status = "approval_required"
                report = self._write_report(automation, run["id"], {"blocked": True, "warnings": safety["warnings"]})
                approval = ApprovalManager().create("automation_blocked_external_action", {"automation_id": automation_id, "task_preview": safe_preview(automation.get("task_prompt", "")), "warnings": safety["warnings"], "send_enabled": False}, None)
                approvals.append(approval["id"])
                log_external_action("automation_blocked_action", "approval_required", {"automation_id": automation_id, "warnings": safety["warnings"]}, None, approval["id"])
                agent_run = None
            else:
                agent_run = AgentRunner().run(automation["agent_slug"], automation["task_prompt"])
                report = self._write_report(automation, run["id"], {"agent_run": agent_run, "reason": reason})
                approvals.extend(self._create_allowed_outputs(automation, agent_run))
                if approvals:
                    status = "approval_required"
            completed_at = utc_now()
            run = update_record("automation_runs", run["id"], {
                "status": status,
                "completed_at": completed_at,
                "output_summary": "Automation completed safely. External actions remain draft-only.",
                "output_path": report,
                "agent_run_id": agent_run.get("id") if agent_run else None,
                "approvals_json": approvals,
                "errors_json": errors,
                "updated_at": completed_at,
            })
            updates = {
                "last_run_at": completed_at,
                "next_run_at": calculate_next_run({**automation, "last_run_at": completed_at}, from_time=datetime.now(timezone.utc)),
                "run_count": int(automation.get("run_count", 0)) + 1,
                "updated_at": completed_at,
            }
            update_record("automations", automation_id, updates)
            log_external_action("automation_run_completed", status, _safe_log({"automation_id": automation_id, "run_id": run["id"], "approvals": approvals}), None)
            response_status = "manual_run_recorded" if reason == "manual" and status == "completed" else status
            return {"status": response_status, "automation": self.show(automation_id), "run": run, "result": "Automation completed safely. External actions remain draft-only."}
        except Exception as exc:
            completed_at = utc_now()
            errors.append({"error": safe_error(exc)})
            run = update_record("automation_runs", run["id"], {"status": "failed", "completed_at": completed_at, "errors_json": errors, "updated_at": completed_at})
            update_record("automations", automation_id, {"last_run_at": completed_at, "failure_count": int(automation.get("failure_count", 0)) + 1, "next_run_at": calculate_next_run(automation), "updated_at": completed_at})
            log_external_action("automation_run_failed", "failed", {"automation_id": automation_id, "run_id": run["id"], "error": safe_error(exc)}, None)
            return {"status": "failed", "automation": self.show(automation_id), "run": run, "errors": errors}

    def set_enabled(self, automation_id: str, enabled: bool) -> dict[str, Any]:
        if not get_record("automations", automation_id):
            raise ValueError(f"Automation not found: {automation_id}")
        row = self.show(automation_id)
        return update_record("automations", automation_id, {"enabled": enabled, "next_run_at": calculate_next_run({**row, "enabled": enabled}), "updated_at": utc_now()})

    def history(self, automation_id: str) -> list[dict[str, Any]]:
        return [row for row in list_records("automation_runs") if row.get("automation_id") == automation_id]

    def delete(self, automation_id: str) -> dict[str, Any]:
        return {"deleted": delete_record("automations", automation_id), "id": automation_id}

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        row = {**row}
        row.setdefault("schedule", {})
        row.setdefault("description", "")
        row.setdefault("workspace_name", "default")
        row.setdefault("allowed_outputs", ["local_report"])
        row.setdefault("external_actions_allowed", False)
        row.setdefault("next_run_at", calculate_next_run(row))
        row.setdefault("run_count", 0)
        row.setdefault("failure_count", 0)
        row["schedule_text"] = row.get("schedule_text") or _schedule_text(row.get("trigger_type", "manual"), row.get("schedule") or {})
        return row

    def _write_report(self, automation: dict[str, Any], run_id: str, payload: dict[str, Any]) -> str:
        content = "\n".join([
            "# Automation Run Report",
            "",
            f"- Automation: {automation.get('name')}",
            f"- Run: {run_id}",
            f"- Trigger: {automation.get('trigger_type')}",
            f"- Schedule: {human_readable_schedule(automation)}",
            f"- Agent: {automation.get('agent_slug')}",
            "",
            "## Safety",
            "External sending, publishing, shell commands, and destructive actions are disabled.",
            "",
            "## Output",
            "```json",
            _json_safe(payload),
            "```",
            "",
        ])
        return write_text(outputs_dir("automations") / f"automation-run-{run_id}.md", content)

    def _create_allowed_outputs(self, automation: dict[str, Any], agent_run: dict[str, Any]) -> list[str]:
        approvals: list[str] = []
        allowed = set(automation.get("allowed_outputs") or ["local_report"])
        task = automation.get("task_prompt", "")
        if "social_draft" in allowed or "social draft" in task.lower():
            draft = SocialContentWorkflow().create_draft("linkedin", f"Draft generated by scheduled automation: {task[:180]}", {"automation_id": automation["id"], "agent_run_id": agent_run["id"]})
            approval = ApprovalManager().create("social_publish", draft, draft["platform"])
            approvals.append(approval["id"])
            log_external_action("automation_social_draft_created", "approval_required", {"automation_id": automation["id"], "draft_id": draft["id"]}, draft["platform"], approval["id"])
        if "email_draft" in allowed or "email draft" in task.lower():
            draft = EmailDraftStore().create(EmailDraft(to=[], subject=f"Draft from automation: {automation['name']}", body=f"Review before sending.\n\n{task}", connector_id="scheduler", status="draft_pending_approval"))
            approval = ApprovalManager().create("email_send", {**draft, "send_enabled": False}, "scheduler")
            approvals.append(approval["id"])
            log_external_action("automation_email_draft_created", "approval_required", {"automation_id": automation["id"], "draft_id": draft["id"], "send_enabled": False}, "scheduler", approval["id"])
        return approvals


def inspect_task_safety(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    blocked_terms = ["ignore safety", "send without approval", "publish automatically", "delete files", "run shell command", "expose key"]
    sensitive_terms = ["password", "otp", "api key", "token", "credit card", "aadhaar", "pan", "bank account", "secret", "confidential"]
    warnings = [term for term in blocked_terms if term in lower]
    sensitive = [term for term in sensitive_terms if term in lower]
    return {"blocked": bool(warnings), "warnings": warnings, "sensitive": bool(sensitive)}


def safe_preview(text: str, limit: int = 140) -> str:
    lower = (text or "").lower()
    if any(term in lower for term in ("password", "otp", "api key", "token", "secret")):
        return "[sensitive automation prompt redacted]"
    return text if len(text) <= limit else text[: limit - 1] + "..."


def safe_error(exc: Exception) -> str:
    return safe_preview(str(exc), 240)


def _safe_log(data: dict[str, Any]) -> dict[str, Any]:
    return data


def _schedule_text(trigger_type: str, schedule: dict[str, Any]) -> str:
    return human_readable_schedule({"trigger_type": trigger_type, "schedule": schedule})


def _json_safe(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, sort_keys=True)
