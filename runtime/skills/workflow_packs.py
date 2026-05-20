"""Workflow Template Packs for Liuant Agentic OS v2.7.0.

Provides support for exporting, validating, inspecting, and importing
multi-workflow template packages (.liuantworkflowpack).
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.storage import ROOT, WORKSPACE
from runtime.skills.workflows import (
    _get_workflow_by_id,
    validate_workflow,
    register_workflow,
    IMPORTED_WORKFLOWS_DIR,
    WORKFLOW_MANIFEST_NAME,
)
from runtime.skills.registry import get_skill, list_installed_skills
from runtime.skills.packs import _check_path_traversal
from runtime.skills.manifest import SECRET_PATTERNS


def get_workflow_dependencies(workflow: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Determine the required skills and skill packs for a workflow."""
    skills = []
    packs = []
    for step in workflow.get("steps", []):
        sid = step.get("skill_id")
        if sid:
            if sid not in skills:
                skills.append(sid)
            s_meta = get_skill(sid)
            if s_meta and s_meta.get("pack_id"):
                pid = s_meta.get("pack_id")
                if pid not in packs:
                    packs.append(pid)
    return skills, packs


def export_workflow_pack(
    workflow_ids: list[str],
    pack_id: str,
    output_path: str | Path,
    pack_meta: dict[str, Any],
) -> dict[str, Any]:
    """Export multiple workflows into a .liuantworkflowpack ZIP package."""
    # Find all workflows and collect metadata
    workflows_data = {}
    aggregated_skills = set()
    aggregated_packs = set()

    for wid in workflow_ids:
        wf = _get_workflow_by_id(wid)
        if not wf:
            return {"status": "error", "message": f"Workflow '{wid}' not found"}
        workflows_data[wid] = wf
        sk, pk = get_workflow_dependencies(wf)
        aggregated_skills.update(sk)
        aggregated_packs.update(pk)

    # Setup temp directory to structure the pack
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create workflows folder
        wfs_dir = tmp_path / "workflows"
        wfs_dir.mkdir(parents=True, exist_ok=True)

        pack_wfs_info = []

        for wid, wf in workflows_data.items():
            wf_dir = wfs_dir / wid
            wf_dir.mkdir(parents=True, exist_ok=True)

            # Check if source folder of workflow has additional resources (README, sample input, etc.)
            src_folder = None
            if "source" in wf:
                src_file_path = Path(wf["source"])
                if src_file_path.exists():
                    src_folder = src_file_path.parent

            # Copy or write files
            files_written = []
            if src_folder and src_folder.is_dir():
                for f in src_folder.iterdir():
                    if f.is_file() and f.name != "CHECKSUMS.json":
                        try:
                            shutil.copy2(f, wf_dir)
                            files_written.append(f.name)
                        except Exception:
                            pass

            if "workflow.json" not in files_written:
                clean_wf = {k: v for k, v in wf.items() if k != "source"}
                (wf_dir / "workflow.json").write_text(json.dumps(clean_wf, indent=2), encoding="utf-8")

            if "README.md" not in files_written:
                (wf_dir / "README.md").write_text(f"# {wf.get('name', wid)}\n\n{wf.get('description', '')}\n", encoding="utf-8")

            if "sample_input.json" not in files_written:
                (wf_dir / "sample_input.json").write_text("{}\n", encoding="utf-8")

            if "expected_output.json" not in files_written:
                (wf_dir / "expected_output.json").write_text("{}\n", encoding="utf-8")

            pack_wfs_info.append({
                "id": wid,
                "path": f"workflows/{wid}/workflow.json"
            })

        # Create workflow-pack.json
        manifest = {
            "schema_version": "1.0",
            "pack_id": pack_id,
            "name": pack_meta.get("name", "Unnamed Pack"),
            "version": pack_meta.get("version", "0.1.0"),
            "description": pack_meta.get("description", ""),
            "workflows": pack_wfs_info,
            "required_skills": sorted(list(aggregated_skills)),
            "required_skill_packs": sorted(list(aggregated_packs)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "liuant_min_version": "2.7.0"
        }
        (tmp_path / "workflow-pack.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Create README.md
        readme_content = f"# {manifest['name']}\n\n{manifest['description']}\n"
        (tmp_path / "README.md").write_text(readme_content, encoding="utf-8")

        # Compute checksums
        checksums = {}
        for f in tmp_path.rglob("*"):
            if f.is_file() and f.name != "CHECKSUMS.json":
                rel_path = f.relative_to(tmp_path).as_posix()
                h = hashlib.sha256()
                h.update(f.read_bytes())
                checksums[rel_path] = h.hexdigest()

        (tmp_path / "CHECKSUMS.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

        # Zip it up to output_path
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
                for f in tmp_path.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(tmp_path)
                        z.write(f, rel)
        except Exception as e:
            return {"status": "error", "message": f"Failed to write pack: {e}"}

    return {
        "status": "exported",
        "pack_id": pack_id,
        "path": str(output_path),
    }


def validate_workflow_pack(pack_path: str | Path) -> dict[str, Any]:
    """Validate a .liuantworkflowpack ZIP package."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "failed", "errors": [f"File not found: {pack_path}"], "warnings": []}

    if not zipfile.is_zipfile(pack_path):
        return {"status": "failed", "errors": ["Not a valid ZIP archive"], "warnings": []}

    errors = []
    warnings = []

    try:
        with zipfile.ZipFile(pack_path, "r") as z:
            namelist = z.namelist()

            # Path traversal check
            traversal_violations = _check_path_traversal(namelist)
            if traversal_violations:
                return {"status": "failed", "errors": traversal_violations, "warnings": []}

            # Check essential files
            if "workflow-pack.json" not in namelist:
                return {"status": "failed", "errors": ["Missing workflow-pack.json in archive"], "warnings": []}

            if "CHECKSUMS.json" not in namelist:
                return {"status": "failed", "errors": ["Missing CHECKSUMS.json in archive"], "warnings": []}

            # Load and verify CHECKSUMS
            try:
                checksums_data = json.loads(z.read("CHECKSUMS.json").decode("utf-8"))
            except Exception as e:
                return {"status": "failed", "errors": [f"Failed to parse CHECKSUMS.json: {e}"], "warnings": []}

            files_in_zip = [name for name in namelist if name != "CHECKSUMS.json" and not name.endswith("/")]

            for name in files_in_zip:
                if name not in checksums_data:
                    errors.append(f"File '{name}' in archive is not listed in CHECKSUMS.json")
                    continue
                content = z.read(name)
                h = hashlib.sha256()
                h.update(content)
                actual_sha = h.hexdigest()
                if actual_sha != checksums_data[name]:
                    errors.append(f"Checksum mismatch for file '{name}': expected {checksums_data[name]}, got {actual_sha}")

            for name in checksums_data:
                # If zip entry doesn't exist (taking directories/trailing slashes into account)
                if name not in namelist and (name + "/") not in namelist:
                    errors.append(f"File '{name}' listed in CHECKSUMS.json is missing from the archive")

            if errors:
                return {"status": "failed", "errors": errors, "warnings": []}

            # Scan for secrets in text files
            text_extensions = {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".js", ".ts"}
            for name in files_in_zip:
                ext = Path(name).suffix.lower()
                if ext in text_extensions or ext == "":
                    try:
                        content_str = z.read(name).decode("utf-8", errors="ignore")
                        for pattern_str in SECRET_PATTERNS:
                            pattern = re.compile(pattern_str) if isinstance(pattern_str, str) else pattern_str
                            if pattern.search(content_str):
                                errors.append(f"Secret-like pattern detected in '{name}'")
                    except Exception:
                        pass

            if errors:
                return {"status": "failed", "errors": errors, "warnings": []}

            # Parse and validate workflow-pack.json schema
            try:
                pack_manifest = json.loads(z.read("workflow-pack.json").decode("utf-8"))
            except Exception as e:
                return {"status": "failed", "errors": [f"Failed to parse workflow-pack.json: {e}"], "warnings": []}

            required_fields = ["schema_version", "pack_id", "name", "version", "workflows"]
            for field in required_fields:
                if field not in pack_manifest:
                    errors.append(f"Missing required manifest field: {field}")

            if errors:
                return {"status": "failed", "errors": errors, "warnings": []}

            # Validate each workflow inside the pack
            for wf_info in pack_manifest.get("workflows", []):
                wf_path = wf_info.get("path")
                if not wf_path or wf_path not in namelist:
                    errors.append(f"Workflow path '{wf_path}' not found in archive")
                    continue

                # Temporary file for validation
                with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                    tmp.write(z.read(wf_path))
                    tmp_path = Path(tmp.name)

                try:
                    wf_val = validate_workflow(tmp_path)
                    if wf_val["status"] == "failed":
                        errors.extend([f"Workflow '{wf_info.get('id')}' validation error: {err}" for err in wf_val.get("errors", [])])
                    else:
                        warnings.extend([f"Workflow '{wf_info.get('id')}' warning: {w}" for w in wf_val.get("warnings", [])])
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

    except Exception as e:
        return {"status": "failed", "errors": [f"Validation exception: {e}"], "warnings": []}

    status = "passed" if not errors else "failed"
    if not errors and warnings:
        status = "warning"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "pack_id": pack_manifest.get("pack_id", "") if "pack_manifest" in locals() else ""
    }


def inspect_workflow_pack(pack_path: str | Path) -> dict[str, Any]:
    """Inspect and return metadata + dependency details for a workflow pack."""
    pack_path = Path(pack_path)
    val = validate_workflow_pack(pack_path)
    if val["status"] == "failed":
        return {"status": "error", "message": "Workflow pack validation failed", "errors": val["errors"]}

    try:
        with zipfile.ZipFile(pack_path, "r") as z:
            pack_manifest = json.loads(z.read("workflow-pack.json").decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": f"Failed to read manifest: {e}"}

    # Verify dependencies
    installed_skills = {s["skill_id"] for s in list_installed_skills()}
    # Let's count installed packs
    from runtime.skills.packs import list_imported_packs
    installed_packs = {p["pack_id"] for p in list_imported_packs()}

    required_skills = pack_manifest.get("required_skills", [])
    required_packs = pack_manifest.get("required_skill_packs", [])

    missing_skills = [s for s in required_skills if s not in installed_skills]
    missing_packs = [p for p in required_packs if p not in installed_packs]

    return {
        "status": "ok",
        "pack_id": pack_manifest.get("pack_id"),
        "name": pack_manifest.get("name"),
        "version": pack_manifest.get("version"),
        "description": pack_manifest.get("description"),
        "workflows": pack_manifest.get("workflows"),
        "dependencies": {
            "required_skills": required_skills,
            "missing_skills": missing_skills,
            "required_skill_packs": required_packs,
            "missing_skill_packs": missing_packs
        }
    }


def import_workflow_pack(pack_path: str | Path, confirm: bool = False) -> dict[str, Any]:
    """Import all workflows from a workflow template pack."""
    pack_path = Path(pack_path)
    insp = inspect_workflow_pack(pack_path)
    if insp["status"] == "error":
        return insp

    if not confirm:
        return {
            "status": "blocked",
            "message": "Import requires confirmation. Dependencies may be missing.",
            "dependencies": insp["dependencies"]
        }

    warnings = []
    dep = insp["dependencies"]
    if dep["missing_skills"] or dep["missing_skill_packs"]:
        warnings.append("Missing required skills or packs: some workflow steps might fail to run.")

    # Extract workflows
    pack_id = insp["pack_id"]
    try:
        with zipfile.ZipFile(pack_path, "r") as z:
            # We want to extract each workflow to imported folder and register it
            pack_manifest = json.loads(z.read("workflow-pack.json").decode("utf-8"))

            for wf_info in pack_manifest.get("workflows", []):
                wf_id = wf_info.get("id")
                wf_manifest_path = wf_info.get("path") # e.g. "workflows/wf_id/workflow.json"

                # target folder
                target_dir = IMPORTED_WORKFLOWS_DIR / wf_id
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir(parents=True, exist_ok=True)

                # Extract files under workflows/wf_id/ to target_dir
                prefix = f"workflows/{wf_id}/"
                for name in z.namelist():
                    if name.startswith(prefix) and not name.endswith("/"):
                        rel_name = name[len(prefix):]
                        with z.open(name) as src, open(target_dir / rel_name, "wb") as dest:
                            shutil.copyfileobj(src, dest)

                # Register it
                reg_res = register_workflow(target_dir / "workflow.json")
                if reg_res["status"] == "error":
                    warnings.append(f"Failed to register workflow '{wf_id}': {reg_res.get('message')}")

    except Exception as e:
        return {"status": "error", "message": f"Failed to extract workflow pack: {e}"}

    return {
        "status": "imported",
        "pack_id": pack_id,
        "warnings": warnings,
        "message": f"Workflow pack '{pack_id}' imported successfully. Workflows do not auto-run."
    }
