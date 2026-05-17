from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.connectors.email.registry import EMAIL_CONNECTORS, list_email_connectors
from runtime.connectors.social.registry import SOCIAL_CONNECTORS, list_social_connectors
from runtime.connectors.webhook_connector import WebhookConnector
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.config import SettingsManager


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ConnectorAccount:
    channel: str
    provider: str
    name: str
    status: str = "needs_oauth"
    config_json: dict[str, Any] = field(default_factory=dict)
    scopes_json: list[str] = field(default_factory=list)
    assigned_agent_slug: str = "content-creator-agent"
    permission_mode: str = "safe"
    last_tested_at: str | None = None
    enabled: bool = False
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    disconnected_at: str | None = None
    # Backward-compatible aliases used by older UI/tests.
    connector_type: str | None = None
    display_name: str | None = None
    scopes: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConnectorManager:
    def available(self) -> dict[str, Any]:
        return {
            "social": list_social_connectors(),
            "email": list_email_connectors(),
            "messaging": [
                {
                    "platform": "telegram",
                    "display_name": "Telegram Bot",
                    "status": "bot_api_ready",
                    "safety": "Draft-only by default; incoming messages are untrusted.",
                }
            ],
            "webhook": WebhookConnector().describe(),
        }

    def list(self) -> list[dict[str, Any]]:
        return [self._sanitize(row) for row in list_records("connectors")]

    def create(
        self,
        provider: str,
        connector_type: str = "social",
        display_name: str | None = None,
        scopes: list[str] | None = None,
        config: dict[str, Any] | None = None,
        assigned_agent_slug: str = "content-creator-agent",
        permission_mode: str | None = None,
    ) -> dict[str, Any]:
        known = set(SOCIAL_CONNECTORS) | set(EMAIL_CONNECTORS) | {"webhook", "telegram", "telegram_bot"}
        if provider in {"social", "email", "webhook"} and connector_type in known:
            provider, connector_type = connector_type, provider
        if provider in {"telegram", "telegram_bot"}:
            from runtime.connectors.messaging import TelegramConnector

            return TelegramConnector().setup(
                bot_token=(config or {}).get("bot_token"),
                assigned_agent_slug=assigned_agent_slug if assigned_agent_slug != "content-creator-agent" else None,
                permission_mode=permission_mode or SettingsManager().get("permission_mode")["value"],
            )["connector"]
        if provider not in known:
            raise ValueError(f"Unknown connector provider: {provider}")
        account = ConnectorAccount(
            channel=connector_type,
            provider=provider,
            name=display_name or provider,
            status="needs_oauth" if provider not in {"webhook", "imap_smtp"} else "configured",
            config_json=config or {},
            scopes_json=scopes or [],
            assigned_agent_slug=assigned_agent_slug,
            permission_mode=permission_mode or SettingsManager().get("permission_mode")["value"],
            connector_type=connector_type,
            display_name=display_name or provider,
            scopes=scopes or [],
            config=config or {},
        )
        return insert_record("connectors", account.to_dict())

    def test(self, connector_id: str) -> dict[str, Any]:
        connector = self._find(connector_id)
        if connector.get("provider") == "telegram_bot":
            from runtime.connectors.messaging import TelegramConnector

            return TelegramConnector().test_connection()
        return {
            "id": connector_id,
            "provider": connector["provider"],
            "status": connector["status"],
            "enabled": connector["enabled"],
            "last_tested_at": utc_now(),
            "result": "Local connector config is valid. Live OAuth/API test is not performed in MVP.",
        }

    def set_enabled(self, connector_id: str, enabled: bool) -> dict[str, Any]:
        row = self._find(connector_id)
        if row.get("provider") == "telegram_bot":
            from runtime.connectors.messaging import TelegramConnector

            return TelegramConnector().enable() if enabled else TelegramConnector().disable()
        status = "disabled" if not enabled else "enabled"
        return update_record("connectors", connector_id, {"enabled": enabled, "status": status, "updated_at": utc_now()})

    def disconnect(self, connector_id: str) -> dict[str, Any]:
        row = self._find(connector_id)
        if row.get("provider") == "telegram_bot":
            from runtime.connectors.messaging import TelegramConnector

            return TelegramConnector().disconnect()
        return update_record(
            "connectors",
            connector_id,
            {"enabled": False, "status": "disabled", "disconnected_at": utc_now(), "config": {}, "config_json": {}, "updated_at": utc_now()},
        )

    def show(self, connector_id: str) -> dict[str, Any]:
        return self._sanitize(self._find(connector_id))

    def _find(self, connector_id: str) -> dict[str, Any]:
        connector = get_record("connectors", connector_id)
        if connector:
            return connector
        raise ValueError(f"Connector not found: {connector_id}")

    def _sanitize(self, connector: dict[str, Any]) -> dict[str, Any]:
        if connector.get("provider") != "telegram_bot":
            return connector
        config = {**(connector.get("config_json") or {})}
        token = config.pop("bot_token_local", "")
        if token and not config.get("bot_token_masked"):
            config["bot_token_masked"] = f"****{token[-4:]}"
        row = {**connector, "config_json": config}
        row["config"] = {"bot_token_masked": config.get("bot_token_masked", ""), "webhook_url": config.get("webhook_url", "")}
        return row
