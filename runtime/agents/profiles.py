from __future__ import annotations

from typing import Any

from runtime.agents.registry import BUILT_IN_AGENTS
from runtime.config import utc_now
from runtime.db import get_record, insert_record, list_records, update_record


class AgentProfileManager:
    def ensure_builtins(self) -> None:
        for agent in BUILT_IN_AGENTS:
            existing = get_record("agent_profiles", agent["slug"])
            row = {
                "id": agent["slug"],
                "name": agent["name"],
                "slug": agent["slug"],
                "role": agent.get("role", agent.get("name", "")),
                "goal": agent.get("goal", agent.get("purpose", "")),
                "instructions": agent.get("instructions", agent.get("purpose", "")),
                "personality": agent.get("personality", "calm, useful, approval-aware"),
                "tools_json": agent.get("tools", []),
                "permissions_json": agent.get("permissions", {"mode": "safe"}),
                "memory_scope": "workspace",
                "workflows_json": [],
                "example_tasks_json": agent.get("example_tasks", agent.get("capabilities", [])),
            "provider_preferences": agent.get("provider_preferences", {}),
            "preferred_model_role": agent.get("preferred_model_role", "default"),
            "allow_discussion_mode": agent.get("allow_discussion_mode", False),
            "discussion_roles": agent.get("discussion_roles", []),
            "discussion_rounds": agent.get("discussion_rounds", 2),
            "is_builtin": True,
                "enabled": existing.get("enabled", True) if existing else True,
                "created_at": existing.get("created_at", utc_now()) if existing else utc_now(),
                "updated_at": utc_now(),
            }
            insert_record("agent_profiles", row)

    def list(self) -> list[dict[str, Any]]:
        self.ensure_builtins()
        return sorted(list_records("agent_profiles"), key=lambda row: (not row.get("is_builtin"), row["name"]))

    def show(self, slug: str) -> dict[str, Any]:
        self.ensure_builtins()
        row = get_record("agent_profiles", slug)
        if not row:
            raise ValueError(f"Unknown agent: {slug}")
        return row

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        slug = data.get("slug") or data["name"].lower().replace(" ", "-")
        row = {
            "id": slug,
            "name": data.get("name", slug),
            "slug": slug,
            "role": data.get("role", "Custom Agent"),
            "goal": data.get("goal", data.get("instructions", "")),
            "instructions": data.get("instructions", ""),
            "personality": data.get("personality", "helpful and precise"),
            "tools_json": data.get("tools_json", []),
            "permissions_json": data.get("permissions_json", {"mode": "safe"}),
            "memory_scope": data.get("memory_scope", "workspace"),
            "workflows_json": data.get("workflows_json", []),
            "example_tasks_json": data.get("example_tasks_json", []),
            "provider_preferences": data.get("provider_preferences") or data.get("provider_preferences_json", {}),
            "preferred_model_role": data.get("preferred_model_role", "default"),
            "allow_discussion_mode": bool(data.get("allow_discussion_mode", False)),
            "discussion_roles": data.get("discussion_roles", []),
            "discussion_rounds": int(data.get("discussion_rounds", 2)),
            "is_builtin": False,
            "enabled": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        return insert_record("agent_profiles", row)

    def update(self, slug: str, data: dict[str, Any]) -> dict[str, Any]:
        self.show(slug)
        data["updated_at"] = utc_now()
        return update_record("agent_profiles", slug, data)

    def set_enabled(self, slug: str, enabled: bool) -> dict[str, Any]:
        self.show(slug)
        return update_record("agent_profiles", slug, {"enabled": enabled, "updated_at": utc_now()})
