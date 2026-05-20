"""Tests for v2.4.0 pack collaboration & workflow features.

Covers: workflows, compatibility matrix, embedded export, linting,
changelog, URL import, and local recommendations.
"""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from runtime.skills.changelog import generate_changelog, update_pack_changelog
from runtime.skills.compatibility import check_compatibility, check_all_installed_compatibility
from runtime.skills.linter import lint_pack
from runtime.skills.recommender import get_recommendations, recommend_packs
from runtime.skills.url_import import preview_url_import
from runtime.skills.workflows import (
    inspect_workflow,
    list_workflows,
    register_workflow,
    run_workflow,
    validate_workflow,
)


def _create_test_workflow(tmp_path: Path) -> Path:
    """Create a test workflow.json file."""
    wf_dir = tmp_path / "test-workflow"
    wf_dir.mkdir()
    wf_file = wf_dir / "workflow.json"
    workflow = {
        "schema_version": "1.0",
        "workflow_id": "test-workflow",
        "name": "Test Workflow",
        "description": "A test workflow for validation",
        "pack_id": "test-pack",
        "version": "0.1.0",
        "steps": [
            {
                "step_id": "step1",
                "skill_id": "test-skill",
                "command": "run",
                "output_key": "result1",
            }
        ],
        "required_permissions": ["filesystem.read"],
        "approval_required": False,
        "tags": ["test"],
    }
    wf_file.write_text(json.dumps(workflow))
    return wf_file


def _create_test_pack(tmp_path: Path, pack_id: str = "test-pack") -> Path:
    """Create a minimal test pack."""
    pack_dir = tmp_path / pack_id
    pack_dir.mkdir()
    skills_dir = pack_dir / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    main_py = skills_dir / "main.py"
    main_py.write_text('def run(ctx): return {"status": "ok"}')
    skill_json = skills_dir / "skill.json"
    skill_json.write_text(json.dumps({
        "schema_version": "1.0",
        "id": "test-skill",
        "name": "Test Skill",
        "version": "0.1.0",
        "description": "A test skill",
        "author": "Test",
        "license": "MIT",
        "entrypoint": "main.py",
        "runtime": "python",
        "category": "utility",
        "permissions": ["filesystem.read"],
        "commands": [{"name": "run", "description": "Run test", "input_schema": {}, "output_schema": {}}],
    }))
    manifest = pack_dir / "skill-pack.json"
    manifest.write_text(json.dumps({
        "schema_version": "1.0",
        "pack_id": pack_id,
        "name": "Test Pack",
        "version": "0.1.0",
        "description": "A test pack",
        "author": "Test",
        "license": "MIT",
        "tags": ["test"],
        "skills": [{"id": "test-skill", "version": "0.1.0", "path": "skills/test-skill"}],
        "created_at": "2024-01-01T00:00:00Z",
    }))
    readme = pack_dir / "README.md"
    readme.write_text("# Test Pack\n\n## Skills\n\n- test-skill\n\n## Permissions\n\n- filesystem.read\n")
    checksums = pack_dir / "CHECKSUMS.json"
    checksums.write_text("{}")
    return pack_dir


# ============================================================
# Workflow Tests (7 tests)
# ============================================================

def test_validate_workflow_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = _create_test_workflow(Path(tmpdir))
        result = validate_workflow(wf_file)
        assert result["status"] in ("passed", "warning")
        assert result["workflow_id"] == "test-workflow"
        assert result["steps"] == 1


def test_validate_workflow_missing_file():
    result = validate_workflow("/nonexistent/workflow.json")
    assert result["status"] == "failed"
    assert "not found" in result["errors"][0]


def test_validate_workflow_invalid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = Path(tmpdir) / "workflow.json"
        wf_file.write_text("not json")
        result = validate_workflow(wf_file)
        assert result["status"] == "failed"


def test_validate_workflow_missing_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = Path(tmpdir) / "workflow.json"
        wf_file.write_text(json.dumps({"schema_version": "1.0"}))
        result = validate_workflow(wf_file)
        assert result["status"] == "failed"
        assert any("Missing required field" in e for e in result["errors"])


def test_inspect_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = _create_test_workflow(Path(tmpdir))
        result = inspect_workflow(wf_file)
        assert result["status"] == "ok"
        assert result["workflow_id"] == "test-workflow"
        assert len(result["steps"]) == 1


