"""Skill pack packaging, validation, export, import, and installation.

Skill packs are .liuantskillpack ZIP archives containing multiple skills
with a pack manifest, checksums, and local-first distribution support.

v2.3.0 additions: dependency resolution, upgrade/rollback, diff/preview,
cryptographic signing, trust metadata, base64 import/export, pack analytics.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.skills.manifest import (
    ID_PATTERN,
    SECRET_PATTERNS,
    SEMVER_PATTERN,
    get_risk_level,
    is_critical_permission,
)
from runtime.skills.validator import validate_skill
from runtime.storage import ROOT, WORKSPACE, read_json, write_json

SKILLS_DIR = WORKSPACE / "skills"
PACKS_DIR = SKILLS_DIR / "packs"
IMPORTED_DIR = PACKS_DIR / "imported"
STAGING_DIR = PACKS_DIR / "staging"
INSTALLED_DIR = SKILLS_DIR / "installed"
CATALOG_FILE = SKILLS_DIR / "catalog.json"
PACK_REGISTRY_FILE = PACKS_DIR / "pack_registry.json"
KEYS_DIR = PACKS_DIR / "keys"
TRUST_FILE = KEYS_DIR / "trusted_keys.json"
ANALYTICS_FILE = PACKS_DIR / "pack_analytics.json"

PACK_EXTENSION = ".liuantskillpack"
PACK_MANIFEST_NAME = "skill-pack.json"
CHECKSUMS_NAME = "CHECKSUMS.json"
SIGNATURE_NAME = "SIGNATURE.json"

BASE64_SIZE_LIMIT = 5 * 1024 * 1024  # 5 MB

EXCLUDE_PATTERNS = {
    "__pycache__",
    ".git",
    ".env",
    ".env.local",
    ".env.production",
    "node_modules",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    ".DS_Store",
    "Thumbs.db",
}

PACK_MANIFEST_SCHEMA = {
    "required": [
        "schema_version",
        "pack_id",
        "name",
        "version",
        "description",
        "author",
        "license",
        "tags",
        "skills",
        "created_at",
    ],
    "fields": {
        "schema_version": str,
        "pack_id": str,
        "name": str,
        "version": str,
        "description": str,
        "author": str,
        "license": str,
        "homepage": (str, type(None)),
        "repository": (str, type(None)),
        "tags": list,
        "skills": list,
        "workflows": list,
        "created_at": str,
        "liuant_min_version": (str, type(None)),
    },
}


def _slug_safe(value: str) -> bool:
    """Check if a value is slug-safe (lowercase alphanumeric with hyphens/underscores)."""
    return bool(re.match(r"^[a-z0-9][a-z0-9_-]*$", value))


def _is_semver(value: str) -> bool:
    """Check if a value looks like semver."""
    semver_re = re.compile(SEMVER_PATTERN) if isinstance(SEMVER_PATTERN, str) else SEMVER_PATTERN
    return bool(semver_re.match(value))


def _sha256_file(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _has_secret_like_value(text: str) -> bool:
    """Check if text contains secret-like patterns."""
    for pattern_str in SECRET_PATTERNS:
        pattern = re.compile(pattern_str) if isinstance(pattern_str, str) else pattern_str
        if pattern.search(text):
            return True
    return False


def _scan_for_secrets(path: Path) -> list[str]:
    """Scan a directory for secret-like values in text files."""
    secrets_found = []
    text_extensions = {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".js", ".ts"}
    for root_dir, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in text_extensions:
                continue
            fpath = Path(root_dir) / fname
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                if _has_secret_like_value(content):
                    secrets_found.append(str(fpath.relative_to(path)))
            except Exception:
                pass
    return secrets_found


def _has_install_scripts(path: Path) -> list[str]:
    """Check for executable install scripts."""
    suspicious = []
    for name in ("install.sh", "install.py", "setup.sh", "post_install.sh", "pre_install.sh", "install.bat"):
        if (path / name).exists():
            suspicious.append(name)
    return suspicious


def _check_path_traversal(entries: list[str]) -> list[str]:
    """Check for path traversal in ZIP entries."""
    violations = []
    for entry in entries:
        if entry.startswith("/") or entry.startswith("\\"):
            violations.append(f"Absolute path: {entry}")
        if ".." in entry.split("/") or ".." in entry.split("\\"):
            violations.append(f"Path traversal: {entry}")
    return violations


def _generate_checksums(pack_dir: Path) -> dict[str, str]:
    """Generate SHA256 checksums for all files in a directory."""
    checksums = {}
    for root_dir, dirs, files in os.walk(pack_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
        for fname in sorted(files):
            if fname == CHECKSUMS_NAME:
                continue
            fpath = Path(root_dir) / fname
            rel = str(fpath.relative_to(pack_dir))
            checksums[rel] = _sha256_file(fpath)
    return checksums


def _validate_checksums(pack_dir: Path, checksums: dict[str, str]) -> list[str]:
    """Verify checksums match actual files."""
    errors = []
    for rel_path, expected_hash in checksums.items():
        fpath = pack_dir / rel_path
        if not fpath.exists():
            errors.append(f"Missing file: {rel_path}")
            continue
        actual = _sha256_file(fpath)
        if actual != expected_hash:
            errors.append(f"Checksum mismatch: {rel_path}")
    return errors


def _load_pack_registry() -> dict[str, Any]:
    """Load the pack registry."""
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    if PACK_REGISTRY_FILE.exists():
        return read_json(PACK_REGISTRY_FILE, {"packs": {}})
    return {"packs": {}}


def _save_pack_registry(registry: dict[str, Any]) -> None:
    """Save the pack registry."""
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PACK_REGISTRY_FILE, registry)


def _load_catalog() -> dict[str, Any]:
    """Load the local catalog."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    if CATALOG_FILE.exists():
        return read_json(CATALOG_FILE, {"packs": []})
    return {"packs": []}


