"""Skill execution audit logging for Liuant Agentic OS v2.1.0.

Records skill execution metadata without storing secrets, raw prompts,
file contents, API keys, or tokens.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.storage import WORKSPACE

AUDIT_DIR = WORKSPACE / "skills" / "audit_logs"
SECRET_PATTERNS = [
    r"(?i)(api.?key|secret|token|password)\s*[=:]\s*\S+",
    r"sk-[A-Za-z0-9]{20,}",
    r"Bearer\s+[A-Za-z0-9._\-]+",
]


def _redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def _ensure_dir() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def record_audit(
    skill_id: str,
    command: str,
    status: str,
    duration_ms: int,
    permission_check_result: str,
    approval_required: bool,
    warnings_count: int,
    error_redacted: str = "",
    workspace: str = "default",
    execution_mode: str = "process_isolated",
) -> dict[str, Any]:
    """Record a skill execution audit entry."""
    _ensure_dir()
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": f"audit_{skill_id}_{ts.replace(':', '-').replace('.', '-')}",
        "skill_id": skill_id,
        "command": command,
        "status": status,
        "duration_ms": duration_ms,
        "permission_check_result": permission_check_result,
        "approval_required": approval_required,
        "warnings_count": warnings_count,
        "error_redacted": _redact(error_redacted)[:500],
        "timestamp": ts,
        "workspace": workspace,
        "execution_mode": execution_mode,
    }
    filepath = AUDIT_DIR / f"{entry['id']}.json"
    filepath.write_text(json.dumps(entry, indent=2, sort_keys=True), encoding="utf-8")
    return entry


def get_audit_logs(skill_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Get audit logs, optionally filtered by skill_id."""
    _ensure_dir()
    logs = []
    for f in sorted(AUDIT_DIR.glob("audit_*.json"), reverse=True):
        try:
            entry = json.loads(f.read_text(encoding="utf-8"))
            if skill_id and entry.get("skill_id") != skill_id:
                continue
            logs.append(entry)
            if len(logs) >= limit:
                break
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)


def get_latest_audit(skill_id: str | None = None) -> dict[str, Any] | None:
    """Get the most recent audit log entry."""
    logs = get_audit_logs(skill_id=skill_id, limit=1)
    return logs[0] if logs else None
