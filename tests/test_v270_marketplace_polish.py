from __future__ import annotations

import json
import shutil
import zipfile
import hashlib
from pathlib import Path
import pytest

from runtime.storage import WORKSPACE
from runtime.db import insert_record, get_record, delete_record
from runtime.skills.workflows import (
    register_workflow,
    export_workflow,
    validate_workflow_file,
    import_workflow,
    export_workflow_run_report,
    get_workflow_run_timeline,
)
from runtime.skills.workflow_packs import (
    export_workflow_pack,
    validate_workflow_pack,
    inspect_workflow_pack,
    import_workflow_pack,
)
from runtime.backup import BackupManager


@pytest.fixture()
def setup_workspace_monkeypatch(tmp_path, monkeypatch):
    """Monkeypatch workspace variables across modules for absolute isolation."""
    wfs_dir = tmp_path / "skills" / "workflows"
    wfs_dir.mkdir(parents=True, exist_ok=True)
    imported_dir = wfs_dir / "imported"
    imported_dir.mkdir(parents=True, exist_ok=True)

    audit_dir = tmp_path / "skills" / "workflow_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    import runtime.skills.workflows
    import runtime.skills.workflow_packs
    import runtime.skills.workflow_audit
    import runtime.backup

    # Patch runtime.skills.workflows paths
    monkeypatch.setattr(runtime.skills.workflows, "WORKSPACE", tmp_path)
    monkeypatch.setattr(runtime.skills.workflows, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(runtime.skills.workflows, "WORKFLOWS_DIR", wfs_dir)
    monkeypatch.setattr(runtime.skills.workflows, "WORKFLOW_REGISTRY_FILE", wfs_dir / "registry.json")
    monkeypatch.setattr(runtime.skills.workflows, "IMPORTED_WORKFLOWS_DIR", imported_dir)

    # Patch runtime.skills.workflow_packs paths
    monkeypatch.setattr(runtime.skills.workflow_packs, "IMPORTED_WORKFLOWS_DIR", imported_dir)

    # Patch runtime.skills.workflow_audit paths
    monkeypatch.setattr(runtime.skills.workflow_audit, "WORKSPACE", tmp_path)
    monkeypatch.setattr(runtime.skills.workflow_audit, "AUDIT_DIR", audit_dir)
    monkeypatch.setattr(runtime.skills.workflow_audit, "AUDIT_RUNS_FILE", audit_dir / "workflow_runs.json")
    monkeypatch.setattr(runtime.skills.workflow_audit, "AUDIT_STEPS_FILE", audit_dir / "workflow_steps.json")

    # Patch runtime.backup paths
    monkeypatch.setattr(runtime.backup, "WORKSPACE", tmp_path)

    return tmp_path, wfs_dir, imported_dir, audit_dir


def test_workflow_export_import_cycle(tmp_path, monkeypatch):
    _, wfs_dir, imported_dir, audit_dir = setup_workspace_monkeypatch(tmp_path, monkeypatch)

    # Create schema-compliant dummy workflow source
    wf_id = "test-export-wf"
    src_dir = wfs_dir / wf_id
    src_dir.mkdir(parents=True, exist_ok=True)

    wf_data = {
        "schema_version": "1.0",
        "workflow_id": wf_id,
        "name": "Test Export Workflow",
        "description": "Demonstrates export and import",
        "pack_id": "test_pack",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": "step_1",
                "skill_id": "test_skill",
                "command": "run_command"
            }
        ]
    }
    (src_dir / "workflow.json").write_text(json.dumps(wf_data), encoding="utf-8")
    (src_dir / "README.md").write_text("# Test Export Workflow", encoding="utf-8")

    # Register workflow
    register_workflow(src_dir / "workflow.json")

    # Export to .liuantworkflow
    archive_path = tmp_path / "test_wf.liuantworkflow"
    res = export_workflow(wf_id, archive_path)
    assert res["status"] == "exported"
    assert archive_path.exists()

    # Validate archive
    val_res = validate_workflow_file(archive_path)
    assert val_res["status"] in ("passed", "warning")

    # Simulating path traversal
    traversal_archive = tmp_path / "traversal.liuantworkflow"
    with zipfile.ZipFile(archive_path, "r") as src_zip:
        with zipfile.ZipFile(traversal_archive, "w") as dest_zip:
            for item in src_zip.infolist():
                if item.filename == "workflow.json":
                    dest_zip.writestr("../workflow.json", src_zip.read(item))
                else:
                    dest_zip.writestr(item.filename, src_zip.read(item))

    # Import the traversal archive (should fail)
    bad_res = import_workflow(traversal_archive, confirm=True)
    assert bad_res["status"] == "failed"
    assert any("traversal" in err.lower() for err in bad_res["errors"])

    # Simulating missing workflow.json
    missing_json_archive = tmp_path / "missing.liuantworkflow"
    with zipfile.ZipFile(archive_path, "r") as src_zip:
        with zipfile.ZipFile(missing_json_archive, "w") as dest_zip:
            for item in src_zip.infolist():
                if item.filename != "workflow.json":
                    dest_zip.writestr(item.filename, src_zip.read(item))
    missing_res = import_workflow(missing_json_archive, confirm=True)
    assert missing_res["status"] == "failed"
    assert any("workflow.json" in err.lower() for err in missing_res["errors"])

    # Create dummy secret workflow
    secret_wf_id = "test-secret-wf"
    secret_wf_dir = wfs_dir / secret_wf_id
    secret_wf_dir.mkdir(parents=True, exist_ok=True)
    bad_data = wf_data.copy()
    bad_data["workflow_id"] = secret_wf_id
    bad_data["secret_api_key"] = "sk-placeholderAPIkey12345"
    (secret_wf_dir / "workflow.json").write_text(json.dumps(bad_data), encoding="utf-8")
    register_workflow(secret_wf_dir / "workflow.json")

    secret_archive = tmp_path / "secret.liuantworkflow"
    export_workflow(secret_wf_id, secret_archive)
    sec_res = validate_workflow_file(secret_archive)
    assert sec_res["status"] == "failed"
    assert any("secret" in err.lower() for err in sec_res["errors"])

    # Import the clean archive
    import_res = import_workflow(archive_path, confirm=True)
    assert import_res["status"] == "imported"
    assert (imported_dir / wf_id / "workflow.json").exists()


