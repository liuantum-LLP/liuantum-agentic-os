from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.db import get_record, insert_record, list_records, update_record


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ApprovalRequest:
    action_type: str
    preview: dict[str, Any]
    connector_id: str | None = None
    requires_exact_preview: bool = True
    id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    created_at: str = field(default_factory=utc_now)
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApprovalManager:
    def list(self) -> list[dict[str, Any]]:
        return list_records("approvals")

    def create(self, action_type: str, preview: dict[str, Any], connector_id: str | None = None) -> dict[str, Any]:
        approval = ApprovalRequest(action_type=action_type, preview=preview, connector_id=connector_id)
        return insert_record("approvals", approval.to_dict())

    def decide(self, approval_id: str, status: str) -> dict[str, Any]:
        approval = get_record("approvals", approval_id)
        if not approval:
            raise ValueError(f"Approval not found: {approval_id}")
        approval = update_record("approvals", approval_id, {"status": status, "decided_at": utc_now()})
        log_external_action(
            f"approval_{status}",
            status,
            approval["preview"],
            approval.get("connector_id"),
            approval["id"],
        )
        return approval
