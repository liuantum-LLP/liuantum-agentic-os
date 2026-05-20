"""Skill pack linting for Liuant Agentic OS v2.5.0.

Scores packs 0-100 based on:
- README quality (presence, length, sections)
- Permissions justification (each permission documented)
- Changelog presence (version history)
- Secret scanning (no secret-like values)
- Workflow documentation (workflows documented)

Strict mode turns warnings into failures.
v2.5.0 adds auto-fix suggestions for safe, non-destructive fixes.
"""

from __future__ import annotations

import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from runtime.skills.packs import (
    CHECKSUMS_NAME,
    PACK_MANIFEST_NAME,
    SIGNATURE_NAME,
    _scan_for_secrets,
    validate_pack,
)
from runtime.skills.manifest import KNOWN_PERMISSIONS

LINT_SCORE_WEIGHTS = {
    "readme_quality": 25,
    "permissions_justification": 25,
    "changelog_presence": 15,
    "secret_scan": 20,
    "workflow_documentation": 15,
}

SAFE_FIX_TEMPLATES = {
    "README.md": """# {pack_name}

{pack_description}

## Skills

{skills_list}

## Installation

1. Import the pack: `liuant skills pack import <pack_id>.liuantskillpack`
2. Review permissions for each skill.
3. Enable skills after review: `liuant skills enable <skill_id>`

## Usage

{usage_placeholder}

## Permissions

{permissions_list}

## Workflows

{workflows_placeholder}
""",
    "sample_input.json": """{
  "description": "Sample input for the skill",
  "input": {}
}
""",
    "expected_output.json": """{
  "description": "Expected output for the sample input",
  "output": {}
}
""",
}


def _extract_pack_contents(pack_path: str | Path) -> Path | None:
    """Extract pack contents to a temp directory."""
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return None

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


def _score_readme(extracted: Path) -> tuple[int, list[str], list[str], list[str]]:
    """Score README quality (0-100). Returns (score, warnings, info, fix_suggestions)."""
    readme_path = extracted / "README.md"
    fix_suggestions = []
    if not readme_path.exists():
        manifest_path = extracted / PACK_MANIFEST_NAME
        pack_name = "Unknown Pack"
        pack_desc = ""
        skills_list = "- (no skills listed)"
        permissions_list = "- (no permissions listed)"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                pack_name = manifest.get("name", "Unknown Pack")
                pack_desc = manifest.get("description", "")
                skills = manifest.get("skills", [])
                if skills:
                    skills_list = "\n".join(f"- {s.get('id', 'unknown')}" for s in skills)
            except Exception:
                pass
        content = SAFE_FIX_TEMPLATES["README.md"].format(
            pack_name=pack_name,
            pack_description=pack_desc,
            skills_list=skills_list,
            usage_placeholder="Describe how to use this pack.",
            permissions_list=permissions_list,
            workflows_placeholder="List available workflows or remove this section.",
        )
        fix_suggestions.append(json.dumps({
            "issue": "README.md missing",
            "fix_type": "create_file",
            "path": "README.md",
            "suggested_content": content,
        }))
        return 0, ["Missing README.md"], [], fix_suggestions

    content = readme_path.read_text(encoding="utf-8", errors="ignore")
    warnings = []
    info = []

    score = 0
    if len(content) > 100:
        score += 30
    else:
        warnings.append("README.md is too short (< 100 chars)")

    if len(content) > 500:
        score += 20

    required_sections = ["## Skills", "## Installation", "## Usage", "## Permissions"]
    for section in required_sections:
        if section.lower() in content.lower():
            score += 10
        else:
            warnings.append(f"README.md missing section: {section}")

    if score > 100:
        score = 100

    return score, warnings, info, fix_suggestions


def _score_permissions(extracted: Path) -> tuple[int, list[str], list[str], list[str]]:
    """Score permissions justification (0-100)."""
    manifest_path = extracted / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return 0, ["Missing manifest"], [], []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    skills = manifest.get("skills", [])

    if not skills:
        return 50, ["No skills in pack"], [], []

    total_perms = 0
    justified_perms = 0
    warnings = []
    info = []

    for skill_entry in skills:
        skill_path = skill_entry.get("path", "")
        skill_dir = extracted / skill_path
        if not skill_dir.exists():
            continue

        skill_manifest_path = skill_dir / "skill.json"
        if not skill_manifest_path.exists():
            continue

        try:
            skill_manifest = json.loads(skill_manifest_path.read_text(encoding="utf-8"))
            perms = skill_manifest.get("permissions", [])
            total_perms += len(perms)

            for perm in perms:
                if perm in KNOWN_PERMISSIONS:
                    justified_perms += 1
                else:
                    warnings.append(f"Unknown permission: {perm}")
        except Exception:
            pass

    if total_perms == 0:
        return 100, [], ["No permissions required"], []

    score = int((justified_perms / total_perms) * 100) if total_perms > 0 else 0
    return score, warnings, info, []


