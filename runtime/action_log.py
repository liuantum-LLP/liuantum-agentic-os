from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.db import insert_record, list_records


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExternalActionLog:
    action_type: str
    status: str
    connector_id: str | None
    preview: dict[str, Any]
    approval_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def log_external_action(
    action_type: str,
    status: str,
    preview: dict[str, Any],
    connector_id: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    entry = ExternalActionLog(
        action_type=action_type,
        status=status,
        connector_id=connector_id,
        preview=preview,
        approval_id=approval_id,
    )
    return insert_record("action_logs", entry.to_dict())


def list_external_actions() -> list[dict[str, Any]]:
    return list_records("action_logs")
