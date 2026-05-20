"""FastAPI app for Liuant Agentic OS MVP.

Run with: uvicorn runtime.api.app:app --reload
"""

from __future__ import annotations

import json
from typing import Any

try:
    from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:
    class FastAPI:
        """Development fallback so route definitions remain inspectable before install."""

        def __init__(self, title: str, version: str) -> None:
            self.title = title
            self.version = version
            self.routes: list[Any] = []

        def _route(self, method: str, path: str):
            class _Route:
                def __init__(self, m: str, p: str, n: str) -> None:
                    self.method = m
                    self.path = p
                    self.name = n
            def decorator(func):
                self.routes.append(_Route(method, path, func.__name__))
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

        def websocket(self, path: str):
            return self._route("WS", path)
    CORSMiddleware = None
    def Header(default: Any = None, alias: str | None = None) -> Any:
        return default
    HTTPException = Exception
    Request = Any
    WebSocket = Any
    WebSocketDisconnect = Exception

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

app = FastAPI(title="Liuant Agentic OS", version="3.0.0")
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


@app.post("/api/chat/discussion-stream")
def chat_discussion_stream(payload: dict[str, Any]):
    """Stream discussion mode response using Server-Sent Events."""
    from fastapi.responses import StreamingResponse
    message = payload.get("message", "")
    if not message:
        return {"status": "error", "message": "No message provided."}
    roles = payload.get("roles")
    rounds = int(payload.get("rounds", 2))
    final_role = payload.get("final_role", "thinking")

    def event_stream():
        from runtime.chat.discussion import stream_discussion
        for chunk in stream_discussion(user_message=message, roles=roles, rounds=rounds, final_role=final_role):
            yield f"event: {chunk['type']}\ndata: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/chat/stream")
def chat_stream(payload: dict[str, Any]):
    """Stream chat response using Server-Sent Events."""
    from fastapi.responses import StreamingResponse
    message = payload.get("message", "")
    if not message:
        return {"status": "error", "message": "No message provided."}
    provider_name = payload.get("provider")
    model = payload.get("model")
    role = payload.get("role")

    def event_stream():
        hub = ModelHub()
        for chunk in hub.stream_text(
            prompt=message,
            provider_name=provider_name,
            model=model,
            role=role,
        ):
            yield f"event: {chunk['type']}\ndata: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/models/stream")
def models_stream(payload: dict[str, Any]):
    """Stream text generation from a specific provider."""
    from fastapi.responses import StreamingResponse
    prompt = payload.get("prompt", "")
    if not prompt:
        return {"status": "error", "message": "No prompt provided."}
    provider_name = payload.get("provider")
    model = payload.get("model")
    role = payload.get("role", "default")

    def event_stream():
        hub = ModelHub()
        for chunk in hub.stream_text(
            prompt=prompt,
            provider_name=provider_name,
            model=model,
            role=role,
        ):
            yield f"event: {chunk['type']}\ndata: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/agents/{agent_slug}/stream")
def agent_stream(agent_slug: str, payload: dict[str, Any]):
    """Stream agent run response."""
    from fastapi.responses import StreamingResponse
    from runtime.agents import AgentRunner
    from runtime.model_router import get_model_for_role
    from runtime.model_roles import ModelRoleManager

    prompt = payload.get("prompt", "")
    if not prompt:
        return {"status": "error", "message": "No prompt provided."}
    model_role = payload.get("model_role")

    rm = ModelRoleManager()
    role = model_role or "default"
    model_cfg = get_model_for_role(role, rm)

    def event_stream():
        hub = ModelHub()
        yield f"event: metadata\ndata: {json.dumps({'agent_slug': agent_slug, 'role': role, 'provider': model_cfg.get('provider', ''), 'model': model_cfg.get('model', '')})}\n\n"
        if model_cfg["configured"]:
            for chunk in hub.stream_text(
                prompt=prompt,
                provider_name=model_cfg["provider"],
                model=model_cfg["model"],
                role=role,
            ):
                yield f"event: {chunk['type']}\ndata: {json.dumps(chunk)}\n\n"
        else:
            yield f"event: warning\ndata: {json.dumps({'content': f'Role {role} not configured. Configure in Settings > Model Roles.'})}\n\n"
            yield f"event: done\ndata: {json.dumps({'status': 'not_configured'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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


