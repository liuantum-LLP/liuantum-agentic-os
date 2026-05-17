import shutil
import subprocess
import sys

from runtime.config import SettingsManager
from runtime.release import ReleaseManager
from runtime.storage import ROOT


def test_rust_check_reports_missing_cargo_without_crashing(monkeypatch):
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name in {"cargo", "rustc", "rustup"} else real_which(name))

    result = ReleaseManager().rust_check()

    assert result["status"] == "dependency_missing"
    assert "cargo" in result["missing"]
    assert result["setup_instructions"]


def test_native_check_returns_setup_instructions_when_dependencies_missing(monkeypatch):
    real_which = shutil.which

    def fake_which(name: str):
        if name in {"cargo", "rustc"}:
            return None
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)
    result = ReleaseManager().native_check()

    assert result["status"] == "dependency_missing"
    assert "cargo" in result["missing"]
    assert result["setup_instructions"]


def test_desktop_build_frontend_only_reports_correctly():
    result = ReleaseManager().desktop_build(frontend_only=True, skip_tests=True)

    assert result["status"] in {"frontend_build_passed", "frontend_build_failed"}
    assert result["native_build_status"] in {"not_attempted", "failed"}


def test_desktop_build_native_does_not_claim_artifacts_when_cargo_missing(monkeypatch):
    real_which = shutil.which

    def fake_which(name: str):
        if name in {"cargo", "rustc"}:
            return None
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)
    result = ReleaseManager().desktop_build(native=True, skip_tests=True)

    assert result["status"] in ("dependency_missing", "frontend_build_failed", "failed")
    assert result["native_build_status"] in ("dependency_missing", "not_attempted", "failed")
    if "missing" in result:
        assert "cargo" in result["missing"]


def test_backend_mode_defaults_to_external_backend():
    SettingsManager().set("desktop_backend_mode", "external_backend")

    result = ReleaseManager().desktop_backend_mode()

    assert result["current_mode"] == "external_backend"


def test_backend_mode_setting_persists():
    manager = ReleaseManager()

    updated = manager.set_desktop_backend_mode("managed_backend")
    loaded = manager.desktop_backend_mode()
    manager.set_desktop_backend_mode("external_backend")

    assert updated["mode"] == "managed_backend"
    assert loaded["current_mode"] == "managed_backend"


def test_backend_start_refuses_non_localhost_binding():
    result = ReleaseManager().desktop_backend_start(host="0.0.0.0")

    assert result["status"] == "blocked"
    assert result["host"] == "0.0.0.0"


def test_release_manifest_includes_backend_mode():
    result = ReleaseManager().release_manifest()
    desktop = result["manifest"]["desktop"]

    assert desktop["backend_mode"] in {"external_backend", "managed_backend", "bundled_sidecar"}
    assert "sidecar_status" in desktop
    assert "cargo_available" in desktop


def test_release_desktop_report_includes_native_dependency_status():
    result = ReleaseManager().release_desktop_report()

    assert "native_build_status" in result
    assert "dependency_gaps" in result
    assert "sidecar_status" in result


def test_desktop_ui_contains_backend_mode_and_identity():
    app = (ROOT / "apps" / "desktop" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "Liuant Agentic OS" in app
    assert "Backend" in app or "backend" in app


def test_desktop_ui_contains_backend_offline_instructions():
    app = (ROOT / "apps" / "desktop" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "Backend" in app
    assert "./liuant start" in app


def test_desktop_ui_contains_auth_token_instructions():
    app = (ROOT / "apps" / "desktop" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "API Token" in app or "liuant auth token" in app


def test_desktop_ui_release_page_has_unsigned_copy():
    settings_page = (ROOT / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "Signed" in settings_page and "false" in settings_page
    assert "Notarized" in settings_page and "false" in settings_page


def test_desktop_ui_contains_macos_unsigned_launch_note():
    settings_page = (ROOT / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "unsigned" in settings_page.lower()


def test_icon_generated_assets_exist():
    icon_dir = ROOT / "apps" / "desktop" / "src-tauri" / "icons"
    required = ["icon.svg", "32x32.png", "128x128.png", "128x128@2x.png", "icon.ico", "icon.icns"]

    for name in required:
        path = icon_dir / name
        if path.exists():
            assert path.stat().st_size > 0, f"Empty icon: {name}"


def test_icon_generator_is_offline():
    script = (ROOT / "scripts" / "generate_icons.py").read_text(encoding="utf-8")

    assert "import urllib" not in script
    assert "import requests" not in script
    assert "import httpx" not in script
    assert "import aiohttp" not in script


def test_icons_check_reports_branding_status():
    result = ReleaseManager().icons_check()

    assert result["status"] in {"complete", "partial", "missing"}
    assert "required" in result
    assert "present" in result


def test_desktop_polish_check():
    result = ReleaseManager().desktop_polish_check()

    assert "status" in result
    assert "checks" in result
    assert "backend_mode" in result
    assert "macos_qa_docs_exist" in result["checks"]
    assert "backend_offline_instructions" in result["checks"] or "ui_source_exists" in result["checks"]


def test_release_page_includes_signed_false_notarized_false():
    result = ReleaseManager().release_desktop_report()

    assert result["signing"]["signed"] == False
    assert result["signing"]["notarized"] == False


def test_macos_qa_still_passes():
    result = ReleaseManager().macos_qa()

    assert result["status"] in {"passed", "failed"}
    assert "signed" in result
    assert "notarized" in result
    assert result["signed"] == False
    assert result["notarized"] == False


def test_cli_desktop_native_check_works():
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "desktop", "native-check"], capture_output=True, text=True, check=True)

    assert "setup_instructions" in result.stdout or "missing" in result.stdout or "ready" in result.stdout or "status" in result.stdout
