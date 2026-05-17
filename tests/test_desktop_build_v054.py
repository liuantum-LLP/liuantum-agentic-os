import json
import shutil
from pathlib import Path

from runtime.config import SettingsManager
from runtime.release import ReleaseManager
from runtime.storage import ROOT


DESKTOP = ROOT / "apps" / "desktop"


def test_package_json_includes_build_and_tauri_scripts():
    data = json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))

    for script in ("typecheck", "build", "tauri", "tauri:dev", "tauri:build"):
        assert script in data["scripts"]


def test_api_client_does_not_log_tokens():
    client = (DESKTOP / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert "console.log" not in client
    assert "console.error" not in client
    assert "sanitizeError" in client
    assert "X-Liuant-Session" in client


def test_backend_offline_ui_text_exists():
    app = (DESKTOP / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "Backend" in app or "backend" in app
    assert "./liuant start" in app or "liuant start" in app


def test_auth_login_logout_ui_exists():
    app = (DESKTOP / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "Login" in app
    assert "Logout" in app
    assert "API" in app
    assert "Session" in app


def test_desktop_status_includes_frontend_build_status_field():
    result = ReleaseManager().desktop_status()

    assert "frontend_build_status" in result
    assert result["frontend_build_status"] in {"not_run", "frontend_build_passed"}
    assert "tauri_build_status" in result


def test_desktop_check_reports_dependency_missing_honestly(monkeypatch):
    real_which = shutil.which

    def fake_which(name: str):
        if name in {"cargo", "rustc"}:
            return None
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)
    result = ReleaseManager().desktop_check()

    assert result["check_status"] == "passed"
    assert result["dependency_status"] == "dependency_missing"
    assert "cargo" in result["missing"]


def test_release_artifacts_detects_real_files_only():
    result = ReleaseManager().release_artifacts()

    for artifact in result["artifacts"]:
        path = Path(artifact["path"])
        assert path.exists()
        assert path.is_file()
        assert artifact["size_bytes"] > 0
        assert artifact["artifact_type"] in {"frontend", "native"}


def test_release_manifest_includes_artifact_status():
    result = ReleaseManager().release_manifest()
    desktop = result["manifest"]["desktop"]

    assert "artifact_status" in desktop
    assert "frontend_build_status" in desktop
    assert "tauri_build_status" in desktop
    assert desktop["desktop_version"] == SettingsManager().get("app_version")["value"]


def test_checksum_generation_ignores_missing_artifacts_safely():
    result = ReleaseManager().release_checksum()

    assert result["status"] in {"no_artifacts", "created"}
    assert "checksums" in result
    for checksum in result["checksums"]:
        assert len(checksum["sha256"]) == 64


def test_release_manifest_does_not_claim_signed_or_notarized():
    result = ReleaseManager().release_manifest()

    assert result["manifest"]["signing"]["signed"] is False
    assert result["manifest"]["signing"]["notarized"] is False
    assert result["manifest"]["notarization"]["macos"] is False
