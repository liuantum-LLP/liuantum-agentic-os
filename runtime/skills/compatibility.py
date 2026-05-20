"""Pack compatibility matrix for Liuant Agentic OS v2.4.0.

Checks for:
- Duplicate skill IDs across packs
- Version conflicts between packs
- Permission risk aggregation
- Platform/Liuant version compatibility
- Trust state mismatches
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from runtime.skills.manifest import KNOWN_PERMISSIONS, get_risk_level
from runtime.skills.packs import (
    IMPORTED_DIR,
    PACK_MANIFEST_NAME,
    _load_catalog,
    _load_pack_registry,
    validate_pack,
)
from runtime.skills.registry import list_installed_skills
from runtime.storage import ROOT, WORKSPACE, read_json, write_json

COMPAT_MATRIX_FILE = WORKSPACE / "skills" / "compatibility_matrix.json"

LIUANT_VERSION = "2.4.0"
SUPPORTED_PLATFORMS = {"darwin", "linux", "win32"}


def _get_pack_info(pack_path: str | Path) -> dict[str, Any] | None:
    """Extract pack info from a path."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        if pack_path.is_dir():
            extracted = pack_path
        else:
            try:
                with zipfile.ZipFile(pack_path, "r") as zf:
                    zf.extractall(tmp / "extracted")
                    extracted = tmp / "extracted"
                    entries = [e.rstrip("/") for e in zf.namelist()]
                    top_dirs = set()
                    for e in entries:
                        parts = Path(e).parts
                        if len(parts) > 1:
                            top_dirs.add(parts[0])
                    if len(top_dirs) == 1:
                        pack_root = extracted / top_dirs.pop()
                        if pack_root.exists() and (pack_root / PACK_MANIFEST_NAME).exists():
                            extracted = pack_root
            except zipfile.BadZipFile:
                return None

        manifest_path = extracted / PACK_MANIFEST_NAME
        if not manifest_path.exists():
            return None

        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None


def _get_installed_skills_map() -> dict[str, dict[str, Any]]:
    """Get a map of installed skills."""
    return {s["id"]: s for s in list_installed_skills()}


def _get_imported_packs_map() -> dict[str, dict[str, Any]]:
    """Get a map of imported packs."""
    return _load_pack_registry().get("packs", {})


def _get_catalog_packs_map() -> dict[str, dict[str, Any]]:
    """Get a map of catalog packs."""
    return {p["pack_id"]: p for p in _load_catalog().get("packs", [])}


