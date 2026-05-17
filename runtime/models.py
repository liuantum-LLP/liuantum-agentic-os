from __future__ import annotations

from typing import Any

from runtime.providers import ModelHub


class ModelManager:
    """Compatibility wrapper for old `models` commands and routes.

    v0.2.2 routes model configuration through the multi-category ModelHub.
    Legacy model commands keep text-provider semantics.
    """

    def __init__(self) -> None:
        self.hub = ModelHub()

    def list(self) -> list[dict[str, Any]]:
        return self.hub.list_providers()

    def status(self) -> dict[str, Any]:
        return self.hub.get_status()

    def setup(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = data or {}
        provider = data.get("id") or data.get("provider") or data.get("name") or "openai"
        return self.hub.setup_provider(provider, data)

    def test(self, provider: str | None = None) -> dict[str, Any]:
        return self.hub.test_provider(provider or "openai")

    def set_default(self, provider: str) -> dict[str, Any]:
        return self.hub.set_default_provider("text", provider)

    def set_fallback(self, provider: str, model: str) -> dict[str, Any]:
        row = self.hub.get_provider(provider)
        if row.get("category") != "text":
            raise ValueError(f"{provider} is not a text provider.")
        self.hub.set_fallback_provider("text", provider)
        if model:
            from runtime.db import update_record
            from runtime.config import utc_now

            return update_record("model_providers", row["id"], {"fallback_model": model, "updated_at": utc_now()})
        return row
