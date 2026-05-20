"""Workflow audit logs for Liuant Agentic OS v2.5.0.

Records workflow run metadata without secrets, raw prompts, file contents,
API keys, or tokens.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.storage import WORKSPACE, read_json, write_json

AUDIT_DIR = WORKSPACE / "skills" / "workflow_audit"
AUDIT_RUNS_FILE = AUDIT_DIR / "workflow_runs.json"
AUDIT_STEPS_FILE = AUDIT_DIR / "workflow_steps.json"

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9]{16,}",
    r"(?i)(secret|token|password|passwd)\s*[:=]\s*['\"]?[^\s'\"]{8,}",
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{36}",
]


def _redact_secrets(value: str) -> str:
    """Redact secret-like patterns from a string."""
    result = value
    for pattern in SECRET_PATTERNS:
        result = re.sub(pattern, "[REDACTED]", result)
    return result


def _redact_value(value: Any) -> Any:
    """Recursively redact secrets from a value."""
    if isinstance(value, str):
        return _redact_secrets(value)
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _ensure_audit_dir() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _load_runs() -> dict[str, Any]:
    _ensure_audit_dir()
    if AUDIT_RUNS_FILE.exists():
        return read_json(AUDIT_RUNS_FILE, {"runs": {}})
    return {"runs": {}}


def _save_runs(data: dict[str, Any]) -> None:
    _ensure_audit_dir()
    write_json(AUDIT_RUNS_FILE, data)


def _load_steps() -> dict[str, Any]:
    _ensure_audit_dir()
    if AUDIT_STEPS_FILE.exists():
        return read_json(AUDIT_STEPS_FILE, {"steps": {}})
    return {"steps": {}}


def _save_steps(data: dict[str, Any]) -> None:
    _ensure_audit_dir()
    write_json(AUDIT_STEPS_FILE, data)


def record_workflow_run_start(
    workflow_id: str,
    workspace: str = "default",
    dry_run: bool = False,
    user_confirmed: bool = False,
    step_count: int = 0,
) -> str:
    """Record the start of a workflow run. Returns run_id."""
    run_id = str(uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    runs = _load_runs()
    runs["runs"][run_id] = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "workspace": workspace,
        "status": "running",
        "started_at": now,
        "completed_at": None,
        "duration_ms": None,
        "step_count": step_count,
        "completed_steps": 0,
        "failed_step_id": None,
        "approval_required": False,
        "warnings_count": 0,
        "error_redacted": None,
        "external_actions_count": 0,
        "dry_run": dry_run,
        "user_confirmed": user_confirmed,
    }
    _save_runs(runs)
    return run_id


def record_workflow_run_complete(
    run_id: str,
    status: str,
    completed_steps: int = 0,
    failed_step_id: str | None = None,
    approval_required: bool = False,
    warnings_count: int = 0,
    error_redacted: str | None = None,
    external_actions_count: int = 0,
) -> None:
    """Record the completion of a workflow run."""
    runs = _load_runs()
    run_data = runs["runs"].get(run_id)
    if not run_data:
        return

    now = datetime.now(timezone.utc)
    started = datetime.fromisoformat(run_data["started_at"])
    duration_ms = int((now - started).total_seconds() * 1000)

    run_data["status"] = status
    run_data["completed_at"] = now.isoformat()
    run_data["duration_ms"] = duration_ms
    run_data["completed_steps"] = completed_steps
    run_data["failed_step_id"] = failed_step_id
    run_data["approval_required"] = approval_required
    run_data["warnings_count"] = warnings_count
    run_data["error_redacted"] = _redact_secrets(error_redacted) if error_redacted else None
    run_data["external_actions_count"] = external_actions_count
    _save_runs(runs)


def record_workflow_step(
    run_id: str,
    step_id: str,
    skill_id: str,
    command: str,
    status: str,
    duration_ms: int = 0,
    output_key: str = "",
    warnings_count: int = 0,
    error_redacted: str | None = None,
) -> None:
    """Record a workflow step execution."""
    steps = _load_steps()
    step_record = {
        "run_id": run_id,
        "step_id": step_id,
        "skill_id": skill_id,
        "command": command,
        "status": status,
        "duration_ms": duration_ms,
        "output_key": output_key,
        "warnings_count": warnings_count,
        "error_redacted": _redact_secrets(error_redacted) if error_redacted else None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    step_key = f"{run_id}:{step_id}"
    steps["steps"][step_key] = step_record
    _save_steps(steps)


def get_workflow_audit(workflow_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Get workflow audit logs, optionally filtered by workflow_id."""
    runs = _load_runs()
    all_runs = list(runs["runs"].values())

    if workflow_id:
        all_runs = [r for r in all_runs if r.get("workflow_id") == workflow_id]

    all_runs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return all_runs[:limit]


def get_latest_workflow_run(workflow_id: str) -> dict[str, Any] | None:
    """Get the latest run for a workflow."""
    runs = get_workflow_audit(workflow_id=workflow_id, limit=1)
    return runs[0] if runs else None


def get_workflow_steps(run_id: str) -> list[dict[str, Any]]:
    """Get all steps for a workflow run."""
    steps = _load_steps()
    run_steps = [s for s in steps["steps"].values() if s.get("run_id") == run_id]
    return sorted(run_steps, key=lambda x: x.get("recorded_at", ""))


def list_workflow_runs(workflow_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List workflow runs with summary data."""
    return get_workflow_audit(workflow_id=workflow_id, limit=limit)


def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    """Get a specific workflow run."""
    runs = _load_runs()
    return runs["runs"].get(run_id)


def export_workflow_run(run_id: str, format: str = "json") -> str:
    """Export a workflow run as JSON or markdown."""
    run_data = get_workflow_run(run_id)
    if not run_data:
        return f"Run '{run_id}' not found"

    steps = get_workflow_steps(run_id)

    if format == "json":
        return json.dumps({"run": run_data, "steps": steps}, indent=2)

    lines = [f"# Workflow Run: {run_id}\n"]
    lines.append(f"- **Workflow:** {run_data.get('workflow_id', '')}")
    lines.append(f"- **Status:** {run_data.get('status', '')}")
    lines.append(f"- **Started:** {run_data.get('started_at', '')}")
    lines.append(f"- **Completed:** {run_data.get('completed_at', '')}")
    lines.append(f"- **Duration:** {run_data.get('duration_ms', 0)}ms")
    lines.append(f"- **Steps:** {run_data.get('completed_steps', 0)}/{run_data.get('step_count', 0)}")
    if run_data.get("failed_step_id"):
        lines.append(f"- **Failed Step:** {run_data['failed_step_id']}")
    lines.append("")
    lines.append("## Steps\n")
    for step in steps:
        lines.append(f"- {step.get('step_id', '')}: {step.get('skill_id', '')}/{step.get('command', '')} — {step.get('status', '')}")
    return "\n".join(lines)
