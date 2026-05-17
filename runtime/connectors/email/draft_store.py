from __future__ import annotations

from typing import Any

from runtime.action_log import log_external_action
from runtime.connectors.email.base_email import EmailDraft
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.exports import save_email_draft_markdown


class EmailDraftStore:
    def list(self) -> list[dict[str, Any]]:
        return list_records("email_drafts")

    def create(self, draft: EmailDraft) -> dict[str, Any]:
        return self.create_from_dict(draft.to_dict())

    def create_from_dict(self, draft: dict[str, Any]) -> dict[str, Any]:
        row = insert_record("email_drafts", draft)
        row["output_path"] = save_email_draft_markdown(row)
        row = insert_record("email_drafts", row)
        log_external_action("email_draft_created", row.get("status", "draft"), _safe_log_draft(row), row.get("connector_id"))
        return row

    def approve(self, draft_id: str) -> dict[str, Any]:
        row = get_record("email_drafts", draft_id)
        if not row:
            raise ValueError(f"Email draft not found: {draft_id}")
        row = update_record("email_drafts", draft_id, {"status": "approved"})
        log_external_action("email_draft_approved", "approved", row, row.get("connector_id"))
        return row

    def mark_send_ready(self, draft_id: str, approval_id: str | None) -> dict[str, Any]:
        row = get_record("email_drafts", draft_id)
        if not row:
            raise ValueError(f"Email draft not found: {draft_id}")
        if row.get("status") != "approved" or not approval_id:
            log_external_action("email_send_blocked", "blocked", row, row.get("connector_id"), approval_id)
            return {"status": "blocked", "message": "Email draft must be approved before sending."}
        row = update_record("email_drafts", draft_id, {"status": "send_ready_not_sent"})
        log_external_action("email_send_ready", "not_sent_mvp", row, row.get("connector_id"), approval_id)
        return {"status": "send_ready_not_sent", "message": "MVP stops before external send.", "draft": row}


def _safe_log_draft(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "connector_id": row.get("connector_id"),
        "provider": row.get("provider"),
        "to": row.get("to"),
        "subject": row.get("subject"),
        "status": row.get("status"),
        "body_preview": row.get("body_preview") or (row.get("body", "")[:120] if not any(term in row.get("body", "").lower() for term in ("password", "otp", "secret", "token", "api key")) else "[sensitive redacted]"),
    }
