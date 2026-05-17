"""Model role configuration for Liuant Agentic OS v1.1.0.

Each role maps to a provider+model pair. Roles are used by the model router
to select the best model for a given task. Discussion mode lets multiple
roles collaborate on a single response.
"""

from __future__ import annotations

import json
from typing import Any

from runtime.config import SettingsManager, utc_now
from runtime.db import get_record, insert_record, update_record
from runtime.providers import ModelHub

VALID_ROLES = ("default", "thinking", "coding", "planning", "fast", "fallback")

DEFAULT_ROLE_CONFIG = {
    "default": {"provider": "", "model": ""},
    "thinking": {"provider": "", "model": ""},
    "coding": {"provider": "", "model": ""},
    "planning": {"provider": "", "model": ""},
    "fast": {"provider": "", "model": ""},
    "fallback": {"provider": "", "model": ""},
}

DISCUSSION_DEFAULTS = {
    "discussion_mode_enabled": "false",
    "discussion_mode_default_rounds": "2",
    "discussion_mode_max_rounds": "4",
    "discussion_mode_final_role": "thinking",
}


class ModelRoleManager:
    """Manages model role configuration stored in the settings table."""

    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.hub = ModelHub()

    # -- defaults -----------------------------------------------------------

    def ensure_defaults(self) -> None:
        """Insert default role config and discussion settings if missing."""
        self.settings.ensure_defaults()
        existing = self._load_roles()
        merged = {**DEFAULT_ROLE_CONFIG, **existing}
        self._save_roles(merged)
        for key, value in DISCUSSION_DEFAULTS.items():
            if not get_record("settings", key):
                self.settings.set(key, value)

    # -- role CRUD ----------------------------------------------------------

    def get_all_roles(self) -> dict[str, Any]:
        """Return full role config plus discussion mode settings."""
        self.ensure_defaults()
        roles = self._load_roles()
        discussion = self._load_discussion_settings()
        return {"roles": roles, "discussion": discussion}

    def get_role(self, role: str) -> dict[str, Any]:
        """Return config for a single role."""
        self.ensure_defaults()
        if role not in VALID_ROLES:
            raise ValueError(f"Unknown role: {role}. Valid roles: {', '.join(VALID_ROLES)}")
        roles = self._load_roles()
        cfg = roles.get(role, DEFAULT_ROLE_CONFIG.get(role, {}))
        return {
            "role": role,
            "provider": cfg.get("provider", ""),
            "model": cfg.get("model", ""),
            "configured": bool(cfg.get("provider") and cfg.get("model")),
        }

    def set_role(self, role: str, provider: str, model: str) -> dict[str, Any]:
        """Set provider and model for a role."""
        self.ensure_defaults()
        if role not in VALID_ROLES:
            raise ValueError(f"Unknown role: {role}. Valid roles: {', '.join(VALID_ROLES)}")
        roles = self._load_roles()
        roles[role] = {"provider": provider, "model": model}
        self._save_roles(roles)
        return self.get_role(role)

    def reset_role(self, role: str) -> dict[str, Any]:
        """Reset a role to empty config."""
        self.ensure_defaults()
        if role not in VALID_ROLES:
            raise ValueError(f"Unknown role: {role}. Valid roles: {', '.join(VALID_ROLES)}")
        roles = self._load_roles()
        roles[role] = {"provider": "", "model": ""}
        self._save_roles(roles)
        return self.get_role(role)

    def reset_all_roles(self) -> dict[str, Any]:
        """Reset all roles to defaults."""
        self.ensure_defaults()
        self._save_roles({**DEFAULT_ROLE_CONFIG})
        return self.get_all_roles()

    # -- test ---------------------------------------------------------------

    def test_role(self, role: str) -> dict[str, Any]:
        """Test a role's provider/model by calling the provider test."""
        self.ensure_defaults()
        role_cfg = self.get_role(role)
        if not role_cfg["configured"]:
            return {
                "role": role,
                "status": "not_configured",
                "message": f"Role '{role}' has no provider/model configured.",
                "provider": "",
                "model": "",
            }
        provider = role_cfg["provider"]
        try:
            provider_info = self.hub.get_provider(provider)
            test_result = self.hub.test_provider(provider)
            return {
                "role": role,
                "status": test_result["status"],
                "success": test_result["success"],
                "message": test_result["message"],
                "provider": provider,
                "model": role_cfg["model"],
                "provider_info": self.hub._sanitize(provider_info) if hasattr(self.hub, "_sanitize") else provider_info,
            }
        except ValueError:
            return {
                "role": role,
                "status": "provider_not_found",
                "success": False,
                "message": f"Provider '{provider}' not found in ModelHub.",
                "provider": provider,
                "model": role_cfg["model"],
            }

    # -- discussion settings ------------------------------------------------

    def get_discussion_settings(self) -> dict[str, Any]:
        """Return discussion mode settings."""
        self.ensure_defaults()
        return self._load_discussion_settings()

    def set_discussion_setting(self, key: str, value: str) -> dict[str, Any]:
        """Set a single discussion mode setting."""
        self.ensure_defaults()
        if key not in DISCUSSION_DEFAULTS:
            raise ValueError(f"Unknown discussion setting: {key}")
        self.settings.set(key, value)
        return self.get_discussion_settings()

    # -- internal helpers ---------------------------------------------------

    def _load_roles(self) -> dict[str, dict[str, str]]:
        row = get_record("settings", "model_roles_config")
        if not row or not row.get("value"):
            return {**DEFAULT_ROLE_CONFIG}
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return {**DEFAULT_ROLE_CONFIG}

    def _save_roles(self, roles: dict[str, dict[str, str]]) -> None:
        value = json.dumps(roles, sort_keys=True)
        if not get_record("settings", "model_roles_config"):
            insert_record("settings", {"id": "model_roles_config", "key": "model_roles_config", "value": value, "created_at": utc_now(), "updated_at": utc_now()})
        update_record("settings", "model_roles_config", {"value": value, "updated_at": utc_now()})

    def _load_discussion_settings(self) -> dict[str, Any]:
        result = {}
        for key in DISCUSSION_DEFAULTS:
            row = get_record("settings", key)
            result[key] = row["value"] if row else DISCUSSION_DEFAULTS[key]
        result["discussion_mode_default_rounds"] = int(result.get("discussion_mode_default_rounds", "2"))
        result["discussion_mode_max_rounds"] = int(result.get("discussion_mode_max_rounds", "4"))
        result["discussion_mode_enabled"] = result.get("discussion_mode_enabled", "false").lower() == "true"
        return result