def test_workflow_run_report(tmp_path, monkeypatch):
    _, wfs_dir, imported_dir, audit_dir = setup_workspace_monkeypatch(tmp_path, monkeypatch)
    run_id = "test-run-123"

    from runtime.skills.workflow_audit import _load_runs, _save_runs, _load_steps, _save_steps
    
    runs = _load_runs()
    runs["runs"][run_id] = {
        "run_id": run_id,
        "workflow_id": "test-wf",
        "status": "completed",
        "created_at": "2026-05-20T04:00:00Z",
        "updated_at": "2026-05-20T04:00:01Z",
        "started_at": "2026-05-20T04:00:00Z",
        "completed_at": "2026-05-20T04:00:01Z",
        "duration_ms": 1000,
        "completed_steps": 1,
        "step_count": 1,
    }
    _save_runs(runs)

    steps = _load_steps()
    steps["steps"][f"{run_id}:step_1"] = {
        "run_id": run_id,
        "step_index": 0,
        "step_id": "step_1",
        "skill_id": "math_skill",
        "command": "add",
        "input": {"x": 5, "y": 10, "api_key": "xoxb-12345"},
        "output": {"result": 15, "token": "secret_token_abc"},
        "status": "success",
        "started_at": "2026-05-20T04:00:00Z",
        "completed_at": "2026-05-20T04:00:01Z",
        "recorded_at": "2026-05-20T04:00:01Z",
        "duration_ms": 1000,
    }
    _save_steps(steps)

    # 1. Export HTML Report
    html_res = export_workflow_run_report(run_id, "html")
    assert html_res["status"] == "ok"
    html_content = html_res["content"]
    assert run_id in html_content
    # Check secrets redaction
    assert "xoxb-12345" not in html_content
    assert "secret_token_abc" not in html_content

    # 2. Export MD Report
    md_res = export_workflow_run_report(run_id, "markdown")
    assert md_res["status"] == "ok"
    assert run_id in md_res["content"]

    # 3. Export JSON Report
    json_res = export_workflow_run_report(run_id, "json")
    assert json_res["status"] == "ok"
    json_data = json.loads(json_res["content"])
    assert json_data["run"]["run_id"] == run_id
    assert "REDACTED" in json_res["content"]

    # Check timeline
    timeline = get_workflow_run_timeline(run_id)
    assert len(timeline["timeline"]) == 4
    assert timeline["timeline"][0]["event"] == "workflow_started"


