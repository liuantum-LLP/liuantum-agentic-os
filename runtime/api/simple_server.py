from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from runtime.action_log import list_external_actions
from runtime.agents import AgentRunner, list_agents
from runtime.approvals import ApprovalManager
from runtime.automation import AutomationManager, SchedulerEngine
from runtime.backup import BackupManager
from runtime.connectors.manager import ConnectorManager
from runtime.connectors.messaging import TelegramConnector
from runtime.connectors.email.draft_store import EmailDraftStore
from runtime.connectors.email.registry import get_email_connector
from runtime.connectors.social.linkedin_connector import LinkedInConnector
from runtime.connectors.social.x_connector import XConnector
from runtime.dashboard import build_dashboard, build_status
from runtime.doctor import run_doctor
from runtime.env_validation import EnvironmentValidator
from runtime.config import ExportTracker, OnboardingManager, PermissionManager, SettingsManager, SkillManager, WorkspaceManager
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.knowledge import KnowledgeBase
from runtime.memory import MemoryManager
from runtime.providers import ModelHub
from runtime.security_audit import audit_secrets
from runtime.security import AuthManager, SecretManager
from runtime.security.auth import public_api_path
from runtime.verification import VerificationCenter
from runtime.workflows import SocialContentWorkflow


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), LiuantHandler)
    print(f"Liuant API running at http://{host}:{port}")
    server.serve_forever()


class LiuantHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self._send({})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if not self._authorized(path):
            self._send({"status": "unauthorized", "message": "Local API authentication required."}, status=401)
            return
        routes = {
            "/api/auth/status": AuthManager().status,
            "/api/system/dashboard": build_dashboard,
            "/api/system/status": build_status,
            "/api/doctor": run_doctor,
            "/api/action-log": list_external_actions,
            "/api/agents": list_agents,
            "/api/agents/runs": AgentRunner().list_runs,
            "/api/connectors": lambda: {"available": ConnectorManager().available(), "configured": ConnectorManager().list()},
            "/api/telegram/status": TelegramConnector().get_status,
            "/api/telegram/messages": TelegramConnector().list_messages,
            "/api/telegram/drafts": TelegramConnector().list_drafts,
            "/api/social/campaigns": SocialContentWorkflow().list_campaigns,
            "/api/social/drafts": SocialContentWorkflow().list_drafts,
            "/api/social/connectors": lambda: [LinkedInConnector().get_status(), XConnector().get_status()],
            "/api/social/linkedin/status": LinkedInConnector().get_status,
            "/api/social/x/status": XConnector().get_status,
            "/api/approvals": ApprovalManager().list,
            "/api/generation/image/providers": ImageGenerationManager().list_providers,
            "/api/generation/image/jobs": ImageGenerationManager().list_jobs,
            "/api/generation/video/providers": VideoGenerationManager().list_providers,
            "/api/generation/video/jobs": VideoGenerationManager().list_jobs,
            "/api/automations/": AutomationManager().list,
            "/api/scheduler/status": SchedulerEngine().status,
            "/api/scheduler/due": SchedulerEngine().list_due,
            "/api/scheduler/runs": SchedulerEngine().runs,
            "/api/email/drafts": lambda: [],
            "/api/email/connectors": lambda: ConnectorManager().available()["email"],
            "/api/email/gmail/status": lambda: get_email_connector("gmail").get_status(),
            "/api/settings": SettingsManager().list,
            "/api/models/status": lambda: __import__("runtime.models", fromlist=["ModelManager"]).ModelManager().status(),
            "/api/models/providers": lambda: __import__("runtime.models", fromlist=["ModelManager"]).ModelManager().list(),
            "/api/providers/categories": ModelHub().list_categories,
            "/api/providers": lambda: ModelHub().list_providers((query.get("category") or [None])[0]),
            "/api/providers/status": ModelHub().get_status,
            "/api/verify/status": VerificationCenter().status,
            "/api/env/check": EnvironmentValidator().check,
            "/api/env/template": EnvironmentValidator().template,
            "/api/env/missing": EnvironmentValidator().missing,
            "/api/backup/list": BackupManager().list,
            "/api/text/providers": lambda: ModelHub().list_providers("text"),
            "/api/memory": MemoryManager().list,
            "/api/knowledge/sources": KnowledgeBase().sources,
            "/api/permissions/status": PermissionManager().status,
            "/api/permissions/rules": PermissionManager().rules_status,
            "/api/skills/available": SkillManager().available_skills,
            "/api/skills/installed": SkillManager().list,
            "/api/workspaces": WorkspaceManager().list,
            "/api/exports": ExportTracker().list,
            "/api/logs": list_external_actions,
            "/api/onboarding/status": OnboardingManager().status,
            "/api/secrets/status": SecretManager().status,
            "/api/secrets": SecretManager().list_secrets,
        }
        handler = routes.get(path)
        if not handler:
            if path == "/api/social/linkedin/oauth/callback":
                self._send(LinkedInConnector().handle_callback((query.get("code") or [""])[0], (query.get("state") or [None])[0]))
                return
            if path == "/api/social/x/oauth/callback":
                self._send(XConnector().handle_callback((query.get("code") or [""])[0], (query.get("state") or [None])[0]))
                return
            if path.startswith("/api/social/connectors/"):
                connector_id = path.rsplit("/", 1)[-1]
                if connector_id == "linkedin":
                    self._send(LinkedInConnector().get_status())
                    return
                if connector_id == "x":
                    self._send(XConnector().get_status())
                    return
            if path.startswith("/api/providers/"):
                provider_name = path.rsplit("/", 1)[-1]
                self._send(ModelHub().get_provider(provider_name))
                return
            self._send({"error": "not_found", "path": path}, status=404)
            return
        self._send(handler())

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/auth/login":
            payload = self._read_json()
            self._send(AuthManager().login(payload.get("token", ""), self.headers.get("User-Agent")))
            return
        if not self._authorized(path):
            self._send({"status": "unauthorized", "message": "Local API authentication required."}, status=401)
            return
        if path == "/api/auth/logout":
            payload = self._read_json()
            self._send(AuthManager().logout(payload.get("session_token") or self._bearer_token()))
            return
        if path == "/api/auth/rotate-token":
            self._send(AuthManager().rotate_token())
            return
        if path == "/api/secrets/migrate":
            self._send(SecretManager().migrate())
            return
        if path == "/api/secrets/delete":
            payload = self._read_json()
            self._send(SecretManager().delete_secret(payload["name"]))
            return
        if path == "/api/secrets/rotate":
            payload = self._read_json()
            self._send(SecretManager().rotate_secret(payload["name"], payload["value"]))
            return
        if path.startswith("/api/approvals/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] in {"approve", "reject"}:
                status = "approved" if parts[3] == "approve" else "rejected"
                self._send(ApprovalManager().decide(parts[2], status))
                return
        if path == "/api/agents/run":
            payload = self._read_json()
            self._send(AgentRunner().run(payload["agent_slug"], payload["prompt"], payload.get("ai_enhancement"), payload.get("provider_name"), payload.get("model")))
            return
        if path == "/api/agents/create":
            payload = self._read_json()
            self._send(__import__("runtime.agents", fromlist=["AgentProfileManager"]).AgentProfileManager().create(payload))
            return
        if path == "/api/social/campaign/create":
            payload = self._read_json()
            self._send(SocialContentWorkflow().create_campaign(**payload))
            return
        if path == "/api/social/linkedin/setup":
            self._send(LinkedInConnector().setup())
            return
        if path == "/api/social/linkedin/oauth/start":
            self._send(LinkedInConnector().start_oauth())
            return
        if path == "/api/social/linkedin/test":
            self._send(LinkedInConnector().test_connection())
            return
        if path == "/api/social/linkedin/disconnect":
            self._send(LinkedInConnector().disconnect())
            return
        if path == "/api/social/x/setup":
            self._send(XConnector().setup())
            return
        if path == "/api/social/x/oauth/start":
            self._send(XConnector().start_oauth())
            return
        if path == "/api/social/x/test":
            self._send(XConnector().test_connection())
            return
        if path == "/api/social/x/disconnect":
            self._send(XConnector().disconnect())
            return
        if path.startswith("/api/social/connectors/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[4] == "enable-publish":
                self._send(SocialContentWorkflow().enable_connector_publish(parts[3]))
                return
            if len(parts) == 5 and parts[4] == "disable-publish":
                self._send(SocialContentWorkflow().disable_connector_publish(parts[3]))
                return
        if path.startswith("/api/social/drafts/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[4] == "publish-approved":
                payload = self._read_json()
                self._send(SocialContentWorkflow().publish_approved_draft(parts[3], payload.get("connector_id") or payload.get("connector"), bool(payload.get("confirm_sensitive", False))))
                return
            if len(parts) == 5 and parts[4] == "approve":
                self._send(SocialContentWorkflow().approve_draft(parts[3]))
                return
        if path == "/api/generation/image/generate":
            payload = self._read_json()
            self._send(ImageGenerationManager().generate(**payload))
            return
        if path == "/api/verify/all":
            payload = self._read_json()
            self._send(VerificationCenter().verify_all(live_generate=bool(payload.get("live_generate", False))))
            return
        if path == "/api/verify/providers":
            payload = self._read_json()
            self._send(VerificationCenter().verify_providers(category=payload.get("category"), live_generate=bool(payload.get("live_generate", False))))
            return
        if path.startswith("/api/verify/provider/"):
            payload = self._read_json()
            provider = path.rsplit("/", 1)[-1]
            self._send(VerificationCenter().verify_provider(provider, live_generate=bool(payload.get("live_generate", False))))
            return
        if path == "/api/verify/gmail":
            self._send(VerificationCenter().verify_gmail())
            return
        if path == "/api/verify/telegram":
            self._send(VerificationCenter().verify_telegram())
            return
        if path == "/api/verify/social":
            self._send(VerificationCenter().verify_social())
            return
        if path == "/api/verify/storage":
            self._send(VerificationCenter().verify_storage())
            return
        if path == "/api/verify/security":
            self._send(VerificationCenter().verify_security())
            return
        if path == "/api/security/audit-secrets":
            self._send(audit_secrets())
            return
        if path == "/api/backup/create":
            payload = self._read_json()
            self._send(BackupManager().create(include_secrets=bool(payload.get("include_secrets", False)), include_encrypted_secrets=bool(payload.get("include_encrypted_secrets", False)), confirm=bool(payload.get("confirm", False))))
            return
        if path == "/api/generation/video/generate":
            payload = self._read_json()
            self._send(VideoGenerationManager().generate(**payload))
            return
        if path == "/api/generation/video/storyboard":
            payload = self._read_json()
            self._send(VideoGenerationManager().storyboard(**payload))
            return
        if path.startswith("/api/generation/video/jobs/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[4] == "poll":
                self._send(VideoGenerationManager().poll_job(parts[3]))
                return
            if len(parts) == 5 and parts[4] == "download":
                self._send(VideoGenerationManager().download_job(parts[3]))
                return
            if len(parts) == 5 and parts[4] == "cancel":
                self._send(VideoGenerationManager().cancel_job(parts[3]))
                return
            if len(parts) == 5 and parts[4] == "export":
                self._send(VideoGenerationManager().export_job(parts[3]))
                return
        if path == "/api/email/draft-reply":
            payload = self._read_json()
            connector = get_email_connector(payload.get("provider", "gmail"))
            if payload.get("provider", "gmail") == "gmail" and payload.get("message_id"):
                self._send(connector.create_draft_reply(payload.get("message_id"), payload.get("body"), payload.get("tone", "professional")))
            else:
                self._send(EmailDraftStore().create(connector.draft_reply(payload.get("message_id", "latest"), payload.get("tone", "professional"))))
            return
        if path in {"/api/telegram/webhook", "/api/connectors/telegram/webhook"}:
            import os

            expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
            provided = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if expected and provided != expected:
                self._send({"status": "forbidden", "code": 403, "message": "Invalid Telegram webhook secret."}, status=403)
                return
            self._send(TelegramConnector().process_update(self._read_json()))
            return
        if path == "/api/telegram/setup":
            payload = self._read_json()
            self._send(TelegramConnector().setup(payload.get("bot_token"), payload.get("assigned_agent_slug"), payload.get("permission_mode", "safe")))
            return
        if path == "/api/telegram/test":
            self._send(TelegramConnector().test_connection())
            return
        if path == "/api/telegram/enable":
            self._send(TelegramConnector().enable())
            return
        if path == "/api/telegram/disable":
            self._send(TelegramConnector().disable())
            return
        if path == "/api/telegram/disconnect":
            self._send(TelegramConnector().disconnect())
            return
        if path.startswith("/api/telegram/drafts/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[4] == "approve":
                self._send(TelegramConnector().approve_draft(parts[3]))
                return
            if len(parts) == 5 and parts[4] == "reject":
                self._send(TelegramConnector().reject_draft(parts[3]))
                return
            if len(parts) == 5 and parts[4] == "send-approved":
                self._send(TelegramConnector().send_approved(parts[3]))
                return
        if path == "/api/email/gmail/setup":
            self._send(get_email_connector("gmail").setup())
            return
        if path == "/api/email/gmail/oauth/start":
            self._send(get_email_connector("gmail").start_oauth())
            return
        if path == "/api/email/gmail/disconnect":
            self._send(get_email_connector("gmail").disconnect())
            return
        if path == "/api/email/gmail/test":
            self._send(get_email_connector("gmail").test_connection())
            return
        if path == "/api/email/recent":
            payload = self._read_json()
            self._send(get_email_connector(payload.get("provider", "gmail")).recent_messages(int(payload.get("max_results", 10))))
            return
        if path == "/api/email/search":
            payload = self._read_json()
            self._send(get_email_connector(payload.get("provider", "gmail")).search_messages(payload.get("query", ""), int(payload.get("max_results", 10))))
            return
        if path == "/api/email/read":
            payload = self._read_json()
            self._send(get_email_connector(payload.get("provider", "gmail")).read_message(payload["message_id"]))
            return
        if path == "/api/email/summarize":
            payload = self._read_json()
            self._send(get_email_connector(payload.get("provider", "gmail")).summarize_message(payload["message_id"]))
            return
        if path == "/api/automations/create":
            payload = self._read_json()
            self._send(AutomationManager().create(payload))
            return
        if path == "/api/automations/create-daily":
            payload = self._read_json()
            self._send(AutomationManager().create_daily(payload["name"], payload.get("time_of_day", "09:00"), payload.get("agent_slug", "personal-assistant-agent"), payload["task_prompt"], payload.get("timezone", "Asia/Kolkata")))
            return
        if path == "/api/automations/create-weekly":
            payload = self._read_json()
            self._send(AutomationManager().create_weekly(payload["name"], payload.get("day", "monday"), payload.get("time_of_day", "10:00"), payload.get("agent_slug", "content-creator-agent"), payload["task_prompt"], payload.get("timezone", "Asia/Kolkata")))
            return
        if path == "/api/automations/create-interval":
            payload = self._read_json()
            self._send(AutomationManager().create_interval(payload["name"], int(payload.get("minutes", 60)), payload.get("agent_slug", "personal-assistant-agent"), payload["task_prompt"]))
            return
        if path.startswith("/api/automations/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "run":
                self._send(AutomationManager().run(parts[2]))
                return
            if len(parts) == 4 and parts[3] in {"enable", "disable"}:
                self._send(AutomationManager().set_enabled(parts[2], parts[3] == "enable"))
                return
            if len(parts) == 4 and parts[3] == "history":
                self._send(AutomationManager().history(parts[2]))
                return
        if path == "/api/scheduler/tick":
            self._send(SchedulerEngine().tick())
            return
        if path == "/api/scheduler/run-due":
            payload = self._read_json()
            self._send(SchedulerEngine().run_due(limit=int(payload.get("limit", 5))))
            return
        if path.startswith("/api/skills/"):
            payload = self._read_json()
            action = path.rsplit("/", 1)[-1]
            if action == "install":
                self._send(SkillManager().install(payload["skill_name"]))
                return
            if action in {"enable", "disable"}:
                self._send(SkillManager().set_enabled(payload["skill_name"], action == "enable"))
                return
        if path == "/api/workspaces/create":
            payload = self._read_json()
            self._send(WorkspaceManager().create(payload["name"], payload.get("path")))
            return
        if path == "/api/workspaces/default":
            payload = self._read_json()
            self._send(WorkspaceManager().set_default(payload["name"]))
            return
        if path == "/api/models/test":
            payload = self._read_json()
            self._send(__import__("runtime.models", fromlist=["ModelManager"]).ModelManager().test(payload.get("provider")))
            return
        if path == "/api/models/setup":
            payload = self._read_json()
            self._send(__import__("runtime.models", fromlist=["ModelManager"]).ModelManager().setup(payload))
            return
        if path == "/api/models/default":
            payload = self._read_json()
            self._send(__import__("runtime.models", fromlist=["ModelManager"]).ModelManager().set_default(payload["provider"]))
            return
        if path == "/api/providers/setup":
            payload = self._read_json()
            self._send(ModelHub().setup_provider(payload.get("name") or payload.get("id") or payload.get("provider_name"), payload))
            return
        if path == "/api/providers/default":
            payload = self._read_json()
            self._send(ModelHub().set_default_provider(payload["category"], payload["provider_name"]))
            return
        if path == "/api/providers/model":
            payload = self._read_json()
            self._send(ModelHub().set_default_model(payload["category"], payload["model"]))
            return
        if path == "/api/providers/fallback":
            payload = self._read_json()
            self._send(ModelHub().set_fallback_provider(payload["category"], payload["provider_name"]))
            return
        if path.startswith("/api/providers/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "test":
                self._send(ModelHub().test_provider(parts[2]))
                return
            if len(parts) == 4 and parts[3] == "enable":
                self._send(ModelHub().enable_provider(parts[2]))
                return
            if len(parts) == 4 and parts[3] == "disable":
                self._send(ModelHub().disable_provider(parts[2]))
                return
        if path == "/api/text/generate":
            payload = self._read_json()
            self._send(ModelHub().generate_text(
                prompt=payload["prompt"],
                system_prompt=payload.get("system_prompt"),
                provider_name=payload.get("provider_name"),
                model=payload.get("model"),
                temperature=float(payload.get("temperature", 0.7)),
                max_tokens=payload.get("max_tokens"),
                workspace_name=payload.get("workspace_name"),
                metadata=payload.get("metadata"),
            ))
            return
        if path == "/api/embedding/create":
            payload = self._read_json()
            self._send(ModelHub().create_embedding(payload["text"], payload.get("provider_name"), payload.get("model"), payload.get("metadata")))
            return
        if path == "/api/memory/add":
            payload = self._read_json()
            self._send(MemoryManager().add(payload["content"], payload.get("memory_type", "user"), payload.get("title"), payload.get("agent_slug"), payload.get("workspace_name"), payload.get("metadata")))
            return
        if path == "/api/memory/search":
            payload = self._read_json()
            self._send(MemoryManager().search(payload["query"], payload.get("workspace_name"), int(payload.get("limit", 5))))
            return
        if path == "/api/knowledge/add-text":
            payload = self._read_json()
            self._send(KnowledgeBase().add_text(payload["text"], payload.get("title", "API Text"), payload.get("workspace_name")))
            return
        if path == "/api/knowledge/index-file":
            payload = self._read_json()
            self._send(KnowledgeBase().index_file(payload["path"], payload.get("workspace_name")))
            return
        if path == "/api/knowledge/index-agent-run":
            payload = self._read_json()
            self._send(KnowledgeBase().index_agent_run(payload["run_id"], payload.get("workspace_name")))
            return
        if path == "/api/knowledge/search":
            payload = self._read_json()
            self._send(KnowledgeBase().search(payload["query"], payload.get("workspace_name"), int(payload.get("limit", 5))))
            return
        if path.startswith("/api/text/providers/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[4] == "test":
                self._send(ModelHub().test_provider(parts[3]))
                return
        self._send({"error": "not_found", "path": path}, status=404)

    def _authorized(self, path: str) -> bool:
        if public_api_path(path):
            return True
        return AuthManager().authorize(self.headers.get("Authorization"), self.headers.get("X-Liuant-Session"))

    def _bearer_token(self) -> str | None:
        auth = self.headers.get("Authorization")
        if not auth:
            return None
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        return auth.strip()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type, authorization, x-liuant-session")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return
