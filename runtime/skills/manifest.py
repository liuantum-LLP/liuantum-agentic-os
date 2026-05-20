"""Skill manifest schema for Liuant Agentic OS v2.0.0.

Defines the structure and validation rules for skill.json manifest files.
"""

from __future__ import annotations

from typing import Any

MANIFEST_SCHEMA_VERSION = "1.0"

REQUIRED_FIELDS = [
    "schema_version",
    "id",
    "name",
    "version",
    "description",
    "author",
    "license",
    "entrypoint",
    "runtime",
    "category",
]

KNOWN_PERMISSIONS = {
    "filesystem.read",
    "filesystem.write",
    "network.http",
    "secrets.read",
    "tools.browser",
    "tools.email_draft",
    "tools.social_draft",
    "tools.shell",
    "workspace.read",
    "workspace.write",
    "usage.read",
    "models.generate",
    "browser.open_url",
    "browser.search_web",
    "browser.read_page",
    "browser.screenshot",
    "browser.click",
    "browser.fill_form",
    "browser.download_file",
    "browser.upload_file",
    "desktop.open_app",
    "desktop.open_file",
    "desktop.open_folder",
    "desktop.reveal_file",
    "desktop.clipboard_read",
    "desktop.clipboard_write",
    "system.shell_command",
}

PERMISSION_RISK_LEVELS: dict[str, str] = {
    "filesystem.read": "low",
    "workspace.read": "low",
    "usage.read": "low",
    "models.generate": "medium",
    "filesystem.write": "medium",
    "workspace.write": "medium",
    "tools.browser": "medium",
    "tools.email_draft": "high",
    "tools.social_draft": "high",
    "network.http": "high",
    "tools.shell": "critical",
    "secrets.read": "critical",
    "browser.open_url": "low",
    "browser.read_page": "low",
    "desktop.open_folder": "low",
    "desktop.reveal_file": "low",
    "browser.search_web": "medium",
    "browser.screenshot": "medium",
    "desktop.open_app": "medium",
    "desktop.open_file": "medium",
    "desktop.clipboard_read": "medium",
    "browser.click": "high",
    "browser.fill_form": "high",
    "browser.download_file": "high",
    "browser.upload_file": "high",
    "desktop.clipboard_write": "high",
    "system.shell_command": "critical",
}

CRITICAL_PERMISSIONS = {
    "secrets.read",
    "tools.shell",
    "network.http",
    "tools.email_draft",
    "tools.social_draft",
    "system.shell_command",
}

SUPPORTED_RUNTIMES = {"python"}

VALID_CATEGORIES = {
    "analytics",
    "productivity",
    "development",
    "communication",
    "automation",
    "review",
    "utility",
    "other",
}

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$"

SEMVER_PATTERN = r"^\d+\.\d+\.\d+"

SECRET_PATTERNS = [
    r"(?i)(api.?key|secret|token|password)\s*[=:]\s*[\"'\\]?[^\"'\\,}]+[\"'\\]?",
    r"sk-[A-Za-z0-9]{20,}",
    r"Bearer\s+[A-Za-z0-9._\-]+",
]

COMMAND_SCHEMA = {
    "type": "object",
    "required": ["name", "description"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "input_schema": {"type": "object"},
    },
}

TRIGGER_SCHEMA = {
    "type": "object",
    "required": ["type", "pattern"],
    "properties": {
        "type": {"type": "string", "enum": ["keyword", "regex", "intent"]},
        "pattern": {"type": "string"},
        "description": {"type": "string"},
    },
}

UI_SCHEMA = {
    "type": "object",
    "properties": {
        "panel": {"type": "boolean"},
        "settings": {"type": "object"},
        "inputs": {"type": "array"},
    },
}


def get_risk_level(permissions: list[str]) -> str:
    """Calculate overall risk level from permissions."""
    if not permissions:
        return "low"
    levels = [PERMISSION_RISK_LEVELS.get(p, "low") for p in permissions]
    if "critical" in levels:
        return "critical"
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def is_critical_permission(permission: str) -> bool:
    """Check if a permission is critical."""
    return permission in CRITICAL_PERMISSIONS


def default_manifest(skill_id: str, name: str = "", description: str = "") -> dict[str, Any]:
    """Generate a default skill manifest template."""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "id": skill_id,
        "name": name or skill_id.replace("-", " ").title(),
        "version": "0.1.0",
        "description": description or "A Liuant skill.",
        "author": "Liuant contributors",
        "license": "MIT",
        "entrypoint": "skill.py",
        "runtime": "python",
        "category": "utility",
        "permissions": [],
        "commands": [],
        "triggers": [],
        "ui": {},
        "tags": [],
    }
