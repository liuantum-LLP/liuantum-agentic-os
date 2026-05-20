"""Skill registry for Liuant Agentic OS v2.0.0.

Manages skill installation, validation, enabling/disabling, and permission tracking.
All skills are local-first with no marketplace or cloud sync.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.config import utc_now
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.skills.manifest import CRITICAL_PERMISSIONS, is_critical_permission
from runtime.skills.validator import validate_skill
from runtime.storage import ROOT, WORKSPACE

SKILLS_DIR = WORKSPACE / "skills"
INSTALLED_DIR = SKILLS_DIR / "installed"
ENABLED_DIR = SKILLS_DIR / "enabled"
REGISTRY_FILE = SKILLS_DIR / "registry.json"

SKILL_TABLE = "skill_records"


def _ensure_dirs() -> None:
    """Ensure skill directories exist."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
    ENABLED_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict[str, Any]:
    """Load the skill registry."""
    _ensure_dirs()
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"skills": {}}


def _save_registry(registry: dict[str, Any]) -> None:
    """Save the skill registry."""
    _ensure_dirs()
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")


def _record_to_dict(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a DB record to a skill dict."""
    if "data" in record:
        try:
            return json.loads(record["data"])
        except (json.JSONDecodeError, TypeError):
            pass
    return record


def list_installed_skills() -> list[dict[str, Any]]:
    """List all installed skills."""
    _ensure_dirs()
    registry = _load_registry()
    skills = []
    for skill_id, info in registry.get("skills", {}).items():
        skills.append({
            "id": skill_id,
            "name": info.get("name", skill_id),
            "version": info.get("version", "unknown"),
            "path": info.get("path", ""),
            "enabled": info.get("enabled", False),
            "installed_at": info.get("installed_at", ""),
            "permissions": info.get("permissions", []),
            "approved_permissions": info.get("approved_permissions", []),
            "validation_status": info.get("validation_status", "unknown"),
            "risk_level": info.get("risk_level", "unknown"),
        })
    return sorted(skills, key=lambda s: s["id"])


def get_skill(skill_id: str) -> dict[str, Any] | None:
    """Get a single skill by ID."""
    registry = _load_registry()
    info = registry.get("skills", {}).get(skill_id)
    if not info:
        return None
    return {
        "id": skill_id,
        "name": info.get("name", skill_id),
        "version": info.get("version", "unknown"),
        "path": info.get("path", ""),
        "enabled": info.get("enabled", False),
        "installed_at": info.get("installed_at", ""),
        "permissions": info.get("permissions", []),
        "approved_permissions": info.get("approved_permissions", []),
        "validation_status": info.get("validation_status", "unknown"),
        "risk_level": info.get("risk_level", "unknown"),
    }


def install_skill(source_path: str | Path, upgrade: bool = False) -> dict[str, Any]:
    """Install a skill from a local path.

    Copies the skill folder to skills/installed/<skill_id>/.
    Installed skills are disabled by default.
    """
    _ensure_dirs()
    source = Path(source_path)
    if not source.exists():
        return {"status": "error", "message": f"Source path not found: {source}"}

    manifest_path = source / "skill.json"
    if not manifest_path.exists():
        return {"status": "error", "message": "skill.json not found in source"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"Invalid skill.json: {exc}"}

    skill_id = manifest.get("id", "")
    if not skill_id:
        return {"status": "error", "message": "Skill manifest missing 'id' field"}

    # Validate first
    validation = validate_skill(source)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Validation failed", "errors": validation["errors"]}

    registry = _load_registry()

    # Check for duplicate
    if skill_id in registry.get("skills", {}) and not upgrade:
        return {
            "status": "error",
            "message": f"Skill '{skill_id}' already installed. Use --upgrade to update.",
        }

    # Copy skill folder
    dest = INSTALLED_DIR / skill_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)

    # Update registry
    registry.setdefault("skills", {})[skill_id] = {
        "name": manifest.get("name", skill_id),
        "version": manifest.get("version", "0.1.0"),
        "path": str(dest),
        "enabled": False,
        "installed_at": utc_now(),
        "permissions": manifest.get("permissions", []),
        "approved_permissions": [],
        "validation_status": validation["status"],
        "risk_level": validation["risk_level"],
    }
    _save_registry(registry)

    return {
        "status": "installed",
        "skill_id": skill_id,
        "name": manifest.get("name", skill_id),
        "version": manifest.get("version", "0.1.0"),
        "enabled": False,
        "validation_status": validation["status"],
        "risk_level": validation["risk_level"],
        "warnings": validation.get("warnings", []),
        "message": f"Skill '{skill_id}' installed. It is disabled by default. Run 'liuant skills enable {skill_id}' to enable.",
    }


def uninstall_skill(skill_id: str, confirm: bool = False) -> dict[str, Any]:
    """Uninstall a skill. Removes registry entry and skill folder."""
    if not confirm:
        return {"status": "error", "message": f"Uninstalling '{skill_id}' requires --confirm true."}

    registry = _load_registry()
    if skill_id not in registry.get("skills", {}):
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}

    # Remove skill folder
    dest = INSTALLED_DIR / skill_id
    if dest.exists():
        shutil.rmtree(dest)

    # Remove from enabled
    enabled_link = ENABLED_DIR / skill_id
    if enabled_link.exists():
        enabled_link.unlink()

    # Remove from registry
    del registry["skills"][skill_id]
    _save_registry(registry)

    return {"status": "uninstalled", "skill_id": skill_id, "message": f"Skill '{skill_id}' uninstalled."}


def enable_skill(skill_id: str) -> dict[str, Any]:
    """Enable a skill. Requires validation passed."""
    registry = _load_registry()
    if skill_id not in registry.get("skills", {}):
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}

    info = registry["skills"][skill_id]

    # Check validation
    if info.get("validation_status") == "failed":
        return {"status": "error", "message": f"Skill '{skill_id}' failed validation. Fix errors before enabling."}

    # Check critical permissions
    permissions = info.get("permissions", [])
    approved = info.get("approved_permissions", [])
    critical_unapproved = [p for p in permissions if is_critical_permission(p) and p not in approved]
    if critical_unapproved:
        return {
            "status": "error",
            "message": f"Skill '{skill_id}' has unapproved critical permissions: {critical_unapproved}. Approve them first.",
            "unapproved_critical": critical_unapproved,
        }

    info["enabled"] = True
    registry["skills"][skill_id] = info
    _save_registry(registry)

    return {"status": "enabled", "skill_id": skill_id, "message": f"Skill '{skill_id}' enabled."}


def disable_skill(skill_id: str) -> dict[str, Any]:
    """Disable a skill."""
    registry = _load_registry()
    if skill_id not in registry.get("skills", {}):
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}

    registry["skills"][skill_id]["enabled"] = False
    _save_registry(registry)

    return {"status": "disabled", "skill_id": skill_id, "message": f"Skill '{skill_id}' disabled."}


def skill_status(skill_id: str) -> dict[str, Any]:
    """Get detailed status of a skill."""
    skill = get_skill(skill_id)
    if not skill:
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}
    return skill


def skill_permissions(skill_id: str) -> dict[str, Any]:
    """Get permissions for a skill."""
    skill = get_skill(skill_id)
    if not skill:
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}
    return {
        "skill_id": skill_id,
        "permissions": skill.get("permissions", []),
        "approved_permissions": skill.get("approved_permissions", []),
        "unapproved_critical": [
            p for p in skill.get("permissions", [])
            if is_critical_permission(p) and p not in skill.get("approved_permissions", [])
        ],
    }


def approve_skill_permissions(skill_id: str, permissions: list[str], confirm: bool = False) -> dict[str, Any]:
    """Approve specific permissions for a skill."""
    if not confirm:
        return {"status": "error", "message": "Approving permissions requires --confirm true."}

    registry = _load_registry()
    if skill_id not in registry.get("skills", {}):
        return {"status": "error", "message": f"Skill '{skill_id}' not found."}

    info = registry["skills"][skill_id]
    approved = set(info.get("approved_permissions", []))
    approved.update(permissions)
    info["approved_permissions"] = sorted(approved)
    registry["skills"][skill_id] = info
    _save_registry(registry)

    return {
        "status": "approved",
        "skill_id": skill_id,
        "approved_permissions": info["approved_permissions"],
        "message": f"Permissions approved for '{skill_id}'.",
    }


def get_skill_templates() -> list[dict[str, Any]]:
    """List available skill templates."""
    templates = []
    for templates_dir in [SKILLS_DIR / "templates", ROOT / "examples" / "templates" / "skills"]:
        if templates_dir.exists():
            for item in sorted(templates_dir.iterdir()):
                if item.is_dir() and (item / "skill.json").exists():
                    try:
                        manifest = json.loads((item / "skill.json").read_text(encoding="utf-8"))
                        templates.append({
                            "id": manifest.get("id", item.name),
                            "name": manifest.get("name", item.name),
                            "description": manifest.get("description", ""),
                            "category": manifest.get("category", "other"),
                            "path": str(item),
                        })
                    except (json.JSONDecodeError, OSError):
                        pass
    return templates


def discover_skills(paths: list[str] | None = None) -> list[dict[str, Any]]:
    """Discover skills in local directories."""
    from runtime.skills.validator import validate_skill
    search_paths = paths or [
        str(ROOT / "examples" / "skills"),
        str(INSTALLED_DIR),
        str(SKILLS_DIR / "templates"),
    ]
    discovered = []
    for search_path in search_paths:
        path = Path(search_path)
        if not path.exists():
            continue
        for item in sorted(path.iterdir()):
            if item.is_dir() and (item / "skill.json").exists():
                try:
                    manifest = json.loads((item / "skill.json").read_text(encoding="utf-8"))
                    validation = validate_skill(item)
                    skill_id = manifest.get("id", item.name)
                    registry = _load_registry()
                    is_installed = skill_id in registry.get("skills", {})
                    discovered.append({
                        "id": skill_id,
                        "name": manifest.get("name", skill_id),
                        "version": manifest.get("version", "0.1.0"),
                        "description": manifest.get("description", ""),
                        "path": str(item),
                        "installed": is_installed,
                        "risk_level": validation.get("risk_level", "unknown"),
                        "category": manifest.get("category", "other"),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
    return discovered


def search_skills(query: str) -> list[dict[str, Any]]:
    """Search discovered skills by query string."""
    all_skills = discover_skills()
    if not query:
        return all_skills
    query_lower = query.lower()
    return [
        s for s in all_skills
        if query_lower in s["id"].lower()
        or query_lower in s["name"].lower()
        or query_lower in s["description"].lower()
        or query_lower in s.get("category", "").lower()
    ]


def create_skill_from_template(template_id: str, new_skill_id: str, new_name: str = "") -> dict[str, Any]:
    """Create a new skill from a template."""
    templates = get_skill_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        return {"status": "error", "message": f"Template '{template_id}' not found."}

    template_path = Path(template["path"])
    dest = INSTALLED_DIR / new_skill_id
    if dest.exists():
        return {"status": "error", "message": f"Skill '{new_skill_id}' already exists."}

    shutil.copytree(template_path, dest)

    manifest_path = dest / "skill.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["id"] = new_skill_id
        manifest["name"] = new_name or new_skill_id.replace("-", " ").title()
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    skill_py = dest / "skill.py"
    if skill_py.exists():
        content = skill_py.read_text(encoding="utf-8")
        content = content.replace("template-skill", new_skill_id)
        skill_py.write_text(content, encoding="utf-8")

    return {
        "status": "created",
        "skill_id": new_skill_id,
        "path": str(dest),
        "message": f"Skill '{new_skill_id}' created from template '{template_id}'. Not installed or enabled.",
    }


def upgrade_skill(source_path: str | Path, confirm: bool = False, force: bool = False) -> dict[str, Any]:
    """Upgrade an existing skill from a local path."""
    from runtime.skills.validator import validate_skill
    _ensure_dirs()
    source = Path(source_path)
    if not source.exists():
        return {"status": "error", "message": f"Source path not found: {source}"}

    manifest_path = source / "skill.json"
    if not manifest_path.exists():
        return {"status": "error", "message": "skill.json not found in source"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"Invalid skill.json: {exc}"}

    skill_id = manifest.get("id", "")
    if not skill_id:
        return {"status": "error", "message": "Skill manifest missing 'id' field"}

    registry = _load_registry()
    if skill_id not in registry.get("skills", {}):
        return {"status": "error", "message": f"Skill '{skill_id}' not installed. Use install instead."}

    existing = registry["skills"][skill_id]
    existing_version = existing.get("version", "0.0.0")
    new_version = manifest.get("version", "0.0.0")

    if not force and new_version <= existing_version:
        return {"status": "error", "message": f"New version {new_version} is not greater than installed {existing_version}. Use --force to override."}

    validation = validate_skill(source)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Validation failed", "errors": validation["errors"]}

    # Backup existing skill
    backup_path = INSTALLED_DIR / f"{skill_id}_backup_{existing_version}"
    dest = INSTALLED_DIR / skill_id
    if dest.exists():
        shutil.copytree(dest, backup_path)

    # Copy new version
    shutil.rmtree(dest)
    shutil.copytree(source, dest)

    # Preserve approved permissions only if no new permissions added
    old_permissions = set(existing.get("permissions", []))
    new_permissions = set(manifest.get("permissions", []))
    added_permissions = new_permissions - old_permissions
    approved = existing.get("approved_permissions", [])
    if added_permissions:
        approved = []

    existing.update({
        "version": new_version,
        "path": str(dest),
        "permissions": manifest.get("permissions", []),
        "approved_permissions": approved,
        "validation_status": validation["status"],
        "risk_level": validation["risk_level"],
    })
    registry["skills"][skill_id] = existing
    _save_registry(registry)

    return {
        "status": "upgraded",
        "skill_id": skill_id,
        "old_version": existing_version,
        "new_version": new_version,
        "backup_path": str(backup_path),
        "permissions_reset": bool(added_permissions),
        "added_permissions": list(added_permissions),
        "message": f"Skill '{skill_id}' upgraded from {existing_version} to {new_version}." + (f" Permissions reset due to new permissions: {added_permissions}" if added_permissions else ""),
    }
