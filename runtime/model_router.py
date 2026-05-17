"""Model role router for Liuant Agentic OS v1.1.0.

Deterministically maps a user message to the best model role based on
keyword patterns. No cloud AI is used for routing.
"""

from __future__ import annotations

import re
from typing import Any

ROLE_PATTERNS: dict[str, list[str]] = {
    "coding": [
        r"\b(code|coding|debug|fix\s*error|implement|refactor|test|API|database|terminal\s*error|traceback)\b",
        r"\b(python|javascript|typescript|rust|go|java|flask|django|react|flutter)\b.*\b(error|bug|issue|fix)\b",
        r"\b(error|bug|issue|fix|patch)\b.*\b(python|javascript|typescript|rust|go|java|flask|django|react|flutter)\b",
        r"\b(write|create|build)\b.*\b(function|class|module|script|endpoint|route|component)\b",
        r"\b(function|class|module|script|endpoint|route|component)\b.*\b(write|create|build)\b",
        r"\b(unit\s*test|integration\s*test|test\s*case)\b",
        r"\b(security\s*risk|vulnerability|CVE|exploit)\b.*\b(code|fix|patch)\b",
        r"\b(rewrite|optimize|improve)\b.*\b(performance|speed|memory)\b",
    ],
    "planning": [
        r"\b(roadmap|plan|strategy|schedule|project\s*breakdown|milestone|business\s*plan|launch\s*plan)\b",
        r"\b(create|write|draft)\b.*\b(plan|roadmap|strategy|timeline|schedule|proposal)\b",
        r"\b(plan|roadmap|strategy|timeline|schedule|proposal)\b.*\b(create|write|draft)\b",
        r"\b(marketing|campaign|product|feature|go-to-market)\b.*\b(strategy|plan|launch)\b",
        r"\b(step\s*by\s*step|break\s*down|phase|stage)\b.*\b(plan|approach|execution)\b",
        r"\b(goal|objective|target)\b.*\b(achieve|reach|meet)\b",
        r"\b(content\s*calendar|editorial\s*plan|posting\s*schedule)\b",
    ],
    "thinking": [
        r"\b(analyze|compare|decide|reason|architecture|pros\s*and\s*cons|review|security\s*risk)\b",
        r"\b(what\s*do\s*you\s*think|your\s*opinion|evaluate|assess|weigh)\b",
        r"\b(advantage|disadvantage|trade.?off|limitation|constraint)\b",
        r"\b(why|how\s*does|explain\s*the)\b.*\b(work|function|design|approach)\b",
        r"\b(risk|threat|vulnerability)\b.*\b(analysis|assessment|review)\b",
        r"\b(best\s*practice|recommendation|guideline)\b",
        r"\b(should\s*I|should\s*we|is\s*it\s*better)\b",
    ],
}

ROLE_PRIORITY = ["coding", "planning", "thinking", "fast", "default"]


def route_task_to_role(message: str, context: dict[str, Any] | None = None) -> str:
    """Return the best role for a message. Deterministic, no cloud AI."""
    message_lower = message.lower().strip()

    for role in ROLE_PRIORITY:
        if role == "fast" or role == "default":
            continue
        patterns = ROLE_PATTERNS.get(role, [])
        matches = sum(1 for p in patterns if re.search(p, message_lower))
        if matches > 0:
            return role

    return "default"


def get_model_for_role(role: str, role_manager: Any | None = None) -> dict[str, Any]:
    """Return the provider and model for a given role."""
    if role_manager is None:
        from runtime.model_roles import ModelRoleManager
        role_manager = ModelRoleManager()

    role_cfg = role_manager.get_role(role)
    if role_cfg["configured"]:
        return {
            "role": role,
            "provider": role_cfg["provider"],
            "model": role_cfg["model"],
            "configured": True,
        }

    if role != "default":
        fallback_cfg = role_manager.get_role("fallback")
        if fallback_cfg["configured"]:
            return {
                "role": "fallback",
                "provider": fallback_cfg["provider"],
                "model": fallback_cfg["model"],
                "configured": True,
                "fallback_from": role,
            }

    default_cfg = role_manager.get_role("default")
    if default_cfg["configured"]:
        return {
            "role": "default",
            "provider": default_cfg["provider"],
            "model": default_cfg["model"],
            "configured": True,
            "fallback_from": role,
        }

    return {
        "role": role,
        "provider": "",
        "model": "",
        "configured": False,
        "message": f"No model configured for role '{role}' and no fallback/default available.",
    }
