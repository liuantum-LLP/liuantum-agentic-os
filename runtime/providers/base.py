from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    category: str
    provider_type: str
    base_url: str = ""
    api_key_env: str = ""
    default_model: str = ""
    fallback_model: str = ""
    is_enabled: bool = False
    is_default: bool = False
    status: str = "placeholder"
    capabilities: dict[str, bool] = field(default_factory=dict)
    models: list[str] = field(default_factory=list)
    notes: str = ""
    setup_instruction: str = ""

    def to_record(self, now: str) -> dict[str, Any]:
        return {
            "id": self.name,
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "env_var": self.api_key_env,
            "api_key_masked": "",
            "default_model": self.default_model,
            "fallback_model": self.fallback_model,
            "is_enabled": self.is_enabled,
            "is_default": self.is_default,
            "status": self.status,
            "capabilities": self.capabilities,
            "models": self.models,
            "last_tested_at": None,
            "notes": self.notes,
            "setup_instruction": self.setup_instruction,
            "created_at": now,
            "updated_at": now,
        }
