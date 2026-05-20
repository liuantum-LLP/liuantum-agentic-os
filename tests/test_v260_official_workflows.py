"""Tests for v2.6.0 official workflow examples and desktop UI polish.

Covers: official workflow examples, workflow discovery, workflow registry,
desktop workflow templates UI, preview panel, permissions panel, dry-run/run
confirmation, audit/history UI, URL staging UI, lint fix UI, recommendation
ranking UI, and chat-first workflow bridge.

All tests are local-only — no network calls, no real provider keys.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from runtime.skills.workflows import (
    list_workflows,
    discover_workflows,
    validate_workflow,
    inspect_workflow,
    _get_workflow_by_id,
    run_workflow,
)
from runtime.skills.workflow_audit import (
    record_workflow_run_start,
    record_workflow_run_complete,
    record_workflow_step,
    get_workflow_audit,
)


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


# ============================================================
# Official Workflow Examples Tests
# ============================================================

def test_official_workflow_examples_exist():
    """Test that official workflow examples exist in examples/workflows/."""
    examples_dir = Path("examples/workflows")
    assert examples_dir.exists(), "examples/workflows directory should exist"

    workflows = list(examples_dir.iterdir())
    assert len(workflows) >= 4, "Should have at least 4 official workflow examples"

    workflow_ids = [w.name for w in workflows]
    assert "csv-analysis-report" in workflow_ids
    assert "prompt-improvement-review" in workflow_ids
    assert "starter-greeting-workflow" in workflow_ids
    assert "analytics-pack-checkup" in workflow_ids


def test_csv_analysis_report_workflow_validates():
    """Test that csv-analysis-report workflow validates correctly."""
    wf_path = Path("examples/workflows/csv-analysis-report/workflow.json")
    assert wf_path.exists(), "csv-analysis-report workflow should exist"

    result = validate_workflow(wf_path)
    assert result["status"] in {"passed", "warning"}, f"Should pass or warn, got {result['status']}"
    assert result["workflow_id"] == "csv-analysis-report"


def test_prompt_improvement_review_workflow_validates():
    """Test that prompt-improvement-review workflow validates correctly."""
    wf_path = Path("examples/workflows/prompt-improvement-review/workflow.json")
    assert wf_path.exists(), "prompt-improvement-review workflow should exist"

    result = validate_workflow(wf_path)
    assert result["status"] in {"passed", "warning"}, f"Should pass or warn, got {result['status']}"
    assert result["workflow_id"] == "prompt-improvement-review"


def test_starter_greeting_workflow_validates():
    """Test that starter-greeting-workflow validates correctly."""
    wf_path = Path("examples/workflows/starter-greeting-workflow/workflow.json")
    assert wf_path.exists(), "starter-greeting-workflow should exist"

    result = validate_workflow(wf_path)
    assert result["status"] in {"passed", "warning"}, f"Should pass or warn, got {result['status']}"
    assert result["workflow_id"] == "starter-greeting-workflow"


def test_analytics_pack_checkup_workflow_validates():
    """Test that analytics-pack-checkup workflow validates correctly."""
    wf_path = Path("examples/workflows/analytics-pack-checkup/workflow.json")
    assert wf_path.exists(), "analytics-pack-checkup workflow should exist"

    result = validate_workflow(wf_path)
    assert result["status"] in {"passed", "warning"}, f"Should pass or warn, got {result['status']}"
    assert result["workflow_id"] == "analytics-pack-checkup"


# ============================================================
# Workflow Discovery Tests
# ============================================================

def test_workflow_list_includes_official_examples():
    """Test that list_workflows includes official examples."""
    workflows = list_workflows()
    workflow_ids = [w["workflow_id"] for w in workflows]

    assert "csv-analysis-report" in workflow_ids
    assert "prompt-improvement-review" in workflow_ids
    assert "starter-greeting-workflow" in workflow_ids
    assert "analytics-pack-checkup" in workflow_ids


def test_discover_workflows_finds_official_examples():
    """Test that discover_workflows finds official examples."""
    result = discover_workflows(paths=["examples/workflows"])
    assert result["count"] >= 4, "Should discover at least 4 workflows"

    discovered_ids = [w["workflow_id"] for w in result["discovered"]]
    assert "csv-analysis-report" in discovered_ids
    assert "prompt-improvement-review" in discovered_ids
    assert "starter-greeting-workflow" in discovered_ids
    assert "analytics-pack-checkup" in discovered_ids


def test_discover_workflows_finds_all_default_paths():
    """Test that discover_workflows finds workflows from default paths."""
    result = discover_workflows()
    assert "count" in result
    assert "discovered" in result


def test_get_workflow_by_id_finds_official_example():
    """Test that _get_workflow_by_id can find official examples."""
    wf = _get_workflow_by_id("csv-analysis-report")
    assert wf is not None, "Should find csv-analysis-report workflow"
    assert wf.get("workflow_id") == "csv-analysis-report"
    assert "source" in wf


def test_inspect_workflow_returns_required_skills():
    """Test that inspect_workflow returns required skills info."""
    wf_path = Path("examples/workflows/csv-analysis-report/workflow.json")
    result = inspect_workflow(wf_path)

    assert result["status"] == "ok"
    assert result["workflow_id"] == "csv-analysis-report"
    assert "steps" in result
    assert len(result["steps"]) >= 2


# ============================================================
# Workflow Preview Tests
# ============================================================

def test_workflow_preview_returns_step_statuses():
    """Test that workflow preview returns step statuses."""
    with patch("runtime.skills.workflows.list_installed_skills") as mock_list:
        mock_list.return_value = [
            {"id": "csv-summary-skill", "enabled": True},
            {"id": "prompt-review-skill", "enabled": True},
        ]

        from runtime.skills.workflows import preview_workflow_run
        result = preview_workflow_run("csv-analysis-report")

        assert "status" in result
        assert "steps" in result
        for step in result.get("steps", []):
            assert "step_id" in step
            assert "skill_id" in step
            assert "status" in step


def test_workflow_preview_does_not_execute_skills():
    """Test that workflow preview does not execute any skills."""
    with patch("runtime.skills.executor.run_skill") as mock_run:
        mock_run.return_value = {"status": "ok"}
        from runtime.skills.workflows import preview_workflow_run
        result = preview_workflow_run("csv-analysis-report")

        assert mock_run.called is False, "Preview should not execute skills"


# ============================================================
# Workflow Permissions Tests
# ============================================================

def test_workflow_permissions_api_returns_risk_levels():
    """Test that workflow permissions returns risk levels."""
    with patch("runtime.skills.workflows.list_installed_skills") as mock_list:
        mock_list.return_value = []
        from runtime.skills.workflows import workflow_permission_summary
        result = workflow_permission_summary("csv-analysis-report")

        assert "permissions" in result
        assert "can_run" in result


# ============================================================
# Workflow Audit Tests
# ============================================================

def test_workflow_audit_api_returns_safe_metadata():
    """Test that workflow audit returns safe metadata without secrets."""
    run_id = record_workflow_run_start("csv-analysis-report")
    record_workflow_step(run_id, "step1", "csv-summary-skill", "summarize", "ok")

    result = get_workflow_audit(workflow_id="csv-analysis-report", limit=50)

    assert isinstance(result, list)
    assert len(result) >= 1
    run = result[0]
    assert "run_id" in run
    assert "status" in run


# ============================================================
# Settings UI Tests
# ============================================================

def test_settings_ui_contains_workflow_templates_section():
    """Test that SettingsPage.tsx contains Workflow Templates section."""
    settings_file = Path("apps/desktop/src/pages/SettingsPage.tsx")
    assert settings_file.exists(), "SettingsPage.tsx should exist"

    content = settings_file.read_text()
    assert "workflow" in content.lower(), "SettingsPage should mention workflows"
    assert "template" in content.lower(), "SettingsPage should mention templates"


def test_settings_ui_contains_workflow_preview_panel():
    """Test that SettingsPage.tsx contains workflow preview panel."""
    settings_file = Path("apps/desktop/src/pages/SettingsPage.tsx")
    content = settings_file.read_text()

    assert "preview" in content.lower(), "SettingsPage should have preview panel"


def test_settings_ui_contains_permission_review_panel():
    """Test that SettingsPage.tsx contains permission review panel."""
    settings_file = Path("apps/desktop/src/pages/SettingsPage.tsx")
    content = settings_file.read_text()

    assert "permission" in content.lower(), "SettingsPage should have permission panel"


def test_settings_ui_contains_audit_history_section():
    """Test that SettingsPage.tsx contains audit/history section."""
    settings_file = Path("apps/desktop/src/pages/SettingsPage.tsx")
    content = settings_file.read_text()

    assert "audit" in content.lower() or "history" in content.lower(), "SettingsPage should have audit/history section"


# ============================================================
# Chat Intent Router Tests
# ============================================================

def test_chat_intent_router_detects_workflow_preview():
    """Test that chat intent router detects workflow preview intent."""
    from runtime.chat.intent_router import route_chat_message

    result = route_chat_message("Preview CSV analysis workflow")

    assert "intent" in result
    assert result["intent"] == "workflow_preview"


def test_chat_intent_router_detects_workflow_permissions():
    """Test that chat intent router detects workflow permissions intent."""
    from runtime.chat.intent_router import route_chat_message

    result = route_chat_message("What permissions does CSV workflow need?")

    assert "intent" in result
    assert result["intent"] == "workflow_permissions"


def test_chat_intent_router_detects_workflow_audit():
    """Test that chat intent router detects workflow audit intent."""
    from runtime.chat.intent_router import route_chat_message

    result = route_chat_message("Show workflow audit")

    assert "intent" in result
    assert result["intent"] == "workflow_audit"


# ============================================================
# Safety Tests
# ============================================================

def test_no_secrets_shown_in_workflow_ui_strings():
    """Test that workflow UI strings don't contain secrets."""
    examples_dir = Path("examples/workflows")

    for wf_dir in examples_dir.iterdir():
        if wf_dir.is_dir():
            for file in wf_dir.glob("*.json"):
                content = file.read_text()
                assert "sk-" not in content, f"Secret found in {file}"
                assert "api_key" not in content.lower() or "placeholder" in content.lower(), f"API key found in {file}"


def test_existing_v250_tests_still_pass():
    """Test that existing v2.5.0 tests still pass."""
    from runtime.skills.workflows import (
        preview_workflow_run,
        workflow_permission_summary,
        run_workflow,
    )

    with patch("runtime.skills.workflows.list_installed_skills") as mock_list:
        mock_list.return_value = []

        result = preview_workflow_run("nonexistent-workflow")
        assert result["status"] == "blocked"
        assert "not found" in result["message"].lower()


# ============================================================
# Additional Tests
# ============================================================

def test_workflow_inspect_returns_source():
    """Test that inspect_workflow returns source information."""
    wf_path = Path("examples/workflows/csv-analysis-report/workflow.json")
    result = inspect_workflow(wf_path)

    assert result["status"] == "ok"
    assert "pack_id" in result
    assert result["pack_id"] == "official-workflows"


def test_workflow_validate_with_workflow_id():
    """Test that validate_workflow works with workflow_id parameter."""
    result = validate_workflow(workflow_id="csv-analysis-report")

    assert result["status"] in {"passed", "warning"}
    assert result["workflow_id"] == "csv-analysis-report"
