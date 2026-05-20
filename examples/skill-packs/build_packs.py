#!/usr/bin/env python3
"""Build .liuantskillpack archives from source directories."""

import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = ROOT / "examples" / "skill-packs"
EXCLUDE_PATTERNS = {"__pycache__", ".git", ".env", "node_modules", "*.pyc", ".DS_Store"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_checksums(pack_dir: Path) -> dict[str, str]:
    checksums = {}
    for root_dir, dirs, files in os.walk(pack_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
        for fname in sorted(files):
            if fname == "CHECKSUMS.json":
                continue
            fpath = Path(root_dir) / fname
            rel = str(fpath.relative_to(pack_dir))
            checksums[rel] = sha256_file(fpath)
    return checksums


def build_pack(pack_source_dir: Path) -> Path:
    pack_id = None
    manifest_path = pack_source_dir / "skill-pack.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pack_id = manifest.get("pack_id", "unnamed-pack")
    else:
        pack_id = pack_source_dir.name

    output_path = pack_source_dir.parent / f"{pack_id}.liuantskillpack"

    readme_path = pack_source_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            f"# {pack_id}\n\nSkill pack for Liuant Agentic OS.\n",
            encoding="utf-8",
        )

    checksums = generate_checksums(pack_source_dir)
    checksums_path = pack_source_dir / "CHECKSUMS.json"
    checksums_path.write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, dirs, files in os.walk(pack_source_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
            for fname in files:
                fpath = Path(root_dir) / fname
                arcname = f"{pack_id}/{fpath.relative_to(pack_source_dir)}"
                zf.write(fpath, arcname)

    print(f"Built: {output_path}")
    return output_path


if __name__ == "__main__":
    for pack_dir in sorted(PACKS_DIR.iterdir()):
        if pack_dir.is_dir():
            source = pack_dir / "source"
            if source.exists():
                build_pack(source)
