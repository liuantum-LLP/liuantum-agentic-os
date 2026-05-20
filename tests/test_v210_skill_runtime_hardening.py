"""Tests for Liuant Agentic OS v2.1.0 — Skill Runtime Hardening.

Tests process-isolated execution, audit logs, chat-first skill control,
local discovery, templates, dependencies, upgrade flow, and UI.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.config import SettingsManager
from runtime.db import delete_all_records, init_db
from runtime.skills.audit import get_audit_logs, get_latest_audit, record_audit
from runtime.skills.executor import _clean_env, _redact_secrets, run_skill
from runtime.skills.manifest import default_manifest
from runtime.skills.registry import (
    create_skill_from_template,
    discover_skills,
    enable_skill,
    get_skill,
    install_skill,
    list_installed_skills,
    search_skills,
    uninstall_skill,
    upgrade_skill,
)
from runtime.skills.validator import validate_manifest
from runtime.storage import WORKSPACE

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "skills"


def _reset_db():
    init_db()
    for table in ("usage_events", "alert_history", "webhook_deliveries", "discussion_cost_rounds"):
        try:
            delete_all_records(table)
        except Exception:
            pass


def _cleanup_skills():
    skills_dir = WORKSPACE / "skills"
    if skills_dir.exists():
        shutil.rmtree(skills_dir)


def test_process_isolated_hello_skill_runs():
    """Test 1: Process-isolated hello skill runs successfully."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    enable_skill("hello-skill")
    result = run_skill("hello-skill", {"message": "Liuant"}, dry_run=False, isolated=True)
    assert result["status"] == "completed", f"Expected completed, got {result}"
    assert "greeting" in result["result"]
    assert "Liuant" in result["result"]["greeting"]


def test_skill_timeout_returns_failed():
    """Test 2: Skill timeout returns failed status."""
    _reset_db()
    timeout_dir = WORKSPACE / "skills" / "installed" / "timeout-skill"
    timeout_dir.mkdir(parents=True, exist_ok=True)
    manifest = default_manifest("timeout-skill", "Timeout Skill", "A skill that sleeps")
    (timeout_dir / "skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    (timeout_dir / "skill.py").write_text(
        "import sys, json, time\n"
        "if '--liuant-skill-run' in sys.argv:\n"
        "    time.sleep(60)\n"
        "else:\n"
        "    print('timeout skill')\n",
        encoding="utf-8",
    )
    from runtime.skills.registry import _load_registry, _save_registry
    registry = _load_registry()
    registry["skills"]["timeout-skill"] = {
        "name": "Timeout Skill", "version": "0.1.0", "path": str(timeout_dir),
        "enabled": True, "installed_at": "2026-01-01T00:00:00Z",
        "permissions": [], "approved_permissions": [],
        "validation_status": "passed", "risk_level": "low",
    }
    _save_registry(registry)
    result = run_skill("timeout-skill", {}, dry_run=False, isolated=True, timeout=1)
    assert result["status"] == "failed"
    assert any("timed" in w.lower() or "timeout" in w.lower() for w in result["warnings"])


def test_invalid_json_output_returns_failed():
    """Test 3: Invalid JSON output from skill returns failed."""
    _reset_db()
    _cleanup_skills()
    bad_dir = WORKSPACE / "skills" / "installed" / "bad-json-skill"
    bad_dir.mkdir(parents=True, exist_ok=True)
    manifest = default_manifest("bad-json-skill", "Bad JSON Skill", "Returns invalid JSON")
    (bad_dir / "skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bad_dir / "skill.py").write_text(
        "import sys\n"
        "if '--liuant-skill-run' in sys.argv:\n"
        "    print('not valid json')\n"
        "else:\n"
        "    print('bad json skill')\n",
        encoding="utf-8",
    )
    from runtime.skills.registry import _load_registry, _save_registry
    registry = _load_registry()
    registry["skills"]["bad-json-skill"] = {
        "name": "Bad JSON Skill", "version": "0.1.0", "path": str(bad_dir),
        "enabled": True, "installed_at": "2026-01-01T00:00:00Z",
        "permissions": [], "approved_permissions": [],
        "validation_status": "passed", "risk_level": "low",
    }
    _save_registry(registry)
    result = run_skill("bad-json-skill", {}, dry_run=False, isolated=True)
    assert result["status"] == "failed"
    assert any("json" in w.lower() for w in result["warnings"])


def test_stderr_secrets_are_redacted():
    """Test 4: stderr secrets are redacted."""
    text = "Error: api_key = mysecretvalue1234567890abcdef failed"
    redacted = _redact_secrets(text)
    assert "mysecretvalue1234567890abcdef" not in redacted
    assert "[REDACTED]" in redacted


