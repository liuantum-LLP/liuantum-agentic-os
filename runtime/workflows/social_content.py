from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.connectors.social.registry import get_social_connector
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.exports import save_social_draft_markdown


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SocialContentPlan:
    campaign_name: str
    platforms_json: list[str]
    content_items_json: list[dict[str, Any]]
    workspace_name: str
    status: str = "draft"
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SocialContentWorkflow:
    def create_campaign(
        self,
        campaign_name: str,
        platforms: list[str],
        project: str = "Liuant campaign",
        goal: str = "Generate qualified leads",
        audience: str = "Learners and business owners interested in practical AI skills",
        days: int = 7,
        agent_slug: str = "content-creator-agent",
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for day in range(1, days + 1):
            for platform in platforms:
                items.append(
                    {
                        "day": day,
                        "platform": platform,
                        "goal": goal,
                        "audience": audience,
                        "post_text": (
                            f"Day {day}: {project} helps {audience} move from interest to action. "
                            "Learn with practical tasks, guided projects, and clear outcomes."
                        ),
                        "image_prompt": f"Promotional visual for {project}, platform {platform}, day {day}, modern learning brand",
                        "video_script": f"Hook: Want a practical path into {project}? Show one result, one task, one CTA.",
                        "status": "draft",
                        "campaign_name": campaign_name,
                        "agent_slug": agent_slug,
                    }
                )
        plan = SocialContentPlan(
            campaign_name=campaign_name,
            platforms_json=platforms,
            content_items_json=items,
            workspace_name=project,
        )
        plan_row = insert_record("social_campaigns", plan.to_dict())
        from runtime.approvals import ApprovalManager

        approval_manager = ApprovalManager()
        for item in items:
            draft = self.create_draft(
                platform=item["platform"],
                text=item["post_text"],
                metadata={**item, "campaign_id": plan.id, "campaign_name": campaign_name, "agent_slug": agent_slug},
            )
            approval = approval_manager.create("social_publish", draft, item["platform"])
            update_record("social_drafts", draft["id"], {"approval_id": approval["id"], "updated_at": utc_now()})
        return plan_row

    def list_campaigns(self) -> list[dict[str, Any]]:
        return list_records("social_campaigns")

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        return get_record("social_campaigns", campaign_id)

    def create_draft(self, platform: str, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        connector = get_social_connector(platform)
        draft = connector.create_draft(text=text, metadata=metadata or {})
        row = insert_record("social_drafts", draft.to_dict())
        row = update_record(
            "social_drafts",
            row["id"],
            {
                "connector_id": None,
                "publish_status": "draft",
                "publish_attempted_at": None,
                "published_at": None,
                "external_post_id": "",
                "external_url": "",
                "publish_error": "",
                "approval_id": None,
                "updated_at": utc_now(),
            },
        )
        row["output_path"] = save_social_draft_markdown(row)
        row = insert_record("social_drafts", row)
        log_external_action("social_draft_created", "draft", row, platform)
        return row

    def list_drafts(self) -> list[dict[str, Any]]:
        return list_records("social_drafts")

    def approve_draft(self, draft_id: str) -> dict[str, Any]:
        draft = get_record("social_drafts", draft_id)
        if not draft:
            raise ValueError(f"Draft not found: {draft_id}")
        approval_id = draft.get("approval_id")
        from runtime.approvals import ApprovalManager

        for approval in ApprovalManager().list():
            if approval.get("action_type") == "social_publish" and (approval.get("preview") or {}).get("id") == draft_id:
                approval_id = approval["id"]
                if approval.get("status") == "pending":
                    ApprovalManager().decide(approval["id"], "approved")
                break
        return update_record("social_drafts", draft_id, {"status": "approved", "publish_status": "approved", "approval_id": approval_id, "approved_at": utc_now(), "updated_at": utc_now()})

    def publish_draft(self, draft_id: str) -> dict[str, Any]:
        draft = get_record("social_drafts", draft_id)
        if not draft:
            raise ValueError(f"Draft not found: {draft_id}")
        if draft.get("status") != "approved":
            log_external_action("social_publish_blocked", "blocked", draft, draft["platform"])
            return {"status": "blocked", "message": "Draft must be approved before publish."}
        draft = update_record("social_drafts", draft_id, {"status": "publish_ready_not_sent"})
        log_external_action("social_publish_ready", "not_sent_mvp", draft, draft["platform"])
        return {"status": "publish_ready_not_sent", "message": "MVP stops before external posting.", "draft": draft}

    def publish_approved_draft(self, draft_id: str, connector_id: str | None = None, confirm_sensitive: bool = False) -> dict[str, Any]:
        draft = get_record("social_drafts", draft_id)
        if not draft:
            raise ValueError(f"Draft not found: {draft_id}")
        connector = get_social_connector((draft.get("platform") or "").lower())
        if connector_id and connector_id != connector.platform:
            return {"status": "publish_blocked", "message": f"Connector {connector_id} does not match draft platform {draft.get('platform')}.", "published": False}
        return connector.publish_approved_draft(draft_id, confirm_sensitive=confirm_sensitive)

    def publish_approved_bulk(self, draft_ids: list[str], connector_id: str | None = None) -> dict[str, Any]:
        if len(draft_ids) > 5:
            log_external_action("social_bulk_publish_blocked", "blocked", {"draft_count": len(draft_ids), "reason": "Bulk publish limit is 5 drafts."}, connector_id)
            return {"status": "bulk_publish_blocked", "message": "Bulk publish is limited to 5 drafts at once.", "draft_count": len(draft_ids), "published": False}
        return {"status": "completed", "results": [self.publish_approved_draft(draft_id, connector_id) for draft_id in draft_ids]}

    def enable_connector_publish(self, connector_id: str) -> dict[str, Any]:
        return get_social_connector(connector_id).enable_manual_publish()

    def disable_connector_publish(self, connector_id: str) -> dict[str, Any]:
        return get_social_connector(connector_id).disable_manual_publish()