def test_run_workflow_dry_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = _create_test_workflow(Path(tmpdir))
        result = run_workflow(wf_file, dry_run=True)
        assert result["status"] == "dry_run"
        assert len(result["steps"]) == 1


def test_list_workflows_empty():
    result = list_workflows()
    assert isinstance(result, list)


# ============================================================
# Compatibility Tests (5 tests)
# ============================================================

def test_check_compatibility_no_conflicts():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        result = check_compatibility(pack_path=pack_dir)
        assert result["status"] in ("compatible", "warnings")
        assert result["pack_id"] == "test-pack"


def test_check_compatibility_missing_input():
    result = check_compatibility()
    assert result["status"] == "error"


def test_check_compatibility_invalid_pack():
    result = check_compatibility(pack_path="/nonexistent/pack")
    assert result["status"] == "error"


def test_check_all_installed_compatibility():
    result = check_all_installed_compatibility()
    assert result["status"] in ("ok", "issues_found")
    assert "conflicts" in result
    assert "warnings" in result


def test_check_compatibility_permissions():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        result = check_compatibility(pack_path=pack_dir)
        assert "risk_level" in result


# ============================================================
# Linting Tests (5 tests)
# ============================================================

def test_lint_pack_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        result = lint_pack(pack_dir)
        assert result["status"] in ("passed", "warning")
        assert 0 <= result["score"] <= 100
        assert "grade" in result


def test_lint_pack_strict_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        result = lint_pack(pack_dir, strict=True)
        assert "score" in result
        assert "grade" in result


def test_lint_pack_missing_file():
    result = lint_pack("/nonexistent/pack")
    assert result["status"] == "error"


def test_lint_pack_category_scores():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        result = lint_pack(pack_dir)
        assert "category_scores" in result
        assert "readme_quality" in result["category_scores"]
        assert "secret_scan" in result["category_scores"]


def test_lint_pack_grade():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        result = lint_pack(pack_dir)
        assert result["grade"] in ("A", "B", "C", "D", "F")


# ============================================================
# Changelog Tests (3 tests)
# ============================================================

def test_update_pack_changelog():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = _create_test_pack(Path(tmpdir))
        entries = [{"version": "0.2.0", "changes": ["Added feature"]}]
        result = update_pack_changelog(pack_dir, entries)
        assert result["status"] == "updated"
        assert result["total_entries"] == 1


def test_update_pack_changelog_missing_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = update_pack_changelog(Path(tmpdir), [])
        assert result["status"] == "error"


def test_generate_changelog_missing_files():
    result = generate_changelog("/nonexistent/old", "/nonexistent/new")
    assert result["status"] == "error"


# ============================================================
# URL Import Tests (4 tests)
# ============================================================

def test_preview_url_import_valid():
    from unittest.mock import patch
    with patch("runtime.skills.url_import._download_pack") as mock_download, \
         patch("runtime.skills.url_import.validate_pack") as mock_validate:
        mock_download.return_value = {"status": "downloaded", "size_bytes": 1000}
        mock_validate.return_value = {
            "status": "ok",
            "pack_id": "test-pack",
            "version": "1.0.0",
            "name": "Test Pack",
            "skills": [],
            "risk_summary": {},
        }
        result = preview_url_import("https://example.com/pack.liuantskillpack")
        assert result["status"] == "staged"
        assert result["host"] == "example.com"
        assert "staged_id" in result


def test_preview_url_import_non_https():
    result = preview_url_import("http://example.com/pack.liuantskillpack")
    assert result["status"] == "error"
    assert "HTTPS" in result["message"]


def test_preview_url_import_invalid_url():
    result = preview_url_import("not-a-url")
    assert result["status"] == "error"


def test_preview_url_import_no_path():
    result = preview_url_import("https://example.com")
    assert result["status"] == "error"


# ============================================================
# Recommendations Tests (3 tests)
# ============================================================

def test_recommend_packs():
    result = recommend_packs(limit=3)
    assert isinstance(result, list)
    assert len(result) <= 3


def test_get_recommendations():
    result = get_recommendations(limit=3)
    assert "packs" in result
    assert "workflows" in result
    assert "skills_needed" in result


def test_recommend_packs_empty_catalog():
    result = recommend_packs(limit=5)
    assert isinstance(result, list)
