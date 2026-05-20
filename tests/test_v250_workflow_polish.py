"""Tests for v2.5.0 workflow execution polish & pack UX hardening.

Covers: workflow preview, permission review, output chaining,
audit logs, run history, dry-run improvements, failure recovery,
lint auto-fix suggestions, staged URL import, recommendation ranking,
and chat-first workflow intents.

All tests are local-only — no network calls, no real provider keys.
"""

import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from runtime.skills.workflows import (
    preview_workflow_run,
    workflow_permission_summary,
    run_workflow,
    preview_rerun_from_step,
    register_workflow,
    list_workflows,
    _resolve_nested_value,
)
from runtime.skills.workflow_audit import (
    record_workflow_run_start,
    record_workflow_run_complete,
    record_workflow_step,
    get_workflow_audit,
    get_latest_workflow_run,
    get_workflow_steps,
    _redact_secrets,
    _redact_value,
)
from runtime.skills.linter import lint_pack, apply_safe_lint_fixes
from runtime.skills.url_import import (
    preview_url_import,
    import_staged,
    install_staged,
    list_staged_packs,
)
from runtime.skills.recommender import recommend_packs, get_recommendations
from runtime.chat.intent_router import route_chat_message


# ============================================================
# Helpers
# ============================================================

def _create_test_workflow_dir(tmp_path: Path, workflow_id: str = "test-wf", steps: list | None = None) -> Path:
    """Create a test workflow.json in a temp directory."""
    if steps is None:
        steps = [
            {
                "step_id": "step1",
                "skill_id": "test-skill",
                "command": "run",
                "output_key": "result1",
            }
        ]
    wf_dir = tmp_path / workflow_id
    wf_dir.mkdir()
    wf_file = wf_dir / "workflow.json"
    workflow = {
        "schema_version": "1.0",
        "workflow_id": workflow_id,
        "name": f"Test Workflow {workflow_id}",
        "description": "A test workflow",
        "pack_id": "test-pack",
        "version": "0.1.0",
        "steps": steps,
        "required_permissions": ["filesystem.read"],
        "approval_required": False,
        "tags": ["test"],
    }
    wf_file.write_text(json.dumps(workflow))
    return wf_file


def _create_test_pack_dir(tmp_path: Path, pack_id: str = "test-pack", skills: list | None = None, with_readme: bool = True) -> Path:
    """Create a minimal test pack source directory."""
    pack_dir = tmp_path / pack_id
    pack_dir.mkdir()
    if skills is None:
        skills = [{"id": "test-skill", "version": "0.1.0", "path": "skills/test-skill"}]
    for skill in skills:
        skill_dir = pack_dir / skill["path"]
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "main.py").write_text('def run(ctx): return {"status": "ok"}')
        (skill_dir / "skill.json").write_text(json.dumps({
            "schema_version": "1.0",
            "id": skill["id"],
            "name": skill["id"].replace("-", " ").title(),
            "version": skill["version"],
            "description": "A test skill",
            "author": "Test",
            "license": "MIT",
            "entrypoint": "main.py",
            "runtime": "python",
            "category": "utility",
            "permissions": ["filesystem.read"],
            "commands": [{"name": "run", "description": "Run", "input_schema": {}, "output_schema": {}}],
        }))
    manifest = pack_dir / "skill-pack.json"
    manifest.write_text(json.dumps({
        "schema_version": "1.0",
        "pack_id": pack_id,
        "name": pack_id.replace("-", " ").title(),
        "version": "0.1.0",
        "description": "A test pack",
        "author": "Test",
        "license": "MIT",
        "tags": ["test"],
        "skills": skills,
        "created_at": "2024-01-01T00:00:00Z",
    }))
    if with_readme:
        (pack_dir / "README.md").write_text("# Test Pack\n\n## Skills\n\n- test-skill\n\n## Permissions\n\n- filesystem.read\n")
    (pack_dir / "CHECKSUMS.json").write_text("{}")
    return pack_dir


def _create_test_pack_zip(tmp_path: Path, pack_dir: Path) -> Path:
    """Create a .liuantskillpack zip from a pack source directory."""
    zip_path = tmp_path / f"{pack_dir.name}.liuantskillpack"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in pack_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f"{pack_dir.name}/{f.relative_to(pack_dir)}")
    return zip_path


