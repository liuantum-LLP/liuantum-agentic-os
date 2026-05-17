from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.db import delete_record, get_record, insert_record, list_records, update_record
from runtime.storage import ROOT, WORKSPACE


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_bool(value: str) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


class SettingsManager:
    defaults = {
        "app_name": "Liuant Agentic OS",
        "app_version": "1.1.0",
        "app_environment": "local",
        "default_workspace": "default",
        "default_agent": "content-creator-agent",
        "default_provider": "openai",
        "default_model": "gpt-4.1-mini",
        "default_text_provider": "openai",
        "default_text_model": "gpt-4.1-mini",
        "default_image_provider": "openai_image",
        "default_image_model": "gpt-image-1",
        "default_video_provider": "hyperframes_skill",
        "default_video_model": "hyperframes-video-skill",
        "default_embedding_provider": "local_hash_embedding",
        "default_embedding_model": "local-hash-384",
        "default_stt_provider": "openai_stt",
        "default_stt_model": "whisper-1",
        "default_tts_provider": "openai_tts",
        "default_tts_model": "gpt-4o-mini-tts",
        "fallback_text_provider": "ollama",
        "fallback_image_provider": "custom_image_api",
        "fallback_video_provider": "hyperframes_skill",
        "allow_local_models": "true",
        "allow_cloud_models": "true",
        "agent_ai_enhancement_enabled": "false",
        "agent_ai_provider": "default_text_provider",
        "agent_ai_model": "default_text_model",
        "telegram_manual_send_enabled": "false",
        "rag_enabled": "false",
        "rag_default_limit": "5",
        "rag_workspace_scope": "true",
        "rag_include_user_memory": "true",
        "rag_include_project_memory": "true",
        "email_rag_enabled": "false",
        "telegram_knowledge_search_enabled": "false",
        "scheduler_rag_enabled": "false",
        "permission_mode": "safe",
        "export_root": str(WORKSPACE / "outputs"),
        "safe_mode_enabled": "true",
        "telemetry_enabled": "false",
        "debug_mode": "false",
        "local_auth_enabled": "true",
        "local_auth_mode": "token",
        "local_api_token_hash": "",
        "session_timeout_minutes": "720",
        "update_channel": "local-mvp",
        "update_feed_url": "",
        "auto_update_enabled": "false",
        "desktop_backend_mode": "external_backend",
        "desktop_backend_url": "http://127.0.0.1:8765",
        "desktop_auto_start_backend": "false",
        "model_roles_config": "{}",
        "discussion_mode_enabled": "false",
        "discussion_mode_default_rounds": "2",
        "discussion_mode_max_rounds": "4",
        "discussion_mode_final_role": "thinking",
    }

    def ensure_defaults(self) -> None:
        for key, value in self.defaults.items():
            if not get_record("settings", key):
                insert_record("settings", {"id": key, "key": key, "value": value, "created_at": utc_now(), "updated_at": utc_now()})
            elif key == "app_version":
                current = get_record("settings", key)
                if current and current.get("value") != value:
                    update_record("settings", key, {"value": value, "updated_at": utc_now()})

    def list(self) -> list[dict[str, Any]]:
        self.ensure_defaults()
        return sorted(list_records("settings"), key=lambda row: row["key"])

    def get(self, key: str) -> dict[str, Any]:
        self.ensure_defaults()
        row = get_record("settings", key)
        if not row:
            raise ValueError(f"Unknown setting: {key}")
        return row

    def set(self, key: str, value: str) -> dict[str, Any]:
        self.ensure_defaults()
        if not get_record("settings", key):
            insert_record("settings", {"id": key, "key": key, "value": value, "created_at": utc_now(), "updated_at": utc_now()})
        return update_record("settings", key, {"value": value, "updated_at": utc_now()})


