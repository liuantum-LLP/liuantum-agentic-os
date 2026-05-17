from __future__ import annotations

import base64
import hashlib
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.approvals import ApprovalManager
from runtime.config import SettingsManager, utc_now
from runtime.connectors.email.oauth_store import OAuthTokenStore, mask_secret
from runtime.connectors.social.base_social import SocialDraft
from runtime.connectors.social import social_api
from runtime.connectors.social.social_safety import detect_sensitive_content, safe_preview
from runtime.db import get_record, insert_record, list_records, update_record


class OAuthSocialConnector:
    platform = "social"
    display_name = "Social Connector"
    client_id_env = ""
    client_secret_env = ""
    redirect_uri_env = ""
    default_redirect_uri = ""
    authorization_url = ""
    token_url = ""
    profile_url = ""
    publish_url = ""
    required_scopes: tuple[str, ...] = ()
    publish_scopes: tuple[str, ...] = ()
    api_access_note = "Publishing depends on official API access and approved scopes."

    def __init__(self) -> None:
        self.store = OAuthTokenStore()

    def setup_instructions(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "requires_oauth": True,
            "required_scopes": list(self.required_scopes),
            "optional_scopes": [],
            "warnings": [
                "Use official platform APIs only.",
                "Do not collect passwords or scrape private pages.",
                "Publishing requires explicit approval and manual publish enablement.",
            ],
        }

    def describe(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "capabilities": self.capabilities.to_dict(),
            "setup": self.setup_instructions(),
        }

    def create_draft(
        self,
        text: str,
        account_id: str | None = None,
        media_paths: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SocialDraft:
        return SocialDraft(
            platform=self.platform,
            text=text,
            account_id=account_id,
            media_paths=media_paths or [],
            metadata=metadata or {},
        )

    def get_status(self) -> dict[str, Any]:
        connector = self._connector()
        token = self.store.sanitized(self.platform)
        configured = bool(_env(self.client_id_env) and _env(self.client_secret_env))
        if not configured:
            status = "missing_client_config"
        elif token and token.get("status") == "authorized":
            status = "authorized"
        elif connector:
            status = connector.get("status", "needs_oauth")
        else:
            status = "not_configured"
        config = connector.get("config_json", {}) if connector else {}
        scopes = token.get("scopes_json") if token else (connector.get("scopes_json") if connector else list(self.required_scopes))
        return {
            "status": status,
            "configured": configured,
            "authorized": status == "authorized",
            "connector_id": connector.get("id") if connector else self.platform,
            "platform": self.platform,
            "account_name": (token or {}).get("account_email") or config.get("account_name", ""),
            "account_id": config.get("account_id", ""),
            "scopes": scopes or list(self.required_scopes),
            "publish_capability": self._publish_capability(scopes or []),
            "approval_required": True,
            "auto_publish_enabled": False,
            "manual_publish_enabled": bool(config.get("manual_publish_enabled", False)),
            "enabled": bool(connector.get("enabled")) if connector else False,
            "token_metadata": token.get("token_metadata_json") if token else None,
            "setup_instructions": self._setup_instructions(configured),
            "notes": self.api_access_note,
        }

    def setup(self) -> dict[str, Any]:
        connector = self._connector()
        if not connector:
            connector = insert_record("connectors", self._connector_record("needs_oauth"))
        status = "needs_oauth" if self.get_status()["configured"] else "missing_client_config"
        connector = update_record(
            "connectors",
            connector["id"],
            {
                "status": status,
                "scopes_json": list(self.required_scopes),
                "scopes": list(self.required_scopes),
                "approval_required": True,
                "auto_publish_enabled": False,
                "updated_at": utc_now(),
            },
        )
        return {"status": status, "connector": self._sanitize_connector(connector), "social": self.get_status()}

    def start_oauth(self) -> dict[str, Any]:
        self.setup()
        if not self.get_status()["configured"]:
            return {"status": "missing_client_config", "authorization_url": None, "setup_instructions": self._setup_instructions(False)}
        state = str(uuid4())
        code_verifier = _code_verifier()
        connector = self._connector()
        config = {**(connector.get("config_json") or {}), "oauth_state": state, "redirect_uri": self._redirect_uri(), "code_verifier": code_verifier}
        update_record("connectors", connector["id"], {"status": "oauth_url_ready", "config_json": config, "config": _public_config(config), "updated_at": utc_now()})
        query = {
            "client_id": _env(self.client_id_env),
            "redirect_uri": self._redirect_uri(),
            "response_type": "code",
            "scope": " ".join(self.required_scopes),
            "state": state,
        }
        if self.platform == "x":
            query["code_challenge"] = _code_challenge(code_verifier)
            query["code_challenge_method"] = "S256"
        url = f"{self.authorization_url}?{urllib.parse.urlencode(query)}"
        log_external_action("social_oauth_started", "oauth_url_ready", {"platform": self.platform, "connector_id": connector["id"]})
        return {"status": "oauth_url_ready", "authorization_url": url, "state": state, "connector_id": connector["id"], "scopes": list(self.required_scopes)}

    def handle_callback(self, code: str, state: str | None = None) -> dict[str, Any]:
        connector = self._connector()
        if not connector:
            raise ValueError(f"Run {self.platform} setup before OAuth callback.")
        config = connector.get("config_json") or {}
        expected_state = config.get("oauth_state")
        if expected_state and state and state != expected_state:
            return {"status": "error", "error": "OAuth state mismatch."}
        token_data = social_api.exchange_code(self.token_url, code, _env(self.client_id_env), _env(self.client_secret_env), self._redirect_uri(), config.get("code_verifier"))
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(token_data.get("expires_in", 3600)))).isoformat()
        scopes = _scopes_from_token(token_data) or list(self.required_scopes)
        profile = self._safe_profile(token_data.get("access_token", ""))
        account_name = profile.get("name") or profile.get("localizedFirstName") or profile.get("username") or profile.get("email") or self.display_name
        account_id = profile.get("id") or profile.get("sub") or ""
        self.store.save(self.platform, connector["id"], token_data, account_email=account_name, scopes=scopes, expires_at=expires_at)
        config = {**config, "account_name": account_name, "account_id": account_id, "manual_publish_enabled": False}
        update_record("connectors", connector["id"], {"status": "authorized", "enabled": True, "config_json": config, "config": _public_config(config), "scopes_json": scopes, "scopes": scopes, "updated_at": utc_now()})
        log_external_action("social_oauth_connected", "authorized", {"platform": self.platform, "connector_id": connector["id"], "account_name": account_name})
        return {"status": "authorized", "account_name": account_name, "account_id": account_id, "connector_id": connector["id"], "token": self.store.sanitized(self.platform)}

    def disconnect(self) -> dict[str, Any]:
        connector = self._connector()
        self.store.disconnect(self.platform)
        if connector:
            update_record("connectors", connector["id"], {"status": "disconnected", "enabled": False, "config_json": {}, "config": {}, "updated_at": utc_now()})
        log_external_action("social_oauth_disconnected", "disconnected", {"platform": self.platform, "connector_id": connector.get("id") if connector else self.platform})
        return {"status": "disconnected", "platform": self.platform}

    def test_connection(self) -> dict[str, Any]:
        token = self._raw_token()
        if not token:
            return {"status": "needs_oauth", "success": False, "message": f"Connect {self.display_name} first."}
        try:
            profile = self._safe_profile(token)
            connector = self._connector()
            if connector:
                update_record("connectors", connector["id"], {"status": "authorized", "last_tested_at": utc_now(), "updated_at": utc_now()})
            return {"status": "authorized", "success": True, "profile": _sanitize_profile(profile)}
        except Exception as exc:
            return {"status": "error", "success": False, "error": _safe_error(exc)}

    def enable_manual_publish(self) -> dict[str, Any]:
        connector = self._connector() or self.setup()["connector"]
        config = {**(connector.get("config_json") or {}), "manual_publish_enabled": True}
        row = update_record("connectors", connector["id"], {"config_json": config, "config": _public_config(config), "manual_publish_enabled": True, "updated_at": utc_now()})
        return {"status": "manual_publish_enabled", "connector": self._sanitize_connector(row)}

    def disable_manual_publish(self) -> dict[str, Any]:
        connector = self._connector() or self.setup()["connector"]
        config = {**(connector.get("config_json") or {}), "manual_publish_enabled": False}
        row = update_record("connectors", connector["id"], {"config_json": config, "config": _public_config(config), "manual_publish_enabled": False, "updated_at": utc_now()})
        return {"status": "manual_publish_disabled", "connector": self._sanitize_connector(row)}

    def create_publish_preview(self, draft_id: str) -> dict[str, Any]:
        draft = get_record("social_drafts", draft_id)
        if not draft:
            raise ValueError(f"Draft not found: {draft_id}")
        return {"platform": self.platform, "draft_id": draft_id, "text_preview": safe_preview(draft.get("text", "")), "approval_required": True, "manual_publish_required": True}

    def publish_approved_draft(self, draft_id: str, confirm_sensitive: bool = False) -> dict[str, Any]:
        draft = get_record("social_drafts", draft_id)
        if not draft:
            raise ValueError(f"Draft not found: {draft_id}")
        connector = self._connector()
        approval = _find_approval(draft)
        blocked = self._publish_block_reason(draft, connector, approval)
        sensitive = detect_sensitive_content(draft.get("text", ""))
        if not blocked and sensitive["sensitive"] and not confirm_sensitive:
            blocked = ("sensitive_confirmation_required", sensitive["warning"])
        if blocked:
            status, message = blocked
            updated = update_record("social_drafts", draft_id, {"publish_status": status, "publish_error": message, "updated_at": utc_now()})
            log_external_action("social_publish_blocked", status, {"draft_id": draft_id, "platform": self.platform, "reason": message, "text_preview": safe_preview(draft.get("text", ""))}, connector.get("id") if connector else self.platform)
            return {"status": status, "message": message, "draft": updated, "published": False}
        try:
            data = self._publish(draft, self._raw_token() or "")
            external_id = self._external_id(data)
            external_url = self._external_url(external_id, data)
            updated = update_record("social_drafts", draft_id, {"status": "published", "publish_status": "published", "published_at": utc_now(), "publish_attempted_at": utc_now(), "external_post_id": external_id, "external_url": external_url, "publish_error": "", "connector_id": connector["id"], "updated_at": utc_now()})
            log_external_action("social_publish_completed", "published", {"draft_id": draft_id, "platform": self.platform, "external_post_id": external_id}, connector["id"], approval["id"])
            return {"status": "published", "published": True, "external_post_id": external_id, "external_url": external_url, "draft": updated}
        except Exception as exc:
            updated = update_record("social_drafts", draft_id, {"publish_status": "provider_error", "publish_error": _safe_error(exc), "publish_attempted_at": utc_now(), "updated_at": utc_now()})
            log_external_action("social_publish_failed", "provider_error", {"draft_id": draft_id, "platform": self.platform, "error": _safe_error(exc)}, connector["id"] if connector else self.platform)
            return {"status": "provider_error", "published": False, "error": _safe_error(exc), "draft": updated}

    def _publish_block_reason(self, draft: dict[str, Any], connector: dict[str, Any] | None, approval: dict[str, Any] | None) -> tuple[str, str] | None:
        if draft.get("platform") != self.platform:
            return ("publish_blocked", f"Draft platform is {draft.get('platform')}, not {self.platform}.")
        if draft.get("status") not in {"approved", "publish_ready"}:
            return ("publish_blocked", "Draft must be approved before publishing.")
        if not approval or approval.get("status") != "approved":
            return ("publish_blocked", "Approval record must be approved before publishing.")
        if not connector or connector.get("status") != "authorized" or not connector.get("enabled"):
            return ("publish_blocked", "Connector must be authorized and enabled.")
        config = connector.get("config_json") or {}
        if not config.get("manual_publish_enabled"):
            return ("manual_publish_disabled", "Manual publishing is disabled for this connector. Draft remains approved but not published.")
        scopes = connector.get("scopes_json") or []
        if self.publish_scopes and not any(scope in scopes for scope in self.publish_scopes):
            return ("capability_unavailable", "Required publish scope is unavailable for this connector.")
        return None

    def _safe_profile(self, token: str) -> dict[str, Any]:
        return social_api.get_json(self.profile_url, token) if self.profile_url else {}

    def _publish(self, draft: dict[str, Any], token: str) -> dict[str, Any]:
        return social_api.post_json(self.publish_url, self._publish_payload(draft), token)

    def _publish_payload(self, draft: dict[str, Any]) -> dict[str, Any]:
        return {"text": draft.get("text", "")}

    def _external_id(self, data: dict[str, Any]) -> str:
        return str(data.get("id") or data.get("post_id") or (data.get("data") or {}).get("id") or "")

    def _external_url(self, external_id: str, data: dict[str, Any]) -> str:
        return str(data.get("url") or "")

    def _connector(self) -> dict[str, Any] | None:
        return next((row for row in list_records("connectors") if row.get("provider") == self.platform and row.get("channel") == "social"), None)

    def _raw_token(self) -> str | None:
        row = self.store.get(self.platform)
        if not row or row.get("status") != "authorized":
            return None
        return row.get("access_token_local")

    def _redirect_uri(self) -> str:
        return _env(self.redirect_uri_env) or self.default_redirect_uri

    def _setup_instructions(self, configured: bool) -> list[str]:
        if configured:
            return [f"Run `liuant social {self.platform} oauth-url` and open the returned URL.", f"Paste the callback code with `liuant social {self.platform} callback <code> --state <state>`."]
        return [f"Set {self.client_id_env}.", f"Set {self.client_secret_env}.", f"Set {self.redirect_uri_env} or use default {self.default_redirect_uri}.", "Never enter a social account password into Liuant."]

    def _publish_capability(self, scopes: list[str]) -> str:
        if self.publish_scopes and any(scope in scopes for scope in self.publish_scopes):
            return "available"
        return "capability_unavailable"

    def _connector_record(self, status: str) -> dict[str, Any]:
        now = utc_now()
        return {
            "id": self.platform,
            "channel": "social",
            "platform": self.platform,
            "provider": self.platform,
            "name": self.display_name,
            "status": status,
            "account_name": "",
            "account_id": "",
            "config_json": {"redirect_uri": self._redirect_uri(), "manual_publish_enabled": False},
            "scopes_json": list(self.required_scopes),
            "assigned_agent_slug": "social-media-manager-agent",
            "permission_mode": SettingsManager().get("permission_mode")["value"],
            "approval_required": True,
            "auto_publish_enabled": False,
            "manual_publish_enabled": False,
            "last_tested_at": None,
            "enabled": False,
            "notes": self.api_access_note,
            "created_at": now,
            "updated_at": now,
            "connector_type": "social",
            "display_name": self.display_name,
            "scopes": list(self.required_scopes),
            "config": {"redirect_uri": self._redirect_uri(), "manual_publish_enabled": False},
        }

    def _sanitize_connector(self, connector: dict[str, Any]) -> dict[str, Any]:
        safe = dict(connector)
        safe["config_json"] = _public_config(safe.get("config_json") or {})
        safe["config"] = _public_config(safe.get("config") or {})
        return safe