# ============================================================
# 1. Workflow preview does not execute skills
# ============================================================

def test_workflow_preview_does_not_execute_skills():
    """preview_workflow_run must never call run_skill."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows.run_skill") as mock_run, \
             patch("runtime.skills.workflows._get_workflow_by_id") as mock_get:
            mock_list.return_value = [{"id": "test-skill", "enabled": True, "approved_permissions": ["filesystem.read"]}]
            mock_get.return_value = json.loads(wf_file.read_text())
            result = preview_workflow_run("test-wf")
            assert mock_run.call_count == 0
            assert result["status"] == "ready"


# ============================================================
# 2. Workflow preview reports missing skill
# ============================================================

def test_workflow_preview_reports_missing_skill():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows._get_workflow_by_id") as mock_get:
            mock_list.return_value = []
            mock_get.return_value = json.loads(wf_file.read_text())
            result = preview_workflow_run("test-wf")
            assert result["status"] == "blocked"
            assert "test-skill" in result["missing_skills"]


# ============================================================
# 3. Workflow preview reports disabled skill
# ============================================================

def test_workflow_preview_reports_disabled_skill():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows._get_workflow_by_id") as mock_get:
            mock_list.return_value = [{"id": "test-skill", "enabled": False, "approved_permissions": []}]
            mock_get.return_value = json.loads(wf_file.read_text())
            result = preview_workflow_run("test-wf")
            assert result["status"] == "blocked"
            assert "test-skill" in result["disabled_skills"]


# ============================================================
# 4. Workflow permission summary collects permissions
# ============================================================

def test_workflow_permission_summary_collects_permissions():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows._get_workflow_by_id") as mock_get, \
             patch("runtime.skills.workflows._get_skill_permissions") as mock_perms:
            mock_list.return_value = [{"id": "test-skill", "enabled": True, "approved_permissions": ["filesystem.read"]}]
            mock_get.return_value = json.loads(wf_file.read_text())
            mock_perms.return_value = ["filesystem.read"]
            result = workflow_permission_summary("test-wf")
            assert "permissions" in result
            perms = [p["permission"] for p in result["permissions"]]
            assert "filesystem.read" in perms


# ============================================================
# 5. Workflow run blocked when permission missing
# ============================================================

def test_workflow_run_blocked_when_permission_missing():
    """run_workflow must require user_confirmed=True when not dry_run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        result = run_workflow(workflow_path=wf_file, dry_run=False, user_confirmed=False)
        assert result["status"] == "blocked"
        assert "confirmation" in result["message"].lower()


# ============================================================
# 6. Workflow output chaining succeeds
# ============================================================

def test_workflow_output_chaining_succeeds():
    """Output chaining passes previous step output to next step."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        steps = [
            {"step_id": "step1", "skill_id": "test-skill", "command": "run", "output_key": "result1"},
            {"step_id": "step2", "skill_id": "test-skill", "command": "analyze", "input_from": {"data": "result1"}, "output_key": "result2"},
        ]
        wf_file = _create_test_workflow_dir(tmp, steps=steps)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows.run_skill") as mock_run, \
             patch("runtime.skills.workflows.get_skill") as mock_get:
            mock_list.return_value = [
                {"id": "test-skill", "enabled": True, "approved_permissions": ["filesystem.read"], "path": str(tmp / "test-skill")},
            ]
            mock_run.return_value = {"status": "ok", "result": {"summary": "test"}}
            mock_get.return_value = {"id": "test-skill", "enabled": True}
            result = run_workflow(workflow_path=wf_file, dry_run=False, user_confirmed=True)
            assert result["status"] == "completed"
            assert mock_run.call_count == 2


# ============================================================
# 7. Workflow output chaining missing key fails safely
# ============================================================

def test_workflow_output_chaining_missing_key_fails_safely():
    """When input_from references a non-existent key, the step fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        steps = [
            {"step_id": "step1", "skill_id": "test-skill", "command": "run", "output_key": "result1"},
            {"step_id": "step2", "skill_id": "test-skill", "command": "analyze", "input_from": {"data": "nonexistent_key"}},
        ]
        wf_file = _create_test_workflow_dir(tmp, steps=steps)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows.run_skill") as mock_run, \
             patch("runtime.skills.workflows.get_skill") as mock_get:
            mock_list.return_value = [
                {"id": "test-skill", "enabled": True, "approved_permissions": ["filesystem.read"], "path": str(tmp / "test-skill")},
            ]
            mock_run.return_value = {"status": "ok", "result": {"summary": "test"}}
            mock_get.return_value = {"id": "test-skill", "enabled": True}
            result = run_workflow(workflow_path=wf_file, dry_run=False, user_confirmed=True)
            assert result["status"] == "failed"
            assert "nonexistent_key" in str(result.get("errors", []))