class ModelProviderConfigManager:
    provider_types = ("openai", "openrouter", "ollama", "custom_openai_compatible")
    defaults = [
        ("openai", "OpenAI", "openai", "https://api.openai.com/v1", "gpt-4.1-mini", "gpt-4.1-mini", "OPENAI_API_KEY", True),
        ("openrouter", "OpenRouter", "openrouter", "https://openrouter.ai/api/v1", "openai/gpt-4.1-mini", "openai/gpt-4.1-mini", "OPENROUTER_API_KEY", False),
        ("ollama", "Ollama Local", "ollama", "http://127.0.0.1:11434/v1", "llama3.2", "llama3.2", "OLLAMA_API_KEY", False),
        ("custom_openai_compatible", "Custom OpenAI Compatible", "custom_openai_compatible", "", "", "", "CUSTOM_OPENAI_API_KEY", False),
    ]

    def ensure_defaults(self) -> None:
        for provider_id, name, provider_type, base_url, default_model, fallback_model, env_var, is_default in self.defaults:
            if not get_record("model_providers", provider_id):
                insert_record(
                    "model_providers",
                    {
                        "id": provider_id,
                        "name": name,
                        "provider_type": provider_type,
                        "base_url": base_url,
                        "default_model": default_model,
                        "fallback_model": fallback_model,
                        "api_key_masked": mask_secret(os.environ.get(env_var)),
                        "env_var": env_var,
                        "is_enabled": provider_id in {"openai", "ollama"},
                        "is_default": is_default,
                        "status": "configured" if os.environ.get(env_var) or provider_id == "ollama" else "missing_key",
                        "last_tested_at": None,
                        "created_at": utc_now(),
                        "updated_at": utc_now(),
                    },
                )

    def list(self) -> list[dict[str, Any]]:
        self.ensure_defaults()
        rows = list_records("model_providers")
        for row in rows:
            env_value = os.environ.get(row.get("env_var", ""))
            row["api_key_masked"] = mask_secret(env_value) or row.get("api_key_masked", "")
            if row.get("status") == "missing_api_key":
                row["status"] = "missing_key"
            if env_value and row.get("status") == "missing_key":
                row["status"] = "configured"
        return sorted(rows, key=lambda row: row["name"])

    def status(self) -> dict[str, Any]:
        providers = self.list()
        return {
            "configured_count": sum(1 for row in providers if row["status"] in {"configured", "reachable"}),
            "default_provider": next((row["id"] for row in providers if row.get("is_default")), None),
            "providers": providers,
        }

    def setup(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        data = data or {}
        provider_id = data.get("id") or data.get("provider") or "openai"
        row = get_record("model_providers", provider_id)
        if not row:
            row = {"id": provider_id, "created_at": utc_now()}
        row.update({k: v for k, v in data.items() if k != "api_key"})
        row.setdefault("name", provider_id)
        row.setdefault("provider_type", provider_id)
        row.setdefault("base_url", "")
        row.setdefault("default_model", "")
        row.setdefault("fallback_model", "")
        row.setdefault("api_key_masked", mask_secret(data.get("api_key")))
        row.setdefault("is_enabled", True)
        row.setdefault("is_default", False)
        row["status"] = "configured" if row.get("api_key_masked") or row.get("provider_type") == "ollama" else "missing_key"
        row["updated_at"] = utc_now()
        return insert_record("model_providers", row)

    def test(self, provider: str | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        provider = provider or self.status()["default_provider"] or "openai"
        row = get_record("model_providers", provider)
        if not row:
            raise ValueError(f"Unknown provider: {provider}")
        reachable = row["provider_type"] == "ollama" or bool(os.environ.get(row.get("env_var", "")))
        status = "configured" if reachable else "missing_key"
        row = update_record("model_providers", provider, {"status": status, "last_tested_at": utc_now(), "updated_at": utc_now()})
        message = "Provider configuration is present." if reachable else f"Missing {row.get('env_var', 'API key')} in .env, .env.local, or environment."
        return {"provider": provider, "success": reachable, "status": status, "message": message, "provider_config": row}

    def set_default(self, provider: str) -> dict[str, Any]:
        self.ensure_defaults()
        if not get_record("model_providers", provider):
            raise ValueError(f"Unknown provider: {provider}")
        for row in self.list():
            update_record("model_providers", row["id"], {"is_default": row["id"] == provider, "updated_at": utc_now()})
        SettingsManager().set("default_provider", provider)
        return get_record("model_providers", provider) or {}

    def set_fallback(self, provider: str, model: str) -> dict[str, Any]:
        self.ensure_defaults()
        if not get_record("model_providers", provider):
            raise ValueError(f"Unknown provider: {provider}")
        return update_record("model_providers", provider, {"fallback_model": model, "updated_at": utc_now()})


class PermissionManager:
    rules = {
        "safe": {
            "allowed": ["draft_generation", "workspace_file_write", "read_local_status"],
            "requires_approval": ["shell_risky", "package_install", "external_publish", "email_send", "destructive_actions"],
            "blocked": ["private_page_scraping", "raw_password_collection"],
            "file_access": "workspace_only",
        },
        "developer": {
            "allowed": ["draft_generation", "shell_safe", "workspace_file_write", "read_local_status"],
            "requires_approval": ["shell_risky", "package_install", "external_publish", "email_send", "destructive_actions"],
            "blocked": ["private_page_scraping", "raw_password_collection"],
            "file_access": "workspace_only",
        },
        "full_automation": {
            "allowed": ["draft_generation", "manual_automation_runs", "safe_recurring_drafts"],
            "requires_approval": ["external_publish", "email_send", "destructive_actions"],
            "blocked": ["private_page_scraping", "raw_password_collection"],
            "file_access": "workspace_only",
        },
    }

    def ensure_defaults(self) -> None:
        active = SettingsManager().get("permission_mode")["value"]
        for mode, rules in self.rules.items():
            if not get_record("permission_profiles", mode):
                insert_record("permission_profiles", {"id": mode, "name": mode.replace("_", " ").title(), "mode": mode, "rules_json": rules, "is_active": mode == active, "created_at": utc_now(), "updated_at": utc_now()})

    def status(self) -> dict[str, Any]:
        self.ensure_defaults()
        active = next((row for row in list_records("permission_profiles") if row.get("is_active")), None)
        return active or self.set("safe")

    def set(self, mode: str) -> dict[str, Any]:
        if mode not in self.rules:
            raise ValueError(f"Unknown permission mode: {mode}")
        self.ensure_defaults()
        for row in list_records("permission_profiles"):
            update_record("permission_profiles", row["id"], {"is_active": row["mode"] == mode, "updated_at": utc_now()})
        SettingsManager().set("permission_mode", mode)
        return get_record("permission_profiles", mode) or {}

    def rules_status(self) -> dict[str, Any]:
        return {"active": self.status(), "profiles": sorted(list_records("permission_profiles"), key=lambda row: row["mode"])}


class WorkspaceManager:
    def ensure_default(self) -> None:
        if not get_record("workspaces", "default"):
            insert_record("workspaces", {"id": "default", "name": "default", "path": str(WORKSPACE), "is_default": True, "created_at": utc_now(), "updated_at": utc_now()})

    def list(self) -> list[dict[str, Any]]:
        self.ensure_default()
        return sorted(list_records("workspaces"), key=lambda row: row["name"])

    def create(self, name: str, path: str | None = None) -> dict[str, Any]:
        path = path or str(WORKSPACE / name)
        Path(path).mkdir(parents=True, exist_ok=True)
        return insert_record("workspaces", {"id": name, "name": name, "path": path, "is_default": False, "created_at": utc_now(), "updated_at": utc_now()})

    def set_default(self, name: str) -> dict[str, Any]:
        self.ensure_default()
        if not get_record("workspaces", name):
            self.create(name)
        for row in self.list():
            update_record("workspaces", row["id"], {"is_default": row["name"] == name, "updated_at": utc_now()})
        SettingsManager().set("default_workspace", name)
        return get_record("workspaces", name) or {}

    def show(self, name: str) -> dict[str, Any]:
        self.ensure_default()
        row = get_record("workspaces", name)
        if not row:
            raise ValueError(f"Unknown workspace: {name}")
        return row

    def default(self) -> dict[str, Any]:
        return next((row for row in self.list() if row.get("is_default")), self.show("default"))


class ExportTracker:
    def record(self, export_type: str, source_table: str, source_id: str, file_path: str, fmt: str, workspace_name: str | None = None) -> dict[str, Any]:
        workspace_name = workspace_name or SettingsManager().get("default_workspace")["value"]
        row = {
            "id": str(uuid4()),
            "workspace_name": workspace_name,
            "export_type": export_type,
            "source_table": source_table,
            "source_id": source_id,
            "file_path": file_path,
            "format": fmt,
            "created_at": utc_now(),
        }
        return insert_record("exported_files", row)

    def list(self) -> list[dict[str, Any]]:
        return list_records("exported_files")

    def show(self, export_id: str) -> dict[str, Any]:
        row = get_record("exported_files", export_id)
        if not row:
            raise ValueError(f"Unknown export: {export_id}")
        return row


class SkillManager:
    available = [
        {"skill_name": "content-planning", "title": "Content Planning", "description": "Plan content themes, channels, and draft calendars.", "category": "content", "version": "0.1", "author": "Liuant", "required_tools_json": ["file_tool"], "safety_level": "safe", "steps": ["Define audience", "Choose channels", "Draft calendar"], "example_inputs": ["Create a 7-day content plan"]},
        {"skill_name": "approval-review", "title": "Approval Review", "description": "Review draft external actions before approval.", "category": "safety", "version": "0.1", "author": "Liuant", "required_tools_json": [], "safety_level": "safe", "steps": ["Show exact preview", "Check risk", "Approve or reject"], "example_inputs": ["Review this social draft"]},
        {"skill_name": "storyboard-writing", "title": "Storyboard Writing", "description": "Create video concepts, scenes, shot lists, and scripts.", "category": "video", "version": "0.1", "author": "Liuant", "required_tools_json": ["file_tool"], "safety_level": "safe", "steps": ["Define concept", "Break into scenes", "Write voiceover"], "example_inputs": ["Storyboard a launch video"]},
        {"skill_name": "hyperframes-image-skill", "title": "HyperFrames Image Skill", "description": "Create HyperFrames-ready image creative packages.", "category": "image", "version": "0.2.1", "author": "Liuant", "required_tools_json": ["file_tool"], "safety_level": "safe", "steps": ["Write creative brief", "Generate prompt pack", "Plan layout"], "example_inputs": ["Create a LinkedIn poster package"]},
        {"skill_name": "hyperframes-video-skill", "title": "HyperFrames Video Skill", "description": "Create HyperFrames-ready video storyboards and HTML/CSS package plans.", "category": "video", "version": "0.2.1", "author": "Liuant", "required_tools_json": ["file_tool"], "safety_level": "safe", "steps": ["Define concept", "Write scenes", "Plan HTML package"], "example_inputs": ["Create a launch video package"]},
        {"skill_name": "create-flask-app", "title": "Create Flask App", "description": "Plan a safe Flask application scaffold.", "category": "coding", "version": "0.1", "author": "Liuant", "required_tools_json": ["file_tool"], "safety_level": "developer", "steps": ["Define routes", "Plan models", "List files", "Suggest safe commands"], "example_inputs": ["Create a Flask CRUD app"]},
        {"skill_name": "analyze-github-repo", "title": "Analyze GitHub Repo", "description": "Analyze repository structure and risks from local files or approved fetches.", "category": "coding", "version": "0.1", "author": "Liuant", "required_tools_json": ["file_tool", "browser_tool"], "safety_level": "developer", "steps": ["Map files", "Identify stack", "Summarize risks"], "example_inputs": ["Analyze this repo"]},
        {"skill_name": "create-course-plan", "title": "Create Course Plan", "description": "Create a structured course outline, lessons, assignments, and projects.", "category": "education", "version": "0.1", "author": "Liuant", "required_tools_json": ["document_tool", "file_tool"], "safety_level": "safe", "steps": ["Define outcome", "Break into modules", "Add projects"], "example_inputs": ["Create a Python course plan"]},
        {"skill_name": "debug-flutter-app", "title": "Debug Flutter App", "description": "Plan debugging steps for Flutter issues without destructive commands.", "category": "coding", "version": "0.1", "author": "Liuant", "required_tools_json": ["file_tool"], "safety_level": "developer", "steps": ["Capture error", "Inspect structure", "Suggest safe checks"], "example_inputs": ["Debug Flutter build error"]},
        {"skill_name": "generate-business-proposal", "title": "Generate Business Proposal", "description": "Draft proposal structure, scope, deliverables, timeline, and pricing notes.", "category": "business", "version": "0.1", "author": "Liuant", "required_tools_json": ["document_tool", "file_tool"], "safety_level": "safe", "steps": ["Define client goal", "Write scope", "Add deliverables"], "example_inputs": ["Proposal for CRM project"]},
        {"skill_name": "create-marketing-campaign", "title": "Create Marketing Campaign", "description": "Create campaign strategy, captions, ad copy, and calendar.", "category": "marketing", "version": "0.1", "author": "Liuant", "required_tools_json": ["social_tool", "file_tool"], "safety_level": "safe", "steps": ["Define offer", "Choose audience", "Draft assets"], "example_inputs": ["Market a Python course"]},
        {"skill_name": "manage-front-desk", "title": "Manage Front Desk", "description": "Create enquiry replies, scripts, and follow-up plans.", "category": "operations", "version": "0.1", "author": "Liuant", "required_tools_json": ["document_tool", "file_tool"], "safety_level": "safe", "steps": ["Classify enquiry", "Draft reply", "Plan follow-up"], "example_inputs": ["Reply to course enquiry"]},
        {"skill_name": "create-social-media-calendar", "title": "Create Social Media Calendar", "description": "Create platform-aware content calendars and draft post ideas.", "category": "social", "version": "0.1", "author": "Liuant", "required_tools_json": ["social_tool", "file_tool"], "safety_level": "safe", "steps": ["Pick platforms", "Plan days", "Draft posts"], "example_inputs": ["Create 30-day Instagram calendar"]},
    ]

    def available_skills(self) -> list[dict[str, Any]]:
        return self.available

    def list(self) -> list[dict[str, Any]]:
        return list_records("skill_installs")

    def install(self, skill_name: str) -> dict[str, Any]:
        skill = next((row for row in self.available if row["skill_name"] == skill_name), None)
        if not skill:
            raise ValueError(f"Unknown skill: {skill_name}")
        row = {**skill, "id": skill_name, "status": "installed", "enabled": True, "source": "builtin", "installed_at": utc_now(), "updated_at": utc_now()}
        return insert_record("skill_installs", row)

    def set_enabled(self, skill_name: str, enabled: bool) -> dict[str, Any]:
        row = get_record("skill_installs", skill_name) or self.install(skill_name)
        return update_record("skill_installs", row["id"], {"enabled": enabled, "status": "enabled" if enabled else "disabled", "updated_at": utc_now()})

    def uninstall(self, skill_name: str) -> dict[str, Any]:
        return {"deleted": delete_record("skill_installs", skill_name), "skill_name": skill_name}


class OnboardingManager:
    steps = ["welcome", "model_setup", "workspace_setup", "agent_selection", "skills_setup", "connectors_setup", "permissions_setup", "finish"]

    def status(self) -> dict[str, Any]:
        row = get_record("onboarding_state", "default")
        if not row:
            row = {"id": "default", "completed": False, "current_step": "welcome", "completed_steps_json": [], "created_at": utc_now(), "updated_at": utc_now()}
            insert_record("onboarding_state", row)
        return row

    def reset(self) -> dict[str, Any]:
        row = {"id": "default", "completed": False, "current_step": "welcome", "completed_steps_json": [], "created_at": self.status().get("created_at", utc_now()), "updated_at": utc_now()}
        return insert_record("onboarding_state", row)

    def complete_step(self, step: str) -> dict[str, Any]:
        if step not in self.steps:
            raise ValueError(f"Unknown onboarding step: {step}")
        row = self.status()
        completed = list(dict.fromkeys([*row.get("completed_steps_json", []), step]))
        index = min(len(completed), len(self.steps) - 1)
        row.update({"completed_steps_json": completed, "current_step": self.steps[index], "completed": "finish" in completed, "updated_at": utc_now()})
        return insert_record("onboarding_state", row)


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}...{value[-4:]}"
