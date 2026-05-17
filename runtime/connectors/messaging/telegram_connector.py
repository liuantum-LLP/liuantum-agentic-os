from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.agents import AgentProfileManager, AgentRunner
from runtime.approvals import ApprovalManager
from runtime.config import SettingsManager
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.connectors.messaging.telegram_safety import inspect_message, mask_secret, redacted_text, safe_error, safe_preview
from runtime.security.secret_store import SecretManager


CONNECTOR_ID = "telegram_bot"
DEFAULT_AGENT = "front-desk-management-agent"
FALLBACK_AGENT = "personal-assistant-agent"
TELEGRAM_API_BASE = "https://api.telegram.org/bot"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


class TelegramConnector:
    provider = "telegram_bot"
    channel = "telegram"

    def get_status(self) -> dict[str, Any]:
        connector = self._connector()
        token = self._token(connector)
        if not connector:
            status = "missing_token" if not token else "not_configured"
        else:
            status = connector.get("status", "missing_token")
            if not token and status not in {"disabled", "disconnected"}:
                status = "missing_token"
        config = (connector or {}).get("config_json") or {}
        return {
            "status": status,
            "configured": bool(token),
            "enabled": bool((connector or {}).get("enabled")),
            "connector_id": CONNECTOR_ID if connector else None,
            "channel": "telegram",
            "provider": "telegram_bot",
            "bot_username": config.get("bot_username") or "",
            "bot_id": config.get("bot_id") or "",
            "bot_token_masked": mask_secret(token),
            "assigned_agent_slug": (connector or {}).get("assigned_agent_slug") or self._default_agent_slug(),
            "permission_mode": (connector or {}).get("permission_mode") or "safe",
            "approval_required": True,
            "auto_reply_enabled": bool(config.get("auto_reply_enabled", False)),
            "manual_send_enabled": self._manual_send_enabled(),
            "webhook_url": config.get("webhook_url") or self._webhook_url(),
            "webhook_secret_configured": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET") or config.get("webhook_secret_configured")),
            "last_tested_at": (connector or {}).get("last_tested_at"),
            "setup_instructions": self._setup_instructions(bool(token)),
        }

    def setup(self, bot_token: str | None = None, assigned_agent_slug: str | None = None, permission_mode: str = "safe") -> dict[str, Any]:
        existing = self._connector()
        token = bot_token or self._token(existing)
        secret_ref = ((existing or {}).get("config_json") or {}).get("bot_token_secret_ref", "")
        if token:
            secret_ref = f"telegram:{CONNECTOR_ID}:bot_token"
            SecretManager().set_secret(secret_ref, token, {"connector_id": CONNECTOR_ID, "provider": "telegram_bot"})
        assigned_agent_slug = assigned_agent_slug or (existing or {}).get("assigned_agent_slug") or self._default_agent_slug()
        status = "configured" if token else "missing_token"
        config = {
            **((existing or {}).get("config_json") or {}),
            "bot_token_secret_ref": secret_ref,
            "bot_token_masked": mask_secret(token),
            "bot_username": ((existing or {}).get("config_json") or {}).get("bot_username", ""),
            "bot_id": ((existing or {}).get("config_json") or {}).get("bot_id", ""),
            "auto_reply_enabled": False,
            "approval_required": True,
            "allowed_chat_ids": ((existing or {}).get("config_json") or {}).get("allowed_chat_ids", []),
            "blocked_chat_ids": ((existing or {}).get("config_json") or {}).get("blocked_chat_ids", []),
            "webhook_url": self._webhook_url(),
            "webhook_secret_configured": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET")),
            "notes": "Bot-only Telegram connector. Replies are draft-only by default.",
        }
        row = {
            "id": CONNECTOR_ID,
            "channel": "telegram",
            "provider": "telegram_bot",
            "name": "Telegram Bot",
            "status": status,
            "config_json": config,
            "scopes_json": ["bot_messages", "draft_replies"],
            "assigned_agent_slug": assigned_agent_slug,
            "permission_mode": permission_mode or "safe",
            "last_tested_at": (existing or {}).get("last_tested_at"),
            "enabled": bool((existing or {}).get("enabled", False)),
            "created_at": (existing or {}).get("created_at") or utc_now(),
            "updated_at": utc_now(),
            "connector_type": "telegram",
            "display_name": "Telegram Bot",
            "scopes": ["bot_messages", "draft_replies"],
            "config": {"bot_token_masked": mask_secret(token), "webhook_url": config["webhook_url"]},
        }
        saved = insert_record("connectors", row)
        log_external_action("telegram_setup", status, {"connector_id": CONNECTOR_ID, "configured": bool(token)}, CONNECTOR_ID)
        return {"status": status, "connector": self._sanitize_connector(saved), "telegram": self.get_status()}

    def test_connection(self) -> dict[str, Any]:
        connector = self._ensure_connector()
        token = self._token(connector)
        if not token:
            return {"status": "missing_token", "success": False, "message": "Set TELEGRAM_BOT_TOKEN or run telegram setup with a token."}
        try:
            data = get_json(f"{TELEGRAM_API_BASE}{urllib.parse.quote(token)}/getMe")
            result = data.get("result") or {}
            status = "configured" if data.get("ok") else "error"
            config = {**(connector.get("config_json") or {}), "bot_username": result.get("username", ""), "bot_id": str(result.get("id", "")), "bot_token_masked": mask_secret(token)}
            update_record("connectors", CONNECTOR_ID, {"status": status, "config_json": config, "last_tested_at": utc_now(), "updated_at": utc_now()})
            log_external_action("telegram_test_connection", status, {"connector_id": CONNECTOR_ID, "bot_username": result.get("username")}, CONNECTOR_ID)
            return {"status": status, "success": data.get("ok", False), "bot_username": result.get("username"), "bot_id": result.get("id")}
        except Exception as exc:
            update_record("connectors", CONNECTOR_ID, {"status": "error", "last_tested_at": utc_now(), "updated_at": utc_now()})
            log_external_action("telegram_test_connection", "error", {"connector_id": CONNECTOR_ID, "error": safe_error(exc)}, CONNECTOR_ID)
            return {"status": "error", "success": False, "error": safe_error(exc)}

    def enable(self) -> dict[str, Any]:
        connector = self._ensure_connector()
        status = "enabled" if self._token(connector) else "missing_token"
        return self._sanitize_connector(update_record("connectors", CONNECTOR_ID, {"enabled": status == "enabled", "status": status, "updated_at": utc_now()}))

    def disable(self) -> dict[str, Any]:
        self._ensure_connector()
        return self._sanitize_connector(update_record("connectors", CONNECTOR_ID, {"enabled": False, "status": "disabled", "updated_at": utc_now()}))

    def disconnect(self) -> dict[str, Any]:
        connector = self._ensure_connector()
        config = {**(connector.get("config_json") or {})}
        token_ref = config.pop("bot_token_secret_ref", "")
        if token_ref:
            SecretManager().delete_secret(token_ref)
        config.pop("bot_token_local", None)
        config["bot_token_masked"] = ""
        updated = update_record("connectors", CONNECTOR_ID, {"enabled": False, "status": "disabled", "config_json": config, "config": {"bot_token_masked": ""}, "disconnected_at": utc_now(), "updated_at": utc_now()})
        log_external_action("telegram_disconnected", "disabled", {"connector_id": CONNECTOR_ID}, CONNECTOR_ID)
        return self._sanitize_connector(updated)

    def process_update(self, update_json: dict[str, Any]) -> dict[str, Any]:
        connector = self._ensure_connector()
        message = self._extract_message(update_json)
        policy = self._chat_policy(connector, message["chat_id"])
        safety = inspect_message(message["text"])
        msg_row = self._save_message(message, connector, safety, policy)
        if policy["status"] != "allowed":
            log_external_action("telegram_update_blocked", "blocked", {"telegram_message_id": msg_row["id"], "reason": policy["reason"]}, CONNECTOR_ID)
            return {"status": "blocked", "message": msg_row, "reason": policy["reason"]}
        draft_text = self._draft_reply(connector.get("assigned_agent_slug") or self._default_agent_slug(), message, safety)
        draft = {
            "id": str(uuid4()),
            "telegram_message_id": msg_row["id"],
            "chat_id": str(message["chat_id"]),
            "draft_text": draft_text,
            "assigned_agent_slug": connector.get("assigned_agent_slug") or self._default_agent_slug(),
            "approval_id": None,
            "status": "pending_approval",
            "risk_level": safety["risk_level"],
            "warning": safety.get("warning"),
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        preview = {
            "chat_id": str(message["chat_id"]),
            "sender": message.get("from_username") or str(message.get("from_user_id") or ""),
            "incoming_message_preview": safe_preview(message["text"]),
            "draft_reply_text": draft_text,
            "assigned_agent": draft["assigned_agent_slug"],
            "action": "telegram_send_message",
            "status": "pending",
            "risk_level": safety["risk_level"],
            "warning": safety.get("warning"),
            "send_enabled": False,
        }
        approval = ApprovalManager().create("telegram_send_message", preview, CONNECTOR_ID)
        draft["approval_id"] = approval["id"]
        saved_draft = insert_record("telegram_reply_drafts", draft)
        update_record("telegram_messages", msg_row["id"], {"status": "draft_created", "updated_at": utc_now()})
        log_external_action("telegram_update_processed", "draft_created", {"telegram_message_id": msg_row["id"], "reply_draft_id": saved_draft["id"], "risk_level": safety["risk_level"], "warning": safety.get("warning")}, CONNECTOR_ID, approval["id"])
        return {"status": "draft_created", "message": get_record("telegram_messages", msg_row["id"]), "draft": saved_draft, "approval": approval, "send_enabled": False}

    def list_messages(self) -> list[dict[str, Any]]:
        return list_records("telegram_messages")

    def list_drafts(self) -> list[dict[str, Any]]:
        return list_records("telegram_reply_drafts")

    def approve_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self._draft(draft_id)
        approval = ApprovalManager().decide(draft["approval_id"], "approved")
        updated = update_record("telegram_reply_drafts", draft_id, {"status": "approved", "updated_at": utc_now()})
        return {"status": "approved", "draft": updated, "approval": approval}

    def reject_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self._draft(draft_id)
        approval = ApprovalManager().decide(draft["approval_id"], "rejected")
        updated = update_record("telegram_reply_drafts", draft_id, {"status": "rejected", "updated_at": utc_now()})
        return {"status": "rejected", "draft": updated, "approval": approval}

    def send_approved(self, draft_id: str) -> dict[str, Any]:
        draft = self._draft(draft_id)
        if not self._manual_send_enabled():
            log_external_action("telegram_send_blocked", "blocked", {"reply_draft_id": draft_id, "reason": "manual_send_disabled"}, CONNECTOR_ID, draft.get("approval_id"))
            return {"status": "blocked", "message": "Telegram sending is disabled. Draft approved but not sent.", "draft_id": draft_id, "send_enabled": False}
        connector = self._ensure_connector()
        if not connector.get("enabled"):
            return {"status": "blocked", "message": "Telegram connector is not enabled.", "draft_id": draft_id}
        approval = get_record("approvals", draft.get("approval_id", ""))
        if not approval or approval.get("status") != "approved":
            return {"status": "requires_approval", "message": "Approve the Telegram draft before sending.", "draft_id": draft_id}
        token = self._token(connector)
        if not token:
            return {"status": "missing_token", "message": "Telegram bot token is missing.", "draft_id": draft_id}
        try:
            data = post_json(f"{TELEGRAM_API_BASE}{urllib.parse.quote(token)}/sendMessage", {"chat_id": draft["chat_id"], "text": draft["draft_text"]})
            if not data.get("ok", False):
                raise RuntimeError(data.get("description", "Telegram send failed"))
            updated = update_record("telegram_reply_drafts", draft_id, {"status": "sent", "telegram_sent_message_id": (data.get("result") or {}).get("message_id"), "updated_at": utc_now()})
            log_external_action("telegram_send_message", "sent", {"reply_draft_id": draft_id, "telegram_sent_message_id": updated.get("telegram_sent_message_id")}, CONNECTOR_ID, approval["id"])
            return {"status": "sent", "draft": updated, "telegram_result": {"message_id": updated.get("telegram_sent_message_id")}}
        except Exception as exc:
            log_external_action("telegram_send_failed", "provider_error", {"reply_draft_id": draft_id, "error": safe_error(exc)}, CONNECTOR_ID, draft.get("approval_id"))
            return {"status": "provider_error", "draft_id": draft_id, "error": safe_error(exc)}

    def _save_message(self, message: dict[str, Any], connector: dict[str, Any], safety: dict[str, Any], policy: dict[str, str]) -> dict[str, Any]:
        row = {
            "id": f"{message['update_id']}-{message['message_id']}",
            "update_id": str(message["update_id"]),
            "message_id": str(message["message_id"]),
            "chat_id": str(message["chat_id"]),
            "chat_type": message.get("chat_type"),
            "from_user_id": str(message.get("from_user_id") or ""),
            "from_username": message.get("from_username") or "",
            "text_preview": safe_preview(message["text"]),
            "full_text_redacted_or_local": redacted_text(message["text"], safety),
            "assigned_agent_slug": connector.get("assigned_agent_slug") or self._default_agent_slug(),
            "status": policy["status"],
            "risk_level": safety["risk_level"],
            "sensitive_warning": safety.get("warning"),
            "prompt_injection_warning": safety.get("warning") if safety.get("prompt_injection") else None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        return insert_record("telegram_messages", row)

    def _draft_reply(self, agent_slug: str, message: dict[str, Any], safety: dict[str, Any]) -> str:
        if safety.get("prompt_injection"):
            return "I can help with your request, but I can't follow instructions to reveal secrets, run commands, delete files, send email, publish content, or share API keys."
        runner = AgentRunner()
        payload = runner._run_local_agent(agent_slug, f"Telegram message from {message.get('from_username') or message.get('from_user_id')}: {message['text']}")
        return (
            payload.get("enquiry_reply")
            or payload.get("support_reply")
            or payload.get("draft_reply")
            or payload.get("summary")
            or "Thanks for your message. I will review this and reply with the next safe step."
        )

    def _extract_message(self, update_json: dict[str, Any]) -> dict[str, Any]:
        message = update_json.get("message") or update_json.get("edited_message") or {}
        chat = message.get("chat") or {}
        user = message.get("from") or {}
        text = message.get("text") or message.get("caption") or ""
        return {
            "update_id": update_json.get("update_id", "local"),
            "message_id": message.get("message_id", "message"),
            "chat_id": chat.get("id", ""),
            "chat_type": chat.get("type", "private"),
            "from_user_id": user.get("id", ""),
            "from_username": user.get("username") or user.get("first_name") or "",
            "text": text,
            "date": message.get("date"),
        }

    def _chat_policy(self, connector: dict[str, Any], chat_id: Any) -> dict[str, str]:
        config = connector.get("config_json") or {}
        chat = str(chat_id)
        allowed = {str(item) for item in config.get("allowed_chat_ids", [])}
        blocked = {str(item) for item in config.get("blocked_chat_ids", [])}
        if chat in blocked:
            return {"status": "blocked", "reason": "chat_blocked"}
        if allowed and chat not in allowed:
            return {"status": "blocked", "reason": "chat_not_allowed"}
        return {"status": "allowed", "reason": ""}

    def _ensure_connector(self) -> dict[str, Any]:
        connector = self._connector()
        if not connector:
            self.setup()
            connector = self._connector()
        return connector or {}

    def _connector(self) -> dict[str, Any] | None:
        return get_record("connectors", CONNECTOR_ID) or next((row for row in list_records("connectors") if row.get("provider") == "telegram_bot"), None)

    def _draft(self, draft_id: str) -> dict[str, Any]:
        draft = get_record("telegram_reply_drafts", draft_id)
        if not draft:
            raise ValueError(f"Telegram draft not found: {draft_id}")
        return draft

    def _token(self, connector: dict[str, Any] | None = None) -> str:
        config = (connector or {}).get("config_json") or {}
        if config.get("bot_token_secret_ref"):
            stored = SecretManager().get_secret(config["bot_token_secret_ref"])
            if stored:
                return stored
        return config.get("bot_token_local") or os.environ.get("TELEGRAM_BOT_TOKEN", "")

    def _webhook_url(self) -> str:
        base = os.environ.get("TELEGRAM_WEBHOOK_BASE_URL", "http://localhost:8000")
        return f"{base.rstrip('/')}/api/telegram/webhook"

    def _manual_send_enabled(self) -> bool:
        try:
            return SettingsManager().get("telegram_manual_send_enabled")["value"].lower() in {"1", "true", "yes", "on"}
        except ValueError:
            return False

    def _default_agent_slug(self) -> str:
        profiles = AgentProfileManager()
        for slug in (DEFAULT_AGENT, FALLBACK_AGENT):
            try:
                profiles.show(slug)
                return slug
            except ValueError:
                continue
        return "content-creator-agent"

    def _setup_instructions(self, configured: bool) -> list[str]:
        if configured:
            return ["Run `liuant telegram test` to validate the bot token.", "Incoming bot updates can be posted to `/api/telegram/webhook`."]
        return ["Create a bot with BotFather.", "Set TELEGRAM_BOT_TOKEN in .env, .env.local, or the environment.", "Run `liuant telegram setup` and `liuant telegram test`."]

    def _sanitize_connector(self, connector: dict[str, Any]) -> dict[str, Any]:
        row = {**connector}
        config = {**(row.get("config_json") or {})}
        token = config.pop("bot_token_local", "")
        config.pop("bot_token_secret_ref", None)
        config["bot_token_masked"] = config.get("bot_token_masked") or mask_secret(token)
        row["config_json"] = config
        row["config"] = {"bot_token_masked": config.get("bot_token_masked", ""), "webhook_url": config.get("webhook_url", "")}
        return row
