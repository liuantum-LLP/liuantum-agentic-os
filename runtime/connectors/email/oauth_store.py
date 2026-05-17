from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.db import delete_record, get_record, insert_record, list_records, update_record
from runtime.security.secret_store import SecretManager


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "****"
    return f"****{text[-4:]}"


class OAuthTokenStore:
    def get(self, provider: str = "gmail") -> dict[str, Any] | None:
        row = get_record("oauth_tokens", provider)
        if not row:
            return None
        hydrated = dict(row)
        secrets = SecretManager()
        if not hydrated.get("access_token_local") and hydrated.get("access_token_secret_ref"):
            hydrated["access_token_local"] = secrets.get_secret(hydrated["access_token_secret_ref"]) or ""
        if not hydrated.get("refresh_token_local") and hydrated.get("refresh_token_secret_ref"):
            hydrated["refresh_token_local"] = secrets.get_secret(hydrated["refresh_token_secret_ref"]) or ""
        return hydrated

    def save(
        self,
        provider: str,
        connector_id: str,
        token_data: dict[str, Any],
        account_email: str | None = None,
        scopes: list[str] | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        existing = self.get(provider) or {}
        secrets = SecretManager()
        access_token = token_data.get("access_token") or existing.get("access_token_local")
        refresh_token = token_data.get("refresh_token") or existing.get("refresh_token_local")
        access_ref = existing.get("access_token_secret_ref")
        refresh_ref = existing.get("refresh_token_secret_ref")
        if access_token:
            access_ref = f"oauth:{provider}:access_token"
            secrets.set_secret(access_ref, access_token, {"provider": provider, "connector_id": connector_id, "kind": "access_token"})
        if refresh_token:
            refresh_ref = f"oauth:{provider}:refresh_token"
            secrets.set_secret(refresh_ref, refresh_token, {"provider": provider, "connector_id": connector_id, "kind": "refresh_token"})
        row = {
            "id": provider,
            "provider": provider,
            "connector_id": connector_id,
            "account_email": account_email or existing.get("account_email"),
            "scopes_json": scopes or existing.get("scopes_json", []),
            "token_metadata_json": {
                "token_type": token_data.get("token_type"),
                "scope": token_data.get("scope"),
                "access_token_masked": mask_secret(token_data.get("access_token")),
                "refresh_token_masked": mask_secret(refresh_token),
            },
            "access_token_secret_ref": access_ref,
            "refresh_token_secret_ref": refresh_ref,
            "access_token_local": "",
            "refresh_token_local": "",
            "expires_at": expires_at or existing.get("expires_at"),
            "status": "authorized",
            "created_at": existing.get("created_at", utc_now()),
            "updated_at": utc_now(),
        }
        return insert_record("oauth_tokens", row)

    def disconnect(self, provider: str = "gmail") -> dict[str, Any]:
        existing = self.get(provider)
        if not existing:
            return {"status": "disconnected", "provider": provider}
        row = existing
        secrets = SecretManager()
        for key in ("access_token_secret_ref", "refresh_token_secret_ref"):
            if row.get(key):
                secrets.delete_secret(row[key])
        update_record("oauth_tokens", provider, {"status": "disconnected", "access_token_local": "", "refresh_token_local": "", "access_token_secret_ref": "", "refresh_token_secret_ref": "", "updated_at": utc_now()})
        return {"status": "disconnected", "provider": provider}

    def sanitized(self, provider: str = "gmail") -> dict[str, Any] | None:
        row = self.get(provider)
        if not row:
            return None
        safe = dict(row)
        safe.pop("access_token_local", None)
        safe.pop("refresh_token_local", None)
        safe.pop("access_token_secret_ref", None)
        safe.pop("refresh_token_secret_ref", None)
        return safe