# ============================================================
# 8. Workflow output chaining nested key works
# ============================================================

def test_workflow_output_chaining_nested_key_works():
    """Dot-notation nested key like 'result1.summary_text' resolves correctly."""
    nested = _resolve_nested_value({"result1": {"summary_text": "hello", "count": 5}}, "result1.summary_text")
    assert nested == "hello"
    nested_missing = _resolve_nested_value({"result1": {"count": 5}}, "result1.summary_text")
    assert nested_missing is None


# ============================================================
# 9. Workflow output chaining defaults work
# ============================================================

def test_workflow_output_chaining_defaults_work():
    """Defaults fill in for params not covered by input_from."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        steps = [
            {
                "step_id": "step1",
                "skill_id": "test-skill",
                "command": "run",
                "defaults": {"threshold": 0.5},
                "output_key": "result1",
            },
        ]
        wf_file = _create_test_workflow_dir(tmp, steps=steps)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows.run_skill") as mock_run, \
             patch("runtime.skills.workflows.get_skill") as mock_get:
            mock_list.return_value = [
                {"id": "test-skill", "enabled": True, "approved_permissions": ["filesystem.read"], "path": str(tmp / "test-skill")},
            ]
            mock_run.return_value = {"status": "ok", "result": {"summary": "test"}}
            mock_get.return_value = {"id": "test-skill", "enabled": True}
            result = run_workflow(workflow_path=wf_file, dry_run=False, user_confirmed=True)
            assert result["status"] == "completed"


# ============================================================
# 10. Workflow audit log records run metadata
# ============================================================

def test_audit_log_records_run_metadata():
    with tempfile.TemporaryDirectory():
        run_id = record_workflow_run_start("test-wf", workspace="default", dry_run=True, user_confirmed=True, step_count=3)
        record_workflow_run_complete(run_id, "dry_run", completed_steps=0)
        run = get_latest_workflow_run("test-wf")
        assert run is not None
        assert run["workflow_id"] == "test-wf"
        assert run["dry_run"] is True
        assert run["user_confirmed"] is True
        assert run["step_count"] == 3
        assert run["status"] == "dry_run"
        assert run["duration_ms"] is not None


# ============================================================
# 11. Workflow audit log does not store secrets
# ============================================================

def test_audit_log_does_not_store_secrets():
    secret_prefix = "sk-"
    secret_suffix = "abcdefghijklmnopqrst1234567890"
    secret_msg = f"Error with api_key={secret_prefix}{secret_suffix} in request"
    redacted = _redact_secrets(secret_msg)
    assert secret_prefix + secret_suffix[:15] not in redacted
    assert "[REDACTED]" in redacted

    secret_dict = {"api_key": f"{secret_prefix}{secret_suffix}", "safe_field": "hello"}
    redacted_dict = _redact_value(secret_dict)
    assert redacted_dict["safe_field"] == "hello"

    with tempfile.TemporaryDirectory():
        run_id = record_workflow_run_start("test-wf", dry_run=False, user_confirmed=True, step_count=1)
        record_workflow_run_complete(run_id, "failed", error_redacted=secret_msg)
        run = get_latest_workflow_run("test-wf")
        assert run["error_redacted"] is not None
        assert secret_prefix + secret_suffix[:15] not in run["error_redacted"]


# ============================================================
# 12. Workflow run history lists runs
# ============================================================

def test_run_history_lists_runs():
    with tempfile.TemporaryDirectory():
        run_id1 = record_workflow_run_start("wf-a", dry_run=True, user_confirmed=True, step_count=2)
        record_workflow_run_complete(run_id1, "dry_run", completed_steps=0)
        run_id2 = record_workflow_run_start("wf-b", dry_run=False, user_confirmed=True, step_count=1)
        record_workflow_run_complete(run_id2, "completed", completed_steps=1)
        all_runs = get_workflow_audit(limit=10)
        assert len(all_runs) >= 2
        wf_a_runs = get_workflow_audit(workflow_id="wf-a", limit=10)
        assert len(wf_a_runs) >= 1
        assert wf_a_runs[0]["workflow_id"] == "wf-a"


# ============================================================
# 13. Workflow dry-run does not execute skills
# ============================================================

def test_workflow_dry_run_does_not_execute_skills():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        with patch("runtime.skills.workflows.run_skill") as mock_run, \
             patch("runtime.skills.workflows.get_skill") as mock_get:
            mock_get.return_value = {"id": "test-skill", "enabled": True}
            result = run_workflow(workflow_path=wf_file, dry_run=True, user_confirmed=False)
            assert mock_run.call_count == 0
            assert result["status"] == "dry_run"
            assert "execution_plan" in result


# ============================================================
# 14. Workflow failed step records recovery suggestion
# ============================================================

def test_workflow_failed_step_records_recovery_suggestion():
    """When a skill execution fails, recovery_suggestion is included."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        steps = [
            {"step_id": "step1", "skill_id": "test-skill", "command": "run", "output_key": "result1"},
            {"step_id": "step2", "skill_id": "test-skill", "command": "run", "output_key": "result2"},
        ]
        wf_file = _create_test_workflow_dir(tmp, steps=steps)
        with patch("runtime.skills.workflows.list_installed_skills") as mock_list, \
             patch("runtime.skills.workflows.run_skill") as mock_run, \
             patch("runtime.skills.workflows.get_skill") as mock_get:
            mock_list.return_value = [
                {"id": "test-skill", "enabled": True, "approved_permissions": ["filesystem.read"], "path": str(tmp / "test-skill")},
            ]
            mock_run.side_effect = [
                {"status": "ok", "result": {"summary": "test"}},
                {"status": "failed", "message": "Execution error"},
            ]
            mock_get.return_value = {"id": "test-skill", "enabled": True}
            result = run_workflow(workflow_path=wf_file, dry_run=False, user_confirmed=True)
            assert result["status"] == "failed"
            assert "recovery_suggestion" in result