@app.get("/api/usage/summary")
def usage_summary(workspace: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_summary(workspace=workspace)


@app.get("/api/usage/today")
def usage_today(workspace: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_today(workspace=workspace)


@app.get("/api/usage/by-provider")
def usage_by_provider(workspace: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_by_provider(workspace=workspace)


@app.get("/api/usage/by-role")
def usage_by_role(workspace: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_by_role(workspace=workspace)


@app.post("/api/usage/reset")
def usage_reset(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    if payload.get("confirm") != "true":
        return {"status": "error", "message": "Set confirm=true to reset usage data."}
    return UsageTracker().reset()


@app.post("/api/usage/record")
def usage_record(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().record_usage(
        provider=payload.get("provider", ""),
        model=payload.get("model", ""),
        model_role=payload.get("model_role", "default"),
        feature=payload.get("feature", "chat"),
        estimated_input_tokens=int(payload.get("estimated_input_tokens", 0)),
        estimated_output_tokens=int(payload.get("estimated_output_tokens", 0)),
        estimated_total_tokens=int(payload.get("estimated_total_tokens", 0)),
        estimated_cost=float(payload.get("estimated_cost", 0.0)),
        estimated=payload.get("estimated", True),
        fallback_used=payload.get("fallback_used", False),
        status=payload.get("status", "completed"),
        discussion_id=payload.get("discussion_id"),
    )


@app.get("/api/usage/budget")
def usage_budget() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_budget()


@app.post("/api/usage/budget")
def usage_budget_set(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().set_budget(**{k: v for k, v in payload.items() if k in (
        "daily_estimated_cost_limit", "monthly_estimated_cost_limit",
        "per_provider_limit", "per_role_limit",
        "discussion_mode_cost_warning_threshold", "cloud_model_warning_enabled",
        "budget_blocking_enabled",
    )})


@app.post("/api/usage/budget-reset")
def usage_budget_reset() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().reset_budget()


@app.get("/api/usage/alerts")
def usage_alerts() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().check_budget_alerts()


@app.post("/api/usage/export")
def usage_export(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    fmt = payload.get("format", "csv")
    return UsageTracker().export_usage(fmt=fmt)


@app.get("/api/usage/anomalies")
def usage_anomalies() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().detect_anomalies()


@app.get("/api/usage/trends")
def usage_trends(days: int = 7, period: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    if period == "monthly":
        return tracker.get_monthly_trends()
    return tracker.get_trends(days=days)


@app.get("/api/usage/alerts/history")
def usage_alerts_history(include_dismissed: bool = False) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    return {"alerts": tracker.get_alert_history(include_dismissed=include_dismissed)}


@app.post("/api/usage/alerts/{alert_id}/dismiss")
def usage_alert_dismiss(alert_id: str) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().dismiss_alert(alert_id)


@app.post("/api/usage/export")
def usage_export(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    fmt = payload.get("format", "csv")
    workspace = payload.get("workspace")
    return UsageTracker().export_usage(fmt=fmt, workspace=workspace)


@app.get("/api/usage/webhook/status")
def webhook_status() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_webhook_status()


@app.post("/api/usage/webhook/set-url")
def webhook_set_url(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().set_webhook_url(payload.get("url", ""), confirm=payload.get("confirm") == "true")


@app.post("/api/usage/webhook/test")
def webhook_test(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().send_webhook_test(event_type=payload.get("event_type", "budget_warning"))


@app.post("/api/usage/webhook/enable")
def webhook_enable(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().enable_webhooks(confirm=payload.get("confirm") == "true")


@app.post("/api/usage/webhook/disable")
def webhook_disable() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().disable_webhooks()


@app.post("/api/usage/webhook/send-test")
def webhook_send_test(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage.webhooks import WebhookDelivery
    return WebhookDelivery().send_test(event_type=payload.get("event_type", "budget_warning"))


@app.get("/api/usage/webhook/delivery-history")
def webhook_delivery_history(limit: int = 50) -> dict[str, Any]:
    from runtime.usage.webhooks import WebhookDelivery
    return {"deliveries": WebhookDelivery().get_delivery_history(limit=limit)}


@app.post("/api/usage/webhook/retry-failed")
def webhook_retry_failed(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage.webhooks import WebhookDelivery
    if payload.get("confirm") != "true":
        return {"status": "error", "message": "Retry requires confirm=true."}
    return WebhookDelivery().retry_failed()


@app.post("/api/usage/webhook/signature-test")
def webhook_signature_test() -> dict[str, Any]:
    from runtime.usage.webhooks import WebhookDelivery
    delivery = WebhookDelivery()
    payload_json = '{"event_type":"test","workspace":"default","level":"info","message":"HMAC signature test","timestamp":"test","source":"liuant-agentic-os"}'
    headers = delivery._build_signature_headers(payload_json, "signature_test")
    has_signature = "X-Liuant-Signature" in headers
    has_timestamp = "X-Liuant-Timestamp" in headers
    return {
        "hmac_enabled": delivery._is_hmac_enabled(),
        "has_signature_header": has_signature,
        "has_timestamp_header": has_timestamp,
        "message": "HMAC signature test complete." if has_signature else "HMAC not enabled or secret not set.",
    }


@app.post("/api/usage/webhook/rotate-secret")
def webhook_rotate_secret(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.config import SettingsManager
    from runtime.usage import UsageTracker
    if payload.get("confirm") != "true":
        return {"status": "error", "message": "Rotating webhook secret requires confirm=true."}
    import secrets
    new_secret = secrets.token_hex(32)
    UsageTracker().settings.set("webhook_secret", new_secret)
    return {"status": "rotated", "message": "Webhook HMAC secret rotated. Update your receiver verification."}


@app.get("/api/usage/discussion-costs/{discussion_id}")
def discussion_costs_by_id(discussion_id: str, rounds: bool = True) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_discussion_costs_by_round(discussion_id=discussion_id, rounds=rounds)


@app.get("/api/usage/discussion-costs/latest")
def discussion_costs_latest(workspace: str | None = None, rounds: bool = True) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    costs = UsageTracker().get_discussion_costs_by_round(workspace=workspace, latest=True, rounds=rounds)
    discussions = costs.get("discussions", [])
    return {"latest": discussions[0] if discussions else None, "total_cost": costs["total_cost"], "total_tokens": costs["total_tokens"]}


@app.get("/api/usage/cleanup-scheduler/status")
def cleanup_scheduler_status() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_cleanup_scheduler_status()


@app.post("/api/usage/cleanup-scheduler/enable")
def cleanup_scheduler_enable(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().enable_cleanup_scheduler(confirm=payload.get("confirm") == "true")


@app.post("/api/usage/cleanup-scheduler/disable")
def cleanup_scheduler_disable() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().disable_cleanup_scheduler()


@app.post("/api/usage/cleanup-scheduler/run-now")
def cleanup_scheduler_run_now(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    dry_run = payload.get("dry_run", False)
    confirm = payload.get("confirm", False)
    export_before = payload.get("export_before", True)
    return UsageTracker().run_cleanup_now(dry_run=dry_run, confirm=confirm, export_before=export_before)


@app.get("/api/usage/discussion-costs")
def discussion_costs(workspace: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_discussion_costs(workspace=workspace)


@app.get("/api/usage/discussion-costs/latest")
def discussion_costs_latest(workspace: str | None = None) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    costs = UsageTracker().get_discussion_costs(workspace=workspace)
    discussions = costs.get("discussions", [])
    return {"latest": discussions[0] if discussions else None, "total_cost": costs["total_cost"], "total_tokens": costs["total_tokens"]}


@app.get("/api/usage/retention")
def usage_retention() -> dict[str, Any]:
    from runtime.usage import UsageTracker
    return UsageTracker().get_retention()


@app.post("/api/usage/retention")
def usage_retention_set(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    days = int(payload.get("days", 90))
    return UsageTracker().set_retention(days=days)


@app.get("/api/usage/cleanup")
def usage_cleanup(dry_run: bool = True) -> dict[str, Any]:
    from runtime.usage import UsageTracker
    if dry_run:
        return UsageTracker().cleanup_dry_run()
    return UsageTracker().cleanup_confirm()
def models_provider_health() -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().get_all_health()


@app.get("/api/models/provider-health/{provider}")
def models_provider_health_one(provider: str) -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().get_health(provider)


@app.post("/api/models/provider-health/{provider}/record-success")
def models_provider_health_success(provider: str) -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().record_success(provider)


@app.post("/api/models/provider-health/{provider}/record-error")
def models_provider_health_error(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().record_error(provider, payload.get("error", ""))


@app.post("/api/models/provider-health/{provider}/record-timeout")
def models_provider_health_timeout(provider: str) -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().record_timeout(provider)


@app.post("/api/models/provider-health/{provider}/record-rate-limit")
def models_provider_health_rate_limit(provider: str) -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().record_rate_limit(provider)


@app.post("/api/models/provider-health/{provider}/reset")
def models_provider_health_reset(provider: str) -> dict[str, Any]:
    from runtime.usage.provider_health import ProviderHealthTracker
    return ProviderHealthTracker().reset_health(provider)


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


@app.get("/api/skills")
def skills_list() -> dict[str, Any]:
    from runtime.skills import list_installed_skills
    return {"skills": list_installed_skills()}


@app.get("/api/skills/{skill_id}")
def skills_get(skill_id: str) -> dict[str, Any]:
    from runtime.skills import get_skill
    skill = get_skill(skill_id)
    if not skill:
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}
    return skill


@app.post("/api/skills/validate")
def skills_validate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills.validator import validate_skill
    path = payload.get("path", "")
    if not path:
        return {"status": "error", "message": "Path required"}
    return validate_skill(path)


@app.post("/api/skills/install")
def skills_install(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import install_skill
    path = payload.get("path", "")
    if not path:
        return {"status": "error", "message": "Path required"}
    return install_skill(path, upgrade=payload.get("upgrade", False))


@app.post("/api/skills/{skill_id}/enable")
def skills_enable(skill_id: str) -> dict[str, Any]:
    from runtime.skills import enable_skill
    return enable_skill(skill_id)


@app.post("/api/skills/{skill_id}/disable")
def skills_disable(skill_id: str) -> dict[str, Any]:
    from runtime.skills import disable_skill
    return disable_skill(skill_id)


@app.post("/api/skills/{skill_id}/uninstall")
def skills_uninstall(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import uninstall_skill
    return uninstall_skill(skill_id, confirm=payload.get("confirm", False))


@app.get("/api/skills/{skill_id}/permissions")
def skills_permissions(skill_id: str) -> dict[str, Any]:
    from runtime.skills import skill_permissions
    return skill_permissions(skill_id)


@app.post("/api/skills/{skill_id}/approve-permissions")
def skills_approve_permissions(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import approve_skill_permissions
    perms = payload.get("permissions", [])
    return approve_skill_permissions(skill_id, perms, confirm=payload.get("confirm", False))


@app.post("/api/skills/{skill_id}/run")
def skills_run(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import run_skill
    inputs = payload.get("inputs", {})
    dry_run = payload.get("dry_run", True)
    return run_skill(skill_id, inputs, dry_run=dry_run)


@app.get("/api/skills/templates")
def skills_templates() -> dict[str, Any]:
    from runtime.skills import get_skill_templates
    return {"templates": get_skill_templates()}


@app.get("/api/skills/search")
def skills_search(q: str = "") -> dict[str, Any]:
    from runtime.skills import search_skills
    return {"results": search_skills(q)}


@app.post("/api/skills/discover")
def skills_discover(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import discover_skills
    paths = payload.get("paths", None)
    return {"discovered": discover_skills(paths)}


@app.post("/api/skills/create")
def skills_create(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import create_skill_from_template
    template_id = payload.get("template_id", "")
    new_id = payload.get("id", "")
    name = payload.get("name", new_id)
    if not template_id or not new_id:
        return {"status": "error", "message": "template_id and id required"}
    return create_skill_from_template(template_id, new_id, name)


@app.post("/api/skills/upgrade")
def skills_upgrade(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import upgrade_skill
    path = payload.get("path", "")
    if not path:
        return {"status": "error", "message": "path required"}
    return upgrade_skill(path, confirm=payload.get("confirm", False), force=payload.get("force", False))


@app.get("/api/skills/audit")
def skills_audit(skill_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    from runtime.skills import get_audit_logs
    return {"audit_logs": get_audit_logs(skill_id, limit)}


@app.get("/api/skills/{skill_id}/audit")
def skills_skill_audit(skill_id: str) -> dict[str, Any]:
    from runtime.skills import get_audit_logs, get_latest_audit
    return {"latest": get_latest_audit(skill_id), "logs": get_audit_logs(skill_id)}


@app.post("/api/skills/{skill_id}/run-dry")
def skills_run_dry(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import run_skill
    inputs = payload.get("inputs", {})
    return run_skill(skill_id, inputs, dry_run=True)


@app.post("/api/skills/packs/validate")
def packs_validate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import validate_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return validate_pack(pack_path)


@app.post("/api/skills/packs/inspect")
def packs_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import inspect_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return inspect_pack(pack_path)


@app.post("/api/skills/packs/import")
def packs_import(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import import_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return import_pack(pack_path, install=payload.get("install", False))


@app.post("/api/skills/packs/install")
def packs_install(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import install_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    selected = payload.get("skills")
    selected_skills = selected if isinstance(selected, list) else None
    return install_pack(pack_path, selected_skills)


@app.get("/api/skills/packs")
def packs_list() -> dict[str, Any]:
    from runtime.skills import list_imported_packs
    return {"packs": list_imported_packs()}


@app.get("/api/skills/packs/{pack_id}")
def packs_get(pack_id: str) -> dict[str, Any]:
    from runtime.skills import pack_status
    return pack_status(pack_id)


@app.post("/api/skills/packs/{pack_id}/remove")
def packs_remove(pack_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import remove_pack
    return remove_pack(pack_id, confirm=payload.get("confirm", False))


@app.get("/api/skills/catalog")
def catalog_get() -> dict[str, Any]:
    from runtime.skills import _load_catalog
    return _load_catalog()


@app.post("/api/skills/catalog/refresh")
def catalog_refresh() -> dict[str, Any]:
    from runtime.skills import refresh_catalog
    return refresh_catalog()


@app.get("/api/skills/catalog/search")
def catalog_search(q: str = "") -> dict[str, Any]:
    from runtime.skills import search_catalog
    return {"results": search_catalog(q)}


@app.post("/api/skills/catalog/install")
def catalog_install(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import catalog_install as _catalog_install
    pack_id = payload.get("pack_id", "")
    if not pack_id:
        return {"status": "error", "message": "pack_id required"}
    return _catalog_install(pack_id)


@app.post("/api/skills/packs/dependencies")
def packs_dependencies(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import resolve_pack_dependencies
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return resolve_pack_dependencies(pack_path)


@app.post("/api/skills/packs/install-plan")
def packs_install_plan(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import dependency_install_plan
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return dependency_install_plan(pack_path)


@app.post("/api/skills/packs/diff")
def packs_diff(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import diff_packs
    old_path = payload.get("old_path", "")
    new_path = payload.get("new_path", "")
    if not old_path or not new_path:
        return {"status": "error", "message": "old_path and new_path required"}
    return diff_packs(old_path, new_path, include_files=payload.get("include_files", False))


@app.post("/api/skills/packs/preview-install")
def packs_preview_install(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import preview_install
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return preview_install(pack_path)


@app.post("/api/skills/packs/upgrade")
def packs_upgrade(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import upgrade_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return upgrade_pack(pack_path, confirm=payload.get("confirm", False), force=payload.get("force", False))


@app.post("/api/skills/packs/upgrade-plan")
def packs_upgrade_plan(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import upgrade_plan
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return upgrade_plan(pack_path)


@app.post("/api/skills/packs/rollback")
def packs_rollback(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import rollback_pack
    pack_id = payload.get("pack_id", "")
    if not pack_id:
        return {"status": "error", "message": "pack_id required"}
    return rollback_pack(pack_id, confirm=payload.get("confirm", False))


@app.post("/api/skills/packs/verify")
def packs_verify(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import verify_pack_signature
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return verify_pack_signature(pack_path)


@app.post("/api/skills/packs/trust-status")
def packs_trust_status(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import get_trust_state
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return get_trust_state(pack_path)


@app.post("/api/skills/packs/sign")
def packs_sign(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import sign_pack
    source_path = payload.get("source_path", "")
    key_id = payload.get("key_id", "")
    if not source_path or not key_id:
        return {"status": "error", "message": "source_path and key_id required"}
    return sign_pack(source_path, key_id)


@app.post("/api/skills/packs/encode")
def packs_encode(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import encode_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return encode_pack(pack_path)


@app.post("/api/skills/packs/decode")
def packs_decode(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import decode_pack
    encoded_path = payload.get("encoded_path", "")
    if not encoded_path:
        return {"status": "error", "message": "encoded_path required"}
    return decode_pack(encoded_path)


@app.post("/api/skills/packs/import-base64")
def packs_import_base64(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import import_base64_pack
    encoded_path = payload.get("encoded_path", "")
    if not encoded_path:
        return {"status": "error", "message": "encoded_path required"}
    return import_base64_pack(encoded_path)


@app.get("/api/skills/packs/analytics")
def packs_analytics(pack_id: str = "") -> dict[str, Any]:
    from runtime.skills import get_pack_analytics
    return get_pack_analytics(pack_id if pack_id else None)


@app.get("/api/skills/packs/{pack_id}/analytics")
def packs_pack_analytics(pack_id: str) -> dict[str, Any]:
    from runtime.skills import get_pack_analytics
    return get_pack_analytics(pack_id)


@app.get("/api/skills/keys")
def keys_list() -> dict[str, Any]:
    from runtime.skills import list_keys
    return {"keys": list_keys()}


@app.post("/api/skills/keys/generate")
def keys_generate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import generate_key
    name = payload.get("name", "local-maintainer")
    return generate_key(name)


@app.post("/api/skills/keys/{key_id}/trust")
def keys_trust(key_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import trust_key
    return trust_key(key_id, confirm=payload.get("confirm", False))


@app.post("/api/skills/keys/{key_id}/untrust")
def keys_untrust(key_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import untrust_key
    return untrust_key(key_id, confirm=payload.get("confirm", False))


@app.get("/api/skills/workflows")
def workflows_list() -> dict[str, Any]:
    from runtime.skills import list_workflows
    return {"workflows": list_workflows()}


@app.post("/api/skills/workflows/discover")
def workflows_discover(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import discover_workflows
    paths = payload.get("paths", [])
    return discover_workflows(paths)


@app.post("/api/skills/workflows/validate")
def workflows_validate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import validate_workflow
    wf_path = payload.get("path", "")
    wf_id = payload.get("workflow_id")
    if not wf_path and not wf_id:
        return {"status": "error", "message": "Workflow path or workflow_id required"}
    if wf_id:
        return validate_workflow(workflow_id=wf_id)
    return validate_workflow(wf_path)


@app.post("/api/skills/workflows/inspect")
def workflows_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import inspect_workflow
    wf_path = payload.get("path", "")
    if not wf_path:
        return {"status": "error", "message": "Workflow path required"}
    return inspect_workflow(wf_path)


@app.post("/api/skills/workflows/run")
def workflows_run(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import run_workflow
    wf_path = payload.get("path", "")
    if not wf_path:
        return {"status": "error", "message": "Workflow path required"}
    inputs = payload.get("inputs", {})
    dry_run = payload.get("dry_run", True)
    return run_workflow(wf_path, inputs=inputs, dry_run=dry_run)


@app.post("/api/skills/workflows/register")
def workflows_register(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import register_workflow
    wf_path = payload.get("path", "")
    if not wf_path:
        return {"status": "error", "message": "Workflow path required"}
    return register_workflow(wf_path)


@app.post("/api/skills/compatibility/check")
def compatibility_check(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import check_compatibility
    pack_path = payload.get("pack_path", "")
    pack_id = payload.get("pack_id", "")
    if not pack_path and not pack_id:
        return {"status": "error", "message": "pack_path or pack_id required"}
    return check_compatibility(pack_path=pack_path if pack_path else None, pack_id=pack_id if pack_id else None)


@app.get("/api/skills/compatibility/check-all")
def compatibility_check_all() -> dict[str, Any]:
    from runtime.skills import check_all_installed_compatibility
    return check_all_installed_compatibility()


@app.post("/api/skills/compatibility/save")
def compatibility_save() -> dict[str, Any]:
    from runtime.skills import save_compatibility_matrix
    return save_compatibility_matrix()


@app.get("/api/skills/compatibility/load")
def compatibility_load() -> dict[str, Any]:
    from runtime.skills import load_compatibility_matrix
    return load_compatibility_matrix()


@app.post("/api/skills/lint")
def skills_lint(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import lint_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    strict = payload.get("strict", False)
    return lint_pack(pack_path, strict=strict)


@app.post("/api/skills/changelog/generate")
def changelog_generate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import generate_changelog
    old_path = payload.get("old_path", "")
    new_path = payload.get("new_path", "")
    if not old_path or not new_path:
        return {"status": "error", "message": "old_path and new_path required"}
    return generate_changelog(old_path, new_path)


@app.get("/api/skills/changelog/{pack_id}")
def changelog_from_registry(pack_id: str) -> dict[str, Any]:
    from runtime.skills import generate_changelog_from_registry
    return generate_changelog_from_registry(pack_id)


@app.post("/api/skills/url-import/preview")
def url_import_preview(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import preview_url_import
    url = payload.get("url", "")
    if not url:
        return {"status": "error", "message": "URL required"}
    return preview_url_import(url)


@app.post("/api/skills/url-import/import")
def url_import(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import import_from_url
    url = payload.get("url", "")
    if not url:
        return {"status": "error", "message": "URL required"}
    install = payload.get("install", False)
    return import_from_url(url, install=install)


@app.get("/api/skills/url-import/staged")
def url_import_staged() -> dict[str, Any]:
    from runtime.skills import list_staged_packs
    return {"staged": list_staged_packs()}


@app.post("/api/skills/url-import/clear")
def url_import_clear() -> dict[str, Any]:
    from runtime.skills import clear_staging
    return clear_staging()


@app.get("/api/skills/recommendations")
def recommendations_get(query: str = "", limit: int = 5) -> dict[str, Any]:
    from runtime.skills import get_recommendations
    return get_recommendations(query=query, limit=limit)


@app.post("/api/skills/recommendations/packs")
def recommendations_packs(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import recommend_packs
    limit = payload.get("limit", 5)
    return {"recommendations": recommend_packs(limit=limit)}


@app.post("/api/skills/recommendations/workflow")
def recommendations_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import recommend_skills_for_workflow
    workflow_id = payload.get("workflow_id", "")
    if not workflow_id:
        return {"status": "error", "message": "workflow_id required"}
    return recommend_skills_for_workflow(workflow_id)


@app.post("/api/skills/recommendations/alternatives")
def recommendations_alternatives(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import recommend_low_risk_alternatives
    pack_id = payload.get("pack_id", "")
    if not pack_id:
        return {"status": "error", "message": "pack_id required"}
    return {"alternatives": recommend_low_risk_alternatives(pack_id)}


@app.get("/api/skills/recommend")
def recommendations_explain(q: str = "", limit: int = 5, explain: bool = False, for_workflow: str = "") -> dict[str, Any]:
    from runtime.skills import get_recommendations
    return get_recommendations(query=q, limit=limit, explain=explain, for_workflow=for_workflow)


@app.get("/api/skills/workflows/{workflow_id}")
def workflows_get(workflow_id: str) -> dict[str, Any]:
    from runtime.skills.workflows import _get_workflow_by_id
    wf = _get_workflow_by_id(workflow_id)
    if not wf:
        return {"status": "error", "message": f"Workflow '{workflow_id}' not found"}
    return wf


@app.post("/api/skills/workflows/{workflow_id}/preview")
def workflows_preview(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import preview_workflow_run
    inputs = payload.get("inputs", {})
    workspace = payload.get("workspace", "default")
    return preview_workflow_run(workflow_id, inputs=inputs, workspace=workspace)


@app.get("/api/skills/workflows/{workflow_id}/permissions")
def workflows_permissions(workflow_id: str) -> dict[str, Any]:
    from runtime.skills import workflow_permission_summary
    return workflow_permission_summary(workflow_id)


@app.post("/api/skills/workflows/{workflow_id}/approve-permissions")
def workflows_approve_permissions(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import workflow_permission_summary
    summary = workflow_permission_summary(workflow_id)
    if summary.get("can_run"):
        return {"status": "ok", "message": "All permissions approved", "workflow_id": workflow_id}
    return {"status": "blocked", "missing_approvals": summary.get("missing_approvals", [])}


@app.post("/api/skills/workflows/{workflow_id}/run")
def workflows_run_v250(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import run_workflow
    inputs = payload.get("inputs", {})
    dry_run = payload.get("dry_run", True)
    user_confirmed = payload.get("user_confirmed", False) or dry_run
    workspace = payload.get("workspace", "default")
    return run_workflow(workflow_id=workflow_id, inputs=inputs, dry_run=dry_run, user_confirmed=user_confirmed, workspace=workspace)


@app.post("/api/skills/workflows/{workflow_id}/run-dry")
def workflows_run_dry(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import run_workflow
    inputs = payload.get("inputs", {})
    return run_workflow(workflow_id=workflow_id, inputs=inputs, dry_run=True, user_confirmed=True)


@app.get("/api/skills/workflows/audit")
def workflows_audit(workflow_id: str = "") -> dict[str, Any]:
    from runtime.skills.workflow_audit import get_workflow_audit
    return {"runs": get_workflow_audit(workflow_id=workflow_id if workflow_id else None, limit=50)}


@app.get("/api/skills/workflows/{workflow_id}/audit")
def workflows_wf_audit(workflow_id: str) -> dict[str, Any]:
    from runtime.skills.workflow_audit import get_workflow_audit
    return {"runs": get_workflow_audit(workflow_id=workflow_id, limit=50)}


@app.get("/api/skills/workflows/runs")
def workflows_runs_list(workflow_id: str = "", limit: int = 20) -> dict[str, Any]:
    from runtime.skills import list_workflow_runs
    return {"runs": list_workflow_runs(workflow_id=workflow_id if workflow_id else None, limit=limit)}


@app.get("/api/skills/workflows/runs/{run_id}")
def workflows_run_detail(run_id: str) -> dict[str, Any]:
    from runtime.skills import get_workflow_run
    from runtime.skills.workflow_audit import get_workflow_steps
    run_data = get_workflow_run(run_id)
    if not run_data:
        return {"status": "error", "message": f"Run '{run_id}' not found"}
    return {"run": run_data, "steps": get_workflow_steps(run_id)}


@app.post("/api/skills/workflows/runs/{run_id}/export")
def workflows_run_export(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import export_workflow_run
    fmt = payload.get("format", "json")
    return {"content": export_workflow_run(run_id, format=fmt)}


@app.post("/api/skills/workflows/rerun-plan")
def workflows_rerun_plan(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import preview_rerun_from_step
    run_id = payload.get("run_id", "")
    step_id = payload.get("step_id", "")
    if not run_id or not step_id:
        return {"status": "error", "message": "run_id and step_id required"}
    return preview_rerun_from_step(run_id, step_id)


@app.post("/api/skills/packs/lint/fix-suggestions")
def packs_lint_fix_suggestions(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import lint_pack
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return lint_pack(pack_path, fix_suggestions=True)


@app.post("/api/skills/packs/lint/apply-safe-fixes")
def packs_lint_apply_fixes(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import apply_safe_lint_fixes
    pack_path = payload.get("path", "")
    if not pack_path:
        return {"status": "error", "message": "Pack path required"}
    return apply_safe_lint_fixes(pack_path, confirm=payload.get("confirm", False))


@app.post("/api/skills/packs/preview-url")
def packs_preview_url(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import preview_url_import
    url = payload.get("url", "")
    if not url:
        return {"status": "error", "message": "URL required"}
    return preview_url_import(url)


@app.post("/api/skills/packs/import-staged")
def packs_import_staged(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import import_staged
    staged_id = payload.get("staged_id", "")
    if not staged_id:
        return {"status": "error", "message": "staged_id required"}
    return import_staged(staged_id, confirm=payload.get("confirm", False))


@app.post("/api/skills/packs/install-staged")
def packs_install_staged(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import install_staged
    staged_id = payload.get("staged_id", "")
    if not staged_id:
        return {"status": "error", "message": "staged_id required"}
    return install_staged(staged_id, confirm=payload.get("confirm", False))


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


# v2.7.0 Workflows & Packs Import/Export/Inspect & Backup Management

@app.post("/api/skills/workflows/{workflow_id}/export")
def api_export_workflow(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import export_workflow
    output_path = payload.get("output_path")
    if not output_path:
        return {"status": "error", "message": "Missing output_path"}
    return export_workflow(workflow_id, output_path)

@app.post("/api/skills/workflows/import")
def api_import_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import import_workflow
    archive_path = payload.get("archive_path")
    confirm = bool(payload.get("confirm", False))
    if not archive_path:
        return {"status": "error", "message": "Missing archive_path"}
    return import_workflow(archive_path, confirm=confirm)

@app.post("/api/skills/workflows/validate-file")
def api_validate_workflow_file(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import validate_workflow_file
    archive_path = payload.get("archive_path")
    if not archive_path:
        return {"status": "error", "message": "Missing archive_path"}
    return validate_workflow_file(archive_path)

@app.post("/api/skills/workflows/packs/export")
def api_export_workflow_pack(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills.workflow_packs import export_workflow_pack
    workflow_ids = payload.get("workflow_ids", [])
    pack_id = payload.get("pack_id")
    output_path = payload.get("output_path")
    metadata = payload.get("metadata", {})
    if not pack_id or not output_path:
        return {"status": "error", "message": "pack_id and output_path required"}
    return export_workflow_pack(workflow_ids, pack_id, output_path, metadata)

@app.post("/api/skills/workflows/packs/import")
def api_import_workflow_pack(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills.workflow_packs import import_workflow_pack
    archive_path = payload.get("archive_path")
    confirm = bool(payload.get("confirm", False))
    if not archive_path:
        return {"status": "error", "message": "Missing archive_path"}
    return import_workflow_pack(archive_path, confirm=confirm)

@app.post("/api/skills/workflows/packs/inspect")
def api_inspect_workflow_pack(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills.workflow_packs import inspect_workflow_pack
    archive_path = payload.get("archive_path")
    if not archive_path:
        return {"status": "error", "message": "Missing archive_path"}
    return inspect_workflow_pack(archive_path)

@app.post("/api/backup/validate")
def api_backup_validate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.backup import BackupManager
    file_path = payload.get("file_path")
    if not file_path:
        return {"status": "error", "message": "Missing file_path"}
    return BackupManager().validate(file_path)

@app.post("/api/backup/inspect")
def api_backup_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.backup import BackupManager
    file_path = payload.get("file_path")
    if not file_path:
        return {"status": "error", "message": "Missing file_path"}
    return BackupManager().inspect(file_path)

@app.post("/api/backup/restore")
def api_backup_restore(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.backup import BackupManager
    file_path = payload.get("file_path")
    confirm = bool(payload.get("confirm", False))
    if not file_path:
        return {"status": "error", "message": "Missing file_path"}
    return BackupManager().restore(file_path, confirm=confirm)

@app.get("/api/skills/workflows/runs/{run_id}/timeline")
def api_workflows_run_timeline(run_id: str) -> dict[str, Any]:
    from runtime.skills import get_workflow_run_timeline
    return get_workflow_run_timeline(run_id)

@app.get("/api/skills/workflows/runs/{run_id}/report")
def api_workflows_run_report(run_id: str, format: str = "html") -> dict[str, Any]:
    from runtime.skills import export_workflow_run_report
    return export_workflow_run_report(run_id, format=format)


@app.get("/api/voice/status")
def api_voice_status() -> dict[str, Any]:
    from runtime.voice.session import VoiceSessionManager
    return VoiceSessionManager().get_status()

@app.get("/api/voice/settings")
def api_voice_settings() -> dict[str, Any]:
    from runtime.voice.settings import get_voice_settings
    return get_voice_settings()

@app.post("/api/voice/settings")
def api_voice_settings_post(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.voice.settings import save_voice_settings
    return save_voice_settings(payload)

@app.post("/api/voice/simulate")
def api_voice_simulate(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.voice.session import VoiceSessionManager
    transcript = payload.get("transcript", "")
    if not transcript:
        return {"status": "error", "message": "Transcript is required"}
    return VoiceSessionManager().simulate_voice_command(transcript)

@app.websocket("/api/voice/ws")
async def api_voice_websocket(websocket: WebSocket):
    await websocket.accept()
    from runtime.voice.session import VoiceSessionManager
    session = VoiceSessionManager()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                
                if action == "status":
                    await websocket.send_text(json.dumps({
                        "type": "voice_status",
                        "data": session.get_status()
                    }))
                    
                elif action == "simulate":
                    transcript = msg.get("transcript", "")
                    if transcript:
                        res = session.simulate_voice_command(transcript)
                        await websocket.send_text(json.dumps({
                            "type": "voice_simulate_result",
                            "data": res
                        }))
                        
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass

from runtime.automation.browser import BrowserAutomationManager
from runtime.automation.search import SearchManager
from runtime.automation.desktop import DesktopAutomationManager
from runtime.approvals.queue import ActionApprovalQueue

browser_manager = BrowserAutomationManager()
search_manager = SearchManager()
desktop_manager = DesktopAutomationManager()
action_queue = ActionApprovalQueue()

@app.get("/api/browser/status")
def get_browser_status() -> dict[str, Any]:
    return browser_manager.status()

@app.get("/api/search/status")
def get_search_status() -> dict[str, Any]:
    # Mocking status based on providers
    return {"provider": "none", "ready": False}

@app.get("/api/desktop/safe-apps")
def get_safe_apps() -> list[str]:
    return desktop_manager.list_safe_apps()

@app.get("/api/approvals")
def list_approvals() -> list[dict[str, Any]]:
    return action_queue.list_pending()

@app.post("/api/approvals/{approval_id}/approve")
def approve_action(approval_id: str) -> dict[str, Any]:
    return action_queue.approve(approval_id)

@app.post("/api/approvals/{approval_id}/reject")
def reject_action(approval_id: str) -> dict[str, Any]:
    return action_queue.reject(approval_id)

