from runtime.agents import AgentProfileManager
from runtime.config import (
    ExportTracker,
    OnboardingManager,
    PermissionManager,
    SettingsManager,
    SkillManager,
    WorkspaceManager,
)
from runtime.connectors.manager import ConnectorManager
from runtime.dashboard import build_dashboard
from runtime.exports import export_campaign_markdown
from runtime.models import ModelManager
from runtime.workflows import SocialContentWorkflow


def test_settings_get_set():
    settings = SettingsManager()
    settings.set("debug_mode", "true")
    assert settings.get("debug_mode")["value"] == "true"


def test_model_provider_config_persistence():
    models = ModelManager()
    models.setup({"id": "openrouter", "provider_type": "openrouter", "default_model": "test-model"})
    models.set_default("openrouter")
    assert models.status()["default_provider"] == "openrouter"


def test_permission_mode_persistence():
    manager = PermissionManager()
    manager.set("developer")
    assert manager.status()["mode"] == "developer"


def test_connector_config_persistence():
    connector = ConnectorManager().create("social", "linkedin", "LinkedIn", assigned_agent_slug="content-creator-agent")
    ConnectorManager().set_enabled(connector["id"], True)
    shown = ConnectorManager().show(connector["id"])
    assert shown["assigned_agent_slug"] == "content-creator-agent"
    assert shown["status"] == "enabled"


def test_custom_agent_creation_persistence():
    manager = AgentProfileManager()
    agent = manager.create({"name": "Research Agent", "slug": "research-agent", "instructions": "Research safely."})
    assert manager.show(agent["slug"])["enabled"] is True


def test_skill_install_enable_disable_persistence():
    skills = SkillManager()
    skills.install("content-planning")
    skills.set_enabled("content-planning", False)
    assert skills.list()[0]["enabled"] is False


def test_default_workspace_persistence():
    workspaces = WorkspaceManager()
    workspaces.create("client-a")
    workspaces.set_default("client-a")
    assert workspaces.default()["name"] == "client-a"


def test_export_tracking():
    campaign = SocialContentWorkflow().create_campaign("Tracked", ["linkedin"], "Tracked Course", days=1)
    path = export_campaign_markdown(campaign["id"])
    exports = ExportTracker().list()
    assert any(row["file_path"] == path for row in exports)


def test_system_dashboard_data():
    dashboard = build_dashboard()
    assert dashboard["app"]["version"]
    assert "active_permission_mode" in dashboard
    assert "export_count" in build_dashboard()["exports"] or "count" in dashboard["exports"]


def test_onboarding_state():
    onboarding = OnboardingManager()
    onboarding.reset()
    onboarding.complete_step("welcome")
    assert "welcome" in onboarding.status()["completed_steps_json"]