def _score_changelog(extracted: Path) -> tuple[int, list[str], list[str], list[str]]:
    """Score changelog presence (0-100)."""
    manifest_path = extracted / PACK_MANIFEST_NAME
    fix_suggestions = []
    if not manifest_path.exists():
        return 0, ["Missing manifest"], [], []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changelog = manifest.get("changelog", [])

    if not changelog:
        changelog_file = extracted / "CHANGELOG.md"
        if changelog_file.exists():
            content = changelog_file.read_text(encoding="utf-8", errors="ignore")
            if len(content) > 50:
                return 80, [], ["CHANGELOG.md found"], []
            return 50, ["CHANGELOG.md is too short"], [], []
        fix_suggestions.append(json.dumps({
            "issue": "Missing changelog",
            "fix_type": "add_manifest_field",
            "field": "changelog",
            "suggested_value": [],
        }))
        return 0, ["No changelog found"], [], fix_suggestions

    score = min(100, len(changelog) * 25)
    return score, [], [f"{len(changelog)} changelog entries"], []


def _score_secrets(extracted: Path) -> tuple[int, list[str], list[str], list[str]]:
    """Score secret scanning (0-100)."""
    secrets = _scan_for_secrets(extracted)
    if secrets:
        return 0, [f"Secret-like values found in: {secrets}"], [], []
    return 100, [], ["No secrets detected"], []


def _score_workflows(extracted: Path) -> tuple[int, list[str], list[str], list[str]]:
    """Score workflow documentation (0-100)."""
    manifest_path = extracted / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return 100, [], ["No workflows required"], []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workflows = manifest.get("workflows", [])

    if not workflows:
        return 100, [], ["No workflows in pack"], []

    workflows_dir = extracted / "workflows"
    if not workflows_dir.exists():
        return 0, ["workflows/ directory missing"], [], []

    documented = 0
    warnings = []
    for wf_entry in workflows:
        wf_path = wf_entry.get("path", "")
        wf_file = extracted / wf_path
        if wf_file.exists():
            documented += 1
        else:
            warnings.append(f"Workflow file not found: {wf_path}")

    score = int((documented / len(workflows)) * 100) if workflows else 100
    return score, warnings, [f"{documented}/{len(workflows)} workflows documented"], []


def lint_pack(pack_path: str | Path, strict: bool = False, fix_suggestions: bool = False) -> dict[str, Any]:
    """Lint a skill pack and return a score 0-100.

    Args:
        pack_path: Path to pack file or directory.
        strict: If True, warnings become failures.
        fix_suggestions: If True, include auto-fix suggestions.

    Returns:
        Lint result with score, grade, warnings, and per-category scores.
    """
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

    validation = validate_pack(pack_path)
    if validation["status"] == "failed":
        return {"status": "failed", "message": "Pack validation failed", "errors": validation["errors"]}

    extracted = _extract_pack_contents(pack_path)
    if not extracted:
        return {"status": "error", "message": "Could not extract pack"}

    all_warnings = []
    all_info = []
    category_scores = {}
    all_fix_suggestions = []

    readme_score, readme_warnings, readme_info, readme_fixes = _score_readme(extracted)
    category_scores["readme_quality"] = readme_score
    all_warnings.extend(readme_warnings)
    all_info.extend(readme_info)
    all_fix_suggestions.extend(readme_fixes)

    perm_score, perm_warnings, perm_info, perm_fixes = _score_permissions(extracted)
    category_scores["permissions_justification"] = perm_score
    all_warnings.extend(perm_warnings)
    all_info.extend(perm_info)
    all_fix_suggestions.extend(perm_fixes)

    changelog_score, changelog_warnings, changelog_info, changelog_fixes = _score_changelog(extracted)
    category_scores["changelog_presence"] = changelog_score
    all_warnings.extend(changelog_warnings)
    all_info.extend(changelog_info)
    all_fix_suggestions.extend(changelog_fixes)

    secrets_score, secrets_warnings, secrets_info, secrets_fixes = _score_secrets(extracted)
    category_scores["secret_scan"] = secrets_score
    all_warnings.extend(secrets_warnings)
    all_info.extend(secrets_info)
    all_fix_suggestions.extend(secrets_fixes)

    workflow_score, workflow_warnings, workflow_info, workflow_fixes = _score_workflows(extracted)
    category_scores["workflow_documentation"] = workflow_score
    all_warnings.extend(workflow_warnings)
    all_info.extend(workflow_info)
    all_fix_suggestions.extend(workflow_fixes)

    total_score = 0
    for category, score in category_scores.items():
        weight = LINT_SCORE_WEIGHTS.get(category, 0)
        total_score += int(score * weight / 100)

    if total_score >= 90:
        grade = "A"
    elif total_score >= 80:
        grade = "B"
    elif total_score >= 70:
        grade = "C"
    elif total_score >= 60:
        grade = "D"
    else:
        grade = "F"

    status = "passed"
    if strict and all_warnings:
        status = "failed"
    elif secrets_score == 0:
        status = "failed"
    elif all_warnings:
        status = "warning"

    result = {
        "status": status,
        "score": total_score,
        "grade": grade,
        "strict": strict,
        "category_scores": category_scores,
        "warnings": all_warnings,
        "info": all_info,
        "pack_id": validation.get("pack_id", ""),
        "version": validation.get("version", ""),
    }

    if fix_suggestions:
        parsed_fixes = []
        for fix_str in all_fix_suggestions:
            try:
                parsed_fixes.append(json.loads(fix_str))
            except Exception:
                pass
        result["fix_suggestions"] = parsed_fixes
        result["auto_fix_available"] = len(parsed_fixes) > 0

    return result


