"""Safe URL import for Liuant Agentic OS v2.5.0.

Downloads packs from HTTPS URLs only, enforces size limits,
stages in workspace/skills/packs/staging/, validates before install.

v2.5.0 additions: staged pack IDs, preview_url returns staged_id,
import_staged and install_staged functions for confirmation flow.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from runtime.skills.packs import (
    PACK_EXTENSION,
    STAGING_DIR,
    IMPORTED_DIR,
    PACK_MANIFEST_NAME,
    _load_pack_registry,
    _save_pack_registry,
    validate_pack,
    import_pack,
    install_pack_from_imported,
)
from runtime.storage import WORKSPACE

URL_IMPORT_MAX_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_SCHEMES = {"https"}
STAGING_REGISTRY_FILE = STAGING_DIR.parent / "staging_registry.json"


def _ensure_staging_dir() -> None:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)


def _load_staging_registry() -> dict[str, Any]:
    _ensure_staging_dir()
    if STAGING_REGISTRY_FILE.exists():
        try:
            return json.loads(STAGING_REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"staged": {}}


def _save_staging_registry(data: dict[str, Any]) -> None:
    _ensure_staging_dir()
    STAGING_REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _validate_url(url: str, allow_localhost: bool = False) -> tuple[bool, str]:
    """Validate URL for safe import."""
    parsed = urlparse(url)

    if allow_localhost and parsed.hostname in ("localhost", "127.0.0.1"):
        pass
    elif parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"URL must use HTTPS. Got scheme: {parsed.scheme}"

    if not parsed.netloc:
        return False, "Invalid URL: no host"

    if not parsed.path:
        return False, "Invalid URL: no path"

    return True, "OK"


def _download_pack(url: str, dest_path: Path) -> dict[str, Any]:
    """Download a pack from URL to destination path."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Liuant-AI/2.5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                size = int(content_length)
                if size > URL_IMPORT_MAX_SIZE:
                    return {
                        "status": "error",
                        "message": f"Pack too large: {size / 1024 / 1024:.1f} MB (max: {URL_IMPORT_MAX_SIZE / 1024 / 1024:.0f} MB)",
                    }

            data = b""
            total_read = 0
            chunk_size = 8192
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > URL_IMPORT_MAX_SIZE:
                    return {
                        "status": "error",
                        "message": f"Download exceeded size limit ({URL_IMPORT_MAX_SIZE / 1024 / 1024:.0f} MB)",
                    }
                data += chunk

            dest_path.write_bytes(data)
            return {
                "status": "downloaded",
                "path": str(dest_path),
                "size_bytes": len(data),
            }
    except urllib.error.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e.code} {e.reason}"}
    except urllib.error.URLError as e:
        return {"status": "error", "message": f"URL error: {e.reason}"}
    except Exception as e:
        return {"status": "error", "message": f"Download failed: {e}"}