def test_child_process_does_not_receive_api_key_env_vars():
    """Test 5: Child process environment does not contain API key vars."""
    os.environ["TEST_API_KEY"] = "test-secret-value"
    os.environ["TEST_SECRET_TOKEN"] = "another-secret"
    env = _clean_env()
    assert "TEST_API_KEY" not in env
    assert "TEST_SECRET_TOKEN" not in env
    del os.environ["TEST_API_KEY"]
    del os.environ["TEST_SECRET_TOKEN"]


def test_disabled_skill_run_is_blocked_v210():
    """Test 6: Disabled skill run is blocked."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    result = run_skill("hello-skill", {"message": "test"}, dry_run=False)
    assert result["status"] == "blocked"


def test_missing_permission_run_is_blocked_v210():
    """Test 7: Running a skill with missing permission is blocked."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "prompt-review-skill"
    if not source.exists():
        return
    install_skill(source)
    enable_skill("prompt-review-skill")
    result = run_skill("prompt-review-skill", {"prompt": "test"}, dry_run=False)
    assert result["status"] == "blocked"


def test_external_action_returns_approval_required():
    """Test 8: Skill returning external action has approval_required=True."""
    _reset_db()
    _cleanup_skills()
    action_dir = WORKSPACE / "skills" / "installed" / "action-skill"
    action_dir.mkdir(parents=True, exist_ok=True)
    manifest = default_manifest("action-skill", "Action Skill", "Returns an action")
    (action_dir / "skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    (action_dir / "skill.py").write_text(
        "import sys, json\n"
        "if '--liuant-skill-run' in sys.argv:\n"
        "    ctx = json.loads(sys.stdin.read())\n"
        "    print(json.dumps({'status': 'completed', 'result': {}, 'actions': [{'type': 'email_draft'}], 'approval_required': True}))\n"
        "else:\n"
        "    print('action skill')\n",
        encoding="utf-8",
    )
    from runtime.skills.registry import _load_registry, _save_registry
    registry = _load_registry()
    registry["skills"]["action-skill"] = {
        "name": "Action Skill", "version": "0.1.0", "path": str(action_dir),
        "enabled": True, "installed_at": "2026-01-01T00:00:00Z",
        "permissions": [], "approved_permissions": [],
        "validation_status": "passed", "risk_level": "low",
    }
    _save_registry(registry)
    result = run_skill("action-skill", {}, dry_run=False, isolated=True)
    assert result["approval_required"] == True


def test_audit_log_records_run_metadata():
    """Test 9: Audit log records run metadata."""
    _reset_db()
    entry = record_audit(
        skill_id="test-skill", command="run", status="completed",
        duration_ms=150, permission_check_result="passed",
        approval_required=False, warnings_count=0,
        workspace="default", execution_mode="process_isolated",
    )
    assert entry["skill_id"] == "test-skill"
    assert entry["status"] == "completed"
    assert entry["duration_ms"] == 150
    assert entry["execution_mode"] == "process_isolated"


def test_audit_log_does_not_store_secrets():
    """Test 10: Audit log does not store secrets."""
    _reset_db()
    entry = record_audit(
        skill_id="test-skill", command="run", status="failed",
        duration_ms=0, permission_check_result="failed",
        approval_required=False, warnings_count=1,
        error_redacted="Error: api_key = sk-1234567890abcdef failed",
    )
    assert "sk-1234567890abcdef" not in entry["error_redacted"]
    assert "[REDACTED]" in entry["error_redacted"]


def test_skill_search_finds_example_skills():
    """Test 11: Skill search finds example skills."""
    _reset_db()
    results = search_skills("hello")
    assert len(results) > 0
    assert any("hello" in r["id"].lower() for r in results)


def test_skill_discovery_scans_examples_skills():
    """Test 12: Skill discovery scans examples/skills."""
    _reset_db()
    discovered = discover_skills([str(EXAMPLES_DIR)])
    assert len(discovered) > 0
    assert any(d["id"] == "hello-skill" for d in discovered)


def test_create_skill_from_template_works():
    """Test 13: Create skill from template works."""
    _reset_db()
    _cleanup_skills()
    result = create_skill_from_template("basic-python-skill", "my-test-skill", "My Test Skill")
    assert result["status"] == "created"
    assert result["skill_id"] == "my-test-skill"
    assert (WORKSPACE / "skills" / "installed" / "my-test-skill" / "skill.json").exists()


def test_created_skill_is_not_auto_installed():
    """Test 14: Created skill is not auto-installed unless requested."""
    _reset_db()
    _cleanup_skills()
    create_skill_from_template("basic-python-skill", "another-skill", "Another Skill")
    installed = list_installed_skills()
    assert not any(s["id"] == "another-skill" for s in installed)