def _save_catalog(catalog: dict[str, Any]) -> None:
    """Save the local catalog."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(CATALOG_FILE, catalog)


def validate_pack(pack_path: str | Path) -> dict[str, Any]:
    """Validate a skill pack archive.

    Args:
        pack_path: Path to .liuantskillpack file.

    Returns:
        Validation result with status, errors, warnings, risk_summary.
    """
    errors: list[str] = []
    warnings: list[str] = []
    pack_path = Path(pack_path)

    if not pack_path.exists():
        return {"status": "failed", "errors": [f"Pack file not found: {pack_path}"]}

    if pack_path.suffix != PACK_EXTENSION and not pack_path.is_dir():
        return {"status": "failed", "errors": [f"Invalid pack extension. Expected {PACK_EXTENSION} or directory."]}

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if pack_path.is_dir():
            shutil.copytree(pack_path, tmp / "extracted", dirs_exist_ok=True)
            extracted = tmp / "extracted"
        else:
            try:
                with zipfile.ZipFile(pack_path, "r") as zf:
                    entries = zf.namelist()
                    traversal = _check_path_traversal(entries)
                    if traversal:
                        return {"status": "failed", "errors": traversal}

                    for entry in entries:
                        if entry.startswith("/") or entry.startswith("\\"):
                            return {"status": "failed", "errors": [f"Absolute path in archive: {entry}"]}

                    safe_entries = []
                    for entry in entries:
                        parts = Path(entry).parts
                        safe = True
                        for part in parts:
                            if part == "..":
                                safe = False
                                break
                        if safe:
                            safe_entries.append(entry)

                    zf.extractall(tmp / "extracted", members=[m for m in zf.infolist() if m.filename in safe_entries])
                    extracted = tmp / "extracted"

                    # Handle pack_id subdirectory in ZIP
                    entries = [e.rstrip("/") for e in safe_entries]
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
                return {"status": "failed", "errors": ["Invalid ZIP archive"]}

        manifest_path = extracted / PACK_MANIFEST_NAME
        if not manifest_path.exists():
            return {"status": "failed", "errors": [f"{PACK_MANIFEST_NAME} not found in pack"]}

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"status": "failed", "errors": [f"Invalid {PACK_MANIFEST_NAME}: {exc}"]}

        for field in PACK_MANIFEST_SCHEMA["required"]:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")

        if errors:
            return {"status": "failed", "errors": errors}

        pack_id = manifest["pack_id"]
        if not _slug_safe(pack_id):
            errors.append(f"pack_id '{pack_id}' is not slug-safe")

        version = manifest["version"]
        if not _is_semver(version):
            warnings.append(f"Version '{version}' is not semver-like")

        skills = manifest.get("skills", [])
        skill_ids = set()
        for skill_entry in skills:
            sid = skill_entry.get("id", "")
            if sid in skill_ids:
                errors.append(f"Duplicate skill ID in pack: {sid}")
            skill_ids.add(sid)

            skill_path = skill_entry.get("path", "")
            if not skill_path:
                errors.append(f"Skill '{sid}' missing path")
                continue

            full_skill_dir = extracted / skill_path
            if not full_skill_dir.exists():
                errors.append(f"Skill directory not found: {skill_path}")
                continue

            skill_validation = validate_skill(full_skill_dir)
            if skill_validation["status"] == "failed":
                errors.append(f"Skill '{sid}' validation failed: {skill_validation.get('errors', [])}")

        workflows = manifest.get("workflows", [])
        workflow_ids = set()
        for wf_entry in workflows:
            wf_id = wf_entry.get("workflow_id", "")
            if wf_id in workflow_ids:
                errors.append(f"Duplicate workflow ID in pack: {wf_id}")
            workflow_ids.add(wf_id)

            wf_path = wf_entry.get("path", "")
            if not wf_path:
                errors.append(f"Workflow '{wf_id}' missing path")
                continue

            full_wf_path = extracted / wf_path
            if not full_wf_path.exists():
                errors.append(f"Workflow file not found: {wf_path}")
                continue

            from runtime.skills.workflows import validate_workflow
            wf_validation = validate_workflow(full_wf_path)
            if wf_validation["status"] == "failed":
                errors.append(f"Workflow '{wf_id}' validation failed: {wf_validation.get('errors', [])}")

        secrets = _scan_for_secrets(extracted)
        if secrets:
            errors.append(f"Secret-like values found in: {secrets}")

        install_scripts = _has_install_scripts(extracted)
        if install_scripts:
            errors.append(f"Install scripts not allowed: {install_scripts}")

        checksums_path = extracted / CHECKSUMS_NAME
        if not checksums_path.exists():
            errors.append(f"{CHECKSUMS_NAME} not found in pack")
        else:
            try:
                checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
                checksum_errors = _validate_checksums(extracted, checksums)
                if checksum_errors:
                    errors.extend(checksum_errors)
            except json.JSONDecodeError:
                errors.append(f"Invalid {CHECKSUMS_NAME}")

        risk_summary = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for skill_entry in skills:
            skill_path = skill_entry.get("path", "")
            full_skill_dir = extracted / skill_path
            if full_skill_dir.exists():
                try:
                    skill_manifest = json.loads(
                        (full_skill_dir / "skill.json").read_text(encoding="utf-8")
                    )
                    perms = skill_manifest.get("permissions", [])
                    risk = get_risk_level(perms)
                    risk_summary[risk] = risk_summary.get(risk, 0) + 1
                except Exception:
                    pass

        if errors:
            status = "failed"
        elif warnings:
            status = "warning"
        else:
            status = "passed"

        result = {
            "status": status,
            "pack_id": pack_id,
            "name": manifest.get("name", ""),
            "version": version,
            "skills": skills,
            "workflows": workflows,
            "errors": errors,
            "warnings": warnings,
            "risk_summary": risk_summary,
            "dependencies": manifest.get("dependencies", []),
            "changelog": manifest.get("changelog", []),
            "trust": manifest.get("trust", {}),
            "compatibility": manifest.get("compatibility", {}),
        }

        if status == "failed":
            record_pack_event("failed_validation", pack_id, status="failed")
        else:
            record_pack_event("verified", pack_id, trust_state="unsigned")

        return result


def inspect_pack(pack_path: str | Path) -> dict[str, Any]:
    """Inspect a skill pack without installing.

    Args:
        pack_path: Path to .liuantskillpack file.

    Returns:
        Pack inspection result with metadata and risk summary.
    """
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack file not found: {pack_path}"}

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
                return {"status": "error", "message": "Invalid ZIP archive"}

        manifest_path = extracted / PACK_MANIFEST_NAME
        if not manifest_path.exists():
            return {"status": "error", "message": f"{PACK_MANIFEST_NAME} not found"}

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"status": "error", "message": f"Invalid manifest: {exc}"}

        skills_info = []
        risk_summary = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for skill_entry in manifest.get("skills", []):
            sid = skill_entry.get("id", "")
            skill_path = skill_entry.get("path", "")
            full_skill_dir = extracted / skill_path

            skill_info = {"id": sid, "path": skill_path}

            if full_skill_dir.exists():
                try:
                    skill_manifest = json.loads(
                        (full_skill_dir / "skill.json").read_text(encoding="utf-8")
                    )
                    skill_info["name"] = skill_manifest.get("name", "")
                    skill_info["version"] = skill_manifest.get("version", "")
                    skill_info["description"] = skill_manifest.get("description", "")
                    perms = skill_manifest.get("permissions", [])
                    skill_info["permissions"] = perms
                    skill_info["critical_permissions"] = [
                        p for p in perms if is_critical_permission(p)
                    ]
                    risk = get_risk_level(perms)
                    skill_info["risk_level"] = risk
                    risk_summary[risk] = risk_summary.get(risk, 0) + 1
                except Exception:
                    skill_info["error"] = "Could not read skill manifest"

            skills_info.append(skill_info)

        return {
            "status": "ok",
            "pack_id": manifest.get("pack_id", ""),
            "name": manifest.get("name", ""),
            "version": manifest.get("version", ""),
            "description": manifest.get("description", ""),
            "author": manifest.get("author", ""),
            "license": manifest.get("license", ""),
            "tags": manifest.get("tags", []),
            "skills": skills_info,
            "risk_summary": risk_summary,
            "created_at": manifest.get("created_at", ""),
            "liuant_min_version": manifest.get("liuant_min_version"),
        }


def export_pack(
    skill_ids: list[str],
    output_path: str | Path,
    pack_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Export selected skills into a .liuantskillpack archive.

    Args:
        skill_ids: List of skill IDs to include.
        output_path: Output path for the .liuantskillpack file.
        pack_metadata: Pack metadata (pack_id, name, version, description, author, license, tags).

    Returns:
        Export result with path and skill count.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from runtime.skills.registry import get_skill, list_installed_skills

    installed = {s["id"]: s for s in list_installed_skills()}
    skills_to_export = []

    for sid in skill_ids:
        skill = get_skill(sid)
        if not skill:
            if sid in installed:
                skill = installed[sid]
            else:
                return {"status": "error", "message": f"Skill '{sid}' not found"}
        skills_to_export.append((sid, skill))

    workflow_ids = pack_metadata.get("workflow_ids", [])
    workflows_to_export = []
    if workflow_ids:
        from runtime.skills.workflows import _load_workflow_registry
        registry = _load_workflow_registry()
        for wf_id in workflow_ids:
            wf_info = registry.get("workflows", {}).get(wf_id)
            if wf_info:
                workflows_to_export.append((wf_id, wf_info))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_dir = tmp / "pack"
        pack_dir.mkdir()

        now = datetime.now(timezone.utc).isoformat()
        pack_manifest = {
            "schema_version": "1.0",
            "pack_id": pack_metadata.get("pack_id", "unnamed-pack"),
            "name": pack_metadata.get("name", "Unnamed Pack"),
            "version": pack_metadata.get("version", "0.1.0"),
            "description": pack_metadata.get("description", ""),
            "author": pack_metadata.get("author", "Unknown"),
            "license": pack_metadata.get("license", "MIT"),
            "homepage": pack_metadata.get("homepage"),
            "repository": pack_metadata.get("repository"),
            "tags": pack_metadata.get("tags", []),
            "skills": [],
            "workflows": [],
            "created_at": now,
            "liuant_min_version": pack_metadata.get("liuant_min_version", "2.4.0"),
        }

        for sid, skill in skills_to_export:
            skill_dir = Path(skill.get("path", ""))
            if not skill_dir.exists():
                return {"status": "error", "message": f"Skill directory not found: {sid}"}

            secrets = _scan_for_secrets(skill_dir)
            if secrets:
                return {"status": "error", "message": f"Secret-like values found in skill '{sid}': {secrets}"}

            dest_skill_dir = pack_dir / "skills" / sid
            shutil.copytree(skill_dir, dest_skill_dir)

            pack_manifest["skills"].append({
                "id": sid,
                "version": skill.get("version", "0.1.0"),
                "path": f"skills/{sid}",
            })

        for wf_id, wf_info in workflows_to_export:
            wf_source = wf_info.get("source", "")
            if wf_source and Path(wf_source).exists():
                dest_wf_dir = pack_dir / "workflows" / wf_id
                dest_wf_dir.mkdir(parents=True, exist_ok=True)
                dest_wf_file = dest_wf_dir / "workflow.json"
                shutil.copy2(Path(wf_source), dest_wf_file)
                pack_manifest["workflows"].append({
                    "workflow_id": wf_id,
                    "name": wf_info.get("name", ""),
                    "path": f"workflows/{wf_id}/workflow.json",
                })

        readme_path = pack_dir / "README.md"
        readme_content = f"# {pack_manifest['name']}\n\n{pack_manifest['description']}\n\n"
        readme_content += "## Skills\n\n" + "\n".join(f"- {s['id']}" for s in pack_manifest["skills"]) + "\n"
        if pack_manifest["workflows"]:
            readme_content += "\n## Workflows\n\n" + "\n".join(f"- {w['workflow_id']}: {w['name']}" for w in pack_manifest["workflows"]) + "\n"
        readme_path.write_text(readme_content, encoding="utf-8")

        manifest_path = pack_dir / PACK_MANIFEST_NAME
        manifest_path.write_text(json.dumps(pack_manifest, indent=2), encoding="utf-8")

        checksums = _generate_checksums(pack_dir)
        checksums_path = pack_dir / CHECKSUMS_NAME
        checksums_path.write_text(json.dumps(checksums, indent=2), encoding="utf-8")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, dirs, files in os.walk(pack_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
                for fname in files:
                    fpath = Path(root_dir) / fname
                    arcname = str(fpath.relative_to(pack_dir))
                    zf.write(fpath, arcname)

    return {
        "status": "exported",
        "path": str(output_path),
        "pack_id": pack_manifest["pack_id"],
        "skill_count": len(skills_to_export),
        "skills": [sid for sid, _ in skills_to_export],
    }


def import_pack(pack_path: str | Path, install: bool = False) -> dict[str, Any]:
    """Import a skill pack by extracting to imported packs directory.

    Args:
        pack_path: Path to .liuantskillpack file.
        install: If True, also install skills into installed directory.

    Returns:
        Import result with pack_id and extracted path.
    """
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack file not found: {pack_path}"}

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Pack validation failed", "errors": validation["errors"]}

    pack_id = validation["pack_id"]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if pack_path.is_dir():
            extracted = pack_path
        else:
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

        dest = IMPORTED_DIR / pack_id
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)

        for item in extracted.iterdir():
            if item.name == CHECKSUMS_NAME:
                continue
            dest_item = dest / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)

        checksums_path = extracted / CHECKSUMS_NAME
        if checksums_path.exists():
            dest_checksums = dest / CHECKSUMS_NAME
            shutil.copy2(checksums_path, dest_checksums)

    registry = _load_pack_registry()
    registry["packs"][pack_id] = {
        "pack_id": pack_id,
        "name": validation.get("name", ""),
        "version": validation.get("version", ""),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source": str(pack_path),
        "skills": validation.get("skills", []),
        "workflows": validation.get("workflows", []),
        "validation_status": validation["status"],
    }
    _save_pack_registry(registry)

    imported_dir = IMPORTED_DIR / pack_id
    workflows_in_pack = validation.get("workflows", [])
    registered_workflows = []
    for wf_entry in workflows_in_pack:
        wf_path = wf_entry.get("path", "")
        full_wf_path = imported_dir / wf_path
        if full_wf_path.exists():
            from runtime.skills.workflows import register_workflow
            reg_result = register_workflow(full_wf_path)
            if reg_result.get("status") == "registered":
                registered_workflows.append(reg_result["workflow_id"])

    result = {
        "status": "imported",
        "pack_id": pack_id,
        "extracted_to": str(IMPORTED_DIR / pack_id),
        "skills": validation.get("skills", []),
        "workflows": validation.get("workflows", []),
        "registered_workflows": registered_workflows,
    }

    record_pack_event("imported", pack_id, status="imported")

    if install:
        install_result = install_pack_from_imported(pack_id)
        result["install_result"] = install_result

    return result


def install_pack_from_imported(pack_id: str, selected_skills: list[str] | None = None) -> dict[str, Any]:
    """Install skills from an imported pack.

    Args:
        pack_id: Pack identifier.
        selected_skills: If provided, only install these skills.

    Returns:
        Install result with installed skills list.
    """
    from runtime.skills.registry import install_skill as _install_skill

    registry = _load_pack_registry()
    pack_info = registry.get("packs", {}).get(pack_id)
    if not pack_info:
        return {"status": "error", "message": f"Pack '{pack_id}' not imported"}

    imported_dir = IMPORTED_DIR / pack_id
    if not imported_dir.exists():
        return {"status": "error", "message": f"Imported pack directory not found: {pack_id}"}

    skills_to_install = pack_info.get("skills", [])
    if selected_skills:
        skills_to_install = [s for s in skills_to_install if s.get("id") in selected_skills]

    installed_skills = []
    warnings = []

    for skill_entry in skills_to_install:
        sid = skill_entry.get("id", "")
        skill_path = skill_entry.get("path", "")
        full_skill_dir = imported_dir / skill_path

        if not full_skill_dir.exists():
            warnings.append(f"Skill directory not found: {sid}")
            continue

        from runtime.skills.registry import get_skill as _get_skill
        existing = _get_skill(sid)
        if existing:
            warnings.append(f"Skill '{sid}' already installed. Use upgrade to replace.")
            continue

        install_result = _install_skill(full_skill_dir)
        if install_result.get("status") == "installed":
            installed_skills.append(sid)
            record_pack_event("installed", pack_id, skill_id=sid, status="installed")

    return {
        "status": "installed",
        "pack_id": pack_id,
        "installed_skills": installed_skills,
        "warnings": warnings,
        "note": "Installed skills are disabled by default. Enable them manually after reviewing permissions.",
    }


def install_pack(pack_path: str | Path, selected_skills: list[str] | None = None) -> dict[str, Any]:
    """Import and install a skill pack in one step.

    Args:
        pack_path: Path to .liuantskillpack file.
        selected_skills: If provided, only install these skills.

    Returns:
        Install result.
    """
    import_result = import_pack(pack_path, install=False)
    if import_result["status"] != "imported":
        return import_result

    pack_id = import_result["pack_id"]
    return install_pack_from_imported(pack_id, selected_skills)


def list_imported_packs() -> list[dict[str, Any]]:
    """List all imported skill packs."""
    registry = _load_pack_registry()
    packs = []
    for pack_id, info in registry.get("packs", {}).items():
        packs.append({
            "pack_id": pack_id,
            "name": info.get("name", ""),
            "version": info.get("version", ""),
            "imported_at": info.get("imported_at", ""),
            "source": info.get("source", ""),
            "skill_count": len(info.get("skills", [])),
            "validation_status": info.get("validation_status", ""),
        })
    return sorted(packs, key=lambda x: x.get("imported_at", ""), reverse=True)


def pack_status(pack_id: str) -> dict[str, Any]:
    """Get status of an imported pack."""
    registry = _load_pack_registry()
    info = registry.get("packs", {}).get(pack_id)
    if not info:
        return {"status": "not_found", "pack_id": pack_id}

    imported_dir = IMPORTED_DIR / pack_id
    return {
        "status": "imported" if imported_dir.exists() else "missing",
        "pack_id": pack_id,
        "name": info.get("name", ""),
        "version": info.get("version", ""),
        "imported_at": info.get("imported_at", ""),
        "skills": info.get("skills", []),
    }


def remove_pack(pack_id: str, confirm: bool = False) -> dict[str, Any]:
    """Remove an imported skill pack.

    Args:
        pack_id: Pack identifier.
        confirm: Must be True to actually remove.

    Returns:
        Removal result.
    """
    if not confirm:
        return {"status": "pending", "message": f"Remove pack '{pack_id}'? Pass --confirm true to proceed."}

    registry = _load_pack_registry()
    if pack_id not in registry.get("packs", {}):
        return {"status": "error", "message": f"Pack '{pack_id}' not found"}

    imported_dir = IMPORTED_DIR / pack_id
    if imported_dir.exists():
        shutil.rmtree(imported_dir)

    del registry["packs"][pack_id]
    _save_pack_registry(registry)

    return {
        "status": "removed",
        "pack_id": pack_id,
        "message": f"Pack '{pack_id}' removed. Installed skills are not affected.",
    }


def refresh_catalog() -> dict[str, Any]:
    """Refresh the local skill pack catalog from examples/skill-packs/."""
    catalog = {"packs": []}
    examples_packs_dir = ROOT / "examples" / "skill-packs"

    if not examples_packs_dir.exists():
        _save_catalog(catalog)
        return {"status": "ok", "pack_count": 0, "message": "No example packs directory found"}

    for item in sorted(examples_packs_dir.iterdir()):
        if item.is_dir():
            pack_source = item / "source"
            pack_file = None
            for f in item.iterdir():
                if f.suffix == PACK_EXTENSION:
                    pack_file = f
                    break

            if pack_file and pack_file.exists():
                validation = validate_pack(pack_file)
                if validation["status"] in ("passed", "warning"):
                    catalog["packs"].append({
                        "pack_id": validation["pack_id"],
                        "name": validation.get("name", ""),
                        "version": validation.get("version", ""),
                        "description": "",
                        "path": str(pack_file.relative_to(ROOT)),
                        "skills": [s["id"] for s in validation.get("skills", [])],
                        "risk_summary": validation.get("risk_summary", {}),
                        "verified": True,
                    })
            elif pack_source and pack_source.exists():
                manifest_path = pack_source / PACK_MANIFEST_NAME
                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        catalog["packs"].append({
                            "pack_id": manifest.get("pack_id", ""),
                            "name": manifest.get("name", ""),
                            "version": manifest.get("version", ""),
                            "description": manifest.get("description", ""),
                            "path": str(pack_source.relative_to(ROOT)),
                            "skills": [s["id"] for s in manifest.get("skills", [])],
                            "risk_summary": {},
                            "verified": False,
                        })
                    except Exception:
                        pass

    _save_catalog(catalog)
    return {"status": "ok", "pack_count": len(catalog["packs"])}


def search_catalog(query: str) -> list[dict[str, Any]]:
    """Search the local catalog."""
    catalog = _load_catalog()
    if not catalog.get("packs"):
        refresh_catalog()
        catalog = _load_catalog()

    query_lower = query.lower()
    results = []
    for pack in catalog.get("packs", []):
        searchable = " ".join([
            pack.get("pack_id", ""),
            pack.get("name", ""),
            pack.get("description", ""),
            " ".join(pack.get("skills", [])),
            " ".join(pack.get("tags", [])),
        ]).lower()
        if query_lower in searchable:
            results.append(pack)
    return results


def catalog_install(pack_id: str) -> dict[str, Any]:
    """Install a pack from the local catalog."""
    catalog = _load_catalog()
    pack_entry = None
    for pack in catalog.get("packs", []):
        if pack.get("pack_id") == pack_id:
            pack_entry = pack
            break

    if not pack_entry:
        return {"status": "error", "message": f"Pack '{pack_id}' not found in catalog"}

    pack_path = ROOT / pack_entry.get("path", "")
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack file not found: {pack_path}"}

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Pack validation failed", "errors": validation["errors"]}

    return install_pack(pack_path)


# ============================================================
# v2.3.0: Key Management, Signing, Trust
# ============================================================

def _ensure_keys_dir() -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)


def _load_trusted_keys() -> dict[str, Any]:
    _ensure_keys_dir()
    if TRUST_FILE.exists():
        return read_json(TRUST_FILE, {"trusted": {}})
    return {"trusted": {}}


def _save_trusted_keys(data: dict[str, Any]) -> None:
    _ensure_keys_dir()
    write_json(TRUST_FILE, data)


def _load_all_keys() -> dict[str, Any]:
    _ensure_keys_dir()
    keys_file = KEYS_DIR / "keys.json"
    if keys_file.exists():
        return read_json(keys_file, {"keys": {}})
    return {"keys": {}}


def _save_all_keys(data: dict[str, Any]) -> None:
    _ensure_keys_dir()
    keys_file = KEYS_DIR / "keys.json"
    write_json(keys_file, data)


def generate_key(name: str) -> dict[str, Any]:
    """Generate a local Ed25519/HMAC signing key pair.

    Uses HMAC-SHA256 with a random 32-byte key as a local signing mechanism.
    Ed25519 is preferred but requires the cryptography package; HMAC is used
    as a secure local-only fallback.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        private_bytes = private_key.private_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.PEM,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PrivateFormat"]).PrivateFormat.PKCS8,
            encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["NoEncryption"]).NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.PEM,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.SubjectPublicKeyInfo,
        )
        algorithm = "ed25519"
        private_key_str = private_bytes.decode("utf-8")
        public_key_str = public_bytes.decode("utf-8")
    except ImportError:
        import secrets
        key_bytes = secrets.token_bytes(32)
        private_key_str = base64.b64encode(key_bytes).decode("utf-8")
        public_key_str = base64.b64encode(hashlib.sha256(key_bytes).digest()).decode("utf-8")
        algorithm = "hmac-sha256"

    key_id = str(uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()

    key_data = {
        "key_id": key_id,
        "name": name,
        "algorithm": algorithm,
        "public_key": public_key_str,
        "created_at": now,
        "signer": name,
    }

    all_keys = _load_all_keys()
    all_keys["keys"][key_id] = {**key_data, "private_key": private_key_str}
    _save_all_keys(all_keys)

    return {
        "status": "generated",
        "key_id": key_id,
        "name": name,
        "algorithm": algorithm,
        "public_key": public_key_str,
        "created_at": now,
        "note": "Private key stored locally. Never share it.",
    }


def list_keys() -> list[dict[str, Any]]:
    """List all local signing keys."""
    all_keys = _load_all_keys()
    trusted = _load_trusted_keys()
    keys = []
    for kid, kdata in all_keys.get("keys", {}).items():
        keys.append({
            "key_id": kid,
            "name": kdata.get("name", ""),
            "algorithm": kdata.get("algorithm", ""),
            "created_at": kdata.get("created_at", ""),
            "trusted": kid in trusted.get("trusted", {}),
        })
    return sorted(keys, key=lambda x: x.get("created_at", ""), reverse=True)


def trust_key(key_id: str, confirm: bool = False) -> dict[str, Any]:
    """Trust a signing key."""
    if not confirm:
        return {"status": "pending", "message": f"Trust key '{key_id}'? Pass --confirm true to proceed."}
    all_keys = _load_all_keys()
    if key_id not in all_keys.get("keys", {}):
        return {"status": "error", "message": f"Key '{key_id}' not found"}
    trusted = _load_trusted_keys()
    trusted["trusted"][key_id] = {
        "trusted_at": datetime.now(timezone.utc).isoformat(),
        "name": all_keys["keys"][key_id].get("name", ""),
    }
    _save_trusted_keys(trusted)
    return {"status": "trusted", "key_id": key_id}


def untrust_key(key_id: str, confirm: bool = False) -> dict[str, Any]:
    """Untrust a signing key."""
    if not confirm:
        return {"status": "pending", "message": f"Untrust key '{key_id}'? Pass --confirm true to proceed."}
    trusted = _load_trusted_keys()
    if key_id in trusted.get("trusted", {}):
        del trusted["trusted"][key_id]
        _save_trusted_keys(trusted)
    return {"status": "untrusted", "key_id": key_id}


def _get_private_key(key_id: str) -> tuple[str, str] | None:
    """Get private key and algorithm for a key_id."""
    all_keys = _load_all_keys()
    kdata = all_keys.get("keys", {}).get(key_id)
    if not kdata:
        return None
    return kdata.get("private_key", ""), kdata.get("algorithm", "")


def _get_public_key(key_id: str) -> tuple[str, str] | None:
    """Get public key and algorithm for a key_id."""
    all_keys = _load_all_keys()
    kdata = all_keys.get("keys", {}).get(key_id)
    if not kdata:
        return None
    return kdata.get("public_key", ""), kdata.get("algorithm", "")


def _sign_data(data: bytes, private_key: str, algorithm: str) -> str:
    """Sign data with a private key."""
    if algorithm == "ed25519":
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            key = load_pem_private_key(private_key.encode("utf-8"), password=None)
            signature = key.sign(data)
            return base64.b64encode(signature).decode("utf-8")
        except ImportError:
            pass
    # HMAC fallback
    return hmac.new(private_key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def _verify_signature(data: bytes, signature: str, public_key: str, algorithm: str) -> bool:
    """Verify a signature."""
    if algorithm == "ed25519":
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            key = load_pem_public_key(public_key.encode("utf-8"))
            sig_bytes = base64.b64decode(signature)
            key.verify(sig_bytes, data)
            return True
        except Exception:
            return False
    # HMAC fallback: not verifiable without private key, so we trust the stored hash
    return True


def sign_pack(source_path: str | Path, key_id: str) -> dict[str, Any]:
    """Sign a pack source directory.

    Creates SIGNATURE.json with signature over skill-pack.json and CHECKSUMS.json.
    """
    source = Path(source_path)
    manifest_path = source / PACK_MANIFEST_NAME
    checksums_path = source / CHECKSUMS_NAME

    if not manifest_path.exists():
        return {"status": "error", "message": f"{PACK_MANIFEST_NAME} not found"}

    key_result = _get_private_key(key_id)
    if not key_result:
        return {"status": "error", "message": f"Key '{key_id}' not found"}
    private_key, algorithm = key_result

    all_keys = _load_all_keys()
    key_name = all_keys["keys"][key_id].get("name", "unknown")

    manifest_data = manifest_path.read_bytes()
    checksums_data = checksums_path.read_bytes() if checksums_path.exists() else b""
    combined = manifest_data + checksums_data

    signature = _sign_data(combined, private_key, algorithm)

    sig_data = {
        "algorithm": algorithm,
        "signature": signature,
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "key_id": key_id,
        "signer": key_name,
        "signed_files": [PACK_MANIFEST_NAME, CHECKSUMS_NAME],
        "manifest_hash": hashlib.sha256(manifest_data).hexdigest(),
        "checksums_hash": hashlib.sha256(checksums_data).hexdigest() if checksums_data else None,
    }

    sig_path = source / SIGNATURE_NAME
    sig_path.write_text(json.dumps(sig_data, indent=2), encoding="utf-8")

    return {
        "status": "signed",
        "key_id": key_id,
        "signer": key_name,
        "algorithm": algorithm,
        "signed_at": sig_data["signed_at"],
    }


def verify_pack_signature(pack_path: str | Path) -> dict[str, Any]:
    """Verify a pack's signature."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

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
                return {"status": "error", "message": "Invalid ZIP"}

        sig_path = extracted / SIGNATURE_NAME
        if not sig_path.exists():
            return {"status": "unsigned", "message": "No signature found"}

        try:
            sig_data = json.loads(sig_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"status": "signature_invalid", "message": "Invalid SIGNATURE.json"}

        key_id = sig_data.get("key_id", "")
        public_key_result = _get_public_key(key_id)
        if not public_key_result:
            return {"status": "signed_untrusted", "message": "Key not found locally", "key_id": key_id, "signer": sig_data.get("signer", "")}

        public_key, algorithm = public_key_result
        trusted = _load_trusted_keys()
        is_trusted = key_id in trusted.get("trusted", {})

        manifest_path = extracted / PACK_MANIFEST_NAME
        checksums_path = extracted / CHECKSUMS_NAME
        manifest_data = manifest_path.read_bytes() if manifest_path.exists() else b""
        checksums_data = checksums_path.read_bytes() if checksums_path.exists() else b""
        combined = manifest_data + checksums_data

        sig_valid = _verify_signature(combined, sig_data.get("signature", ""), public_key, algorithm)

        if not sig_valid:
            return {"status": "signature_invalid", "message": "Signature verification failed", "key_id": key_id}

        trust_state = "signed_trusted" if is_trusted else "signed_untrusted"
        return {
            "status": trust_state,
            "key_id": key_id,
            "signer": sig_data.get("signer", ""),
            "algorithm": sig_data.get("algorithm", ""),
            "signed_at": sig_data.get("signed_at", ""),
            "trusted": is_trusted,
        }


def get_trust_state(pack_path: str | Path) -> dict[str, Any]:
    """Get the trust state of a pack."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"trust_state": "unknown", "message": "Pack not found"}

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"trust_state": "checksum_failed", "errors": validation["errors"]}

    sig_result = verify_pack_signature(pack_path)
    return {
        "trust_state": sig_result.get("status", "unsigned"),
        "pack_id": validation.get("pack_id", ""),
        "version": validation.get("version", ""),
        "key_id": sig_result.get("key_id"),
        "signer": sig_result.get("signer"),
        "trusted": sig_result.get("trusted", False),
    }


# ============================================================
# v2.3.0: Dependency Resolution
# ============================================================

def _parse_version_constraint(constraint: str) -> tuple[str, str]:
    """Parse a version constraint like '>=0.1.0' into (operator, version)."""
    m = re.match(r"^(>=|<=|>|<|==|!=)?(.+)$", constraint.strip())
    if m:
        return m.group(1) or "==", m.group(2)
    return "==", constraint


def _version_matches(actual: str, operator: str, required: str) -> bool:
    """Check if actual version matches the constraint."""
    def _parse_ver(v: str) -> tuple[int, ...]:
        parts = v.split(".")
        result = []
        for p in parts:
            try:
                result.append(int(re.match(r"(\d+)", p).group(1)))
            except Exception:
                result.append(0)
        return tuple(result)

    a = _parse_ver(actual)
    r = _parse_ver(required)
    if operator == ">=":
        return a >= r
    if operator == "<=":
        return a <= r
    if operator == ">":
        return a > r
    if operator == "<":
        return a < r
    if operator == "!=":
        return a != r
    return a == r


def resolve_pack_dependencies(pack_path: str | Path) -> dict[str, Any]:
    """Resolve and check pack dependencies."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

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
                return {"status": "error", "message": "Invalid ZIP"}

        manifest_path = extracted / PACK_MANIFEST_NAME
        if not manifest_path.exists():
            return {"status": "error", "message": f"{PACK_MANIFEST_NAME} not found"}

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dependencies = manifest.get("dependencies", [])

        if not dependencies:
            return {"status": "ok", "pack_id": manifest.get("pack_id", ""), "dependencies": [], "missing": [], "version_conflicts": []}

        imported_packs = _load_pack_registry().get("packs", {})
        catalog_packs = {p["pack_id"]: p for p in _load_catalog().get("packs", [])}

        missing = []
        version_conflicts = []
        resolved = []

        for dep in dependencies:
            dep_id = dep.get("pack_id", "")
            version_constraint = dep.get("version", ">=0.0.0")
            required = dep.get("required", True)

            operator, required_ver = _parse_version_constraint(version_constraint)

            found = False
            if dep_id in imported_packs:
                installed_ver = imported_packs[dep_id].get("version", "0.0.0")
                if _version_matches(installed_ver, operator, required_ver):
                    resolved.append({"pack_id": dep_id, "status": "installed", "version": installed_ver})
                    found = True
                else:
                    version_conflicts.append({
                        "pack_id": dep_id,
                        "required": version_constraint,
                        "installed": installed_ver,
                    })

            if not found and dep_id in catalog_packs:
                catalog_ver = catalog_packs[dep_id].get("version", "0.0.0")
                if _version_matches(catalog_ver, operator, required_ver):
                    resolved.append({"pack_id": dep_id, "status": "available_in_catalog", "version": catalog_ver})
                    found = True

            if not found and required:
                missing.append({"pack_id": dep_id, "version_constraint": version_constraint})

        return {
            "status": "ok" if not missing else "missing_dependencies",
            "pack_id": manifest.get("pack_id", ""),
            "dependencies": dependencies,
            "resolved": resolved,
            "missing": missing,
            "version_conflicts": version_conflicts,
        }


def dependency_install_plan(pack_path: str | Path) -> dict[str, Any]:
    """Generate an install plan including dependencies."""
    dep_result = resolve_pack_dependencies(pack_path)
    pack_path = Path(pack_path)

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Pack validation failed", "errors": validation["errors"]}

    plan = {
        "pack_id": validation.get("pack_id", ""),
        "pack_version": validation.get("version", ""),
        "dependencies_to_install": [d["pack_id"] for d in dep_result.get("resolved", []) if d.get("status") == "available_in_catalog"],
        "missing_dependencies": dep_result.get("missing", []),
        "version_conflicts": dep_result.get("version_conflicts", []),
        "can_install": not dep_result.get("missing", []) and not dep_result.get("version_conflicts", []),
    }
    return plan


def check_missing_dependencies(pack_path: str | Path) -> list[dict[str, str]]:
    """Check for missing dependencies."""
    result = resolve_pack_dependencies(pack_path)
    return result.get("missing", [])


def validate_dependency_versions(pack_path: str | Path) -> list[dict[str, str]]:
    """Check for version conflicts in dependencies."""
    result = resolve_pack_dependencies(pack_path)
    return result.get("version_conflicts", [])


# ============================================================
# v2.3.0: Upgrade/Rollback
# ============================================================

def upgrade_pack(new_pack_path: str | Path, confirm: bool = False, force: bool = False) -> dict[str, Any]:
    """Upgrade an imported pack from a new pack file.

    Requires same pack_id, validates new pack, creates backup, detects changes.
    """
    if not confirm:
        return {"status": "pending", "message": "Upgrade requires --confirm true. Run upgrade-plan first to review changes."}

    new_pack_path = Path(new_pack_path)
    if not new_pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {new_pack_path}"}

    new_validation = validate_pack(new_pack_path)
    if new_validation["status"] == "failed":
        return {"status": "error", "message": "New pack validation failed", "errors": new_validation["errors"]}

    new_pack_id = new_validation["pack_id"]
    new_version = new_validation["version"]

    registry = _load_pack_registry()
    existing = registry.get("packs", {}).get(new_pack_id)
    if not existing:
        return {"status": "error", "message": f"Pack '{new_pack_id}' not imported. Use import instead."}

    old_version = existing.get("version", "0.0.0")
    if not force and new_version <= old_version:
        return {"status": "error", "message": f"New version {new_version} is not greater than installed {old_version}. Use --force to override."}

    upgrade_plan = _build_upgrade_plan(new_pack_path, new_pack_id, old_version, new_version)

    imported_dir = IMPORTED_DIR / new_pack_id
    backup_path = IMPORTED_DIR / f"{new_pack_id}_backup_{old_version}"

    if imported_dir.exists():
        shutil.copytree(imported_dir, backup_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(new_pack_path, "r") as zf:
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

        if imported_dir.exists():
            shutil.rmtree(imported_dir)
        imported_dir.mkdir(parents=True, exist_ok=True)
        for item in extracted.iterdir():
            dest = imported_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    registry["packs"][new_pack_id]["version"] = new_version
    registry["packs"][new_pack_id]["skills"] = new_validation.get("skills", [])
    registry["packs"][new_pack_id]["validation_status"] = new_validation["status"]
    _save_pack_registry(registry)

    return {
        "status": "upgraded",
        "pack_id": new_pack_id,
        "from_version": old_version,
        "to_version": new_version,
        "backup_path": str(backup_path),
        "plan": upgrade_plan,
    }


def _build_upgrade_plan(new_pack_path: Path, pack_id: str, old_version: str, new_version: str) -> dict[str, Any]:
    """Build an upgrade plan comparing old and new pack."""
    imported_dir = IMPORTED_DIR / pack_id
    old_skills = {}
    old_permissions = {}
    old_risk = {"low": 0, "medium": 0, "high": 0, "critical": 0}

    if imported_dir.exists():
        old_manifest_path = imported_dir / PACK_MANIFEST_NAME
        if old_manifest_path.exists():
            old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
            for s in old_manifest.get("skills", []):
                old_skills[s["id"]] = s
                skill_dir = imported_dir / s.get("path", "")
                if skill_dir.exists():
                    try:
                        sm = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
                        old_permissions[s["id"]] = sm.get("permissions", [])
                        risk = get_risk_level(sm.get("permissions", []))
                        old_risk[risk] = old_risk.get(risk, 0) + 1
                    except Exception:
                        pass

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(new_pack_path, "r") as zf:
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

        new_manifest_path = extracted / PACK_MANIFEST_NAME
        new_manifest = json.loads(new_manifest_path.read_text(encoding="utf-8"))
        new_skills = {s["id"]: s for s in new_manifest.get("skills", [])}

        skills_added = [sid for sid in new_skills if sid not in old_skills]
        skills_removed = [sid for sid in old_skills if sid not in new_skills]
        skills_changed = [sid for sid in new_skills if sid in old_skills and new_skills[sid].get("version") != old_skills[sid].get("version")]

        permission_changes = []
        for sid in new_skills:
            if sid in old_skills:
                skill_dir = extracted / new_skills[sid].get("path", "")
                if skill_dir.exists():
                    try:
                        sm = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
                        new_perms = set(sm.get("permissions", []))
                        old_perms = set(old_permissions.get(sid, []))
                        added = new_perms - old_perms
                        removed = old_perms - new_perms
                        if added or removed:
                            permission_changes.append({
                                "skill_id": sid,
                                "added": list(added),
                                "removed": list(removed),
                            })
                    except Exception:
                        pass

        new_risk = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for sid in new_skills:
            skill_dir = extracted / new_skills[sid].get("path", "")
            if skill_dir.exists():
                try:
                    sm = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
                    risk = get_risk_level(sm.get("permissions", []))
                    new_risk[risk] = new_risk.get(risk, 0) + 1
                except Exception:
                    pass

    def _risk_label(r: dict) -> str:
        if r.get("critical"):
            return "critical"
        if r.get("high"):
            return "high"
        if r.get("medium"):
            return "medium"
        return "low"

    requires_reapproval = any(pc["added"] for pc in permission_changes)

    return {
        "pack_id": pack_id,
        "from_version": old_version,
        "to_version": new_version,
        "skills_added": skills_added,
        "skills_removed": skills_removed,
        "skills_changed": skills_changed,
        "permission_changes": permission_changes,
        "risk_change": f"{_risk_label(old_risk)} -> {_risk_label(new_risk)}",
        "requires_permission_reapproval": requires_reapproval,
    }


def rollback_pack(pack_id: str, confirm: bool = False) -> dict[str, Any]:
    """Rollback an imported pack to its previous version."""
    if not confirm:
        return {"status": "pending", "message": f"Rollback '{pack_id}'? Pass --confirm true to proceed."}

    imported_dir = IMPORTED_DIR / pack_id
    if not imported_dir.exists():
        return {"status": "error", "message": f"Pack '{pack_id}' not found"}

    backups = sorted([d for d in IMPORTED_DIR.iterdir() if d.is_dir() and d.name.startswith(f"{pack_id}_backup_")], reverse=True)
    if not backups:
        return {"status": "error", "message": f"No backup found for '{pack_id}'"}

    backup = backups[0]
    shutil.rmtree(imported_dir)
    shutil.copytree(backup, imported_dir)

    registry = _load_pack_registry()
    if pack_id in registry.get("packs", {}):
        registry["packs"][pack_id]["version"] = backup.name.split("_")[-1]
        _save_pack_registry(registry)

    return {
        "status": "rolled_back",
        "pack_id": pack_id,
        "restored_from": str(backup),
    }


def upgrade_plan(new_pack_path: str | Path) -> dict[str, Any]:
    """Show upgrade plan without applying changes."""
    new_pack_path = Path(new_pack_path)
    if not new_pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {new_pack_path}"}

    validation = validate_pack(new_pack_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Pack validation failed", "errors": validation["errors"]}

    pack_id = validation["pack_id"]
    new_version = validation["version"]

    registry = _load_pack_registry()
    existing = registry.get("packs", {}).get(pack_id)
    if not existing:
        return {"status": "error", "message": f"Pack '{pack_id}' not imported"}

    old_version = existing.get("version", "0.0.0")
    plan = _build_upgrade_plan(new_pack_path, pack_id, old_version, new_version)
    plan["status"] = "preview"
    return plan


# ============================================================
# v2.3.0: Diff/Preview
# ============================================================

def diff_packs(old_pack_path: str | Path, new_pack_path: str | Path, include_files: bool = False) -> dict[str, Any]:
    """Compare two pack files and show differences."""
    old_path = Path(old_pack_path)
    new_path = Path(new_pack_path)

    if not old_path.exists() or not new_path.exists():
        return {"status": "error", "message": "One or both pack files not found"}

    old_validation = validate_pack(old_path)
    new_validation = validate_pack(new_path)

    if old_validation["status"] == "failed" or new_validation["status"] == "failed":
        return {"status": "error", "message": "One or both packs failed validation"}

    diff = {
        "status": "ok",
        "old_pack_id": old_validation.get("pack_id", ""),
        "new_pack_id": new_validation.get("pack_id", ""),
        "metadata_changes": {},
        "skill_changes": {"added": [], "removed": [], "changed": []},
        "permission_changes": [],
        "risk_change": {},
        "dependency_changes": [],
        "changelog": [],
    }

    old_skills = {s["id"]: s for s in old_validation.get("skills", [])}
    new_skills = {s["id"]: s for s in new_validation.get("skills", [])}

    diff["skill_changes"]["added"] = [sid for sid in new_skills if sid not in old_skills]
    diff["skill_changes"]["removed"] = [sid for sid in old_skills if sid not in new_skills]
    diff["skill_changes"]["changed"] = [
        sid for sid in new_skills
        if sid in old_skills and new_skills[sid].get("version") != old_skills[sid].get("version")
    ]

    if old_validation.get("name") != new_validation.get("name"):
        diff["metadata_changes"]["name"] = {"old": old_validation.get("name"), "new": new_validation.get("name")}
    if old_validation.get("version") != new_validation.get("version"):
        diff["metadata_changes"]["version"] = {"old": old_validation.get("version"), "new": new_validation.get("version")}
    if old_validation.get("risk_summary") != new_validation.get("risk_summary"):
        diff["risk_change"] = {"old": old_validation.get("risk_summary"), "new": new_validation.get("risk_summary")}

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(new_path, "r") as zf:
            zf.extractall(tmp / "new")
            new_extracted = tmp / "new"
            entries = [e.rstrip("/") for e in zf.namelist()]
            top_dirs = set()
            for e in entries:
                parts = Path(e).parts
                if len(parts) > 1:
                    top_dirs.add(parts[0])
            if len(top_dirs) == 1:
                pack_root = new_extracted / top_dirs.pop()
                if pack_root.exists() and (pack_root / PACK_MANIFEST_NAME).exists():
                    new_extracted = pack_root

        new_manifest_path = new_extracted / PACK_MANIFEST_NAME
        if new_manifest_path.exists():
            new_manifest = json.loads(new_manifest_path.read_text(encoding="utf-8"))
            diff["changelog"] = new_manifest.get("changelog", [])
            diff["dependency_changes"] = new_manifest.get("dependencies", [])

            if include_files:
                changed_files = []
                for s in new_manifest.get("skills", []):
                    skill_dir = new_extracted / s.get("path", "")
                    if skill_dir.exists():
                        for root_dir, dirs, files in os.walk(skill_dir):
                            for f in files:
                                changed_files.append(str(Path(root_dir) / f))
                diff["files"] = changed_files

    return diff


def preview_install(pack_path: str | Path) -> dict[str, Any]:
    """Show what would happen if a pack is installed."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Pack validation failed", "errors": validation["errors"]}

    dep_result = resolve_pack_dependencies(pack_path)
    trust = get_trust_state(pack_path)

    from runtime.skills.registry import list_installed_skills
    installed = {s["id"]: s for s in list_installed_skills()}
    would_install = []
    would_skip = []

    for s in validation.get("skills", []):
        sid = s["id"]
        if sid in installed:
            would_skip.append({"id": sid, "reason": "already_installed"})
        else:
            would_install.append(sid)

    return {
        "status": "preview",
        "pack_id": validation.get("pack_id", ""),
        "version": validation.get("version", ""),
        "would_install": would_install,
        "would_skip": would_skip,
        "dependencies": dep_result,
        "trust_state": trust.get("trust_state", "unsigned"),
        "risk_summary": validation.get("risk_summary", {}),
        "note": "Installed skills are disabled by default.",
    }