def test_workflow_packs(tmp_path, monkeypatch):
    _, wfs_dir, imported_dir, audit_dir = setup_workspace_monkeypatch(tmp_path, monkeypatch)

    # Create two schema-compliant workflows to pack
    wf1_dir = wfs_dir / "wf1"
    wf1_dir.mkdir(parents=True, exist_ok=True)
    (wf1_dir / "workflow.json").write_text(json.dumps({
        "schema_version": "1.0",
        "workflow_id": "wf1",
        "name": "WF 1",
        "description": "WF 1 Description",
        "pack_id": "test-pack",
        "version": "1.0.0",
        "steps": [{"step_id": "s1", "skill_id": "math_skill", "command": "add"}]
    }), encoding="utf-8")

    wf2_dir = wfs_dir / "wf2"
    wf2_dir.mkdir(parents=True, exist_ok=True)
    (wf2_dir / "workflow.json").write_text(json.dumps({
        "schema_version": "1.0",
        "workflow_id": "wf2",
        "name": "WF 2",
        "description": "WF 2 Description",
        "pack_id": "test-pack",
        "version": "1.0.0",
        "steps": [{"step_id": "s1", "skill_id": "string_skill", "command": "upper"}]
    }), encoding="utf-8")

    # Register them
    register_workflow(wf1_dir / "workflow.json")
    register_workflow(wf2_dir / "workflow.json")

    pack_path = tmp_path / "test.liuantworkflowpack"
    meta = {"name": "Test Workflow Pack", "version": "1.2.0", "description": "Pack of workflows"}

    # Export Pack
    exp_res = export_workflow_pack(["wf1", "wf2"], "test-pack", pack_path, meta)
    assert exp_res["status"] == "exported"

    # Validate Pack
    val_res = validate_workflow_pack(pack_path)
    assert val_res["status"] in ("passed", "warning")

    # Inspect Pack
    insp_res = inspect_workflow_pack(pack_path)
    assert insp_res["status"] == "ok"
    assert insp_res["pack_id"] == "test-pack"
    assert len(insp_res["workflows"]) == 2
    assert "math_skill" in insp_res["dependencies"]["required_skills"]

    # Import Pack
    imp_res = import_workflow_pack(pack_path, confirm=True)
    assert imp_res["status"] == "imported"
    assert (imported_dir / "wf1" / "workflow.json").exists()
    assert (imported_dir / "wf2" / "workflow.json").exists()


def test_backup_and_restore(tmp_path, monkeypatch):
    _, wfs_dir, imported_dir, audit_dir = setup_workspace_monkeypatch(tmp_path, monkeypatch)

    backups_dir = tmp_path / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    # Set mock setting in database
    setting_id = "test-setting"
    setting_row = {
        "id": setting_id,
        "value": "v1",
        "enabled": 1,
        "updated_at": "2026-05-20T04:00:00Z"
    }
    insert_record("settings", setting_row)

    bm = BackupManager()
    bm.backup_dir = backups_dir

    # Create Backup
    backup_file = backups_dir / "test_backup.liuantbackup"
    create_res = bm.create(output_path=backup_file, confirm=True)
    assert create_res["status"] == "created"
    assert backup_file.exists()

    # Validate Backup
    val_res = bm.validate(backup_file)
    assert val_res["status"] == "passed"

    # Inspect Backup
    insp_res = bm.inspect(backup_file)
    assert insp_res["status"] == "ok"
    assert insp_res["db_summary"]["settings"] >= 1

    # Modify setting in DB (update local configuration to newer version v2)
    setting_row_new = {
        "id": setting_id,
        "value": "v2",
        "enabled": 1,
        "updated_at": "2026-05-20T04:10:00Z"
    }
    insert_record("settings", setting_row_new)

    # Perform Restoration
    restore_res = bm.restore(backup_file, confirm=True)
    assert restore_res["status"] == "restored"

    # Verify that newer local config was not overwritten (preserved)
    local_row = get_record("settings", setting_id)
    assert local_row["value"] == "v2"

    # Verify safety gate rule: setting from backup would be disabled (enabled=0)
    new_setting_id = "restored-disabled-setting"
    new_setting_row = {
        "id": new_setting_id,
        "value": "some_value",
        "enabled": 1,
        "updated_at": "2026-05-20T03:00:00Z"
    }
    # Clean settings table and insert only in snapshot file
    delete_record("settings", setting_id)
    delete_record("settings", new_setting_id)

    # Make new backup containing new_setting_row
    insert_record("settings", new_setting_row)
    fresh_backup_file = backups_dir / "fresh_backup.liuantbackup"
    bm.create(output_path=fresh_backup_file, confirm=True)

    # Clear setting locally before restore
    delete_record("settings", new_setting_id)

    # Restore fresh backup
    bm.restore(fresh_backup_file, confirm=True)

    # Verify safety gate: enabled = 0
    restored_row = get_record("settings", new_setting_id)
    assert restored_row is not None
    assert restored_row["enabled"] == 0


