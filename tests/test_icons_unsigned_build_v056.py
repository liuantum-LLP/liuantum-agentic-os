from __future__ import annotations

from pathlib import Path

from runtime.release import ReleaseManager
from runtime.storage import ROOT


SCRIPTS = ROOT / "scripts"
ICONS = ROOT / "apps" / "desktop" / "src-tauri" / "icons"


def test_icon_generation_script_exists():
    script = SCRIPTS / "generate_icons.py"

    assert script.exists()
    assert "offline" in script.read_text(encoding="utf-8").lower()


def test_required_png_icon_files_are_generated_or_reported_honestly():
    result = ReleaseManager().icons_check()

    assert result["status"] in {"complete", "partial", "missing"}
    assert result["png_required_count"] == 13
    if result["status"] == "complete":
        assert not result["missing"]
    else:
        assert result["missing"]
    for name in result["required"]:
        if name.endswith(".png") and name not in result["missing"]:
            assert (ICONS / name).exists()


def test_icons_check_reports_unsupported_formats_honestly():
    result = ReleaseManager().icons_check()

    assert "unsupported" in result
    for item in result["unsupported"]:
        assert item["reason"] == "missing_tool"


def test_build_guide_command_returns_os_specific_steps():
    result = ReleaseManager().build_guide()

    assert result["status"] == "ok"
    assert result["platform"]
    assert result["steps"]
    assert any("Rust" in step or "rust" in step for step in result["steps"])


def test_build_helper_scripts_exist():
    for name in ("build_desktop_macos.sh", "build_desktop_linux.sh", "build_desktop_windows.ps1"):
        assert (SCRIPTS / name).exists(), name


def test_build_helper_scripts_do_not_use_sudo_by_default():
    for name in ("build_desktop_macos.sh", "build_desktop_linux.sh", "build_desktop_windows.ps1"):
        text = (SCRIPTS / name).read_text(encoding="utf-8").lower()
        assert "sudo " not in text
        assert "does not" in text


def test_build_report_handles_missing_report():
    path = ROOT / "release" / "build-report.json"
    if path.exists():
        path.unlink()

    result = ReleaseManager().build_report()

    assert result["status"] == "no_report"
    assert result["build_report_path"].endswith("release/build-report.json")


def test_unsigned_artifacts_reports_frontend_only_state_correctly():
    result = ReleaseManager().unsigned_artifacts()

    assert result["status"] in {"no_native_artifacts", "unsigned_artifacts_found"}
    assert result["signed"] is False
    assert result["notarized"] is False
    for artifact in result["native_artifacts"]:
        assert Path(artifact["path"]).exists()
        assert artifact["artifact_type"] == "native"


def test_verify_artifacts_handles_no_native_artifacts_safely():
    result = ReleaseManager().verify_artifacts()

    assert result["status"] in {"no_native_artifacts", "verified"}
    assert result["signed"] is False
    assert result["notarized"] is False
    for artifact in result["verified"]:
        assert artifact["verified"] is True


def test_release_manifest_includes_icon_status():
    result = ReleaseManager().release_manifest()
    desktop = result["manifest"]["desktop"]

    assert "icon_status" in desktop
    assert desktop["icon_status"]["status"] in {"complete", "partial", "missing"}
    assert "frontend_bundle_only" in desktop


def test_release_page_mentions_icon_build_report_and_unsigned_states():
    settings_page = (ROOT / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "Icon" in settings_page
    assert "Signed" in settings_page
    assert "Notarized" in settings_page
    assert "false" in settings_page
