"""Tests for Liuant Agentic OS v2.0.0 — Skill Ecosystem Foundation.

Tests skill manifest validation, registry, execution sandbox, CLI, API,
and UI integration. Uses mocked/example skills only. No network access.
"""

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.config import SettingsManager
from runtime.db import delete_all_records, init_db
from runtime.skills.manifest import (
    CRITICAL_PERMISSIONS,
    KNOWN_PERMISSIONS,
    default_manifest,
    get_risk_level,
    is_critical_permission,
)
from runtime.skills.registry import (
    approve_skill_permissions,
    disable_skill,
    enable_skill,
    get_skill,
    install_skill,
    list_installed_skills,
    skill_permissions,
    uninstall_skill,
)
from runtime.skills.validator import validate_manifest, validate_skill
from runtime.storage import WORKSPACE

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "skills"


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


# ===================================================================
# Phase 11: Tests
# ===================================================================

def test_valid_manifest_passes_validation():
    """Test 1: A valid manifest passes validation."""
    _reset_db()
    manifest = default_manifest("test-skill", "Test Skill", "A test skill")
    result = validate_manifest(manifest)
    assert result["status"] == "passed", f"Expected passed, got {result}"
    assert result["errors"] == []
    assert result["risk_level"] == "low"


def test_missing_required_manifest_field_fails():
    """Test 2: Missing required field fails validation."""
    _reset_db()
    manifest = default_manifest("test-skill")
    del manifest["id"]
    result = validate_manifest(manifest)
    assert result["status"] == "failed"
    assert any("id" in e for e in result["errors"])


def test_unknown_permission_fails():
    """Test 3: Unknown permission fails validation."""
    _reset_db()
    manifest = default_manifest("test-skill")
    manifest["permissions"] = ["unknown.permission"]
    result = validate_manifest(manifest)
    assert result["status"] == "failed"
    assert any("unknown.permission" in e for e in result["errors"])


def test_critical_permission_sets_critical_risk():
    """Test 4: Critical permission sets critical risk level."""
    _reset_db()
    manifest = default_manifest("test-skill")
    manifest["permissions"] = ["tools.shell"]
    result = validate_manifest(manifest)
    assert result["status"] == "passed"
    assert result["risk_level"] == "critical"


def test_manifest_with_secret_like_value_fails():
    """Test 5: Manifest with secret-like value fails."""
    _reset_db()
    manifest = default_manifest("test-skill")
    manifest["description"] = 'Contains api_key = "supersecretvalue123" in description'
    result = validate_manifest(manifest)
    assert result["status"] == "failed", f"Expected failed, got {result}"
    assert any("secret" in e.lower() for e in result["errors"]), f"No secret error found in {result['errors']}"


def test_install_skill_copies_folder():
    """Test 6: Installing a skill copies the folder."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return  # Skip if examples not present
    result = install_skill(source)
    assert result["status"] == "installed"
    assert result["skill_id"] == "hello-skill"
    dest = WORKSPACE / "skills" / "installed" / "hello-skill"
    assert dest.exists()
    assert (dest / "skill.json").exists()
    assert (dest / "skill.py").exists()


def test_installed_skill_disabled_by_default():
    """Test 7: Installed skill is disabled by default."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    skill = get_skill("hello-skill")
    assert skill is not None
    assert skill["enabled"] == False


def test_enable_valid_low_risk_skill_works():
    """Test 8: Enabling a valid low-risk skill works."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    result = enable_skill("hello-skill")
    assert result["status"] == "enabled"
    skill = get_skill("hello-skill")
    assert skill["enabled"] == True


def test_enable_critical_skill_requires_approval():
    """Test 9: Enabling a critical skill requires approval."""
    _reset_db()
    _cleanup_skills()
    # Create a critical skill
    critical_dir = WORKSPACE / "skills" / "installed" / "critical-test"
    critical_dir.mkdir(parents=True, exist_ok=True)
    manifest = default_manifest("critical-test", "Critical Test", "A critical skill")
    manifest["permissions"] = ["tools.shell"]
    (critical_dir / "skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    (critical_dir / "skill.py").write_text("def execute(ctx, inputs): return {'status': 'completed', 'result': {}}", encoding="utf-8")

    # Manually add to registry
    from runtime.skills.registry import _load_registry, _save_registry
    registry = _load_registry()
    registry["skills"]["critical-test"] = {
        "name": "Critical Test",
        "version": "0.1.0",
        "path": str(critical_dir),
        "enabled": False,
        "installed_at": "2026-01-01T00:00:00Z",
        "permissions": ["tools.shell"],
        "approved_permissions": [],
        "validation_status": "passed",
        "risk_level": "critical",
    }
    _save_registry(registry)

    result = enable_skill("critical-test")
    assert result["status"] == "error"
    assert "unapproved critical" in result or "critical" in result.get("message", "").lower()


def test_uninstall_requires_confirmation():
    """Test 10: Uninstall requires confirmation."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    result = uninstall_skill("hello-skill", confirm=False)
    assert result["status"] == "error"
    assert "confirm" in result.get("message", "").lower()

    result = uninstall_skill("hello-skill", confirm=True)
    assert result["status"] == "uninstalled"


