from runtime.agents import AgentRunner, list_agents
from runtime.approvals import ApprovalManager
from runtime.automation import AutomationManager
from runtime.connectors.manager import ConnectorManager
from runtime.dashboard import build_status
from runtime.exports import (
    export_agent_run_markdown,
    export_campaign_markdown,
    export_content_calendar_csv,
    export_image_prompt_markdown,
    export_video_storyboard_markdown,
)
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.workflows import SocialContentWorkflow


def test_creating_campaign_saves_campaign_drafts_and_approvals():
    workflow = SocialContentWorkflow()
    campaign = workflow.create_campaign(
        campaign_name="Python Course",
        platforms=["linkedin", "x"],
        project="Python course",
        days=2,
    )

    assert campaign["id"]
    assert len(workflow.list_campaigns()) == 1
    assert len(workflow.list_drafts()) == 4
    assert len(ApprovalManager().list()) == 4
    assert all("output_path" in draft for draft in workflow.list_drafts())


def test_generating_social_draft_and_approving_it():
    workflow = SocialContentWorkflow()
    draft = workflow.create_draft("linkedin", "Draft post")
    approved = workflow.approve_draft(draft["id"])

    assert approved["status"] == "approved"


def test_approval_creation_and_decision():
    approval = ApprovalManager().create("social_publish", {"text": "Preview"}, "linkedin")
    decided = ApprovalManager().decide(approval["id"], "approved")

    assert decided["status"] == "approved"
    assert decided["decided_at"]


def test_creating_image_job_without_provider_key():
    job = ImageGenerationManager().generate("poster for AI course")

    assert job["prompt"] == "poster for AI course"
    assert job["status"] == "needs_provider_setup"
    assert ImageGenerationManager().get_job(job["id"])["id"] == job["id"]
    assert job["output_path"].endswith(".md")


def test_creating_video_storyboard_saves_job():
    job = VideoGenerationManager().storyboard("promo video for Liuant Agentic OS")

    assert job["status"] == "storyboard_ready"
    assert "video_concept" in job["metadata"]
    assert VideoGenerationManager().get_job(job["id"])["id"] == job["id"]
    assert job["output_path"].endswith(".md")


def test_creating_connector():
    connector = ConnectorManager().create("social", "linkedin", "LinkedIn")

    assert connector["provider"] == "linkedin"
    assert ConnectorManager().test(connector["id"])["result"]


def test_listing_builtin_agents():
    agents = list_agents()

    assert any(agent["slug"] == "content-creator-agent" for agent in agents)


def test_running_content_creator_agent():
    run = AgentRunner().run("content-creator-agent", "Create 5 LinkedIn posts for Liuant Agentic OS")

    assert run["status"] == "completed"
    assert run["agent_slug"] == "content-creator-agent"
    assert run["result"]["draft_count"] == 5
    assert run["output_path"].endswith(".md")


def test_running_automation_manually():
    manager = AutomationManager()
    automation = manager.create(
        {
            "name": "Monday content calendar",
            "agent_slug": "content-creator-agent",
            "trigger_type": "manual",
            "schedule_text": "manual",
            "task_prompt": "Create a content calendar",
        }
    )
    result = manager.run(automation["id"])

    assert result["status"] == "manual_run_recorded"
    assert result["automation"]["last_run_at"]


def test_dashboard_status():
    status = build_status()

    assert status["status"] == "ok"
    assert "pending_approvals" in status


def test_export_files():
    workflow = SocialContentWorkflow()
    campaign = workflow.create_campaign("Export Campaign", ["linkedin"], "Export course", days=1)
    image_job = ImageGenerationManager().generate("image prompt")
    video_job = VideoGenerationManager().storyboard("video prompt")
    run = AgentRunner().run("content-creator-agent", "Create 1 LinkedIn post for Export Agent")

    paths = [
        export_campaign_markdown(campaign["id"]),
        export_content_calendar_csv(campaign["id"]),
        export_image_prompt_markdown(image_job["id"]),
        export_video_storyboard_markdown(video_job["id"]),
        export_agent_run_markdown(run["id"]),
    ]

    for path in paths:
        assert path
        assert __import__("pathlib").Path(path).exists()
