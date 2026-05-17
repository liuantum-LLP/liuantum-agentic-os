import json
import subprocess
import sys
from pathlib import Path

from runtime.config import SettingsManager
from runtime.release import ReleaseManager
from runtime.storage import ROOT


def test_desktop_status_handles_missing_tauri_gracefully():
    result = ReleaseManager().desktop_status()

    assert result["status"] in {"missing_project", "needs_dependency", "ready"}
    assert "setup_instructions" in result


def test_desktop_check_detects_dependency_requirements():
    result = ReleaseManager().desktop_check()

    assert result["check_status"] == "passed"
    assert result["status"] in {"missing_project", "needs_dependency", "ready"}


def test_release_manifest_generated():
    result = ReleaseManager().release_manifest()

    assert result["status"] == "created"
    assert Path(result["manifest_path"]).exists()


def test_release_manifest_includes_version():
    result = ReleaseManager().release_manifest()

    assert result["manifest"]["version"] == SettingsManager().get("app_version")["value"]
    assert result["manifest"]["app"] == "Liuant Agentic OS"


def test_checksum_command_handles_no_artifacts_gracefully():
    result = ReleaseManager().release_checksum()

    assert result["status"] in {"no_artifacts", "created"}
    assert Path(result["checksums_path"]).exists()


def test_signing_status_returns_unsigned_by_default():
    result = ReleaseManager().signing_status()

    assert result["signed"] is False
    assert result["notarized"] is False
    assert result["status"] == "unsigned"


def test_package_scripts_exist():
    for name in ("package_macos.sh", "package_linux.sh", "package_windows.ps1"):
        assert (ROOT / "installer" / name).exists()


def test_package_scripts_do_not_claim_signed_output():
    combined = "\n".join((ROOT / "installer" / name).read_text(encoding="utf-8") for name in ("package_macos.sh", "package_linux.sh", "package_windows.ps1"))

    assert "unsigned" in combined.lower()
    # Scripts should indicate signing is pending, not claimed, or requires separate configuration
    assert any(phrase in combined.lower() for phrase in ("not claimed", "unless", "remain pending", "unsigned build"))


def test_update_config_defaults_auto_update_disabled():
    SettingsManager().ensure_defaults()
    result = ReleaseManager().update_config()

    assert result["auto_update_enabled"] is False


def test_update_check_reads_local_manifest():
    result = ReleaseManager().update_check()

    assert result["network_used"] is False
    assert result["source"].endswith("release.json")


def test_release_page_api_status_route_works():
    from runtime.api.app import release_status

    result = release_status()

    assert result["version"]["app_version"] == SettingsManager().get("app_version")["value"]
    assert "desktop" in result
    assert "signing" in result


def test_desktop_cli_status_works():
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "desktop", "status"], capture_output=True, text=True, check=True)

    assert "tauri_project_exists" in result.stdout


def test_release_cli_manifest_works():
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "release", "manifest"], capture_output=True, text=True, check=True)

    assert "manifest_path" in result.stdout


def test_release_json_v052_shape():
    data = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))

    assert data["version"] == SettingsManager().get("app_version")["value"]
    assert data["channel"] in {"local-mvp", "open-source", "stable-open-source"}