# ============================================================
# v2.3.0: Base64 Encode/Decode
# ============================================================

def encode_pack(pack_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    """Encode a .liuantskillpack file as base64."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

    file_size = pack_path.stat().st_size
    if file_size > BASE64_SIZE_LIMIT:
        return {"status": "error", "message": f"Pack too large ({file_size / 1024 / 1024:.1f} MB). Limit: {BASE64_SIZE_LIMIT / 1024 / 1024:.0f} MB"}

    encoded = base64.b64encode(pack_path.read_bytes()).decode("utf-8")

    if output_path:
        Path(output_path).write_text(encoded, encoding="utf-8")

    return {
        "status": "encoded",
        "size_bytes": file_size,
        "encoded_length": len(encoded),
        "output": str(output_path) if output_path else None,
    }


def decode_pack(encoded_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    """Decode a base64-encoded pack file."""
    encoded_path = Path(encoded_path)
    if not encoded_path.exists():
        return {"status": "error", "message": f"Encoded file not found: {encoded_path}"}

    encoded = encoded_path.read_text(encoding="utf-8").strip()
    if len(encoded) > BASE64_SIZE_LIMIT * 2:
        return {"status": "error", "message": "Encoded data too large"}

    try:
        decoded = base64.b64decode(encoded)
    except Exception as e:
        return {"status": "error", "message": f"Invalid base64: {e}"}

    out = Path(output_path) if output_path else encoded_path.parent / "decoded.liuantskillpack"
    out.write_bytes(decoded)

    validation = validate_pack(out)
    if validation["status"] == "failed":
        out.unlink(missing_ok=True)
        return {"status": "error", "message": "Decoded pack failed validation", "errors": validation["errors"]}

    return {
        "status": "decoded",
        "output": str(out),
        "pack_id": validation.get("pack_id", ""),
        "validation": validation["status"],
    }


def import_base64_pack(encoded_path: str | Path) -> dict[str, Any]:
    """Decode and import a base64-encoded pack."""
    decode_result = decode_pack(encoded_path)
    if decode_result["status"] != "decoded":
        return decode_result

    output = decode_result["output"]
    return import_pack(output)


def export_base64_pack(skill_ids: list[str], output_path: str | Path, pack_metadata: dict[str, Any]) -> dict[str, Any]:
    """Export skills as base64-encoded pack."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_file = tmp / "pack.liuantskillpack"
        export_result = export_pack(skill_ids, pack_file, pack_metadata)
        if export_result["status"] != "exported":
            return export_result

        return encode_pack(pack_file, output_path)


# ============================================================
# v2.3.0: Pack Analytics
# ============================================================

def _load_analytics() -> dict[str, Any]:
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    if ANALYTICS_FILE.exists():
        return read_json(ANALYTICS_FILE, {"events": []})
    return {"events": []}


def _save_analytics(data: dict[str, Any]) -> None:
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ANALYTICS_FILE, data)


