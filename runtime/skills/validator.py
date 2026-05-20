"""Skill validator for Liuant Agentic OS v2.0.0.

Validates skill manifests and skill directories against the manifest schema.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from runtime.skills.manifest import (
    COMMAND_SCHEMA,
    ID_PATTERN,
    KNOWN_PERMISSIONS,
    REQUIRED_FIELDS,
    SECRET_PATTERNS,
    SEMVER_PATTERN,
    SUPPORTED_RUNTIMES,
    TRIGGER_SCHEMA,
    VALID_CATEGORIES,
    get_risk_level,
)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate a skill manifest dictionary.

    Returns:
        {
            "status": "passed | failed | warning",
            "errors": [],
            "warnings": [],
            "risk_level": "low | medium | high | critical"
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"status": "failed", "errors": errors, "warnings": warnings, "risk_level": "unknown"}

    # Validate ID is slug-safe
    skill_id = manifest.get("id", "")
    if not re.match(ID_PATTERN, skill_id):
        errors.append(f"Skill ID '{skill_id}' is not slug-safe. Must match: {ID_PATTERN}")

    # Validate version is semver-like
    version = manifest.get("version", "")
    if not re.match(SEMVER_PATTERN, str(version)):
        errors.append(f"Version '{version}' is not semver-like. Expected major.minor.patch")

    # Validate runtime
    runtime = manifest.get("runtime", "")
    if runtime not in SUPPORTED_RUNTIMES:
        errors.append(f"Unsupported runtime: '{runtime}'. Supported: {sorted(SUPPORTED_RUNTIMES)}")

    # Validate category
    category = manifest.get("category", "")
    if category not in VALID_CATEGORIES:
        warnings.append(f"Unknown category: '{category}'. Suggested: {sorted(VALID_CATEGORIES)}")

    # Validate permissions
    permissions = manifest.get("permissions", [])
    if not isinstance(permissions, list):
        errors.append("Permissions must be a list")
    else:
        for perm in permissions:
            if perm not in KNOWN_PERMISSIONS:
                errors.append(f"Unknown permission: '{perm}'")

    # Check for secrets in manifest
    manifest_str = json.dumps(manifest)
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, manifest_str):
            errors.append("Manifest contains secret-like values. Remove sensitive data.")
            break

    # Validate commands format
    commands = manifest.get("commands", [])
    if not isinstance(commands, list):
        errors.append("Commands must be a list")
    else:
        for cmd in commands:
            if not isinstance(cmd, dict):
                errors.append("Each command must be an object")
            elif "name" not in cmd or "description" not in cmd:
                errors.append(f"Command missing required fields (name, description): {cmd}")

    # Validate triggers format
    triggers = manifest.get("triggers", [])
    if not isinstance(triggers, list):
        errors.append("Triggers must be a list")
    else:
        for trigger in triggers:
            if not isinstance(trigger, dict):
                errors.append("Each trigger must be an object")
            elif "type" not in trigger or "pattern" not in trigger:
                errors.append(f"Trigger missing required fields (type, pattern): {trigger}")

    # Calculate risk level
    risk_level = get_risk_level(permissions) if isinstance(permissions, list) else "unknown"

    if errors:
        return {"status": "failed", "errors": errors, "warnings": warnings, "risk_level": risk_level}

    status = "warning" if warnings else "passed"
    return {"status": status, "errors": errors, "warnings": warnings, "risk_level": risk_level}


def validate_skill(path: str | Path) -> dict[str, Any]:
    """Validate a skill directory.

    Checks:
    - skill.json exists
    - manifest validates
    - entrypoint exists
    - README exists (warning if missing)
    - no suspicious install scripts
    - no absolute dangerous paths
    """
    skill_path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    # Check skill.json exists
    manifest_path = skill_path / "skill.json"
    if not manifest_path.exists():
        return {
            "status": "failed",
            "errors": ["skill.json not found"],
            "warnings": [],
            "risk_level": "unknown",
        }

    # Load and validate manifest
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "failed",
            "errors": [f"Invalid JSON in skill.json: {exc}"],
            "warnings": [],
            "risk_level": "unknown",
        }

    result = validate_manifest(manifest)
    errors.extend(result["errors"])
    warnings.extend(result["warnings"])

    if result["status"] == "failed":
        return result

    # Check entrypoint exists
    entrypoint = manifest.get("entrypoint", "skill.py")
    entrypoint_path = skill_path / entrypoint
    if not entrypoint_path.exists():
        errors.append(f"Entrypoint '{entrypoint}' not found")

    # Check README exists (warning)
    readme_path = skill_path / "README.md"
    if not readme_path.exists():
        warnings.append("README.md not found. Recommended for all skills.")

    # Check for suspicious install scripts
    suspicious_files = ["install.sh", "setup.sh", "post-install.sh", "pre-install.sh"]
    for sf in suspicious_files:
        if (skill_path / sf).exists():
            warnings.append(f"Suspicious install script found: {sf}")

    # Check for absolute dangerous paths in manifest
    manifest_str = json.dumps(manifest)
    dangerous_patterns = [r"/etc/", r"/usr/bin/", r"/root/", r"\\Windows\\"]
    for dp in dangerous_patterns:
        if re.search(dp, manifest_str):
            errors.append(f"Manifest contains suspicious absolute path pattern: {dp}")

    if errors:
        return {"status": "failed", "errors": errors, "warnings": warnings, "risk_level": result["risk_level"]}

    return {"status": result["status"], "errors": errors, "warnings": warnings, "risk_level": result["risk_level"]}
