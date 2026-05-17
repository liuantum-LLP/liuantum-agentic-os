"""FastAPI app for Liuant Agentic OS MVP.

Run with: uvicorn runtime.api.app:app --reload
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:
    class FastAPI:
        """Development fallback so route definitions remain inspectable before install."""

        def __init__(self, title: str, version: str) -> None:
            self.title = title
            self.version = version
            self.routes: list[dict[str, str]] = []

        def _route(self, method: str, path: str):
            def decorator(func):
                self.routes.append({"method": method, "path": path, "name": func.__name__})
                return func

            return decorator

        def get(self, path: str):
            return self._route("GET", path)

        def post(self, path: str):
            return self._route("POST", path)

        def put(self, path: str):
            return self._route("PUT", path)

        def delete(self, path: str):
            return self._route("DELETE", path)
    CORSMiddleware = None
    def Header(default: Any = None, alias: str | None = None) -> Any:
        return default
    HTTPException = Exception
    Request = Any

from runtime.action_log import list_external_actions
from runtime.agents import AgentRunner, list_agents
from runtime.approvals import ApprovalManager
from runtime.automation import AutomationManager, SchedulerEngine
from runtime.content_creator import ContentCreator
from runtime.connectors.manager import ConnectorManager
from runtime.connectors.messaging import TelegramConnector
from runtime.connectors.webhook_connector import WebhookConnector
from runtime.config import ExportTracker, OnboardingManager, PermissionManager, SettingsManager, SkillManager, WorkspaceManager
from runtime.connectors.email.draft_store import EmailDraftStore
from runtime.connectors.email.registry import get_email_connector, list_email_connectors
from runtime.connectors.social.registry import list_social_connectors
from runtime.connectors.social.linkedin_connector import LinkedInConnector
from runtime.connectors.social.x_connector import XConnector
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.knowledge import KnowledgeBase
from runtime.memory import MemoryManager
from runtime.doctor import run_doctor
from runtime.dashboard import build_dashboard, build_status
from runtime.exports import (
    export_agent_run_markdown,
    export_campaign_markdown,
    export_content_calendar_csv,
    export_image_prompt_markdown,
    export_video_storyboard_markdown,
)
from runtime.models import ModelManager
from runtime.providers import ModelHub
from runtime.backup import BackupManager
from runtime.env_validation import EnvironmentValidator
from runtime.security_audit import audit_secrets
from runtime.security import AuthManager
from runtime.security import SecretManager
from runtime.security.auth import public_api_path
from runtime.verification import VerificationCenter
from runtime.release import ReleaseManager
from runtime.chat.intent_router import route_chat_message, execute_intent_action
from runtime.workflows import SocialContentWorkflow

app = FastAPI(title="Liuant Agentic OS", version="0.5.6")
if CORSMiddleware and hasattr(app, "add_middleware"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

image_manager = ImageGenerationManager()
video_manager = VideoGenerationManager()
social_workflow = SocialContentWorkflow()
approval_manager = ApprovalManager()
automation_manager = AutomationManager()
scheduler_engine = SchedulerEngine()
webhook_connector = WebhookConnector()
verification_center = VerificationCenter()
connector_manager = ConnectorManager()
model_manager = ModelManager()
model_hub = ModelHub()
content_creator = ContentCreator()
email_draft_store = EmailDraftStore()
agent_runner = AgentRunner()
telegram_connector = TelegramConnector()
knowledge_base = KnowledgeBase()
memory_manager = MemoryManager()
linkedin_connector = LinkedInConnector()
x_connector = XConnector()
release_manager = ReleaseManager()

if hasattr(app, "middleware"):
    @app.middleware("http")
    async def local_auth_middleware(request: Request, call_next):
        path = request.url.path
        if not public_api_path(path) and not AuthManager().authorize(request.headers.get("authorization"), request.cookies.get("liuant_session")):
            raise HTTPException(status_code=401, detail="Local API authentication required.")
        return await call_next(request)


@app.get("/api/auth/status")
def auth_status() -> dict[str, Any]:
    return AuthManager().status()


@app.post("/api/auth/login")
def auth_login(payload: dict[str, Any], user_agent: str | None = Header(default=None, alias="user-agent")) -> dict[str, Any]:
    return AuthManager().login(payload.get("token", ""), user_agent)


@app.post("/api/auth/logout")
def auth_logout(payload: dict[str, Any] | None = None, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    payload = payload or {}
    session_token = payload.get("session_token")
    if not session_token and authorization and authorization.lower().startswith("bearer "):
        session_token = authorization.split(" ", 1)[1].strip()
    return AuthManager().logout(session_token)


@app.post("/api/auth/rotate-token")
def auth_rotate_token() -> dict[str, Any]:
    return AuthManager().rotate_token()


@app.get("/api/secrets/status")
def secrets_status() -> dict[str, Any]:
    return SecretManager().status()


@app.get("/api/secrets")
def secrets_list() -> list[dict[str, Any]]:
    return SecretManager().list_secrets()


@app.post("/api/secrets/migrate")
def secrets_migrate() -> dict[str, Any]:
    return SecretManager().migrate()


@app.post("/api/secrets/delete")
def secrets_delete(payload: dict[str, Any]) -> dict[str, Any]:
    return SecretManager().delete_secret(payload["name"])


@app.post("/api/secrets/rotate")
def secrets_rotate(payload: dict[str, Any]) -> dict[str, Any]:
    return SecretManager().rotate_secret(payload["name"], payload["value"])


@app.post("/api/chat/message")
def chat_message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message", "")
    context = payload.get("context", {})
    if not message:
        return {"status": "error", "message": "No message provided."}
    return route_chat_message(message.strip(), context)


@app.post("/api/chat/action")
def chat_action(payload: dict[str, Any]) -> dict[str, Any]:
    intent = payload.get("intent", "")
    action = payload.get("action", "")
    data = payload.get("data", {})
    if not intent or not action:
        return {"status": "error", "message": "intent and action are required."}
    return execute_intent_action(intent, action, data)


@app.get("/api/chat/intents")
def chat_intents() -> dict[str, Any]:
    from runtime.chat.intent_router import INTENT_DESCRIPTIONS, INTENT_PATTERNS
    return {
        "intents": {k: {"description": INTENT_DESCRIPTIONS.get(k, ""), "patterns": len(v)} for k, v in INTENT_PATTERNS.items()},
        "count": len(INTENT_PATTERNS),
    }


@app.post("/api/chat/discussion")
def chat_discussion(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message", "")
    if not message:
        return {"status": "error", "message": "No message provided."}
    roles = payload.get("roles")
    rounds = int(payload.get("rounds", 2))
    final_role = payload.get("final_role", "thinking")
    from runtime.chat.discussion import run_discussion
    return run_discussion(user_message=message, roles=roles, rounds=rounds, final_role=final_role)


@app.get("/api/models/roles")
def models_roles() -> dict[str, Any]:
    from runtime.model_roles import ModelRoleManager
    return ModelRoleManager().get_all_roles()


@app.post("/api/models/roles/set")
def models_roles_set(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.model_roles import ModelRoleManager
    role = payload.get("role", "")
    provider = payload.get("provider", "")
    model = payload.get("model", "")
    if not role or not provider or not model:
        return {"status": "error", "message": "role, provider, and model are required."}
    try:
        return ModelRoleManager().set_role(role, provider, model)
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/models/roles/test")
def models_roles_test(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.model_roles import ModelRoleManager
    role = payload.get("role", "")
    if not role:
        return {"status": "error", "message": "role is required."}
    return ModelRoleManager().test_role(role)


@app.post("/api/models/roles/reset")
def models_roles_reset(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.model_roles import ModelRoleManager
    role = payload.get("role")
    if role:
        return ModelRoleManager().reset_role(role)
    return ModelRoleManager().reset_all_roles()


@app.get("/api/models/discussion")
def models_discussion_status() -> dict[str, Any]:
    from runtime.model_roles import ModelRoleManager
    return ModelRoleManager().get_discussion_settings()


@app.post("/api/models/discussion/set")
def models_discussion_set(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.model_roles import ModelRoleManager
    key = payload.get("key", "")
    value = payload.get("value", "")
    if not key:
        return {"status": "error", "message": "key is required."}
    try:
        return ModelRoleManager().set_discussion_setting(key, value)
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/system/dashboard")
def system_dashboard() -> dict[str, Any]:
    return build_dashboard()


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    return build_status()


@app.get("/api/settings")
def settings() -> list[dict[str, Any]]:
    return SettingsManager().list()


@app.get("/api/settings/{key}")
def setting_get(key: str) -> dict[str, Any]:
    return SettingsManager().get(key)


@app.post("/api/settings/set")
def setting_set(payload: dict[str, Any]) -> dict[str, Any]:
    return SettingsManager().set(payload["key"], str(payload["value"]))


@app.get("/api/action-log")
def action_log() -> list[dict[str, Any]]:
    return list_external_actions()


@app.get("/api/logs")
def logs() -> list[dict[str, Any]]:
    return list_external_actions()


@app.get("/api/logs/{log_id}")
def log_show(log_id: str) -> dict[str, Any] | None:
    from runtime.db import get_record

    return get_record("action_logs", log_id)


@app.get("/api/agent-runs")
def agent_runs() -> list[dict[str, Any]]:
    return agent_runner.list_runs()


@app.get("/api/doctor")
def doctor() -> dict[str, Any]:
    return run_doctor()


@app.get("/api/verify/status")
def verify_status() -> dict[str, Any]:
    return verification_center.status()


@app.post("/api/verify/all")
def verify_all(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return verification_center.verify_all(live_generate=bool((payload or {}).get("live_generate", False)))


@app.post("/api/verify/providers")
def verify_providers(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return verification_center.verify_providers(category=payload.get("category"), live_generate=bool(payload.get("live_generate", False)))


@app.post("/api/verify/provider/{provider_name}")
def verify_provider(provider_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return verification_center.verify_provider(provider_name, live_generate=bool((payload or {}).get("live_generate", False)))


@app.post("/api/verify/gmail")
def verify_gmail() -> dict[str, Any]:
    return verification_center.verify_gmail()


@app.post("/api/verify/telegram")
def verify_telegram() -> dict[str, Any]:
    return verification_center.verify_telegram()


@app.post("/api/verify/social")
def verify_social() -> dict[str, Any]:
    return verification_center.verify_social()


@app.post("/api/verify/storage")
def verify_storage() -> dict[str, Any]:
    return verification_center.verify_storage()


@app.post("/api/verify/security")
def verify_security() -> dict[str, Any]:
    return verification_center.verify_security()


@app.post("/api/security/audit-secrets")
def security_audit_secrets() -> dict[str, Any]:
    return audit_secrets()


@app.get("/api/env/check")
def env_check() -> dict[str, Any]:
    return EnvironmentValidator().check()


@app.get("/api/env/template")
def env_template() -> dict[str, Any]:
    return EnvironmentValidator().template()


@app.get("/api/env/missing")
def env_missing() -> dict[str, Any]:
    return EnvironmentValidator().missing()


@app.post("/api/backup/create")
def backup_create(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return BackupManager().create(include_secrets=bool(payload.get("include_secrets", False)), include_encrypted_secrets=bool(payload.get("include_encrypted_secrets", False)), confirm=bool(payload.get("confirm", False)))


@app.get("/api/backup/list")
def backup_list() -> list[dict[str, Any]]:
    return BackupManager().list()


@app.get("/api/agents")
def agents() -> list[dict[str, Any]]:
    return list_agents()


@app.get("/api/agents/{slug}")
def agent_show(slug: str) -> dict[str, Any]:
    from runtime.agents import AgentProfileManager

    return AgentProfileManager().show(slug)


@app.post("/api/agents/create")
def agent_create(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.agents import AgentProfileManager

    return AgentProfileManager().create(payload)


@app.put("/api/agents/{slug}")
def agent_update(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.agents import AgentProfileManager

    return AgentProfileManager().update(slug, payload)


@app.post("/api/agents/{slug}/enable")
def agent_enable(slug: str) -> dict[str, Any]:
    from runtime.agents import AgentProfileManager

    return AgentProfileManager().set_enabled(slug, True)


@app.post("/api/agents/{slug}/disable")
def agent_disable(slug: str) -> dict[str, Any]:
    from runtime.agents import AgentProfileManager

    return AgentProfileManager().set_enabled(slug, False)


@app.post("/api/agents/run")
def agents_run(payload: dict[str, Any]) -> dict[str, Any]:
    return agent_runner.run(payload["agent_slug"], payload["prompt"], payload.get("ai_enhancement"), payload.get("provider_name"), payload.get("model"), payload.get("rag_enabled"), payload.get("workspace_name"), payload.get("rag_query"), payload.get("rag_limit"))


@app.post("/api/agents/{slug}/run")
def agent_run_slug(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    return agent_runner.run(slug, payload["prompt"], payload.get("ai_enhancement"), payload.get("provider_name"), payload.get("model"), payload.get("rag_enabled"), payload.get("workspace_name"), payload.get("rag_query"), payload.get("rag_limit"))


@app.get("/api/agents/runs")
def agents_runs() -> list[dict[str, Any]]:
    return agent_runner.list_runs()


@app.get("/api/models/list")
def models_list() -> list[dict[str, Any]]:
    return model_manager.list()


@app.post("/api/models/setup")
def models_setup(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return model_manager.setup(payload)


@app.post("/api/models/test")
def models_test(payload: dict[str, Any]) -> dict[str, Any]:
    return model_manager.test(payload.get("provider"))


@app.get("/api/models/status")
def models_status() -> dict[str, Any]:
    return model_manager.status()


@app.get("/api/models/providers")
def model_providers() -> list[dict[str, Any]]:
    return model_manager.list()


@app.post("/api/models/default")
def model_default(payload: dict[str, Any]) -> dict[str, Any]:
    return model_manager.set_default(payload["provider"])


@app.post("/api/models/fallback")
def model_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    return model_manager.set_fallback(payload["provider"], payload["model"])


@app.get("/api/providers/categories")
def provider_categories() -> list[str]:
    return model_hub.list_categories()


@app.get("/api/providers")
def providers(category: str | None = None) -> list[dict[str, Any]]:
    return model_hub.list_providers(category)


@app.get("/api/providers/status")
def providers_status() -> dict[str, Any]:
    return model_hub.get_status()


@app.get("/api/providers/{provider_name}")
def provider_show(provider_name: str) -> dict[str, Any]:
    return model_hub.get_provider(provider_name)


@app.post("/api/providers/setup")
def provider_setup(payload: dict[str, Any]) -> dict[str, Any]:
    provider_name = payload.get("name") or payload.get("id") or payload.get("provider_name")
    return model_hub.setup_provider(provider_name, payload)


@app.post("/api/providers/{provider_name}/test")
def provider_test(provider_name: str) -> dict[str, Any]:
    return model_hub.test_provider(provider_name)


@app.post("/api/providers/{provider_name}/enable")
def provider_enable(provider_name: str) -> dict[str, Any]:
    return model_hub.enable_provider(provider_name)


@app.post("/api/providers/{provider_name}/disable")
def provider_disable(provider_name: str) -> dict[str, Any]:
    return model_hub.disable_provider(provider_name)


@app.post("/api/providers/default")
def provider_default(payload: dict[str, Any]) -> dict[str, Any]:
    return model_hub.set_default_provider(payload["category"], payload["provider_name"])


@app.post("/api/providers/model")
def provider_model(payload: dict[str, Any]) -> dict[str, Any]:
    return model_hub.set_default_model(payload["category"], payload["model"])


@app.post("/api/providers/fallback")
def provider_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    return model_hub.set_fallback_provider(payload["category"], payload["provider_name"])


@app.post("/api/text/generate")
def text_generate(payload: dict[str, Any]) -> dict[str, Any]:
    return model_hub.generate_text(
        prompt=payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        provider_name=payload.get("provider_name"),
        model=payload.get("model"),
        temperature=float(payload.get("temperature", 0.7)),
        max_tokens=payload.get("max_tokens"),
        workspace_name=payload.get("workspace_name"),
        metadata=payload.get("metadata"),
    )


@app.get("/api/text/providers")
def text_providers() -> list[dict[str, Any]]:
    return model_hub.list_providers("text")


@app.post("/api/text/providers/{provider_name}/test")
def text_provider_test(provider_name: str) -> dict[str, Any]:
    return model_hub.test_provider(provider_name)


@app.post("/api/embedding/create")
def embedding_create(payload: dict[str, Any]) -> dict[str, Any]:
    return model_hub.create_embedding(payload["text"], payload.get("provider_name"), payload.get("model"), payload.get("metadata"))


@app.get("/api/memory")
def memory_list() -> list[dict[str, Any]]:
    return memory_manager.list()


@app.post("/api/memory/add")
def memory_add(payload: dict[str, Any]) -> dict[str, Any]:
    return memory_manager.add(payload["content"], payload.get("memory_type", "user"), payload.get("title"), payload.get("agent_slug"), payload.get("workspace_name"), payload.get("metadata"))


@app.post("/api/memory/search")
def memory_search(payload: dict[str, Any]) -> dict[str, Any]:
    return memory_manager.search(payload["query"], payload.get("workspace_name"), int(payload.get("limit", 5)))


@app.delete("/api/memory/{memory_id}")
def memory_delete(memory_id: str) -> dict[str, Any]:
    return memory_manager.delete(memory_id)


@app.get("/api/knowledge/sources")
def knowledge_sources() -> list[dict[str, Any]]:
    return knowledge_base.sources()


@app.post("/api/knowledge/add-text")
def knowledge_add_text(payload: dict[str, Any]) -> dict[str, Any]:
    return knowledge_base.add_text(payload["text"], payload.get("title", "API Text"), payload.get("workspace_name"))


@app.post("/api/knowledge/index-file")
def knowledge_index_file(payload: dict[str, Any]) -> dict[str, Any]:
    return knowledge_base.index_file(payload["path"], payload.get("workspace_name"))


@app.post("/api/knowledge/index-agent-run")
def knowledge_index_agent_run(payload: dict[str, Any]) -> dict[str, Any]:
    return knowledge_base.index_agent_run(payload["run_id"], payload.get("workspace_name"))


@app.post("/api/knowledge/search")
def knowledge_search(payload: dict[str, Any]) -> dict[str, Any]:
    return knowledge_base.search(payload["query"], payload.get("workspace_name"), int(payload.get("limit", 5)))


@app.delete("/api/knowledge/sources/{source_id}")
def knowledge_delete_source(source_id: str) -> dict[str, Any]:
    return knowledge_base.delete_source(source_id)


@app.post("/api/knowledge/sources/{source_id}/reindex")
def knowledge_reindex_source(source_id: str) -> dict[str, Any]:
    return knowledge_base.reindex_source(source_id)


@app.get("/api/permissions/status")
def permissions_status() -> dict[str, Any]:
    return PermissionManager().status()


@app.post("/api/permissions/set")
def permissions_set(payload: dict[str, Any]) -> dict[str, Any]:
    return PermissionManager().set(payload["mode"])


@app.get("/api/permissions/rules")
def permissions_rules() -> dict[str, Any]:
    return PermissionManager().rules_status()


@app.get("/api/connectors")
def connectors_list() -> dict[str, Any]:
    return {"available": connector_manager.available(), "configured": connector_manager.list()}


@app.get("/api/connectors/{connector_id}")
def connector_show(connector_id: str) -> dict[str, Any]:
    return connector_manager.show(connector_id)


@app.post("/api/connectors/{connector_id}/test")
def connector_test(connector_id: str) -> dict[str, Any]:
    return connector_manager.test(connector_id)


@app.post("/api/connectors/{connector_id}/enable")
def connector_enable(connector_id: str) -> dict[str, Any]:
    return connector_manager.set_enabled(connector_id, True)


@app.post("/api/connectors/{connector_id}/disable")
def connector_disable(connector_id: str) -> dict[str, Any]:
    return connector_manager.set_enabled(connector_id, False)


@app.post("/api/connectors/{connector_id}/disconnect")
def connector_disconnect(connector_id: str) -> dict[str, Any]:
    return connector_manager.disconnect(connector_id)


@app.post("/api/connectors/create")
def connectors_create(payload: dict[str, Any]) -> dict[str, Any]:
    return connector_manager.create(**payload)


@app.post("/api/connectors/test")
def connectors_test(payload: dict[str, Any]) -> dict[str, Any]:
    return connector_manager.test(payload["connector_id"])


@app.post("/api/connectors/enable")
def connectors_enable(payload: dict[str, Any]) -> dict[str, Any]:
    return connector_manager.set_enabled(payload["connector_id"], True)


@app.post("/api/connectors/disable")
def connectors_disable(payload: dict[str, Any]) -> dict[str, Any]:
    return connector_manager.set_enabled(payload["connector_id"], False)


@app.post("/api/connectors/disconnect")
def connectors_disconnect(payload: dict[str, Any]) -> dict[str, Any]:
    return connector_manager.disconnect(payload["connector_id"])


@app.get("/api/telegram/status")
def telegram_status() -> dict[str, Any]:
    return telegram_connector.get_status()


@app.post("/api/telegram/setup")
def telegram_setup(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return telegram_connector.setup(payload.get("bot_token"), payload.get("assigned_agent_slug"), payload.get("permission_mode", "safe"))


@app.post("/api/telegram/test")
def telegram_test() -> dict[str, Any]:
    return telegram_connector.test_connection()


@app.post("/api/telegram/enable")
def telegram_enable() -> dict[str, Any]:
    return telegram_connector.enable()


@app.post("/api/telegram/disable")
def telegram_disable() -> dict[str, Any]:
    return telegram_connector.disable()


@app.post("/api/telegram/disconnect")
def telegram_disconnect() -> dict[str, Any]:
    return telegram_connector.disconnect()


@app.post("/api/telegram/webhook")
def telegram_webhook(payload: dict[str, Any], x_telegram_secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token")) -> dict[str, Any]:
    return _telegram_webhook(payload, x_telegram_secret)


@app.post("/api/connectors/telegram/webhook")
def telegram_connector_webhook(payload: dict[str, Any], x_telegram_secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token")) -> dict[str, Any]:
    return _telegram_webhook(payload, x_telegram_secret)


@app.get("/api/telegram/messages")
def telegram_messages() -> list[dict[str, Any]]:
    return telegram_connector.list_messages()


@app.get("/api/telegram/drafts")
def telegram_drafts() -> list[dict[str, Any]]:
    return telegram_connector.list_drafts()


@app.post("/api/telegram/drafts/{draft_id}/approve")
def telegram_draft_approve(draft_id: str) -> dict[str, Any]:
    return telegram_connector.approve_draft(draft_id)


@app.post("/api/telegram/drafts/{draft_id}/reject")
def telegram_draft_reject(draft_id: str) -> dict[str, Any]:
    return telegram_connector.reject_draft(draft_id)


@app.post("/api/telegram/drafts/{draft_id}/send-approved")
def telegram_draft_send_approved(draft_id: str) -> dict[str, Any]:
    return telegram_connector.send_approved(draft_id)


def _telegram_webhook(payload: dict[str, Any], secret_header: str | None = None) -> dict[str, Any]:
    import os

    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if expected and secret_header != expected:
        return {"status": "forbidden", "code": 403, "message": "Invalid Telegram webhook secret."}
    return telegram_connector.process_update(payload)


@app.get("/api/connectors/social")
def social_connectors() -> list[dict[str, Any]]:
    return list_social_connectors()


@app.get("/api/connectors/webhook")
def webhook_connector_info() -> dict[str, Any]:
    return webhook_connector.describe()


@app.post("/api/webhooks/receive/{source}")
def webhook_receive(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    return webhook_connector.receive(source, payload)


@app.get("/api/email/connectors")
def email_connectors() -> list[dict[str, Any]]:
    return list_email_connectors()


@app.get("/api/email/gmail/status")
def gmail_status() -> dict[str, Any]:
    return get_email_connector("gmail").get_status()


@app.post("/api/email/gmail/setup")
def gmail_setup_new() -> dict[str, Any]:
    return get_email_connector("gmail").setup()


@app.post("/api/email/gmail/oauth/start")
def gmail_oauth_start() -> dict[str, Any]:
    return get_email_connector("gmail").start_oauth()


@app.get("/api/email/gmail/oauth/callback")
def gmail_oauth_callback(code: str = "", state: str | None = None) -> dict[str, Any]:
    return get_email_connector("gmail").handle_callback(code, state)


@app.post("/api/email/gmail/disconnect")
def gmail_disconnect() -> dict[str, Any]:
    return get_email_connector("gmail").disconnect()


@app.post("/api/email/gmail/test")
def gmail_test() -> dict[str, Any]:
    return get_email_connector("gmail").test_connection()


@app.post("/api/email/connectors/create")
def create_email_connector(payload: dict[str, Any]) -> dict[str, Any]:
    connector = get_email_connector(payload.get("provider", "gmail"))
    return {"status": "setup_required", "connector": connector.describe()}


@app.post("/api/email/search")
def email_search(payload: dict[str, Any]) -> dict[str, Any]:
    return get_email_connector(payload.get("provider", "gmail")).search_messages(payload.get("query", ""), int(payload.get("max_results", 10)))


@app.post("/api/email/summarize")
def email_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    message_id = payload.get("message_id")
    if message_id:
        return get_email_connector(payload.get("provider", "gmail")).summarize_message(message_id)
    return get_email_connector(payload.get("provider", "gmail")).summarize(payload.get("query"))


@app.post("/api/email/recent")
def email_recent(payload: dict[str, Any]) -> dict[str, Any]:
    return get_email_connector(payload.get("provider", "gmail")).recent_messages(int(payload.get("max_results", 10)))


@app.post("/api/email/read")
def email_read(payload: dict[str, Any]) -> dict[str, Any]:
    return get_email_connector(payload.get("provider", "gmail")).read_message(payload["message_id"])


@app.post("/api/email/draft-reply")
def email_draft_reply(payload: dict[str, Any]) -> dict[str, Any]:
    connector = get_email_connector(payload.get("provider", "gmail"))
    if payload.get("provider", "gmail") == "gmail" and payload.get("message_id"):
        return connector.create_draft_reply(payload.get("message_id"), payload.get("body"), payload.get("tone", "professional"))
    draft = connector.draft_reply(payload.get("message_id", "latest"), payload.get("tone", "professional"))
    saved_draft = email_draft_store.create(draft)
    approval = approval_manager.create("email_send", saved_draft, connector.provider)
    return {"draft": saved_draft, "approval": approval}


@app.post("/api/email/send-approved")
def email_send_approved(payload: dict[str, Any]) -> dict[str, Any]:
    return email_draft_store.mark_send_ready(payload["draft_id"], payload.get("approval_id"))


@app.get("/api/email/drafts")
def email_drafts() -> list[dict[str, Any]]:
    return email_draft_store.list()


@app.get("/api/email/drafts/{draft_id}")
def email_draft_show(draft_id: str) -> dict[str, Any] | None:
    from runtime.db import get_record

    return get_record("email_drafts", draft_id)


@app.post("/api/email/drafts/{draft_id}/approve")
def email_draft_approve(draft_id: str) -> dict[str, Any]:
    return email_draft_store.approve(draft_id)


@app.get("/api/generation/image/providers")
def image_providers() -> list[dict[str, Any]]:
    return image_manager.list_providers()


@app.post("/api/generation/image/generate")
def image_generate(payload: dict[str, Any]) -> dict[str, Any]:
    return image_manager.generate(**payload)


@app.get("/api/generation/image/jobs")
def image_jobs() -> list[dict[str, Any]]:
    return image_manager.list_jobs()


@app.get("/api/generation/image/jobs/{job_id}")
def image_job(job_id: str) -> dict[str, Any] | None:
    return image_manager.get_job(job_id)


@app.post("/api/content/package/create")
def content_package_create(payload: dict[str, Any]) -> dict[str, Any]:
    return content_creator.create_package(**payload)


@app.get("/api/content/packages")
def content_packages() -> list[dict[str, Any]]:
    return content_creator.list_packages()


@app.get("/api/generation/video/providers")
def video_providers() -> list[dict[str, Any]]:
    return video_manager.list_providers()


@app.post("/api/generation/video/generate")
def video_generate(payload: dict[str, Any]) -> dict[str, Any]:
    return video_manager.generate(**payload)


@app.post("/api/generation/video/storyboard")
def video_storyboard(payload: dict[str, Any]) -> dict[str, Any]:
    return video_manager.storyboard(**payload)


@app.get("/api/generation/video/jobs")
def video_jobs() -> list[dict[str, Any]]:
    return video_manager.list_jobs()


@app.get("/api/generation/video/jobs/{job_id}")
def video_job(job_id: str) -> dict[str, Any] | None:
    return video_manager.get_job(job_id)


@app.post("/api/generation/video/jobs/{job_id}/poll")
def video_job_poll(job_id: str) -> dict[str, Any]:
    return video_manager.poll_job(job_id)


@app.post("/api/generation/video/jobs/{job_id}/download")
def video_job_download(job_id: str) -> dict[str, Any]:
    return video_manager.download_job(job_id)


@app.post("/api/generation/video/jobs/{job_id}/cancel")
def video_job_cancel(job_id: str) -> dict[str, Any]:
    return video_manager.cancel_job(job_id)


@app.post("/api/social/campaign/create")
def social_campaign_create(payload: dict[str, Any]) -> dict[str, Any]:
    return social_workflow.create_campaign(**payload)


@app.get("/api/social/campaigns")
def social_campaigns() -> list[dict[str, Any]]:
    return social_workflow.list_campaigns()


@app.get("/api/social/campaigns/{campaign_id}")
def social_campaign(campaign_id: str) -> dict[str, Any] | None:
    return social_workflow.get_campaign(campaign_id)


@app.post("/api/social/campaigns/{campaign_id}/export")
def social_campaign_export(campaign_id: str) -> dict[str, Any]:
    return {
        "campaign_markdown": export_campaign_markdown(campaign_id),
        "calendar_csv": export_content_calendar_csv(campaign_id),
    }


@app.post("/api/social/drafts/create")
def social_drafts_create(payload: dict[str, Any]) -> dict[str, Any]:
    draft = social_workflow.create_draft(**payload)
    approval = approval_manager.create("social_publish", draft, draft["platform"])
    return {"draft": draft, "approval": approval}


@app.get("/api/social/drafts")
def social_drafts() -> list[dict[str, Any]]:
    return social_workflow.list_drafts()


@app.post("/api/social/drafts/{draft_id}/approve")
def social_draft_approve(draft_id: str) -> dict[str, Any]:
    return social_workflow.approve_draft(draft_id)


@app.post("/api/social/drafts/{draft_id}/publish")
def social_draft_publish(draft_id: str) -> dict[str, Any]:
    return social_workflow.publish_draft(draft_id)


@app.get("/api/social/connectors")
def social_connectors() -> list[dict[str, Any]]:
    return [linkedin_connector.get_status(), x_connector.get_status()]


@app.get("/api/social/connectors/{connector_id}")
def social_connector_show(connector_id: str) -> dict[str, Any]:
    if connector_id == "linkedin":
        return linkedin_connector.get_status()
    if connector_id == "x":
        return x_connector.get_status()
    return {"status": "placeholder", "connector_id": connector_id, "message": "Connector is config-ready only."}


@app.post("/api/social/connectors/{connector_id}/enable-publish")
def social_connector_enable_publish(connector_id: str) -> dict[str, Any]:
    return social_workflow.enable_connector_publish(connector_id)


@app.post("/api/social/connectors/{connector_id}/disable-publish")
def social_connector_disable_publish(connector_id: str) -> dict[str, Any]:
    return social_workflow.disable_connector_publish(connector_id)


@app.get("/api/social/linkedin/status")
def social_linkedin_status() -> dict[str, Any]:
    return linkedin_connector.get_status()


@app.post("/api/social/linkedin/setup")
def social_linkedin_setup() -> dict[str, Any]:
    return linkedin_connector.setup()


@app.post("/api/social/linkedin/oauth/start")
def social_linkedin_oauth_start() -> dict[str, Any]:
    return linkedin_connector.start_oauth()


@app.get("/api/social/linkedin/oauth/callback")
def social_linkedin_oauth_callback(code: str, state: str | None = None) -> dict[str, Any]:
    return linkedin_connector.handle_callback(code, state)


@app.post("/api/social/linkedin/test")
def social_linkedin_test() -> dict[str, Any]:
    return linkedin_connector.test_connection()


@app.post("/api/social/linkedin/disconnect")
def social_linkedin_disconnect() -> dict[str, Any]:
    return linkedin_connector.disconnect()


@app.get("/api/social/x/status")
def social_x_status() -> dict[str, Any]:
    return x_connector.get_status()


@app.post("/api/social/x/setup")
def social_x_setup() -> dict[str, Any]:
    return x_connector.setup()


@app.post("/api/social/x/oauth/start")
def social_x_oauth_start() -> dict[str, Any]:
    return x_connector.start_oauth()


@app.get("/api/social/x/oauth/callback")
def social_x_oauth_callback(code: str, state: str | None = None) -> dict[str, Any]:
    return x_connector.handle_callback(code, state)


@app.post("/api/social/x/test")
def social_x_test() -> dict[str, Any]:
    return x_connector.test_connection()


@app.post("/api/social/x/disconnect")
def social_x_disconnect() -> dict[str, Any]:
    return x_connector.disconnect()


@app.post("/api/social/drafts/{draft_id}/publish-approved")
def social_draft_publish_approved(draft_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return social_workflow.publish_approved_draft(draft_id, payload.get("connector_id") or payload.get("connector"), bool(payload.get("confirm_sensitive", False)))


@app.get("/api/approvals")
def approvals() -> list[dict[str, Any]]:
    return approval_manager.list()


@app.post("/api/approvals/{approval_id}/approve")
def approval_approve(approval_id: str) -> dict[str, Any]:
    return approval_manager.decide(approval_id, "approved")


@app.post("/api/approvals/{approval_id}/reject")
def approval_reject(approval_id: str) -> dict[str, Any]:
    return approval_manager.decide(approval_id, "rejected")


@app.post("/api/generation/image/jobs/{job_id}/export")
def image_job_export(job_id: str) -> dict[str, Any]:
    return {"image_prompt_markdown": export_image_prompt_markdown(job_id)}


@app.post("/api/generation/video/jobs/{job_id}/export")
def video_job_export(job_id: str) -> dict[str, Any]:
    return video_manager.export_job(job_id)


@app.get("/api/generation/video/jobs/{job_id}/export")
def video_job_export_get(job_id: str) -> dict[str, Any]:
    return video_manager.export_job(job_id)


@app.post("/api/agents/runs/{run_id}/export")
def agent_run_export(run_id: str) -> dict[str, Any]:
    return {"agent_run_markdown": export_agent_run_markdown(run_id)}


@app.get("/api/automations")
@app.get("/api/automations/")
def automations() -> list[dict[str, Any]]:
    return automation_manager.list()


@app.get("/api/automations/{automation_id}")
def automation_show(automation_id: str) -> dict[str, Any]:
    return automation_manager.show(automation_id)


@app.post("/api/automations/create")
def automation_create(payload: dict[str, Any]) -> dict[str, Any]:
    return automation_manager.create(payload)


@app.post("/api/automations/create-daily")
def automation_create_daily(payload: dict[str, Any]) -> dict[str, Any]:
    return automation_manager.create_daily(payload["name"], payload.get("time_of_day", "09:00"), payload.get("agent_slug", "personal-assistant-agent"), payload["task_prompt"], payload.get("timezone", "Asia/Kolkata"), workspace_name=payload.get("workspace_name", "default"), requires_approval=payload.get("requires_approval", True))


@app.post("/api/automations/create-weekly")
def automation_create_weekly(payload: dict[str, Any]) -> dict[str, Any]:
    return automation_manager.create_weekly(payload["name"], payload.get("day", "monday"), payload.get("time_of_day", "10:00"), payload.get("agent_slug", "content-creator-agent"), payload["task_prompt"], payload.get("timezone", "Asia/Kolkata"), workspace_name=payload.get("workspace_name", "default"), requires_approval=payload.get("requires_approval", True))


@app.post("/api/automations/create-interval")
def automation_create_interval(payload: dict[str, Any]) -> dict[str, Any]:
    return automation_manager.create_interval(payload["name"], int(payload.get("minutes", 60)), payload.get("agent_slug", "personal-assistant-agent"), payload["task_prompt"], workspace_name=payload.get("workspace_name", "default"), requires_approval=payload.get("requires_approval", True))


@app.post("/api/automations/{automation_id}/run")
def automation_run(automation_id: str) -> dict[str, Any]:
    return automation_manager.run(automation_id)


@app.post("/api/automations/{automation_id}/enable")
def automation_enable(automation_id: str) -> dict[str, Any]:
    return automation_manager.set_enabled(automation_id, True)


@app.post("/api/automations/{automation_id}/disable")
def automation_disable(automation_id: str) -> dict[str, Any]:
    return automation_manager.set_enabled(automation_id, False)


@app.get("/api/automations/{automation_id}/history")
def automation_history(automation_id: str) -> list[dict[str, Any]]:
    return automation_manager.history(automation_id)


@app.delete("/api/automations/{automation_id}")
def automation_delete(automation_id: str) -> dict[str, Any]:
    return automation_manager.delete(automation_id)


@app.get("/api/scheduler/status")
def scheduler_status() -> dict[str, Any]:
    return scheduler_engine.status()


@app.get("/api/scheduler/due")
def scheduler_due() -> list[dict[str, Any]]:
    return scheduler_engine.list_due()


@app.post("/api/scheduler/tick")
def scheduler_tick() -> dict[str, Any]:
    return scheduler_engine.tick()


@app.post("/api/scheduler/run-due")
def scheduler_run_due(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return scheduler_engine.run_due(limit=int(payload.get("limit", 5)))


@app.get("/api/scheduler/runs")
def scheduler_runs() -> list[dict[str, Any]]:
    return scheduler_engine.runs()


@app.get("/api/scheduler/runs/{run_id}")
def scheduler_run_show(run_id: str) -> dict[str, Any]:
    return scheduler_engine.run_show(run_id)


@app.get("/api/skills/available")
def skills_available() -> list[dict[str, Any]]:
    return SkillManager().available_skills()


@app.get("/api/skills/installed")
def skills_installed() -> list[dict[str, Any]]:
    return SkillManager().list()


@app.post("/api/skills/install")
def skills_install(payload: dict[str, Any]) -> dict[str, Any]:
    return SkillManager().install(payload["skill_name"])


@app.post("/api/skills/enable")
def skills_enable(payload: dict[str, Any]) -> dict[str, Any]:
    return SkillManager().set_enabled(payload["skill_name"], True)


@app.post("/api/skills/disable")
def skills_disable(payload: dict[str, Any]) -> dict[str, Any]:
    return SkillManager().set_enabled(payload["skill_name"], False)


@app.post("/api/skills/uninstall")
def skills_uninstall(payload: dict[str, Any]) -> dict[str, Any]:
    return SkillManager().uninstall(payload["skill_name"])


@app.get("/api/workspaces")
def workspaces() -> list[dict[str, Any]]:
    return WorkspaceManager().list()


@app.post("/api/workspaces/create")
def workspace_create(payload: dict[str, Any]) -> dict[str, Any]:
    return WorkspaceManager().create(payload["name"], payload.get("path"))


@app.post("/api/workspaces/default")
def workspace_default(payload: dict[str, Any]) -> dict[str, Any]:
    return WorkspaceManager().set_default(payload["name"])


@app.get("/api/workspaces/{name}")
def workspace_show(name: str) -> dict[str, Any]:
    return WorkspaceManager().show(name)


@app.get("/api/exports")
def exports() -> list[dict[str, Any]]:
    return ExportTracker().list()


@app.get("/api/exports/{export_id}")
def export_show(export_id: str) -> dict[str, Any]:
    return ExportTracker().show(export_id)


@app.get("/api/onboarding/status")
def onboarding_status() -> dict[str, Any]:
    return OnboardingManager().status()


@app.post("/api/onboarding/complete-step")
def onboarding_complete_step(payload: dict[str, Any]) -> dict[str, Any]:
    return OnboardingManager().complete_step(payload["step"])


@app.post("/api/onboarding/reset")
def onboarding_reset() -> dict[str, Any]:
    return OnboardingManager().reset()


@app.get("/api/release/status")
def release_status() -> dict[str, Any]:
    return {
        "version": release_manager.version(),
        "desktop": release_manager.desktop_status(),
        "signing": release_manager.signing_status(),
        "update": release_manager.update_info(),
        "paths": release_manager.paths(),
    }


@app.get("/api/release/desktop-report")
def api_release_desktop_report() -> dict[str, Any]:
    return release_manager.release_desktop_report()


@app.get("/api/release/unsigned-artifacts")
def api_release_unsigned_artifacts() -> dict[str, Any]:
    return release_manager.unsigned_artifacts()


@app.get("/api/release/verify-artifacts")
def api_release_verify_artifacts() -> dict[str, Any]:
    return release_manager.verify_artifacts()


@app.post("/api/release/check")
def api_release_check(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return release_manager.release_check(run_tests=not bool(payload.get("skip_tests")))


@app.get("/api/desktop/status")
def api_desktop_status() -> dict[str, Any]:
    return release_manager.desktop_status()


@app.post("/api/desktop/check")
def api_desktop_check() -> dict[str, Any]:
    return release_manager.desktop_check()


@app.get("/api/desktop/native-check")
def api_desktop_native_check() -> dict[str, Any]:
    return release_manager.native_check()


@app.get("/api/desktop/rust-check")
def api_desktop_rust_check() -> dict[str, Any]:
    return release_manager.rust_check()


@app.get("/api/desktop/tauri-check")
def api_desktop_tauri_check() -> dict[str, Any]:
    return release_manager.tauri_check()


@app.get("/api/desktop/icons-check")
def api_desktop_icons_check() -> dict[str, Any]:
    return release_manager.icons_check()


@app.post("/api/desktop/icons-generate")
def api_desktop_icons_generate() -> dict[str, Any]:
    return release_manager.icons_generate()


@app.get("/api/desktop/build-guide")
def api_desktop_build_guide() -> dict[str, Any]:
    return release_manager.build_guide()


@app.get("/api/desktop/build-report")
def api_desktop_build_report() -> dict[str, Any]:
    return release_manager.build_report()


@app.get("/api/desktop/backend-status")
def api_desktop_backend_status() -> dict[str, Any]:
    return release_manager.desktop_backend_status()


@app.post("/api/desktop/backend-mode")
def api_desktop_backend_mode(payload: dict[str, Any]) -> dict[str, Any]:
    return release_manager.set_desktop_backend_mode(payload.get("mode", "external_backend"))


@app.get("/api/signing/status")
def api_signing_status() -> dict[str, Any]:
    return release_manager.signing_status()


@app.post("/api/signing/check")
def api_signing_check() -> dict[str, Any]:
    return release_manager.signing_check()


@app.get("/api/signing/macos-status")
def api_signing_macos_status() -> dict[str, Any]:
    return release_manager.signing_macos_status()


@app.get("/api/signing/macos-guide")
def api_signing_macos_guide() -> dict[str, Any]:
    return release_manager.signing_macos_guide()


@app.get("/api/signing/macos-export-env-template")
def api_signing_macos_export_env_template() -> dict[str, Any]:
    return release_manager.signing_macos_export_env_template()


@app.get("/api/signing/macos-preflight")
def api_signing_macos_preflight() -> dict[str, Any]:
    return release_manager.signing_macos_preflight()


@app.post("/api/signing/macos-sign")
def api_signing_macos_sign(payload: dict[str, Any]) -> dict[str, Any]:
    return release_manager.signing_macos_sign(
        artifact_path=payload.get("artifact_path"),
        dry_run=payload.get("dry_run", True),
        confirm=payload.get("confirm", False),
    )


@app.post("/api/signing/macos-notarize")
def api_signing_macos_notarize(payload: dict[str, Any]) -> dict[str, Any]:
    return release_manager.signing_macos_notarize(
        artifact_path=payload.get("artifact_path"),
        dry_run=payload.get("dry_run", True),
        confirm=payload.get("confirm", False),
    )


@app.get("/api/update/info")
def api_update_info() -> dict[str, Any]:
    return release_manager.update_info()