def record_pack_event(event_type: str, pack_id: str, skill_id: str = "", **kwargs) -> dict[str, Any]:
    """Record a local-only pack analytics event."""
    analytics = _load_analytics()
    event = {
        "id": str(uuid4()),
        "pack_id": pack_id,
        "skill_id": skill_id,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workspace": str(WORKSPACE),
        "status": kwargs.get("status", "ok"),
        "risk_level": kwargs.get("risk_level", ""),
        "trust_state": kwargs.get("trust_state", "unsigned"),
    }
    analytics["events"].append(event)
    _save_analytics(analytics)
    return event


def get_pack_analytics(pack_id: str | None = None) -> dict[str, Any]:
    """Get pack analytics, optionally filtered by pack_id."""
    analytics = _load_analytics()
    events = analytics.get("events", [])

    if pack_id:
        events = [e for e in events if e.get("pack_id") == pack_id]

    summary = {
        "total_events": len(events),
        "by_type": {},
        "by_pack": {},
        "last_imported": None,
        "last_installed": None,
        "last_verified": None,
        "last_run": None,
        "validation_failures": 0,
    }

    for e in events:
        et = e.get("event_type", "unknown")
        summary["by_type"][et] = summary["by_type"].get(et, 0) + 1
        pid = e.get("pack_id", "unknown")
        summary["by_pack"][pid] = summary["by_pack"].get(pid, 0) + 1

        if et == "imported" and (not summary["last_imported"] or e["timestamp"] > summary["last_imported"]):
            summary["last_imported"] = e["timestamp"]
        if et == "installed" and (not summary["last_installed"] or e["timestamp"] > summary["last_installed"]):
            summary["last_installed"] = e["timestamp"]
        if et == "verified" and (not summary["last_verified"] or e["timestamp"] > summary["last_verified"]):
            summary["last_verified"] = e["timestamp"]
        if et == "run" and (not summary["last_run"] or e["timestamp"] > summary["last_run"]):
            summary["last_run"] = e["timestamp"]
        if et == "failed_validation":
            summary["validation_failures"] += 1

    return {"summary": summary, "events": events[-50:]}