def test_api_v270_endpoints(tmp_path, monkeypatch):
    try:
        from fastapi.testclient import TestClient
    except Exception:
        return

    _, wfs_dir, imported_dir, audit_dir = setup_workspace_monkeypatch(tmp_path, monkeypatch)
    from runtime.api.app import app
    client = TestClient(app)

    # 1. Create a workflow to export
    wf_id = "api-test-export-wf"
    src_dir = wfs_dir / wf_id
    src_dir.mkdir(parents=True, exist_ok=True)
    wf_data = {
        "schema_version": "1.0",
        "workflow_id": wf_id,
        "name": "API Test Workflow",
        "description": "API test workflow",
        "pack_id": "api_pack",
        "version": "1.0.0",
        "steps": [
            {
                "step_id": "step_1",
                "skill_id": "test_skill",
                "command": "run_command"
            }
        ]
    }
    (src_dir / "workflow.json").write_text(json.dumps(wf_data), encoding="utf-8")
    (src_dir / "README.md").write_text("# API Test Workflow", encoding="utf-8")
    register_workflow(src_dir / "workflow.json")

    # Test POST /api/skills/workflows/{workflow_id}/export
    archive_path = tmp_path / "api_test_wf.liuantworkflow"
    response = client.post(f"/api/skills/workflows/{wf_id}/export", json={"output_path": str(archive_path)})
    assert response.status_code == 200
    assert response.json()["status"] == "exported"

    # Test POST /api/skills/workflows/validate-file
    response = client.post("/api/skills/workflows/validate-file", json={"archive_path": str(archive_path)})
    assert response.status_code == 200
    assert response.json()["status"] in ("passed", "warning")

    # Test POST /api/skills/workflows/import
    dest_path = imported_dir / wf_id
    if dest_path.exists():
        shutil.rmtree(dest_path)
    response = client.post("/api/skills/workflows/import", json={"archive_path": str(archive_path), "confirm": True})
    assert response.status_code == 200
    assert response.json()["status"] == "imported"

    # Test POST /api/skills/workflows/packs/export
    pack_path = tmp_path / "api_test.liuantworkflowpack"
    response = client.post("/api/skills/workflows/packs/export", json={
        "workflow_ids": [wf_id],
        "pack_id": "api_pack",
        "output_path": str(pack_path),
        "metadata": {"name": "API Test Pack", "version": "1.0.0"}
    })
    assert response.status_code == 200
    assert response.json()["status"] == "exported"

    # Test POST /api/skills/workflows/packs/inspect
    response = client.post("/api/skills/workflows/packs/inspect", json={"archive_path": str(pack_path)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["pack_id"] == "api_pack"

    # Test POST /api/skills/workflows/packs/import
    response = client.post("/api/skills/workflows/packs/import", json={"archive_path": str(pack_path), "confirm": True})
    assert response.status_code == 200
    assert response.json()["status"] == "imported"

    # Setup database record for backup
    setting_id = "api-backup-setting"
    insert_record("settings", {"id": setting_id, "value": "api_val", "enabled": 1, "updated_at": "2026-05-20T04:00:00Z"})

    # Test Backup Validate/Inspect/Restore via API
    bm = BackupManager()
    bm.backup_dir = tmp_path / "backups"
    bm.backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = bm.backup_dir / "api_backup.liuantbackup"
    bm.create(output_path=backup_file, confirm=True)

    # Test POST /api/backup/validate
    response = client.post("/api/backup/validate", json={"file_path": str(backup_file)})
    assert response.status_code == 200
    assert response.json()["status"] == "passed"

    # Test POST /api/backup/inspect
    response = client.post("/api/backup/inspect", json={"file_path": str(backup_file)})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["db_summary"]["settings"] >= 1

    # Test POST /api/backup/restore
    # Modify local setting
    insert_record("settings", {"id": setting_id, "value": "api_val_new", "enabled": 1, "updated_at": "2026-05-20T04:10:00Z"})
    response = client.post("/api/backup/restore", json={"file_path": str(backup_file), "confirm": True})
    assert response.status_code == 200
    assert response.json()["status"] == "restored"

    # Test POST /api/skills/workflows/runs/{run_id}/export-report
    # Create audit directories
    from runtime.skills.workflow_audit import _load_runs, _save_runs
    runs = _load_runs()
    runs["runs"]["api-run-id"] = {
        "run_id": "api-run-id",
        "workflow_id": wf_id,
        "status": "completed",
        "created_at": "2026-05-20T04:00:00Z",
        "updated_at": "2026-05-20T04:00:01Z",
        "started_at": "2026-05-20T04:00:00Z",
        "completed_at": "2026-05-20T04:00:01Z",
        "duration_ms": 1000,
        "completed_steps": 1,
        "step_count": 1,
    }
    _save_runs(runs)

    response = client.post("/api/skills/workflows/runs/api-run-id/export-report", json={"format": "json"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Test GET /api/skills/workflows/runs/{run_id}/timeline
    response = client.get("/api/skills/workflows/runs/api-run-id/timeline")
    assert response.status_code == 200
    assert len(response.json()["timeline"]) > 0