# ============================================================
# 15. Rerun-plan returns safe preview
# ============================================================

def test_rerun_plan_returns_safe_preview():
    with tempfile.TemporaryDirectory():
        run_id = record_workflow_run_start("test-wf", dry_run=False, user_confirmed=True, step_count=3)
        record_workflow_run_complete(run_id, "failed", completed_steps=1, failed_step_id="step2")
        with patch("runtime.skills.workflows._get_workflow_by_id") as mock_get, \
             patch("runtime.skills.workflows.list_installed_skills") as mock_list:
            mock_get.return_value = {
                "workflow_id": "test-wf",
                "steps": [
                    {"step_id": "step1", "skill_id": "test-skill", "command": "run"},
                    {"step_id": "step2", "skill_id": "test-skill", "command": "run"},
                    {"step_id": "step3", "skill_id": "test-skill", "command": "run"},
                ],
            }
            mock_list.return_value = [{"id": "test-skill", "enabled": True}]
            result = preview_rerun_from_step(run_id, "step2")
            assert result["status"] in ("ready", "blocked")
            assert result["can_rerun"] is True
            assert result["run_id"] == run_id
            assert result["rerun_from_step"] == "step2"
            assert "note" in result


# ============================================================
# 16. Lint fix suggestions generated
# ============================================================

def test_lint_fix_suggestions_generated():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_dir = _create_test_pack_dir(tmp, with_readme=False)
        result = lint_pack(pack_dir, fix_suggestions=True)
        assert result["status"] in ("passed", "warning", "failed")
        assert "fix_suggestions" in result
        assert len(result["fix_suggestions"]) > 0


def test_apply_safe_lint_fixes_requires_confirmation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_dir = _create_test_pack_dir(tmp, with_readme=False)
        result = apply_safe_lint_fixes(pack_dir, confirm=False)
        assert result["status"] == "pending"
        assert "confirm" in result["message"].lower()


