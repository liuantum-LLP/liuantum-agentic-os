"""Embedded dependency export for Liuant Agentic OS v2.4.0.

Bundles validated local dependency packs into embedded_packs/
with preserved checksums and signatures for offline distribution.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from runtime.skills.packs import (
    CHECKSUMS_NAME,
    IMPORTED_DIR,
    PACK_MANIFEST_NAME,
    SIGNATURE_NAME,
    _load_pack_registry,
    resolve_pack_dependencies,
    validate_pack,
)
from runtime.storage import WORKSPACE

EMBEDDED_DIR = WORKSPACE / "skills" / "packs" / "embedded_packs"


def export_with_embedded_dependencies(
    pack_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Export a pack with all its dependencies embedded.

    Args:
        pack_path: Path to the main pack file.
        output_path: Output path for the bundled pack.

    Returns:
        Export result with embedded pack info.
    """
    pack_path = Path(pack_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Pack validation failed", "errors": validation["errors"]}

    dep_result = resolve_pack_dependencies(pack_path)
    dependencies = dep_result.get("resolved", [])
    missing = dep_result.get("missing", [])

    if missing:
        return {
            "status": "error",
            "message": "Missing dependencies cannot be embedded",
            "missing": missing,
        }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        main_pack_dir = tmp / "main_pack"
        main_pack_dir.mkdir()

        if pack_path.is_dir():
            shutil.copytree(pack_path, main_pack_dir, dirs_exist_ok=True)
        else:
            with zipfile.ZipFile(pack_path, "r") as zf:
                zf.extractall(main_pack_dir)
                entries = [e.rstrip("/") for e in zf.namelist()]
                top_dirs = set()
                for e in entries:
                    parts = Path(e).parts
                    if len(parts) > 1:
                        top_dirs.add(parts[0])
                if len(top_dirs) == 1:
                    pack_root = main_pack_dir / top_dirs.pop()
                    if pack_root.exists() and (pack_root / PACK_MANIFEST_NAME).exists():
                        for item in pack_root.iterdir():
                            dest = main_pack_dir / item.name
                            if item.is_dir():
                                shutil.copytree(item, dest, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, dest)

        embedded_dir = main_pack_dir / "embedded_packs"
        embedded_dir.mkdir(exist_ok=True)
        embedded_pack_ids = []

        for dep in dependencies:
            dep_id = dep.get("pack_id", "")
            if dep.get("status") == "installed":
                imported_dir = IMPORTED_DIR / dep_id
                if imported_dir.exists():
                    dest_dep_dir = embedded_dir / dep_id
                    shutil.copytree(imported_dir, dest_dep_dir)

                    checksums_path = imported_dir / CHECKSUMS_NAME
                    if checksums_path.exists():
                        shutil.copy2(checksums_path, dest_dep_dir / CHECKSUMS_NAME)

                    sig_path = imported_dir / SIGNATURE_NAME
                    if sig_path.exists():
                        shutil.copy2(sig_path, dest_dep_dir / SIGNATURE_NAME)

                    embedded_pack_ids.append(dep_id)

        manifest_path = main_pack_dir / PACK_MANIFEST_NAME
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["embedded_dependencies"] = embedded_pack_ids
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, dirs, files in main_pack_dir.rglob("*"):
                pass
            for root_dir, dirs, files in os.walk(main_pack_dir):
                for fname in files:
                    fpath = Path(root_dir) / fname
                    arcname = str(fpath.relative_to(main_pack_dir))
                    zf.write(fpath, arcname)

    return {
        "status": "exported",
        "path": str(output_path),
        "pack_id": validation.get("pack_id", ""),
        "embedded_dependencies": embedded_pack_ids,
        "total_packs": 1 + len(embedded_pack_ids),
    }


def list_embedded_packs(pack_path: str | Path) -> list[dict[str, Any]]:
    """List embedded packs within a bundled pack."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        if pack_path.is_dir():
            extracted = pack_path
        else:
            try:
                with zipfile.ZipFile(pack_path, "r") as zf:
                    zf.extractall(tmp / "extracted")
                    extracted = tmp / "extracted"
            except zipfile.BadZipFile:
                return []

        embedded_dir = extracted / "embedded_packs"
        if not embedded_dir.exists():
            return []

        result = []
        for dep_dir in embedded_dir.iterdir():
            if dep_dir.is_dir():
                manifest_path = dep_dir / PACK_MANIFEST_NAME
                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        result.append({
                            "pack_id": manifest.get("pack_id", dep_dir.name),
                            "name": manifest.get("name", ""),
                            "version": manifest.get("version", ""),
                            "has_checksums": (dep_dir / CHECKSUMS_NAME).exists(),
                            "has_signature": (dep_dir / SIGNATURE_NAME).exists(),
                        })
                    except Exception:
                        result.append({
                            "pack_id": dep_dir.name,
                            "name": "",
                            "version": "",
                            "has_checksums": (dep_dir / CHECKSUMS_NAME).exists(),
                            "has_signature": (dep_dir / SIGNATURE_NAME).exists(),
                        })

        return result
