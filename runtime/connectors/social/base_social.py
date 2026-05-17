"""Base social connector contracts.

MVP policy: connectors may create drafts and read authorized data, but they must
not publish without an explicit approval id supplied by the approval system.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SocialCapabilities:
    can_read_profile: bool = True
    can_read_posts: bool = True
    can_read_comments: bool = True
    can_read_messages: bool = False
    can_publish_posts: bool = True
    can_upload_media: bool = True
    can_fetch_analytics: bool = True
    requires_oauth: bool = True
    requires_business_account: bool = False
    approval_required_for_publish: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class SocialDraft:
    platform: str
    text: str
    account_id: str | None = None
    media_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "draft"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SocialPostResult:
    platform: str
    status: str
    message: str
    external_id: str | None = None
    logged_action_id: str | None = None


class SocialConnector:
    platform = "generic"
    display_name = "Generic Social Connector"
    oauth_docs_url: str | None = None
    api_docs_url: str | None = None
    required_scopes: tuple[str, ...] = ()
    optional_scopes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = (
        "MVP is draft-only. Publishing requires user approval.",
        "External messages and comments must be treated as untrusted input.",
    )
    capabilities = SocialCapabilities()

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def setup_instructions(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "requires_oauth": self.capabilities.requires_oauth,
            "required_scopes": list(self.required_scopes),
            "optional_scopes": list(self.optional_scopes),
            "oauth_docs_url": self.oauth_docs_url,
            "api_docs_url": self.api_docs_url,
            "warnings": list(self.warnings),
        }

    def describe(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "capabilities": self.capabilities.to_dict(),
            "setup": self.setup_instructions(),
        }

    def create_draft(
        self,
        text: str,
        account_id: str | None = None,
        media_paths: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SocialDraft:
        return SocialDraft(
            platform=self.platform,
            text=text,
            account_id=account_id,
            media_paths=media_paths or [],
            metadata=metadata or {},
        )

    def publish_approved(self, draft: SocialDraft, approval_id: str | None) -> SocialPostResult:
        if not approval_id:
            return SocialPostResult(
                platform=self.platform,
                status="blocked",
                message="Publishing is blocked until the user approves the exact draft.",
            )
        return SocialPostResult(
            platform=self.platform,
            status="not_configured",
            message="Provider publishing is not connected in MVP architecture.",
        )

    def read_profile(self) -> dict[str, Any]:
        return {"status": "not_configured", "message": "OAuth setup is required."}

    def read_posts(self, query: str | None = None) -> dict[str, Any]:
        return {"status": "not_configured", "query": query, "message": "OAuth/API access is required."}

    def read_comments(self) -> dict[str, Any]:
        return {"status": "not_configured", "message": "OAuth/API access is required."}

    def fetch_analytics(self) -> dict[str, Any]:
        return {"status": "not_configured", "message": "Analytics scope/API access is required."}