def preview_url_import(url: str, allow_localhost: bool = False) -> dict[str, Any]:
    """Preview a URL import: download to staging, validate, return staged_id.

    Does NOT install. Only stages and validates.
    """
    url_valid, url_message = _validate_url(url, allow_localhost=allow_localhost)
    if not url_valid:
        return {"status": "error", "message": url_message}

    _ensure_staging_dir()

    parsed = urlparse(url)
    filename = Path(parsed.path).name
    if not filename.endswith(PACK_EXTENSION):
        filename = "downloaded_pack" + PACK_EXTENSION

    staged_id = f"staged-{str(uuid4())[:8]}"
    dest_path = STAGING_DIR / f"{staged_id}-{filename}"

    download_result = _download_pack(url, dest_path)
    if download_result["status"] != "downloaded":
        return download_result

    validation = validate_pack(dest_path)
    if validation["status"] == "failed":
        dest_path.unlink(missing_ok=True)
        return {
            "status": "error",
            "message": "Pack validation failed",
            "errors": validation["errors"],
        }

    registry = _load_staging_registry()
    registry["staged"][staged_id] = {
        "staged_id": staged_id,
        "url": url,
        "filename": filename,
        "path": str(dest_path),
        "size_bytes": download_result.get("size_bytes", 0),
        "pack_id": validation.get("pack_id", ""),
        "version": validation.get("version", ""),
        "name": validation.get("name", ""),
        "validation_status": validation.get("status", ""),
        "skills": validation.get("skills", []),
        "risk_summary": validation.get("risk_summary", {}),
        "staged_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_staging_registry(registry)

    return {
        "status": "staged",
        "staged_id": staged_id,
        "url": url,
        "host": parsed.netloc,
        "filename": filename,
        "pack_id": validation.get("pack_id", ""),
        "version": validation.get("version", ""),
        "name": validation.get("name", ""),
        "validation_status": validation.get("status", ""),
        "size_bytes": download_result.get("size_bytes", 0),
        "risk_summary": validation.get("risk_summary", {}),
        "note": "Pack staged for review. Use import_staged to import, then install_staged to install.",
    }


def import_staged(staged_id: str, confirm: bool = False) -> dict[str, Any]:
    """Import a staged pack into the imported packs directory."""
    if not confirm:
        return {"status": "pending", "message": "Import staged pack? Pass --confirm true to proceed."}

    registry = _load_staging_registry()
    staged_info = registry.get("staged", {}).get(staged_id)
    if not staged_info:
        return {"status": "error", "message": f"Staged pack '{staged_id}' not found"}

    pack_path = Path(staged_info["path"])
    if not pack_path.exists():
        return {"status": "error", "message": "Staged pack file not found"}

    result = import_pack(pack_path, install=False)
    if result.get("status") == "imported":
        del registry["staged"][staged_id]
        _save_staging_registry(registry)

    return result


def install_staged(staged_id: str, confirm: bool = False, selected_skills: list[str] | None = None) -> dict[str, Any]:
    """Install skills from a staged pack."""
    if not confirm:
        return {"status": "pending", "message": "Install staged pack skills? Pass --confirm true to proceed."}

    registry = _load_staging_registry()
    staged_info = registry.get("staged", {}).get(staged_id)
    if not staged_info:
        return {"status": "error", "message": f"Staged pack '{staged_id}' not found. Import it first."}

    pack_id = staged_info.get("pack_id", "")
    pack_registry = _load_pack_registry()
    if pack_id not in pack_registry.get("packs", {}):
        return {"status": "error", "message": f"Pack '{pack_id}' not imported. Import it first."}

    result = install_pack_from_imported(pack_id, selected_skills)
    result["staged_id"] = staged_id
    result["note"] = "Installed skills are disabled by default. Enable them manually after reviewing permissions."
    return result


def list_staged_packs() -> list[dict[str, Any]]:
    """List all staged packs awaiting import."""
    registry = _load_staging_registry()
    staged = []
    for sid, info in registry.get("staged", {}).items():
        staged.append({
            "staged_id": sid,
            "url": info.get("url", ""),
            "filename": info.get("filename", ""),
            "pack_id": info.get("pack_id", ""),
            "version": info.get("version", ""),
            "name": info.get("name", ""),
            "size_bytes": info.get("size_bytes", 0),
            "validation_status": info.get("validation_status", ""),
            "staged_at": info.get("staged_at", ""),
            "risk_summary": info.get("risk_summary", {}),
        })
    return sorted(staged, key=lambda x: x.get("staged_at", ""), reverse=True)


def clear_staging() -> dict[str, Any]:
    """Clear all staged packs."""
    if not STAGING_DIR.exists():
        return {"status": "ok", "message": "Staging directory is empty"}

    cleared = 0
    for f in STAGING_DIR.iterdir():
        if f.is_file():
            f.unlink()
            cleared += 1

    registry = _load_staging_registry()
    registry["staged"] = {}
    _save_staging_registry(registry)

    return {"status": "cleared", "files_removed": cleared}
