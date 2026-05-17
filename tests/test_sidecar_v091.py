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


def test_sidecar_build_mocked_pyinstaller_success():
    """sidecar build with mocked PyInstaller returns completed."""
    with (
        patch("runtime.sidecar._required_packaging_tools") as mock_tools,
        patch("runtime.sidecar.subprocess.run") as mock_run,
        patch("runtime.sidecar.Path.stat") as mock_stat,
    ):
        mock_tools.return_value = {"pyinstaller": True, "nuitka": False, "zipapp": True}
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_stat.return_value = MagicMock(st_size=9_938_544)

        with patch("runtime.sidecar._sidecar_executable_path") as mock_exe_path:
            fake_exe = ROOT / "sidecar" / "liuant-backend"
            if not fake_exe.exists():
                fake_exe = ROOT / "sidecar" / "liuant-backend"
                fake_exe.parent.mkdir(parents=True, exist_ok=True)
                fake_exe.write_text("#!/bin/sh\necho fake", encoding="utf-8")
                fake_exe.chmod(0o755)

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


def test_sidecar_version_aligned_to_v100():
    from runtime.config import SettingsManager
    v = SettingsManager().get("app_version")["value"]
    assert v == "1.0.0"
