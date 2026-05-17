from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_sidecar_status_reports_unavailable_by_default():
    result = sidecar_status()
    assert result["status"] in ("available", "unavailable")
    # In CI/default: should be unavailable (no executable built)
    if result["status"] == "unavailable":
        assert result["executable"] is None
        assert "sidecar build" in result["message"].lower()


def test_sidecar_build_reports_no_tool():
    result = sidecar_build(confirm=False)
    assert result["status"] == "blocked"
    assert result["message"]


def test_sidecar_build_no_packaging_tool():
    with patch("runtime.sidecar._required_packaging_tools") as mock_tools:
        mock_tools.return_value = {"pyinstaller": False, "nuitka": False, "zipapp": True}
        result = sidecar_build(confirm=True)
        assert result["status"] == "dependency_missing"
        assert "pyinstaller" in result["message"].lower() or "nuitka" in result["message"].lower()


def test_sidecar_run_refuses_non_localhost():
    result = sidecar_run(host="0.0.0.0")
    assert result["status"] == "blocked"
    assert "localhost" in result["message"].lower()


def test_sidecar_run_no_executable():
    with patch("runtime.sidecar._sidecar_executable_path") as mock_exe:
        mock_exe.return_value = None
        result = sidecar_run(host="127.0.0.1", port=8765)
        assert result["status"] == "unavailable"
        assert "build" in result["message"].lower()


def test_sidecar_check_no_executable():
    with patch("runtime.sidecar._sidecar_executable_path") as mock_exe:
        mock_exe.return_value = None
        result = sidecar_check()
        assert result["status"] == "unavailable"
        assert result["executable"] is None


def test_sidecar_stop_not_running():
    if SIDECAR_STATUS_PATH.exists():
        SIDECAR_STATUS_PATH.unlink()
    result = sidecar_stop(confirm=True)
    assert result["status"] in ("not_running", "stopped")


def test_sidecar_stop_requires_confirm():
    result = sidecar_stop(confirm=False)
    assert result["status"] == "blocked"


def test_bundled_sidecar_mode_reports_not_available():
    result = ReleaseManager().set_desktop_backend_mode("bundled_sidecar")
    assert result["status"] in ("sidecar_not_available", "updated")
    if result["status"] == "sidecar_not_available":
        assert "sidecar" in result["message"].lower()


def test_external_backend_mode_still_works():
    result = ReleaseManager().set_desktop_backend_mode("external_backend")
    assert result["status"] == "updated"
    assert result["mode"] == "external_backend"


def test_managed_backend_mode_still_works():
    result = ReleaseManager().set_desktop_backend_mode("managed_backend")
    assert result["status"] == "updated"
    assert result["mode"] == "managed_backend"


def test_desktop_ui_backend_settings_include_sidecar():
    """Desktop UI BackendSettings mentions sidecar."""
    from pathlib import Path as P
    ui = (ROOT / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
    assert "bundled_sidecar" in ui
    assert "sidecar status" in ui.lower() or "./liuant sidecar" in ui


def test_docs_explain_sidecar_build():
    docs = [
        ROOT / "docs" / "SIDECAR_BACKEND.md",
        ROOT / "docs" / "INSTALLATION.md",
        ROOT / "docs" / "DESKTOP_PACKAGING.md",
    ]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        assert "sidecar build" in text.lower() or "sidecar backend" in text.lower()


def test_no_secrets_in_sidecar_status():
    result = sidecar_status()
    output = json.dumps(result)
    assert "sk-" not in output
    assert "-----BEGIN" not in output
    assert result.get("status") in ("available", "unavailable")


def test_sidecar_cli_commands_registered():
    """CLI has sidecar area with expected subcommands."""
    text = (ROOT / "cli" / "liuant.py").read_text(encoding="utf-8")
    assert "sidecar" in text
    assert "sidecar_status" in text
    assert "sidecar_build" in text
    assert "sidecar_check" in text
    assert "sidecar_run" in text
    assert "sidecar_stop" in text
