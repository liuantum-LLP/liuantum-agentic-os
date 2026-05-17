from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.storage import WORKSPACE, append_json_list, read_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WebhookEvent:
    source: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    received_at: str = field(default_factory=utc_now)
    trusted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WebhookConnector:
    connector_id = "webhook"
    display_name = "Generic Webhook"
    capabilities = {
        "can_receive_events": True,
        "can_verify_signature": True,
        "can_trigger_automations": True,
        "can_run_shell_tools": False,
        "approval_required_for_external_actions": True,
    }
    warnings = [
        "Webhook payloads are untrusted input.",
        "Agents triggered from public or messenger channels cannot run shell tools.",
        "MVP records events and can trigger draft-only automations.",
    ]

    def __init__(self) -> None:
        self.events_path = WORKSPACE / "webhooks" / "events.json"

    def describe(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "warnings": self.warnings,
        }

    def receive(self, source: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = WebhookEvent(source=source, payload=payload)
        row = append_json_list(self.events_path, event.to_dict())
        log_external_action("webhook_received", "recorded", row, self.connector_id)
        return row

    def list_events(self) -> list[dict[str, Any]]:
        return read_json(self.events_path, [])

