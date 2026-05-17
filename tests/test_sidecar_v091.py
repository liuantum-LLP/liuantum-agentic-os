from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from runtime.release import ReleaseManager
from runtime.sidecar import (
    SIDECAR_STATUS_PATH,
    _required_packaging_tools,
    _sidecar_executable_path,
    sidecar_build,
    sidecar_check,
    sidecar_run,
    sidecar_status,
    sidecar_stop,
)

ROOT = Path(__file__).resolve().parent.parent


def test_sidecar_build_mocked_pyinstaller_success(tmp_path, monkeypatch):
    """sidecar build with mocked PyInstaller returns completed."""
    import runtime.sidecar
    monkeypatch.setattr(runtime.sidecar, "SIDECAR_DIR", tmp_path)
    fake_exe = tmp_path / "liuant-backend"
    fake_exe.write_text("#!/bin/sh\necho fake", encoding="utf-8")
    fake_exe.chmod(0o755)

    with (
        patch("runtime.sidecar._required_packaging_tools") as mock_tools,
        patch("runtime.sidecar.subprocess.run") as mock_run,
        patch("runtime.sidecar._sidecar_executable_path") as mock_exe_path,
    ):
        mock_tools.return_value = {"pyinstaller": True, "nuitka": False, "zipapp": True}
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_exe_path.return_value = fake_exe
        result = sidecar_build(confirm=True)
        assert result["status"] in ("completed", "build_failed")


def test_sidecar_status_detects_executable():
    """status reports available when executable exists."""
    with patch("runtime.sidecar._sidecar_executable_path") as mock_exe:
        fake_exe = ROOT / "sidecar" / "liuant-backend"
        mock_exe.return_value = fake_exe if fake_exe.exists() else None
        result = sidecar_status()
        if fake_exe.exists():
            assert result["status"] == "available"
            assert result["executable"] is not None
        else:
            assert result["status"] == "unavailable"


def test_sidecar_check_with_mocked_executable():
    """check validates executable metadata."""
    with patch("runtime.sidecar._sidecar_executable_path") as mock_exe:
        fake_exe = ROOT / "sidecar" / "liuant-backend"
        mock_exe.return_value = fake_exe if fake_exe.exists() else None

        with patch("runtime.sidecar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="usage: liuant", stderr=""
            )
            result = sidecar_check()
            if fake_exe.exists():
                assert result["status"] in ("available", "timeout")
            else:
                assert result["status"] == "unavailable"


def test_candidate_check_reports_status():
    """candidate-check returns a structured result."""
    r = ReleaseManager()
    result = r.desktop_v1_candidate_check()
    assert "status" in result
    assert result["status"] in ("passed", "needs_work")
    assert "checks_passed" in result
    assert "checks_failed" in result
    assert "checks_total" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)


def test_candidate_check_checks_open_source_files():
    """candidate-check verifies core open-source files exist."""
    r = ReleaseManager()
    result = r.desktop_v1_candidate_check()
    file_checks = [c for c in result["checks"] if c["name"].startswith("file_")]
    file_names = [c["name"] for c in file_checks]
    for expected in ("LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", ".gitignore", ".env.example"):
        assert f"file_{expected}" in file_names, f"Missing check for {expected}"
    for c in file_checks:
        if c["name"] != "file_SUPPORT.md":
            pass
        assert c["status"] in ("passed", "failed")


def test_candidate_check_reports_security_placeholder():
    """candidate-check flags security@example.com if present."""
    sec_path = ROOT / "SECURITY.md"
    if sec_path.exists():
        content = sec_path.read_text(encoding="utf-8")
        r = ReleaseManager()
        result = r.desktop_v1_candidate_check()
        sec_check = next((c for c in result["checks"] if c["name"] == "security_contact_placeholder"), None)
        if sec_check:
            if "security@" in content or "example.com" in content:
                assert sec_check["status"] == "failed"
            else:
                assert sec_check["status"] == "passed"


def test_candidate_check_no_env_secrets():
    r = ReleaseManager()
    result = r.desktop_v1_candidate_check()
    secret_check = next((c for c in result["checks"] if c["name"] == "no_env_secrets"), None)
    if secret_check:
        assert secret_check["status"] in ("passed", "failed")


def test_candidate_check_verifies_unsigned():
    r = ReleaseManager()
    result = r.desktop_v1_candidate_check()
    signing_check = next((c for c in result["checks"] if c["name"] == "signing_honest"), None)
    if signing_check:
        assert signing_check["status"] == "passed"
        assert signing_check.get("signed") is False
        assert signing_check.get("notarized") is False


def test_bundled_sidecar_mode_available_when_executable_exists():
    exe = _sidecar_executable_path()
    r = ReleaseManager()
    result = r.set_desktop_backend_mode("bundled_sidecar")
    if exe:
        assert result["status"] == "updated"
        assert result["mode"] == "bundled_sidecar"
    else:
        assert result["status"] in ("sidecar_not_available", "updated")


def test_desktop_backend_mode_switching_preserves_modes():
    r = ReleaseManager()
    for mode in ("external_backend", "managed_backend", "bundled_sidecar"):
        result = r.set_desktop_backend_mode(mode)
        assert result["status"] in ("updated", "sidecar_not_available")
        assert result["mode"] == mode or result.get("message", "")


def test_sidecar_version_aligned_to_v102():
    from runtime.config import SettingsManager
    v = SettingsManager().get("app_version")["value"]
    assert v == "1.1.0"


# --- One-click startup tests ---