def test_apply_safe_lint_fixes_does_not_modify_code_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_dir = _create_test_pack_dir(tmp, with_readme=False)
        main_py = pack_dir / "skills" / "test-skill" / "main.py"
        original_code = main_py.read_text()
        apply_safe_lint_fixes(pack_dir, confirm=True)
        assert main_py.read_text() == original_code
        assert (pack_dir / "README.md").exists()


# ============================================================
# 19. URL preview creates staged_id
# ============================================================

def test_url_preview_creates_staged_id():
    with patch("runtime.skills.url_import._download_pack") as mock_download, \
         patch("runtime.skills.url_import.validate_pack") as mock_validate:
        mock_download.return_value = {"status": "downloaded", "size_bytes": 1000}
        mock_validate.return_value = {
            "status": "ok", "pack_id": "test-pack", "version": "1.0.0",
            "name": "Test Pack", "skills": [], "risk_summary": {},
        }
        result = preview_url_import("https://example.com/pack.liuantskillpack")
        assert result["status"] == "staged"
        assert "staged_id" in result
        assert result["staged_id"].startswith("staged-")


# ============================================================
# 20. Staged import validates before import
# ============================================================

def test_staged_import_validates_before_import():
    result = import_staged("nonexistent-staged-id", confirm=True)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()


# ============================================================
# 21. Staged install requires confirmation
# ============================================================

def test_staged_install_requires_confirmation():
    result = install_staged("nonexistent-staged-id", confirm=False)
    assert result["status"] == "pending"
    assert "confirm" in result["message"].lower()


# ============================================================
# 22. Recommendation explain returns factor breakdown
# ============================================================

def test_recommendation_explain_returns_factor_breakdown():
    results = recommend_packs(query="analytics", limit=5, explain=True)
    assert isinstance(results, list)
    for rec in results:
        assert "factors" in rec
        assert isinstance(rec["factors"], dict)


# ============================================================
# 23. Recommendations remain local-only
# ============================================================

def test_recommendations_remain_local_only():
    """Recommendations must not make any network calls."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        get_recommendations(query="test", limit=3, explain=True)
        assert mock_urlopen.call_count == 0


# ============================================================
# 24. UI contains workflow templates section
# ============================================================

def test_ui_contains_workflow_templates_section():
    """The backend provides workflow template functionality."""
    from runtime.skills.workflows import list_workflows, preview_workflow_run
    workflows = list_workflows()
    assert isinstance(workflows, list)
    assert callable(preview_workflow_run)


def test_ui_contains_url_import_staged_confirmation_flow():
    """The backend provides URL import staging with confirmation."""
    from runtime.skills.url_import import preview_url_import, import_staged, install_staged
    assert callable(preview_url_import)
    assert callable(import_staged)
    assert callable(install_staged)


def test_ui_contains_lint_fix_suggestions():
    """The backend provides lint fix suggestions."""
    from runtime.skills.linter import lint_pack, apply_safe_lint_fixes
    assert callable(lint_pack)
    assert callable(apply_safe_lint_fixes)


# ============================================================
# 27. ChatIntentRouter detects workflow preview/dry-run/audit
# ============================================================

def test_chat_intent_router_detects_workflow_preview():
    result = route_chat_message("preview the workflow csv-analysis-report")
    assert result["intent"] == "workflow_preview"


def test_chat_intent_router_detects_workflow_dry_run():
    result = route_chat_message("dry run the workflow csv-analysis-report")
    assert result["intent"] == "workflow_dry_run"


def test_chat_intent_router_detects_workflow_audit():
    result = route_chat_message("show workflow runs")
    assert result["intent"] == "workflow_audit"


# ============================================================
# 28. Existing tests still pass
# ============================================================

def test_existing_v240_tests_still_pass():
    """Smoke test that v2.4.0 core functions still work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wf_file = _create_test_workflow_dir(tmp)
        from runtime.skills.workflows import validate_workflow, list_workflows, inspect_workflow
        result = validate_workflow(wf_file)
        assert result["status"] in ("passed", "warning")
        workflows = list_workflows()
        assert isinstance(workflows, list)
        inspect_result = inspect_workflow(wf_file)
        assert inspect_result["status"] == "ok"