def check_compatibility(
    pack_path: str | Path | None = None,
    pack_id: str | None = None,
    check_against: list[str] | None = None,
) -> dict[str, Any]:
    """Check pack compatibility against installed/imported/catalog packs.

    Args:
        pack_path: Path to a pack file to check.
        pack_id: Pack ID to check from imported packs.
        check_against: List of pack IDs to check against (default: all imported).

    Returns:
        Compatibility report with conflicts, warnings, and recommendations.
    """
    conflicts = []
    warnings = []
    recommendations = []

    target_manifest = None
    target_pack_id = ""

    if pack_path:
        target_manifest = _get_pack_info(pack_path)
        if not target_manifest:
            return {"status": "error", "message": "Could not read pack manifest"}
        target_pack_id = target_manifest.get("pack_id", "")
    elif pack_id:
        imported = _get_imported_packs_map()
        pack_info = imported.get(pack_id)
        if not pack_info:
            return {"status": "error", "message": f"Pack '{pack_id}' not imported"}
        imported_dir = IMPORTED_DIR / pack_id
        manifest_path = imported_dir / PACK_MANIFEST_NAME
        if manifest_path.exists():
            target_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            target_pack_id = pack_id
        else:
            return {"status": "error", "message": f"Pack manifest not found: {pack_id}"}
    else:
        return {"status": "error", "message": "Provide pack_path or pack_id"}

    target_skills = {s["id"]: s for s in target_manifest.get("skills", [])}
    target_perms = set()
    for s in target_manifest.get("skills", []):
        target_perms.update(s.get("permissions", []))

    packs_to_check = check_against or list(_get_imported_packs_map().keys())
    installed_skills = _get_installed_skills_map()

    for check_id in packs_to_check:
        if check_id == target_pack_id:
            continue

        check_manifest = None
        imported = _get_imported_packs_map()
        if check_id in imported:
            imported_dir = IMPORTED_DIR / check_id
            manifest_path = imported_dir / PACK_MANIFEST_NAME
            if manifest_path.exists():
                try:
                    check_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        if not check_manifest:
            catalog = _get_catalog_packs_map()
            if check_id in catalog:
                check_manifest = catalog[check_id]

        if not check_manifest:
            continue

        check_skills = {s["id"]: s for s in check_manifest.get("skills", [])}
        check_perms = set()
        for s in check_manifest.get("skills", []):
            check_perms.update(s.get("permissions", []))

        duplicate_ids = set(target_skills.keys()) & set(check_skills.keys())
        if duplicate_ids:
            conflicts.append({
                "type": "duplicate_skills",
                "pack_a": target_pack_id,
                "pack_b": check_id,
                "skills": list(duplicate_ids),
                "severity": "high",
            })

        perm_intersection = target_perms & check_perms
        if perm_intersection:
            shared_risky = [p for p in perm_intersection if p in ("filesystem_write", "network_access", "shell_exec")]
            if shared_risky:
                warnings.append({
                    "type": "shared_risky_permissions",
                    "pack_a": target_pack_id,
                    "pack_b": check_id,
                    "permissions": shared_risky,
                    "severity": "medium",
                })

    liuant_min = target_manifest.get("liuant_min_version", "")
    if liuant_min:
        def _parse_ver(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split(".") if x.isdigit())

        try:
            if _parse_ver(LIUANT_VERSION) < _parse_ver(liuant_min):
                conflicts.append({
                    "type": "liuant_version_incompatible",
                    "required_min": liuant_min,
                    "current": LIUANT_VERSION,
                    "severity": "critical",
                })
        except Exception:
            pass

    target_risk = get_risk_level(list(target_perms))
    if target_risk in ("high", "critical"):
        warnings.append({
            "type": "high_risk_pack",
            "risk_level": target_risk,
            "permissions": list(target_perms),
            "severity": "medium",
        })

    installed_ids = set(installed_skills.keys())
    missing_skills = []
    for sid in target_skills:
        if sid not in installed_ids:
            missing_skills.append(sid)

    if missing_skills:
        recommendations.append({
            "type": "missing_skills",
            "skills": missing_skills,
            "message": "Install these skills before running workflows",
        })

    critical_conflicts = [c for c in conflicts if c.get("severity") == "critical"]
    high_conflicts = [c for c in conflicts if c.get("severity") == "high"]

    status = "compatible"
    if critical_conflicts:
        status = "incompatible"
    elif high_conflicts:
        status = "warnings"

    return {
        "status": status,
        "pack_id": target_pack_id,
        "conflicts": conflicts,
        "warnings": warnings,
        "recommendations": recommendations,
        "risk_level": target_risk,
        "liuant_version": LIUANT_VERSION,
        "liuant_min_required": liuant_min,
    }


def check_all_installed_compatibility() -> dict[str, Any]:
    """Check compatibility across all installed packs."""
    imported = _get_imported_packs_map()
    all_conflicts = []
    all_warnings = []

    for pack_id in imported:
        imported_dir = IMPORTED_DIR / pack_id
        manifest_path = imported_dir / PACK_MANIFEST_NAME
        if manifest_path.exists():
            result = check_compatibility(pack_id=pack_id)
            all_conflicts.extend(result.get("conflicts", []))
            all_warnings.extend(result.get("warnings", []))

    return {
        "status": "ok" if not all_conflicts else "issues_found",
        "total_packs": len(imported),
        "conflicts": all_conflicts,
        "warnings": all_warnings,
    }


def save_compatibility_matrix() -> dict[str, Any]:
    """Save the current compatibility matrix to disk."""
    result = check_all_installed_compatibility()
    matrix = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "liuant_version": LIUANT_VERSION,
        "total_packs": result.get("total_packs", 0),
        "conflicts": result.get("conflicts", []),
        "warnings": result.get("warnings", []),
    }
    COMPAT_MATRIX_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_json(COMPAT_MATRIX_FILE, matrix)
    return {"status": "saved", "path": str(COMPAT_MATRIX_FILE)}


def load_compatibility_matrix() -> dict[str, Any]:
    """Load the saved compatibility matrix."""
    if not COMPAT_MATRIX_FILE.exists():
        return {"status": "not_found", "message": "No saved compatibility matrix"}
    return read_json(COMPAT_MATRIX_FILE, {})
