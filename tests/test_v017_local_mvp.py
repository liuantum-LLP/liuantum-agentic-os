from pathlib import Path

from runtime.agents import AgentRunner, list_agents
from runtime.config import SkillManager


def test_requested_builtin_agents_exist_and_run():
    expected = {
        "marketing-agent",
        "personal-assistant-agent",
        "front-desk-management-agent",
        "coding-agent",
        "business-analyst-agent",
        "sales-agent",
        "hr-agent",
        "customer-support-agent",
        "tutor-agent",
    }
    agents = {agent["slug"]: agent for agent in list_agents()}

    assert expected.issubset(set(agents))
    for slug in expected:
        run = AgentRunner().run(slug, "Create useful local output")
        assert run["status"] == "completed"
        assert run["result"]["summary"]
        assert Path(run["output_path"]).exists()


def test_requested_skills_are_available_and_manageable():
    expected = {
        "create-flask-app",
        "analyze-github-repo",
        "create-course-plan",
        "debug-flutter-app",
        "generate-business-proposal",
        "create-marketing-campaign",
        "manage-front-desk",
        "create-social-media-calendar",
    }
    manager = SkillManager()
    available = {skill["skill_name"]: skill for skill in manager.available_skills()}

    assert expected.issubset(set(available))
    installed = manager.install("create-flask-app")
    disabled = manager.set_enabled("create-flask-app", False)
    enabled = manager.set_enabled("create-flask-app", True)

    assert installed["description"]
    assert disabled["enabled"] is False
    assert enabled["enabled"] is True
