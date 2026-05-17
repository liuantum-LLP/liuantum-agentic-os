"""Base email connector contracts with draft-first safety."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EmailCapabilities:
    can_read_inbox: bool = True
    can_summarize: bool = True
    can_classify_priority: bool = True
    can_draft_replies: bool = True
    can_create_followups: bool = True
    can_extract_tasks: bool = True
    can_search: bool = True
    can_send: bool = True
    approval_required_for_send: bool = True
    requires_oauth: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class EmailDraft:
    to: list[str]
    subject: str
    body: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    in_reply_to: str | None = None
    connector_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "draft"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EmailConnector:
    provider = "generic_email"
    display_name = "Generic Email"
    api_docs_url: str | None = None
    oauth_docs_url: str | None = None
    required_scopes: tuple[str, ...] = ()
    optional_scopes: tuple[str, ...] = ()
    capabilities = EmailCapabilities()
    warnings: tuple[str, ...] = (
        "MVP is safe mode: email sending requires explicit approval.",
        "Show recipient, subject, and body before sending.",
        "Warn before reply-all, attachments, and sensitive content.",
        "Never store raw OAuth tokens in plain text for production.",
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "capabilities": self.capabilities.to_dict(),
            "required_scopes": list(self.required_scopes),
            "optional_scopes": list(self.optional_scopes),
            "oauth_docs_url": self.oauth_docs_url,
            "api_docs_url": self.api_docs_url,
            "warnings": list(self.warnings),
        }

    def search(self, query: str) -> dict[str, Any]:
        return {"status": "not_configured", "query": query, "results": []}

    def summarize(self, query: str | None = None) -> dict[str, Any]:
        return {
            "status": "draft_summary",
            "summary": "Connect an email provider to summarize real messages.",
            "query": query,
            "priority_emails": [],
        }

    def draft_reply(self, message_id: str, tone: str = "professional") -> EmailDraft:
        return EmailDraft(
            to=[],
            subject="Draft reply",
            body=f"Draft reply for message {message_id} in a {tone} tone. Review before sending.",
            in_reply_to=message_id,
            connector_id=self.provider,
        )

    def send_approved(self, draft: EmailDraft, approval_id: str | None) -> dict[str, Any]:
        if not approval_id:
            return {"status": "blocked", "message": "Email send requires approval for the exact draft."}
        return {"status": "not_configured", "message": "Provider send transport is not configured in MVP."}