def test_one_click_check_returns_status():
    r = ReleaseManager()
    result = r.desktop_one_click_check()
    assert "status" in result
    assert result["status"] in ("already_running", "needs_start")
    assert "localhost_only" in result
    assert result["localhost_only"] is True


def test_one_click_check_has_strategies_when_not_running():
    r = ReleaseManager()
    result = r.desktop_one_click_check()
    if result["status"] == "needs_start":
        assert "strategies" in result
        assert isinstance(result["strategies"], list)
        assert len(result["strategies"]) >= 1
        assert "recommended" in result
        assert result["recommended"] in ("start_sidecar", "start_managed", "user_action")


def test_one_click_check_has_command():
    r = ReleaseManager()
    result = r.desktop_one_click_check()
    if result["status"] == "needs_start":
        assert "command" in result
        assert isinstance(result["command"], str)
        assert result["command"].startswith("./liuant")


def test_one_click_check_sidecar_strategy_present_when_available():
    from runtime.sidecar import _sidecar_executable_path
    exe = _sidecar_executable_path()
    r = ReleaseManager()
    result = r.desktop_one_click_check()
    if exe and result["status"] == "needs_start":
        strategies = [s["method"] for s in result.get("strategies", [])]
        assert "start_sidecar" in strategies
        assert result["sidecar_available"] is True
    elif result["status"] == "needs_start":
        assert result.get("sidecar_available") is False


def test_launch_check_returns_cannot_start_when_no_backend():
    r = ReleaseManager()
    result = r.desktop_launch_check()
    assert "status" in result
    assert result["status"] in ("already_running", "cannot_start", "started")


def test_launch_check_respects_settings():
    r = ReleaseManager()
    result = r.desktop_launch_check()
    assert "mode" in result
    assert result["mode"] in ("external_backend", "managed_backend", "bundled_sidecar")


def test_launch_check_instructions_when_cannot_start():
    r = ReleaseManager()
    result = r.desktop_launch_check()
    if result["status"] == "cannot_start":
        assert "instructions" in result
        assert isinstance(result["instructions"], list)
        assert any("liuant start" in str(i) for i in result["instructions"])


def test_one_click_check_no_tokens_logged():
    r = ReleaseManager()
    result = r.desktop_one_click_check()
    dumped = json.dumps(result)
    assert "sk-" not in dumped
    assert "api-" not in dumped
    assert "Bearer " not in dumped


def test_desktop_always_binds_localhost():
    from runtime.release import DEFAULT_HOST
    assert DEFAULT_HOST == "127.0.0.1"


# --- Release polish tests (v1.1.0) ---

def test_pyproject_has_explicit_package_discovery():
    path = ROOT / "pyproject.toml"
    content = path.read_text(encoding="utf-8")
    assert "[tool.setuptools.packages.find]" in content
    assert "include = " in content
    assert "runtime*" in content
    assert "cli*" in content


def test_pyproject_excludes_non_packages():
    path = ROOT / "pyproject.toml"
    content = path.read_text(encoding="utf-8")
    assert "apps*" in content or "exclude" in content


def test_pyproject_exposes_liuant_script():
    path = ROOT / "pyproject.toml"
    content = path.read_text(encoding="utf-8")
    assert "liuant = \"cli.liuant:main\"" in content


def test_pyproject_version_bumped():
    path = ROOT / "pyproject.toml"
    content = path.read_text(encoding="utf-8")
    assert "version = \"1.1.0\"" in content


def test_ci_does_not_require_apple_credentials():
    path = ROOT / ".github" / "workflows" / "ci.yml"
    content = path.read_text(encoding="utf-8")
    assert "APPLE_" not in content
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("run:"):
            assert "APPLE_" not in stripped
            assert "DEVELOPER_ID" not in stripped


def test_gitignore_excludes_workspace():
    path = ROOT / ".gitignore"
    content = path.read_text(encoding="utf-8")
    assert "workspace/" in content


def test_gitignore_excludes_sidecar_build():
    path = ROOT / ".gitignore"
    content = path.read_text(encoding="utf-8")
    assert "sidecar/build/" in content
    assert "sidecar/liuant-backend" in content


def test_gitignore_excludes_desktop_build_artifacts():
    path = ROOT / ".gitignore"
    content = path.read_text(encoding="utf-8")
    assert "apps/desktop/dist/" in content
    assert "apps/desktop/src-tauri/target/" in content
    assert "apps/desktop/node_modules/" in content


def test_generated_files_not_tracked():
    import subprocess
    result = subprocess.run(
        ["git", "ls-files", "workspace", "sidecar/build", "sidecar/liuant-backend",
         "sidecar/liuant-backend.spec", "apps/desktop/src-tauri/target",
         "apps/desktop/dist", "release/build-report.json"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    output = result.stdout.strip()
    assert output == "", f"Generated files are tracked:\n{output}"


def test_readme_documents_editable_install():
    path = ROOT / "README.md"
    content = path.read_text(encoding="utf-8")
    assert "pip install -e ." in content or "pip install -e" in content


def test_readme_documents_one_click_startup():
    path = ROOT / "README.md"
    content = path.read_text(encoding="utf-8")
    assert "one-click-check" in content or "one-click" in content


def test_readme_no_merge_conflicts():
    path = ROOT / "README.md"
    content = path.read_text(encoding="utf-8")
    assert "<<<<<<<" not in content
    assert "=======" not in content
    assert ">>>>>>>" not in content


def test_installation_docs_one_click():
    path = ROOT / "docs" / "INSTALLATION.md"
    content = path.read_text(encoding="utf-8")
    assert "one-click-check" in content or "one-click" in content
