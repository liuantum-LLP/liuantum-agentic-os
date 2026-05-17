import json
from pathlib import Path

from runtime.config import SettingsManager
from runtime.release import ReleaseManager
from runtime.storage import ROOT


DESKTOP = ROOT / "apps" / "desktop"
TAURI = DESKTOP / "src-tauri"


def test_tauri_project_files_exist():
    expected = [
        DESKTOP / "package.json",
        DESKTOP / "vite.config.ts",
        DESKTOP / "tsconfig.json",
        DESKTOP / "index.html",
        DESKTOP / "src" / "main.tsx",
        DESKTOP / "src" / "App.tsx",
        TAURI / "tauri.conf.json",
        TAURI / "Cargo.toml",
        TAURI / "src" / "main.rs",
    ]

    for path in expected:
        assert path.exists(), str(path)


def test_desktop_package_json_has_required_scripts():
    data = json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))

    for script in ("dev", "build", "tauri", "tauri:dev", "tauri:build", "typecheck"):
        assert script in data["scripts"]
    assert data["version"] == SettingsManager().get("app_version")["value"]


def test_tauri_config_has_app_name_and_identifier():
    data = json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))

    assert data["productName"] == "Liuant Agentic OS"
    assert data["identifier"] == "com.liuant.agenticos"
    assert data["version"] == SettingsManager().get("app_version")["value"]
    assert data["app"]["windows"][0]["title"] == "Liuant Agentic OS"


def test_desktop_status_detects_project_true():
    result = ReleaseManager().desktop_status()

    assert result["tauri_project"] is True
    assert result["tauri_project_exists"] is True
    assert result["tauri_config"].endswith("tauri.conf.json")
    assert result["bundle_identifier"] == "com.liuant.agenticos"
    assert result["backend_mode"] == "external_backend"


def test_desktop_check_reports_dependency_status_without_crashing():
    result = ReleaseManager().desktop_check()

    assert result["check_status"] == "passed"
    assert result["status"] in {"ready", "needs_dependency"}
    assert "setup_instructions" in result


def test_release_manifest_includes_desktop_project_status():
    result = ReleaseManager().release_manifest()
    desktop = result["manifest"]["desktop"]

    assert desktop["tauri_project_exists"] is True
    assert desktop["desktop_version"] == SettingsManager().get("app_version")["value"]
    assert desktop["bundle_identifier"] == "com.liuant.agenticos"
    assert desktop["backend_mode"] == "external_backend"


def test_backend_offline_ui_state_exists_in_react_files():
    app = (DESKTOP / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "Backend" in app or "backend" in app
    assert "./liuant start" in app or "liuant start" in app
    assert "Retry" in app or "retry" in app


def test_auth_login_ui_component_exists():
    app = (DESKTOP / "src" / "App.tsx").read_text(encoding="utf-8")
    client = (DESKTOP / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert "Login" in app
    assert "API" in app
    assert "LIUANT_API_TOKEN" in client


def test_desktop_icon_placeholder_exists():
    icon = TAURI / "icons" / "icon.svg"

    assert icon.exists()
    assert "Liuant Agentic OS" in icon.read_text(encoding="utf-8")