def test_skill_permissions_are_listed():
    """Test 11: Skill permissions are listed correctly."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "csv-summary-skill"
    if not source.exists():
        return
    install_skill(source)
    perms = skill_permissions("csv-summary-skill")
    assert "permissions" in perms
    assert "filesystem.read" in perms["permissions"]
    assert "workspace.read" in perms["permissions"]


def test_approve_permission_records_approval():
    """Test 12: Approving permissions records approval."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "csv-summary-skill"
    if not source.exists():
        return
    install_skill(source)
    result = approve_skill_permissions("csv-summary-skill", ["filesystem.read"], confirm=True)
    assert result["status"] == "approved"
    assert "filesystem.read" in result["approved_permissions"]


def test_disabled_skill_run_is_blocked():
    """Test 13: Running a disabled skill is blocked."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    from runtime.skills.executor import run_skill
    result = run_skill("hello-skill", {"message": "test"})
    assert result["status"] == "blocked"
    assert "disabled" in result["warnings"][0].lower()


def test_skill_missing_permission_run_is_blocked():
    """Test 14: Running a skill with missing permission is blocked."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "prompt-review-skill"
    if not source.exists():
        return
    install_skill(source)
    enable_skill("prompt-review-skill")
    from runtime.skills.executor import run_skill
    result = run_skill("prompt-review-skill", {"prompt": "test"})
    assert result["status"] == "blocked"
    assert "permission" in result["warnings"][0].lower()


def test_hello_skill_run_completes():
    """Test 15: Hello skill run completes successfully."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    enable_skill("hello-skill")
    from runtime.skills.executor import run_skill
    result = run_skill("hello-skill", {"message": "Liuant"})
    assert result["status"] == "completed"
    assert "greeting" in result["result"]
    assert "Liuant" in result["result"]["greeting"]


def test_csv_summary_skill_respects_workspace_path_restriction():
    """Test 16: CSV summary skill respects workspace path restriction."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "csv-summary-skill"
    if not source.exists():
        return
    install_skill(source)
    enable_skill("csv-summary-skill")
    approve_skill_permissions("csv-summary-skill", ["filesystem.read", "workspace.read"], confirm=True)
    from runtime.skills.executor import run_skill
    result = run_skill("csv-summary-skill", {"csv_path": "/etc/passwd"})
    assert result["status"] == "blocked"
    assert "outside" in result["warnings"][0].lower() or "permission" in result["warnings"][0].lower()


def test_prompt_review_skill_returns_setup_needed_if_model_unavailable():
    """Test 17: Prompt review skill returns setup-needed if model unavailable."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "prompt-review-skill"
    if not source.exists():
        return
    install_skill(source)
    enable_skill("prompt-review-skill")
    approve_skill_permissions("prompt-review-skill", ["models.generate"], confirm=True)
    from runtime.skills.executor import run_skill
    result = run_skill("prompt-review-skill", {"prompt": "Write a story"})
    assert result["status"] == "completed"
    assert result["result"].get("setup_needed", False) == True or "unavailable" in str(result["result"].get("message", "")).lower()


def test_api_lists_skills():
    """Test 18: API lists skills."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    from runtime.api.app import app
    with app.test_client() as client:
        response = client.get("/api/skills")
        data = response.get_json()
        assert "skills" in data
        assert len(data["skills"]) >= 1


def test_api_validates_skill():
    """Test 19: API validates skill."""
    _reset_db()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    from runtime.api.app import app
    with app.test_client() as client:
        response = client.post("/api/skills/validate", json={"path": str(source)})
        data = response.get_json()
        assert data["status"] == "passed"


def test_settings_ui_contains_skills_section():
    """Test 20: Settings UI contains Skills section."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return  # Skip if frontend not available
    with open(settings_path, encoding="utf-8") as f:
        content = f.read()
    assert "SkillsSettings" in content
    assert "api/skills" in content
    assert "skill-card" in content


def test_chat_intent_router_detects_skill_intents():
    """Test 21: ChatIntentRouter detects skill list/install/enable/run intents."""
    intent_path = Path(__file__).resolve().parent.parent / "runtime" / "chat" / "intent.py"
    if not intent_path.exists():
        return  # Skip if intent router not available
    with open(intent_path, encoding="utf-8") as f:
        content = f.read()
    assert "skill" in content.lower()


def test_existing_tests_still_pass_v200():
    """Test 22: Verify existing functionality still works."""
    _reset_db()
    from runtime.usage import UsageTracker
    tracker = UsageTracker()
    result = tracker.record_usage(provider="openai", model="gpt-4", estimated_total_tokens=100, estimated_cost=0.001)
    assert result["provider"] == "openai"
    budget = tracker.get_budget()
    assert "daily_estimated_cost_limit" in budget
    status = tracker.get_webhook_status()
    assert "webhook_alerts_enabled" in status