def _find_approval(draft: dict[str, Any]) -> dict[str, Any] | None:
    approval_id = draft.get("approval_id")
    if approval_id:
        approval = get_record("approvals", approval_id)
        if approval:
            return approval
    for approval in list_records("approvals"):
        preview = approval.get("preview") or {}
        if preview.get("id") == draft.get("id") and approval.get("action_type") == "social_publish":
            return approval
    return None


def _env(key: str) -> str:
    if not key:
        return ""
    value = os.environ.get(key)
    if value:
        return value
    for filename in (".env.local", ".env"):
        path = os.getcwd() + "/" + filename
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _public_config(config: dict[str, Any]) -> dict[str, Any]:
    safe = dict(config)
    for key in ("client_secret", "access_token", "refresh_token", "code_verifier"):
        safe.pop(key, None)
    return safe


def _scopes_from_token(token_data: dict[str, Any]) -> list[str]:
    scope = token_data.get("scope")
    if isinstance(scope, str):
        return scope.replace(",", " ").split()
    if isinstance(scope, list):
        return scope
    return []


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for key in ("LINKEDIN_CLIENT_SECRET", "X_CLIENT_SECRET"):
        secret = _env(key)
        if secret:
            text = text.replace(secret, mask_secret(secret))
    return text[:500]


def _sanitize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in profile.items() if "token" not in key.lower() and "secret" not in key.lower()}


def _code_verifier() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")


def _code_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