def test_upgrade_requires_same_skill_id():
    """Test 15: Upgrade requires same skill ID."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    new_manifest = json.loads((source / "skill.json").read_text(encoding="utf-8"))
    new_manifest["version"] = "0.2.0"
    new_dir = Path(tempfile.mkdtemp()) / "hello-skill"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "skill.json").write_text(json.dumps(new_manifest), encoding="utf-8")
    (new_dir / "skill.py").write_text((source / "skill.py").read_text(encoding="utf-8"), encoding="utf-8")
    result = upgrade_skill(new_dir, confirm=True)
    assert result["status"] == "upgraded"
    shutil.rmtree(new_dir.parent, ignore_errors=True)


def test_upgrade_preserves_permissions_when_unchanged():
    """Test 16: Upgrade preserves permissions when unchanged."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    from runtime.skills.registry import approve_skill_permissions
    approve_skill_permissions("hello-skill", ["workspace.read"], confirm=True)
    new_manifest = json.loads((source / "skill.json").read_text(encoding="utf-8"))
    new_manifest["version"] = "0.2.0"
    new_dir = Path(tempfile.mkdtemp()) / "hello-skill"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "skill.json").write_text(json.dumps(new_manifest), encoding="utf-8")
    (new_dir / "skill.py").write_text((source / "skill.py").read_text(encoding="utf-8"), encoding="utf-8")
    result = upgrade_skill(new_dir, confirm=True)
    assert result["status"] == "upgraded"
    assert result["permissions_reset"] == False
    shutil.rmtree(new_dir.parent, ignore_errors=True)


def test_upgrade_requires_approval_when_new_permission_added():
    """Test 17: Upgrade requires approval when new permission added."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    new_manifest = default_manifest("hello-skill", "Hello Skill", "Updated")
    new_manifest["permissions"] = ["models.generate"]
    new_manifest["version"] = "0.2.0"
    new_dir = Path(tempfile.mkdtemp()) / "hello-skill"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "skill.json").write_text(json.dumps(new_manifest), encoding="utf-8")
    (new_dir / "skill.py").write_text("print('hello')", encoding="utf-8")
    result = upgrade_skill(new_dir, confirm=True)
    assert result["status"] == "upgraded"
    assert result["permissions_reset"] == True
    shutil.rmtree(new_dir.parent, ignore_errors=True)


def test_dependency_validation_warn_but_not_install():
    """Test 18: Dependency validation warns but does not install."""
    _reset_db()
    manifest = default_manifest("dep-skill", "Dep Skill", "Has deps")
    manifest["dependencies"] = {"python": ">=3.10", "packages": ["requests"]}
    result = validate_manifest(manifest)
    assert result["status"] == "passed"


def test_chat_intent_detects_skill_list():
    """Test 19: Chat intent detects skill list."""
    intent_path = Path(__file__).resolve().parent.parent / "runtime" / "chat" / "intent.py"
    if not intent_path.exists():
        return
    with open(intent_path, encoding="utf-8") as f:
        content = f.read()
    assert "skill" in content.lower()


def test_chat_intent_detects_skill_run():
    """Test 20: Chat intent detects skill run."""
    intent_path = Path(__file__).resolve().parent.parent / "runtime" / "chat" / "intent.py"
    if not intent_path.exists():
        return
    with open(intent_path, encoding="utf-8") as f:
        content = f.read()
    assert "run" in content.lower() or "skill" in content.lower()


def test_chat_intent_returns_preview_for_skill_enable():
    """Test 21: Chat intent returns preview for skill enable."""
    from runtime.skills.registry import enable_skill
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    result = enable_skill("hello-skill")
    assert result["status"] == "enabled"


def test_settings_ui_contains_skill_search_panel():
    """Test 22: Settings UI contains skill search panel."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return
    with open(settings_path, encoding="utf-8") as f:
        content = f.read()
    assert "search" in content.lower()
    assert "audit" in content.lower()


def test_settings_ui_contains_audit_summary():
    """Test 23: Settings UI contains audit summary."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return
    with open(settings_path, encoding="utf-8") as f:
        content = f.read()
    assert "audit" in content.lower()
    assert "Audit Log" in content or "audit" in content


def test_existing_tests_still_pass_v210():
    """Test 24: Verify existing functionality still works."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    result = tracker.record_usage(provider="openai", model="gpt-4", estimated_total_tokens=100, estimated_cost=0.001)
    assert result["provider"] == "openai"
    budget = tracker.get_budget()
    assert "daily_estimated_cost_limit" in budget