def apply_safe_lint_fixes(pack_path: str | Path, confirm: bool = False) -> dict[str, Any]:
    """Apply safe lint fixes to a pack source directory.

    Safe fixes:
    - Create missing README.md template
    - Create missing sample_input.json template
    - Create missing expected_output.json template
    - Add empty changelog field to manifest
    - Add missing tags placeholder

    Does NOT:
    - Modify code files
    - Add permissions
    - Change skill logic
    """
    pack_path = Path(pack_path)
    if not pack_path.exists():
        return {"status": "error", "message": f"Pack not found: {pack_path}"}

    if not confirm:
        return {"status": "pending", "message": "Apply safe lint fixes? Pass --confirm true to proceed."}

    manifest_path = pack_path / PACK_MANIFEST_NAME
    if not manifest_path.exists():
        return {"status": "error", "message": f"{PACK_MANIFEST_NAME} not found"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid manifest"}

    fixes_applied = []

    if not (pack_path / "README.md").exists():
        pack_name = manifest.get("name", "Unknown Pack")
        pack_desc = manifest.get("description", "")
        skills = manifest.get("skills", [])
        skills_list = "\n".join(f"- {s.get('id', 'unknown')}" for s in skills) if skills else "- (no skills listed)"
        content = SAFE_FIX_TEMPLATES["README.md"].format(
            pack_name=pack_name,
            pack_description=pack_desc,
            skills_list=skills_list,
            usage_placeholder="Describe how to use this pack.",
            permissions_list="- (list permissions here)",
            workflows_placeholder="List available workflows or remove this section.",
        )
        (pack_path / "README.md").write_text(content, encoding="utf-8")
        fixes_applied.append("Created README template")

    if not manifest.get("changelog"):
        manifest["changelog"] = []
        fixes_applied.append("Added empty changelog field")

    if not manifest.get("tags"):
        manifest["tags"] = ["untagged"]
        fixes_applied.append("Added tags placeholder")

    for skill_entry in manifest.get("skills", []):
        skill_path = skill_entry.get("path", "")
        skill_dir = pack_path / skill_path
        if skill_dir.exists():
            if not (skill_dir / "sample_input.json").exists():
                (skill_dir / "sample_input.json").write_text(SAFE_FIX_TEMPLATES["sample_input.json"], encoding="utf-8")
                fixes_applied.append(f"Created sample_input.json for {skill_entry.get('id', 'unknown')}")
            if not (skill_dir / "expected_output.json").exists():
                (skill_dir / "expected_output.json").write_text(SAFE_FIX_TEMPLATES["expected_output.json"], encoding="utf-8")
                fixes_applied.append(f"Created expected_output.json for {skill_entry.get('id', 'unknown')}")

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "status": "applied",
        "fixes_applied": fixes_applied,
        "pack_id": manifest.get("pack_id", ""),
    }
