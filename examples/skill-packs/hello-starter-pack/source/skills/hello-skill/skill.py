"""Hello Skill - A minimal starter skill for Liuant Agentic OS.

No permissions required. Simply greets the user.
Supports both import-based and process-isolated execution.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def execute(ctx: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute the hello skill."""
    message = inputs.get("message", "World")
    greeting = f"Hello, {message}! Welcome to Liuant Agentic OS."
    return {
        "status": "completed",
        "result": {"greeting": greeting, "skill_id": ctx.skill_id, "permissions_used": []},
        "actions": [],
        "warnings": [],
        "approval_required": False,
    }


def run(ctx: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    return execute(ctx, inputs)


class _ProcessContext:
    """Minimal context for process-isolated execution."""
    def __init__(self, context: dict[str, Any]) -> None:
        self.skill_id = context["skill_id"]
        self.inputs = context["inputs"]
        self.permissions = context["permissions"]
        self.approved_permissions = context["approved_permissions"]
        self.workspace = context["workspace"]
        self.skill_dir = context["allowed_paths"][0] if context["allowed_paths"] else ""

    def has_permission(self, permission: str) -> bool:
        return permission in self.approved_permissions

    def has_any_permission(self, *permissions: str) -> bool:
        return any(p in self.approved_permissions for p in permissions)

    def resolve_path(self, path: str) -> str:
        import os
        resolved = os.path.realpath(path)
        for allowed in (self.skill_dir, self.workspace):
            if resolved.startswith(os.path.realpath(allowed)):
                return resolved
        raise PermissionError(f"Path '{path}' is outside allowed directories")

    def get_model_client(self) -> dict[str, Any]:
        return {"available": True, "message": "Model access requires models.generate permission"}

    def get_usage_client(self) -> dict[str, Any]:
        return {"available": True, "message": "Usage tracking available"}


if __name__ == "__main__":
    if "--liuant-skill-run" in sys.argv:
        raw = sys.stdin.read()
        context = json.loads(raw)
        ctx = _ProcessContext(context)
        result = execute(ctx, context["inputs"])
        print(json.dumps(result))
    else:
        print("Hello Skill — use via Liuant CLI: ./liuant skills run hello-skill")
