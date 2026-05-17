import json
import subprocess
import sys
import shutil
from pathlib import Path

from runtime.config import SettingsManager
from runtime.db import get_record, insert_record, list_records
from runtime.release import ReleaseManager
from runtime.storage import ROOT, WORKSPACE


def test_version_command_returns_app_version():
    from runtime.config import SettingsManager
    expected_version = SettingsManager().get("app_version")["value"]
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "version"], capture_output=True, text=True, check=True)

    assert expected_version in result.stdout
    assert "python_version" in result.stdout


def test_paths_command_returns_expected_paths():
    paths = ReleaseManager().paths()

    assert paths["app_root"] == str(ROOT)
    assert paths["workspace_path"] == str(WORKSPACE)
    assert paths["database_path"].endswith("liuant-test.db")


def test_repair_creates_missing_folders(tmp_path, monkeypatch):
    monkeypatch.setenv("LIUANT_DB_PATH", str(tmp_path / "db" / "liuant-test.db"))

    result = ReleaseManager().repair()

    assert result["status"] == "repaired"
    assert (WORKSPACE / "outputs" / "images").exists()
    assert (WORKSPACE / "logs").exists()


def test_repair_does_not_delete_existing_data():
    insert_record("settings", {"id": "custom-setting", "key": "custom-setting", "value": "keep-me", "created_at": "now", "updated_at": "now"})

    ReleaseManager().repair()

    assert get_record("settings", "custom-setting")["value"] == "keep-me"


def test_reset_requires_confirm():
    result = ReleaseManager().reset(confirm=False)

    assert result["status"] == "blocked"


def test_reset_creates_backup_first():
    SettingsManager().set("debug_mode", "true")

    result = ReleaseManager().reset(confirm=True)

    assert result["status"] == "reset"
    assert result["backup_id"]
    assert Path(result["backup_path"]).exists()


def test_update_check_works_with_local_release_metadata():
    result = ReleaseManager().update_check()

    assert result["network_used"] is False
    from runtime.config import SettingsManager; expected_version = SettingsManager().get("app_version")["value"]; assert result["latest_version"] == expected_version


def test_release_check_returns_structured_summary():
    result = ReleaseManager().release_check(run_tests=False)

    assert result["status"] == "passed"
    assert any(row["name"] == "tests" and row["status"] == "skipped" for row in result["checks"])


def test_installer_scripts_exist():
    expected = [
        "install_macos.sh",
        "install_linux.sh",
        "install_windows.ps1",
        "uninstall_macos.sh",
        "uninstall_linux.sh",
        "uninstall_windows.ps1",
        "README.md",
    ]

    for name in expected:
        assert (ROOT / "installer" / name).exists()


def test_installer_scripts_do_not_overwrite_env():
    text = (ROOT / "installer" / "install_macos.sh").read_text(encoding="utf-8")
    linux = (ROOT / "installer" / "install_linux.sh").read_text(encoding="utf-8")
    windows = (ROOT / "installer" / "install_windows.ps1").read_text(encoding="utf-8")

    assert "[ ! -f .env ]" in text
    assert "[ ! -f .env ]" in linux
    assert "-not (Test-Path \".env\")" in windows


def test_env_template_contains_names_only():
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "env", "template"], capture_output=True, text=True, check=True)

    assert "OPENAI_API_KEY" in result.stdout
    assert "sk-" not in result.stdout


def test_start_binds_localhost_by_default():
    result = ReleaseManager().start(port=8123, host="0.0.0.0")

    assert result["status"] == "blocked"
    assert result["host"] == "0.0.0.0"


def test_ui_check_handles_missing_pnpm_gracefully(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)

    result = ReleaseManager().ui("build")

    assert result["status"] == "missing_node_tooling"


def test_troubleshooting_output_redacts_secrets():
    insert_record("action_logs", {"id": "secret-log", "action_type": "x", "status": "error", "preview": {"api_key": "raw-secret-value"}, "created_at": "now"})

    result = ReleaseManager().troubleshoot()
    serialized = json.dumps(result)

    assert "raw-secret-value" not in serialized
    assert "[redacted]" in serialized


def test_logs_path_command_works():
    result = ReleaseManager().logs_path()

    assert result["status"] == "ok"
    assert result["logs_path"].endswith("workspace/logs")


def test_release_json_shape():
    metadata = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))

    assert metadata["version"] == SettingsManager().get("app_version")["value"]
    assert "windows" in metadata["supported_platforms"]
