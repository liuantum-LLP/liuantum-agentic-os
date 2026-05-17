from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from runtime.config import SettingsManager, utc_now
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.security.secret_store import SecretManager, mask_secret


TOKEN_SECRET_NAME = "local_api_token"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _enabled() -> bool:
    try:
        return SettingsManager().get("local_auth_enabled")["value"].lower() in {"1", "true", "yes", "on"}
    except ValueError:
        return True


class AuthManager:
    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.secrets = SecretManager()

    def ensure_token(self) -> dict[str, Any]:
        self.settings.ensure_defaults()
        existing_hash = self._token_hash()
        existing_token = self.secrets.get_secret(TOKEN_SECRET_NAME)
        if existing_hash and existing_token:
            return self.status()
        self._provision_token()
        return self.status()

    def status(self) -> dict[str, Any]:
        self.settings.ensure_defaults()
        if _enabled() and (not self._token_hash() or not self.secrets.get_secret(TOKEN_SECRET_NAME)):
            self._provision_token()
        token = self.secrets.get_secret(TOKEN_SECRET_NAME)
        return {
            "status": "enabled" if _enabled() else "disabled",
            "local_auth_enabled": _enabled(),
            "local_auth_mode": self.settings.get("local_auth_mode")["value"],
            "token_status": "stored" if self._token_hash() else "missing",
            "token_backend": self.secrets.backend if token else None,
            "token_masked": mask_secret(token),
            "session_timeout_minutes": int(self.settings.get("session_timeout_minutes")["value"]),
            "active_session_count": sum(1 for row in list_records("sessions") if row.get("status") == "active" and not self._expired(row)),
            "created_at": utc_now(),
        }

    def enable(self) -> dict[str, Any]:
        self.settings.set("local_auth_enabled", "true")
        self.ensure_token()
        return self.status()

    def disable(self, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "blocked", "message": "Disabling local auth requires --confirm."}
        self.settings.set("local_auth_enabled", "false")
        return self.status()

    def token(self) -> dict[str, Any]:
        self.ensure_token()
        token = self.secrets.get_secret(TOKEN_SECRET_NAME)
        return {
            "status": "available",
            "token": token,
            "token_masked": mask_secret(token),
            "warning": "This token authorizes local Liuant API access. Do not paste it into websites or logs.",
        }

    def rotate_token(self) -> dict[str, Any]:
        old_hash = self._token_hash()
        token = self._generate_token()
        self.secrets.rotate_secret(TOKEN_SECRET_NAME, token)
        self.settings.set("local_api_token_hash", _hash_token(token))
        for row in list_records("sessions"):
            if row.get("status") == "active":
                update_record("sessions", row["id"], {"status": "revoked", "updated_at": utc_now()})
        return {"status": "rotated", "old_token_invalidated": bool(old_hash), "token_masked": mask_secret(token)}

    def login(self, token: str, user_agent: str | None = None) -> dict[str, Any]:
        if not self.validate_token(token):
            return {"status": "unauthorized", "authenticated": False}
        session_token = f"liuants_{secrets.token_urlsafe(32)}"
        now = datetime.now(timezone.utc)
        timeout = int(self.settings.get("session_timeout_minutes")["value"])
        row = {
            "id": str(uuid4()),
            "session_token_hash": _hash_token(session_token),
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=timeout)).isoformat(),
            "last_seen_at": now.isoformat(),
            "user_agent_hash": _hash_token(user_agent or ""),
            "status": "active",
            "updated_at": now.isoformat(),
        }
        insert_record("sessions", row)
        return {"status": "authenticated", "authenticated": True, "session_token": session_token, "expires_at": row["expires_at"]}

    def logout(self, session_token: str | None) -> dict[str, Any]:
        if not session_token:
            return {"status": "missing_session"}
        token_hash = _hash_token(session_token)
        for row in list_records("sessions"):
            if row.get("session_token_hash") == token_hash:
                update_record("sessions", row["id"], {"status": "logged_out", "updated_at": utc_now()})
                return {"status": "logged_out"}
        return {"status": "not_found"}

    def validate_token(self, token: str | None) -> bool:
        if not token:
            return False
        self.ensure_token()
        expected = self._token_hash()
        return bool(expected and hmac.compare_digest(expected, _hash_token(token)))

    def validate_session(self, session_token: str | None) -> bool:
        if not session_token:
            return False
        token_hash = _hash_token(session_token)
        for row in list_records("sessions"):
            if row.get("session_token_hash") != token_hash or row.get("status") != "active":
                continue
            if self._expired(row):
                update_record("sessions", row["id"], {"status": "expired", "updated_at": utc_now()})
                return False
            update_record("sessions", row["id"], {"last_seen_at": utc_now(), "updated_at": utc_now()})
            return True
        return False

    def authorize(self, authorization: str | None = None, session_token: str | None = None) -> bool:
        if not _enabled():
            return True
        token = _bearer_token(authorization)
        return self.validate_token(token) or self.validate_session(session_token)

    def _token_hash(self) -> str:
        try:
            return self.settings.get("local_api_token_hash")["value"]
        except ValueError:
            return ""

    def _generate_token(self) -> str:
        return f"liuant_{secrets.token_urlsafe(32)}"

    def _provision_token(self) -> str:
        token = self._generate_token()
        self.secrets.set_secret(TOKEN_SECRET_NAME, token, {"purpose": "local_api_auth"})
        self.settings.set("local_api_token_hash", _hash_token(token))
        return token

    def _expired(self, row: dict[str, Any]) -> bool:
        try:
            expires = datetime.fromisoformat(row.get("expires_at", ""))
            return expires <= datetime.now(timezone.utc)
        except Exception:
            return True


def require_api_authorization(authorization: str | None = None, session_token: str | None = None) -> None:
    if not AuthManager().authorize(authorization, session_token):
        raise PermissionError("Local API authentication required.")


def public_api_path(path: str) -> bool:
    public_exact = {
        "/api/auth/status",
        "/api/auth/login",
        "/api/doctor",
        "/api/system/status",
        "/api/system/dashboard",
    }
    return path in public_exact


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return authorization.strip()