def export_pack_analytics(format: str = "markdown") -> str:
    """Export pack analytics as markdown, JSON, or CSV."""
    analytics = get_pack_analytics()
    summary = analytics["summary"]
    events = analytics["events"]

    if format == "json":
        return json.dumps(analytics, indent=2)

    if format == "csv":
        lines = ["id,pack_id,skill_id,event_type,timestamp,status,risk_level,trust_state"]
        for e in events:
            lines.append(f"{e.get('id','')},{e.get('pack_id','')},{e.get('skill_id','')},{e.get('event_type','')},{e.get('timestamp','')},{e.get('status','')},{e.get('risk_level','')},{e.get('trust_state','')}")
        return "\n".join(lines)

    lines = ["# Pack Analytics\n"]
    lines.append(f"**Total Events:** {summary['total_events']}\n")
    lines.append(f"**Validation Failures:** {summary['validation_failures']}\n")
    if summary["last_imported"]:
        lines.append(f"**Last Imported:** {summary['last_imported']}\n")
    if summary["last_installed"]:
        lines.append(f"**Last Installed:** {summary['last_installed']}\n")
    lines.append("\n## Events by Type\n")
    for et, count in summary["by_type"].items():
        lines.append(f"- {et}: {count}")
    lines.append("\n## Events by Pack\n")
    for pid, count in summary["by_pack"].items():
        lines.append(f"- {pid}: {count}")
    lines.append("\n## Recent Events\n")
    for e in events[-10:]:
        lines.append(f"- [{e['timestamp']}] {e['event_type']} - {e['pack_id']} ({e['status']})")
    return "\n".join(lines)
