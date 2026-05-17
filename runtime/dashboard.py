from __future__ import annotations

from typing import Any

from runtime.agents import list_agents
from runtime.approvals import ApprovalManager
from runtime.automation import AutomationManager
from runtime.connectors.manager import ConnectorManager
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.models import ModelManager
from runtime.workflows import SocialContentWorkflow
from runtime.config import ExportTracker, OnboardingManager, PermissionManager, SettingsManager, WorkspaceManager
from runtime.db import health


def build_dashboard() -> dict[str, Any]:
    approvals = ApprovalManager().list()
    campaigns = SocialContentWorkflow().list_campaigns()
    social_drafts = SocialContentWorkflow().list_drafts()
    image_jobs = ImageGenerationManager().list_jobs()
    video_jobs = VideoGenerationManager().list_jobs()
    automations = AutomationManager().list()
    models = ModelManager().status()
    connectors = ConnectorManager().list()
    settings = {row["key"]: row["value"] for row in SettingsManager().list()}
    workspace = WorkspaceManager().default()
    permissions = PermissionManager().status()
    exports = ExportTracker().list()
    onboarding = OnboardingManager().status()
    agents = list_agents()
    return {
        "mode": "draft_only",
        "app": {"name": settings["app_name"], "version": settings["app_version"], "environment": settings["app_environment"]},
        "database": health(),
        "active_workspace": workspace,
        "active_permission_mode": permissions["mode"],
        "agents": {"count": len(agents), "custom_count": sum(1 for row in agents if not row.get("is_builtin")), "items": agents},
        "campaigns": {"count": len(campaigns), "latest": campaigns[:5]},
        "social_drafts": {"count": len(social_drafts), "pending": sum(1 for row in social_drafts if row.get("status") == "draft")},
        "approvals": {
            "count": len(approvals),
            "pending": sum(1 for row in approvals if row.get("status") == "pending"),
            "approved": sum(1 for row in approvals if row.get("status") == "approved"),
            "rejected": sum(1 for row in approvals if row.get("status") == "rejected"),
        },
        "jobs": {
            "image": {"count": len(image_jobs), "latest": image_jobs[:3]},
            "video": {"count": len(video_jobs), "latest": video_jobs[:3]},
        },
        "automations": {
            "count": len(automations),
            "enabled": sum(1 for row in automations if row.get("enabled")),
            "latest": automations[:5],
        },
        "connectors": {"configured_count": len(connectors), "enabled_count": sum(1 for row in connectors if row.get("enabled")), "configured": connectors},
        "providers": models,
        "exports": {"count": len(exports), "recent": exports[:10]},
        "onboarding": onboarding,
        "recent_errors": [row for row in list_external_errors()][:5],
    }


def build_status() -> dict[str, Any]:
    dashboard = build_dashboard()
    return {
        "status": "ok",
        "mode": dashboard["mode"],
        "agents": dashboard["agents"]["count"],
        "campaigns": dashboard["campaigns"]["count"],
        "pending_approvals": dashboard["approvals"]["pending"],
        "image_jobs": dashboard["jobs"]["image"]["count"],
        "video_jobs": dashboard["jobs"]["video"]["count"],
        "automations": dashboard["automations"]["count"],
        "configured_providers": dashboard["providers"]["configured_count"],
        "app_version": dashboard["app"]["version"],
        "active_workspace": dashboard["active_workspace"]["name"],
        "active_permission_mode": dashboard["active_permission_mode"],
        "custom_agents": dashboard["agents"]["custom_count"],
        "connector_count": dashboard["connectors"]["configured_count"],
        "enabled_connector_count": dashboard["connectors"]["enabled_count"],
        "export_count": dashboard["exports"]["count"],
        "database_status": "ok" if dashboard["database"]["database_exists"] else "missing",
    }


def list_external_errors() -> list[dict]:
    from runtime.action_log import list_external_actions

    return [row for row in list_external_actions() if row.get("status") == "error"]
