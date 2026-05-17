from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.agents.profiles import AgentProfileManager
from runtime.action_log import log_external_action
from runtime.config import SettingsManager
from runtime.content_creator import ContentCreator
from runtime.db import insert_record, list_records
from runtime.exports import export_agent_run_markdown
from runtime.providers import ModelHub
from runtime.workflows.social_content import SocialContentWorkflow


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentRun:
    agent_slug: str
    prompt: str
    status: str
    result: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentRunner:
    def list_runs(self) -> list[dict[str, Any]]:
        return list_records("agent_runs")

    def run(
        self,
        agent_slug: str,
        prompt: str,
        ai_enhancement: bool | None = None,
        provider_name: str | None = None,
        model: str | None = None,
        rag_enabled: bool | None = None,
        workspace_name: str | None = None,
        rag_query: str | None = None,
        rag_limit: int | None = None,
    ) -> dict[str, Any]:
        agent = AgentProfileManager().show(agent_slug)
        if not agent.get("enabled", True):
            raise ValueError(f"Agent is disabled: {agent_slug}")
        if agent_slug == "content-creator-agent":
            result = self._run_content_creator(prompt)
        else:
            result = self._run_local_agent(agent_slug, prompt)
        result["provider_routing"] = self._resolve_provider_routing(agent)
        if self._should_use_rag(rag_enabled):
            result = self._attach_rag_context(result, rag_query or prompt, workspace_name, rag_limit)
        if self._should_enhance(ai_enhancement):
            result = self._enhance_with_ai(agent, prompt, result, provider_name, model)
        run = AgentRun(agent_slug=agent_slug, prompt=prompt, status="completed", result=result)
        row = insert_record("agent_runs", run.to_dict())
        row["output_path"] = export_agent_run_markdown(row["id"])
        return insert_record("agent_runs", row)

    def _run_content_creator(self, prompt: str) -> dict[str, Any]:
        topic = _extract_topic(prompt)
        days = _extract_days(prompt) or 7
        platforms = _extract_platforms(prompt)
        content_package = ContentCreator().create_package(topic=topic, platforms=platforms)
        campaign = SocialContentWorkflow().create_campaign(
            campaign_name=f"{topic} Campaign",
            platforms=platforms,
            project=topic,
            days=days,
        )
        return {
            "content_package": content_package,
            "campaign": campaign,
            "draft_count": len(platforms) * days,
            "approval_required": True,
        }

    def _run_local_agent(self, agent_slug: str, prompt: str) -> dict[str, Any]:
        topic = prompt.strip().strip('"') or "local task"
        builders = {
            "marketing-agent": lambda: {
                "campaign_plan": [f"Position {topic} around a clear outcome.", "Use proof-led posts for LinkedIn and short WhatsApp follow-ups.", "End every asset with one direct CTA."],
                "captions": [f"{topic}: learn the workflow, build the project, show the result.", f"Stop collecting tutorials. Start shipping {topic} with a guided plan."],
                "whatsapp_promo_message": f"Hi! We are opening practical sessions for {topic}. You will learn through guided tasks and a real project. Reply YES for details.",
                "ad_copy": {"headline": f"Master {topic}", "primary_text": "Practical training, clear outcomes, and project-first learning.", "cta": "Apply now"},
            },
            "personal-assistant-agent": lambda: {
                "daily_plan": ["Review top priorities", f"Block focused time for: {topic}", "Handle follow-ups", "End with a short review"],
                "task_list": [f"Clarify outcome for {topic}", "Break work into 3 actions", "Schedule reminders", "Prepare tomorrow's next step"],
                "reminder_style_plan": ["Morning: choose top task", "Afternoon: check progress", "Evening: summarize and reset"],
            },
            "front-desk-management-agent": lambda: {
                "enquiry_reply": f"Thank you for your interest in {topic}. We can help with course details, duration, fees, demo timing, and admission steps.",
                "call_script": ["Greet and confirm interest", "Ask background and goal", "Explain course outcome", "Offer demo/admission next step"],
                "admission_follow_up": f"Hi, following up on your {topic} enquiry. Would you like the next batch details and demo slot?",
            },
            "coding-agent": lambda: {
                "project_plan": [f"Define MVP scope for {topic}", "Create data model", "Build routes/services", "Add tests", "Document run steps"],
                "file_structure": ["app.py", "models.py", "routes.py", "templates/", "static/", "tests/test_app.py", "README.md"],
                "implementation_steps": ["Create virtual environment", "Install framework dependency after approval", "Build CRUD endpoints", "Add validation", "Run tests"],
                "safe_command_suggestions": ["python -m venv .venv", "python -m pytest", "python app.py"],
            },
            "business-analyst-agent": lambda: {
                "brd_outline": ["Business objective", "Stakeholders", "Current process", "Pain points", "Success metrics"],
                "frd_outline": ["Functional modules", "Inputs/outputs", "Validation rules", "Reports", "Permissions"],
                "user_stories": [f"As a user, I want to manage {topic} so that work is trackable.", "As an admin, I want approvals before external actions."],
                "workflow_steps": ["Capture request", "Validate data", "Generate draft", "Review", "Approve", "Export"],
            },
            "sales-agent": lambda: {
                "sales_script": [f"Open with the outcome of {topic}", "Ask about current challenge", "Map feature to benefit", "Confirm next step"],
                "follow_up_message": f"Thanks for discussing {topic}. Based on your goal, the next best step is a short demo and plan review.",
                "objection_handling": {"price": "Anchor to project outcome and support.", "time": "Offer a focused starting plan.", "trust": "Share proof, syllabus, and sample output."},
            },
            "hr-agent": lambda: {
                "job_description": f"Role for {topic}: own delivery, communication, quality, and measurable outcomes.",
                "interview_questions": ["Describe a relevant project.", "How do you handle deadlines?", "How would you explain a complex topic simply?"],
                "onboarding_checklist": ["Offer letter", "Tools access", "Role briefing", "First-week goals", "Review meeting"],
            },
            "customer-support-agent": lambda: {
                "faq": [f"What is the status of {topic}?", "How do I get help?", "What information should I share?"],
                "support_reply": f"Thanks for reaching out about {topic}. I will help you troubleshoot step by step and keep the action safe.",
                "troubleshooting_script": ["Confirm issue", "Collect context", "Check common causes", "Offer next action", "Escalate if unresolved"],
            },
            "tutor-agent": lambda: {
                "lesson_plan": [f"Introduce {topic}", "Show example", "Guided practice", "Independent task", "Review"],
                "quiz": ["What is the core concept?", "Which step comes first?", "How would you debug a simple issue?"],
                "assignment": f"Create a small project that demonstrates {topic} with notes and screenshots.",
                "project_idea": f"Build a beginner-friendly demo project for {topic}.",
            },
            "social-media-manager-agent": lambda: {
                "content_calendar": [f"Day 1 hook for {topic}", f"Day 2 proof for {topic}", f"Day 3 CTA for {topic}"],
                "draft_posts": [f"{topic} can become a clear campaign when every post has one job."],
                "analysis_plan": ["Track replies", "Track saves/clicks", "Review approved drafts only"],
            },
            "email-assistant-agent": lambda: {
                "inbox_plan": ["Classify urgent items", "Extract tasks", "Draft replies for review"],
                "draft_reply": f"Thank you for your message about {topic}. I will review and respond with the next steps.",
                "follow_up_tasks": ["Confirm recipient", "Check attachments", "Ask before sending"],
            },
            "automation-builder-agent": lambda: {
                "automation_definition": {"trigger_type": "manual", "task_prompt": topic, "requires_approval": True},
                "safety_notes": ["External actions remain draft-only", "Manual run is supported in MVP"],
            },
            "brand-strategist-agent": lambda: {
                "positioning": f"Position {topic} as practical, trustworthy, and outcome-led.",
                "voice": "Clear, confident, useful, and honest.",
                "campaign_direction": ["Outcome first", "Proof second", "CTA third"],
            },
            "video-creator-agent": lambda: {
                "script": f"Open with the problem, show how {topic} helps, close with one CTA.",
                "scene_plan": ["Hook", "Problem", "Workflow", "Proof", "CTA"],
                "prompts": [f"Vertical video keyframe for {topic}, premium product style"],
            },
            "image-creator-agent": lambda: {
                "poster_copy": {"headline": topic.title(), "subheadline": "Practical, clear, and ready to act.", "cta": "Start now"},
                "image_prompts": [f"Premium poster for {topic}, clean layout, readable text space"],
                "thumbnail_plan": "High contrast subject, short headline, proof badge.",
            },
        }
        output = builders.get(agent_slug, lambda: {"plan": [f"Clarify task: {topic}", "Draft local plan", "Ask for approval before external action"]})()
        return {
            "summary": f"{agent_slug} created a local MVP output package.",
            "prompt": prompt,
            "safe_mode": "draft_only",
            "approval_required_for_external_actions": True,
            **output,
        }

    def _resolve_provider_routing(self, agent: dict[str, Any]) -> dict[str, Any]:
        preferences = agent.get("provider_preferences") or agent.get("provider_preferences_json") or {}
        hub = ModelHub()
        text_provider = hub.resolve_provider_for_task("text", preferences.get("text_provider"))
        image_provider = hub.resolve_provider_for_task("image", preferences.get("image_provider"))
        video_provider = hub.resolve_provider_for_task("video", preferences.get("video_provider"))
        return {
            "text_provider": text_provider["id"],
            "text_model": preferences.get("text_model") or text_provider.get("default_model"),
            "image_provider": image_provider["id"],
            "video_provider": video_provider["id"],
            "source": "agent_preferences" if preferences else "global_defaults",
            "note": "Local MVP output used provider routing metadata; no fake model completion was performed.",
        }

    def _should_enhance(self, explicit: bool | None) -> bool:
        if explicit is not None:
            return explicit
        try:
            return SettingsManager().get("agent_ai_enhancement_enabled")["value"].lower() in {"1", "true", "yes", "on"}
        except ValueError:
            return False

    def _should_use_rag(self, explicit: bool | None) -> bool:
        if explicit is not None:
            return explicit
        try:
            return SettingsManager().get("rag_enabled")["value"].lower() in {"1", "true", "yes", "on"}
        except ValueError:
            return False

    def _attach_rag_context(self, local_output: dict[str, Any], query: str, workspace_name: str | None, limit: int | None) -> dict[str, Any]:
        try:
            from runtime.knowledge import KnowledgeBase
            from runtime.memory import MemoryManager

            rag_limit = limit or int(SettingsManager().get("rag_default_limit")["value"])
            knowledge = KnowledgeBase().search(query, workspace_name=workspace_name, limit=rag_limit)
            memories = MemoryManager().search(query, workspace_name=workspace_name, limit=rag_limit)
            context = {
                "knowledge": [{"source_id": row.get("source_id"), "title": row.get("title"), "score": row.get("score"), "content_preview": row.get("content_preview")} for row in knowledge.get("results", [])],
                "memories": [{"id": row.get("id"), "title": row.get("title"), "memory_type": row.get("memory_type"), "score": row.get("score"), "content_preview": row.get("content_preview")} for row in memories.get("results", [])],
            }
            log_external_action("rag_context_used", "completed", {"query_preview": query[:120], "knowledge_count": len(context["knowledge"]), "memory_count": len(context["memories"])})
            return {**local_output, "retrieved_context": context, "rag_enabled": True}
        except Exception as exc:
            log_external_action("rag_context_failed", "failed", {"query_preview": query[:120], "error": str(exc)[:200]})
            return {**local_output, "retrieved_context": {"error": str(exc)[:200], "knowledge": [], "memories": []}, "rag_enabled": True}

    def _enhance_with_ai(
        self,
        agent: dict[str, Any],
        prompt: str,
        local_output: dict[str, Any],
        provider_name: str | None,
        model: str | None,
    ) -> dict[str, Any]:
        preferences = agent.get("provider_preferences") or agent.get("provider_preferences_json") or {}
        provider_name = provider_name or preferences.get("text_provider")
        model = model or preferences.get("text_model")
        hub = ModelHub()
        log_external_action(
            "agent_ai_enhancement_started",
            "started",
            {"agent_slug": agent["slug"], "provider": provider_name or "default", "model": model or "default", "prompt_summary": prompt[:120]},
        )
        enhancement_prompt = (
            "Refine the following deterministic local agent output while preserving safety, structure, and draft-only behavior.\n\n"
            f"User task: {prompt}\n\nLocal output:\n{local_output}"
        )
        ai_result = hub.generate_text(
            prompt=enhancement_prompt,
            system_prompt="You enhance Liuant Agentic OS local draft outputs. Keep the result concise, useful, and approval-aware.",
            provider_name=provider_name,
            model=model,
            metadata={"agent_slug": agent["slug"], "feature": "agent_ai_enhancement"},
        )
        enhanced = {
            **local_output,
            "local_output": dict(local_output),
            "ai_enhancement": {
                "enabled": True,
                "status": ai_result["status"],
                "provider": ai_result["provider"],
                "model": ai_result["model"],
                "fallback_used": ai_result.get("fallback_used", False),
                "fallback_provider": ai_result.get("fallback_provider"),
                "error": ai_result.get("error"),
            },
        }
        if ai_result["status"] == "completed":
            enhanced["ai_enhanced_output"] = ai_result["text"]
            log_external_action("agent_ai_enhancement_completed", "completed", {"agent_slug": agent["slug"], "provider": ai_result["provider"], "model": ai_result["model"], "fallback_used": ai_result.get("fallback_used", False)})
        else:
            log_external_action("agent_ai_enhancement_failed", ai_result["status"], {"agent_slug": agent["slug"], "provider": ai_result["provider"], "model": ai_result["model"], "error": ai_result.get("error")})
        return enhanced


def _extract_topic(prompt: str) -> str:
    cleaned = prompt.strip().strip('"')
    lowered = cleaned.lower()
    if " for " in lowered:
        return cleaned[lowered.rfind(" for ") + 5 :].strip(" .")
    return cleaned or "Liuant campaign"


def _extract_days(prompt: str) -> int | None:
    words = prompt.replace("-", " ").split()
    for index, word in enumerate(words):
        if not word.isdigit():
            continue
        next_word = words[index + 1].lower() if index + 1 < len(words) else ""
        if next_word.startswith(("day", "post")) or 1 <= int(word) <= 30:
            return int(word)
    return None


def _extract_platforms(prompt: str) -> list[str]:
    lowered = prompt.lower()
    platforms = []
    for keyword, platform in (
        ("linkedin", "linkedin"),
        ("instagram", "instagram"),
        ("twitter", "x"),
        ("x", "x"),
        ("youtube", "youtube"),
        ("whatsapp", "whatsapp"),
    ):
        if keyword in lowered and platform not in platforms:
            platforms.append(platform)
    return platforms or ["linkedin", "instagram", "x", "whatsapp"]
