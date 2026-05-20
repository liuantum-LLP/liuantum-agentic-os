"""Auto changelog generation for Liuant Agentic OS v2.4.0.

Generates changelog entries by diffing between pack versions.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.skills.packs import (
    IMPORTED_DIR,
    PACK_MANIFEST_NAME,
    _load_pack_registry,
    validate_pack,
)


def _extract_pack_to_temp(pack_path: Path) -> Path | None:
    """Extract pack to temp directory and return the root."""
    tmp = Path(tempfile.mkdtemp())
    if pack_path.is_dir():
        return pack_path

    try:
        with zipfile.ZipFile(pack_path, "r") as zf:
            zf.extractall(tmp)
            entries = [e.rstrip("/") for e in zf.namelist()]
            top_dirs = set()
            for e in entries:
                parts = Path(e).parts
                if len(parts) > 1:
                    top_dirs.add(parts[0])
            if len(top_dirs) == 1:
                pack_root = tmp / top_dirs.pop()
                if pack_root.exists() and (pack_root / PACK_MANIFEST_NAME).exists():
                    return pack_root
            return tmp
    except zipfile.BadZipFile:
        return None


def _get_pack_skills(extracted: Path) -> dict[str, dict[str, Any]]:
    """Get skills from an extracted pack."""
    manifest_path = extracted / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return {}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    skills = {}
    for s in manifest.get("skills", []):
        skills[s["id"]] = s
    return skills


def _get_pack_workflows(extracted: Path) -> dict[str, dict[str, Any]]:
    """Get workflows from an extracted pack."""
    manifest_path = extracted / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return {}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workflows = {}
    for w in manifest.get("workflows", []):
        workflows[w["workflow_id"]] = w
    return workflows


def generate_changelog(
    old_pack_path: str | Path,
    new_pack_path: str | Path,
) -> dict[str, Any]:
    """Generate changelog by diffing two pack versions.

    Args:
        old_pack_path: Path to the old pack version.
        new_pack_path: Path to the new pack version.

    Returns:
        Changelog with added/removed/changed skills and workflows.
    """
    old_path = Path(old_pack_path)
    new_path = Path(new_pack_path)

    if not old_path.exists() or not new_path.exists():
        return {"status": "error", "message": "One or both pack files not found"}

    old_extracted = _extract_pack_to_temp(old_path)
    new_extracted = _extract_pack_to_temp(new_path)

    if not old_extracted or not new_extracted:
        return {"status": "error", "message": "Could not extract packs"}

    old_skills = _get_pack_skills(old_extracted)
    new_skills = _get_pack_skills(new_extracted)
    old_workflows = _get_pack_workflows(old_extracted)
    new_workflows = _get_pack_workflows(new_extracted)

    old_manifest = json.loads((old_extracted / PACK_MANIFEST_NAME).read_text(encoding="utf-8"))
    new_manifest = json.loads((new_extracted / PACK_MANIFEST_NAME).read_text(encoding="utf-8"))

    old_version = old_manifest.get("version", "0.0.0")
    new_version = new_manifest.get("version", "0.0.0")

    added_skills = [sid for sid in new_skills if sid not in old_skills]
    removed_skills = [sid for sid in old_skills if sid not in new_skills]
    changed_skills = []

    for sid in new_skills:
        if sid in old_skills:
            old_ver = old_skills[sid].get("version", "0.0.0")
            new_ver = new_skills[sid].get("version", "0.0.0")
            if old_ver != new_ver:
                changed_skills.append({
                    "skill_id": sid,
                    "old_version": old_ver,
                    "new_version": new_ver,
                })

    added_workflows = [wid for wid in new_workflows if wid not in old_workflows]
    removed_workflows = [wid for wid in old_workflows if wid not in new_workflows]

    old_perms = set()
    for s in old_skills.values():
        old_perms.update(s.get("permissions", []))
    new_perms = set()
    for s in new_skills.values():
        new_perms.update(s.get("permissions", []))

    added_permissions = list(new_perms - old_perms)
    removed_permissions = list(old_perms - new_perms)

    changelog_entries = []
    if added_skills:
        changelog_entries.append({
            "type": "added",
            "category": "skills",
            "items": added_skills,
            "description": f"Added {len(added_skills)} new skill(s)",
        })
    if removed_skills:
        changelog_entries.append({
            "type": "removed",
            "category": "skills",
            "items": removed_skills,
            "description": f"Removed {len(removed_skills)} skill(s)",
        })
    if changed_skills:
        changelog_entries.append({
            "type": "changed",
            "category": "skills",
            "items": changed_skills,
            "description": f"Updated {len(changed_skills)} skill(s)",
        })
    if added_workflows:
        changelog_entries.append({
            "type": "added",
            "category": "workflows",
            "items": added_workflows,
            "description": f"Added {len(added_workflows)} workflow(s)",
        })
    if removed_workflows:
        changelog_entries.append({
            "type": "removed",
            "category": "workflows",
            "items": removed_workflows,
            "description": f"Removed {len(removed_workflows)} workflow(s)",
        })
    if added_permissions:
        changelog_entries.append({
            "type": "added",
            "category": "permissions",
            "items": added_permissions,
            "description": f"Added {len(added_permissions)} permission(s)",
        })
    if removed_permissions:
        changelog_entries.append({
            "type": "removed",
            "category": "permissions",
            "items": removed_permissions,
            "description": f"Removed {len(removed_permissions)} permission(s)",
        })

    return {
        "status": "ok",
        "pack_id": new_manifest.get("pack_id", ""),
        "old_version": old_version,
        "new_version": new_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": changelog_entries,
        "summary": {
            "skills_added": len(added_skills),
            "skills_removed": len(removed_skills),
            "skills_changed": len(changed_skills),
            "workflows_added": len(added_workflows),
            "workflows_removed": len(removed_workflows),
            "permissions_added": len(added_permissions),
            "permissions_removed": len(removed_permissions),
        },
    }


def generate_changelog_from_registry(pack_id: str) -> dict[str, Any]:
    """Generate changelog from imported pack registry history."""
    registry = _load_pack_registry()
    pack_info = registry.get("packs", {}).get(pack_id)
    if not pack_info:
        return {"status": "error", "message": f"Pack '{pack_id}' not found in registry"}

    imported_dir = IMPORTED_DIR / pack_id
    manifest_path = imported_dir / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return {"status": "error", "message": "Pack manifest not found"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing_changelog = manifest.get("changelog", [])

    return {
        "status": "ok",
        "pack_id": pack_id,
        "version": manifest.get("version", ""),
        "existing_changelog": existing_changelog,
        "note": "Use generate_changelog() with two pack versions to auto-generate",
    }


def update_pack_changelog(
    pack_path: str | Path,
    changelog_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Update a pack's manifest with new changelog entries.

    Args:
        pack_path: Path to pack source directory.
        changelog_entries: List of changelog entries to add.

    Returns:
        Update result.
    """
    pack_path = Path(pack_path)
    manifest_path = pack_path / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return {"status": "error", "message": f"{PACK_MANIFEST_NAME} not found"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = manifest.get("changelog", [])
    existing.extend(changelog_entries)
    manifest["changelog"] = existing

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "status": "updated",
        "pack_id": manifest.get("pack_id", ""),
        "total_entries": len(existing),
    }
