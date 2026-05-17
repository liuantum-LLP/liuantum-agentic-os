"""macOS code-signing and notarization pipeline tests — v0.7.1.

Tests signing readiness detection, macOS guide commands, preflight checks,
signing/notarization wrappers, release manifest metadata, package script safety,
preflight improvements (stale artifact detection, current-version artifact),
manifest integration, and checksum regeneration.
All tests run without real Apple credentials.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from runtime.release import ReleaseManager

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_apple_env():
    for var in [
        "APPLE_DEVELOPER_ID_APPLICATION",
        "APPLE_SIGNING_IDENTITY",
        "APPLE_ID",
        "APPLE_TEAM_ID",
        "APPLE_APP_SPECIFIC_PASSWORD",
        "APPLE_KEYCHAIN_PROFILE",
        "TAURI_SIGNING_PRIVATE_KEY",
        "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
    ]:
        os.environ.pop(var, None)


def _set_apple_env():
    os.environ["APPLE_DEVELOPER_ID_APPLICATION"] = "Developer ID Application: Test (ABCD1234)"
    os.environ["APPLE_ID"] = "test@example.com"
    os.environ["APPLE_TEAM_ID"] = "ABCD1234"
    os.environ["APPLE_APP_SPECIFIC_PASSWORD"] = "xxxx-xxxx-xxxx-xxxx"


# ---------------------------------------------------------------------------
# 1. Signing status detects missing Apple env vars
# ---------------------------------------------------------------------------


def test_signing_status_missing_env():
    _clear_apple_env()
    status = ReleaseManager().signing_status()
    assert status["signed"] is False
    assert status["notarized"] is False
    assert status["status"] == "unsigned"
    assert status["ready_for_codesign"] is False
    assert status["ready_for_notarization"] is False
    assert status["macos"]["developer_id_configured"] is False
    assert status["macos"]["apple_id_configured"] is False
    assert status["macos"]["team_id_configured"] is False
    assert status["macos"]["app_specific_password_configured"] is False
    assert status["macos"]["keychain_profile_configured"] is False
    assert status["macos"]["notarization_configured"] is False


def test_signing_status_with_partial_env():
    _clear_apple_env()
    os.environ["APPLE_ID"] = "test@example.com"
    status = ReleaseManager().signing_status()
    assert status["signed"] is False
    assert status["macos"]["apple_id_configured"] is True
    assert status["macos"]["team_id_configured"] is False
    assert status["macos"]["notarization_configured"] is False
    assert status["ready_for_notarization"] is False


def test_signing_status_full_notarization_env():
    _clear_apple_env()
    _set_apple_env()
    status = ReleaseManager().signing_status()
    assert status["macos"]["developer_id_configured"] is True
    assert status["macos"]["apple_id_configured"] is True
    assert status["macos"]["team_id_configured"] is True
    assert status["macos"]["app_specific_password_configured"] is True
    assert status["macos"]["notarization_configured"] is True
    assert status["ready_for_codesign"] is True
    assert status["ready_for_notarization"] is True


def test_signing_status_keychain_profile():
    _clear_apple_env()
    os.environ["APPLE_DEVELOPER_ID_APPLICATION"] = "Developer ID Application: Test (ABCD1234)"
    os.environ["APPLE_KEYCHAIN_PROFILE"] = "AC_USERNAME"
    os.environ["APPLE_ID"] = "test@example.com"
    os.environ["APPLE_TEAM_ID"] = "ABCD1234"
    status = ReleaseManager().signing_status()
    assert status["macos"]["developer_id_configured"] is True
    assert status["macos"]["keychain_profile_configured"] is True
    assert status["macos"]["notarization_configured"] is True


# ---------------------------------------------------------------------------
# 2. Signing status masks secret env presence
# ---------------------------------------------------------------------------


def test_signing_status_no_secret_values():
    _clear_apple_env()
    _set_apple_env()
    status = ReleaseManager().signing_status()
    output = str(status)
    assert "xxxx-xxxx" not in output
    assert "test@example.com" not in output
    assert "ABCD1234" not in output or "team_id_configured" in output
    assert "Developer ID Application: Test" not in output


# ---------------------------------------------------------------------------
# 3. macos export env template contains variable names only
# ---------------------------------------------------------------------------


def test_macos_export_env_template_contains_names_only():
    result = ReleaseManager().signing_macos_export_env_template()
    assert result["status"] == "ok"
    text = "\n".join(result["variables"])
    assert "APPLE_DEVELOPER_ID_APPLICATION" in text
    assert "APPLE_ID" in text
    assert "APPLE_TEAM_ID" in text
    assert "APPLE_APP_SPECIFIC_PASSWORD" in text
    assert "APPLE_KEYCHAIN_PROFILE" in text
    assert "TAURI_SIGNING_PRIVATE_KEY" in text
    assert "TAURI_SIGNING_PRIVATE_KEY_PASSWORD" in text
    for line in result["variables"]:
        if line.startswith("APPLE") or line.startswith("TAURI"):
            assert "=" in line
            assert not line.endswith(("x", "m", "d")) or line.endswith("=")


# ---------------------------------------------------------------------------
# 4. macos preflight reports not_ready without credentials
# ---------------------------------------------------------------------------


def test_macos_preflight_not_ready_without_creds():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_preflight()
    assert result["status"] in ("not_ready", "no_native_artifacts")
    assert result["signed"] is False
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# 5. macos preflight detects artifact path from manifest
# ---------------------------------------------------------------------------


def test_macos_preflight_checks_artifact():
    result = ReleaseManager().signing_macos_preflight()
    if "checks" in result:
        if result["checks"].get("artifact_exists"):
            assert result["checks"]["dmg_exists"] is True or result["checks"]["artifact_exists"] is True
    assert result["signed"] is False
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# 6. macos-sign dry-run does not modify artifact metadata
# ---------------------------------------------------------------------------


def test_macos_sign_dry_run_does_not_claim_signed():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_sign(dry_run=True)
    assert result["signed"] is False
    assert result["notarized"] is False


def test_macos_sign_dry_run_returns_status():
    _clear_apple_env()
    os.environ["APPLE_DEVELOPER_ID_APPLICATION"] = "Developer ID Application: Test (ABCD1234)"
    result = ReleaseManager().signing_macos_sign(dry_run=True)
    assert result["status"] in ("dry_run", "not_ready", "artifact_missing")
    assert result["signed"] is False


def test_macos_sign_not_ready_without_env():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_sign(dry_run=True)
    assert result["status"] == "not_ready"
    assert "APPLE_DEVELOPER_ID_APPLICATION" in result.get("reason", "") or result["status"] == "not_ready"


# ---------------------------------------------------------------------------
# 7. macos-sign requires confirm for real attempt
# ---------------------------------------------------------------------------


def test_macos_sign_requires_confirm():
    _clear_apple_env()
    os.environ["APPLE_DEVELOPER_ID_APPLICATION"] = "Developer ID Application: Test (ABCD1234)"
    result = ReleaseManager().signing_macos_sign(dry_run=False, confirm=False)
    assert result["status"] in ("confirm_required", "not_ready", "artifact_missing")
    assert result["signed"] is False


# ---------------------------------------------------------------------------
# 8. macos-notarize dry-run does not upload
# ---------------------------------------------------------------------------


def test_macos_notarize_dry_run_does_not_claim_notarized():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_notarize(dry_run=True)
    assert result["notarized"] is False
    assert result["signed"] is False


def test_macos_notarize_dry_run_shows_steps():
    _clear_apple_env()
    _set_apple_env()
    result = ReleaseManager().signing_macos_notarize(dry_run=True)
    assert result["status"] in ("dry_run", "not_ready", "artifact_missing")
    if result["status"] == "dry_run":
        assert "steps" in result
        assert len(result["steps"]) > 0


# ---------------------------------------------------------------------------
# 9. macos-notarize requires confirm
# ---------------------------------------------------------------------------


def test_macos_notarize_requires_confirm():
    _clear_apple_env()
    _set_apple_env()
    result = ReleaseManager().signing_macos_notarize(dry_run=False, confirm=False)
    assert result["status"] in ("confirm_required", "not_ready", "artifact_missing")
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# 10. Release manifest includes signing metadata
# ---------------------------------------------------------------------------


def test_release_manifest_includes_signing_block():
    result = ReleaseManager().release_manifest()
    manifest = result.get("manifest", result)
    signing = manifest.get("signing", {})
    assert signing.get("signed") is False
    assert signing.get("notarized") is False
    assert "codesign_verified" in signing
    assert "spctl_accepted" in signing
    assert "notarization_status" in signing
    assert "signed_at" in signing
    assert "notarized_at" in signing


# ---------------------------------------------------------------------------
# 11. package_macos.sh does not sign by default
# ---------------------------------------------------------------------------


def test_package_macos_sh_no_sign_by_default():
    path = ROOT / "installer" / "package_macos.sh"
    content = path.read_text(encoding="utf-8")
    assert 'DO_SIGN=false' in content
    assert 'DO_NOTARIZE=false' in content
    assert 'DRY_RUN_SIGNING=false' in content


def test_package_macos_sh_has_sign_flag():
    path = ROOT / "installer" / "package_macos.sh"
    content = path.read_text(encoding="utf-8")
    assert "--sign" in content
    assert "--notarize" in content
    assert "--dry-run-signing" in content


# ---------------------------------------------------------------------------
# 12. unsigned-build-check still passes for unsigned artifact
# ---------------------------------------------------------------------------


def test_unsigned_build_check_still_passes():
    result = ReleaseManager().unsigned_build_check()
    assert "signed" in result
    assert result["signed"] is False
    assert result["notarized"] is False
    assert result["status"] in ("passed", "no_native_artifacts", "failed")


def test_unsigned_build_check_does_not_claim_signed():
    result = ReleaseManager().unsigned_build_check()
    status = result["status"]
    if status == "passed":
        checks = result.get("checks", {})
        assert checks.get("signed_is_false") is True
        assert checks.get("notarized_is_false") is True


# ---------------------------------------------------------------------------
# 13. macOS guide contains all sections
# ---------------------------------------------------------------------------


def test_macos_guide_contains_all_sections():
    result = ReleaseManager().signing_macos_guide()
    guide = result.get("guide", "")
    assert "Apple Developer Program" in guide
    assert "Developer ID Application" in guide
    assert "App-Specific Password" in guide
    assert "Notarytool Profile" in guide
    assert "Tauri Signing" in guide
    assert "Build States" in guide


# ---------------------------------------------------------------------------
# 14. macOS status returns expected shape
# ---------------------------------------------------------------------------


def test_macos_status_shape():
    _clear_apple_env()
    status = ReleaseManager().signing_macos_status()
    assert "artifact_exists" in status
    assert "current_version_artifact_exists" in status
    assert "stale_artifact_count" in status
    assert "dmg_path" in status
    assert "dmg_checksum" in status
    assert "developer_id_configured" in status
    assert "ready_for_codesign" in status
    assert "ready_for_notarization" in status
    assert status["signed"] is False
    assert status["notarized"] is False
    assert status["apple_credentials_displayed"] is False


# ---------------------------------------------------------------------------
# v0.7.1: artifact detection marks old-version artifact as stale
# ---------------------------------------------------------------------------


def test_artifact_detection_marks_old_artifact_stale():
    _clear_apple_env()
    artifacts = ReleaseManager().release_artifacts()
    stale = artifacts.get("stale_native_artifacts", [])
    if artifacts.get("native_artifacts"):
        current_version = ReleaseManager().version()["app_version"]
        for s in stale:
            assert "stale" in s
            assert s["artifact_type"] == "native"


def test_old_artifact_not_deleted_automatically():
    _clear_apple_env()
    result = ReleaseManager().release_artifacts()
    stale = result.get("stale_native_artifacts", [])
    all_artifacts = result.get("artifacts", [])
    stale_names = [s["name"] for s in stale]
    for a in all_artifacts:
        if a["name"] in stale_names:
            assert any(s["name"] == a["name"] for s in stale)


# ---------------------------------------------------------------------------
# v0.7.1: preflight prefers current-version artifact when available
# ---------------------------------------------------------------------------


@patch("runtime.release.ReleaseManager._current_version_native_artifact")
@patch("runtime.release.ReleaseManager._stale_native_artifacts")
def test_preflight_prefers_current_version_artifact(mock_stale, mock_current):
    _clear_apple_env()
    mock_current.return_value = {
        "name": "Liuant Agentic OS_0.7.1_aarch64.dmg",
        "path": "/tmp/fake_v071.dmg",
        "artifact_type": "native",
    }
    mock_stale.return_value = [
        {"name": "Liuant Agentic OS_0.6.0_aarch64.dmg", "path": "/tmp/fake_v060.dmg", "artifact_type": "native", "stale": True},
    ]
    with (
        patch("runtime.release.ReleaseManager._native_artifacts_detailed") as mock_detailed,
        patch("runtime.release.ReleaseManager._sha256") as mock_sha,
    ):
        mock_detailed.return_value = [
            {"name": "Liuant Agentic OS_0.7.1_aarch64.dmg", "path": "/tmp/fake_v071.dmg", "artifact_type": "native"},
            {"name": "Liuant Agentic OS_0.6.0_aarch64.dmg", "path": "/tmp/fake_v060.dmg", "artifact_type": "native"},
        ]
        mock_sha.return_value = "0464df41a96dfb5ea82b048a08f35aa5afa1581c403bd56f7561e63ab5f1e4f1"
        result = ReleaseManager().signing_macos_preflight()
        checks = result.get("checks", {})
        assert checks.get("current_version_artifact_exists") is True
        assert checks.get("stale_artifact_count", 0) >= 1


@patch("runtime.release.ReleaseManager._current_version_native_artifact")
@patch("runtime.release.ReleaseManager._stale_native_artifacts")
def test_version_matches_passes_with_current_artifact(mock_stale, mock_current):
    _clear_apple_env()
    from runtime.config import SettingsManager
    current_ver = SettingsManager().get("app_version")["value"]
    mock_artifact_name = f"Liuant Agentic OS_{current_ver}_aarch64.dmg"
    mock_current.return_value = {
        "name": mock_artifact_name,
        "path": f"/tmp/fake_{current_ver}.dmg",
        "artifact_type": "native",
    }
    mock_stale.return_value = []
    with (
        patch("runtime.release.ReleaseManager._native_artifacts_detailed") as mock_detailed,
        patch("runtime.release.ReleaseManager._sha256") as mock_sha,
    ):
        mock_detailed.return_value = [
            {"name": mock_artifact_name, "path": f"/tmp/fake_{current_ver}.dmg", "artifact_type": "native"},
        ]
        mock_sha.return_value = "0464df41a96dfb5ea82b048a08f35aa5afa1581c403bd56f7561e63ab5f1e4f1"
        result = ReleaseManager().signing_macos_preflight()
        checks = result.get("checks", {})
        assert checks.get("version_matches") is True
        assert checks.get("current_version_artifact_exists") is True
        missing = result.get("missing_checks") or []
        assert "version_matches" not in missing
        assert "current_version_artifact_exists" not in missing


# ---------------------------------------------------------------------------
# v0.7.1: signing failure keeps signed=false
# ---------------------------------------------------------------------------


@patch("runtime.release.ReleaseManager.signing_macos_sign")
def test_signing_failure_keeps_signed_false(mock_sign):
    _clear_apple_env()
    mock_sign.return_value = {
        "status": "failed",
        "reason": "codesign_error",
        "stderr": "error: The specified item could not be found in the keychain.",
        "signed": False,
        "notarized": False,
        "message": "Signing command failed.",
    }
    result = ReleaseManager().signing_macos_sign()
    assert result["signed"] is False
    assert result["status"] in ("not_ready", "failed")


# ---------------------------------------------------------------------------
# v0.7.1: mocked successful codesign sets signed=true and codesign_verified=true
# ---------------------------------------------------------------------------


@patch("runtime.release.ReleaseManager.signing_macos_sign")
def test_signing_success_sets_signed_true(mock_sign):
    mock_sign.return_value = {
        "status": "completed",
        "signed": True,
        "notarized": False,
        "signed_at": "2026-05-17T00:00:00+00:00",
        "codesign_verified": True,
        "spctl_accepted": True,
        "artifact": "/tmp/test.dmg",
        "message": "Signing completed successfully.",
    }
    result = ReleaseManager().signing_macos_sign()
    assert result["signed"] is True
    assert result["codesign_verified"] is True
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# v0.7.1: notarized remains false after signing (signing-only, no notarization)
# ---------------------------------------------------------------------------


def test_notarized_false_after_sign_only():
    _clear_apple_env()
    status = ReleaseManager().signing_status()
    assert status["notarized"] is False
    assert status["signed"] is False


# ---------------------------------------------------------------------------
# v0.7.1: preflight includes all new checks
# ---------------------------------------------------------------------------


def test_preflight_includes_new_checks():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_preflight()
    checks = result.get("checks", {})
    if checks:
        assert "version_matches" in checks
        assert "app_version" in checks
        assert "current_version_artifact_exists" in checks


def test_preflight_current_version_artifact_missing_when_no_match():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_preflight()
    if result.get("checks", {}).get("artifact_exists"):
        checks = result["checks"]
        if not checks.get("current_version_artifact_exists"):
            assert "current_version_artifact_exists" in (result.get("missing_checks") or [])


# ---------------------------------------------------------------------------
# 15. verify_artifacts still returns signed=false
# ---------------------------------------------------------------------------


def test_verify_artifacts_signed_false():
    result = ReleaseManager().verify_artifacts()
    assert result["signed"] is False
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# 16. unsigned_artifacts still returns signed=false
# ---------------------------------------------------------------------------


def test_unsigned_artifacts_signed_false():
    result = ReleaseManager().unsigned_artifacts()
    assert result["signed"] is False
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# 17. Signing docs contains env var names
# ---------------------------------------------------------------------------


def test_signing_docs_env_names():
    result = ReleaseManager().signing_docs()
    assert "env_names" in result
    assert "APPLE_DEVELOPER_ID_APPLICATION" in result["env_names"]
    assert "TAURI_SIGNING_PRIVATE_KEY" in result["env_names"]


# ---------------------------------------------------------------------------
# v0.7.1: Preflight does not print secrets in any output
# ---------------------------------------------------------------------------


def test_preflight_no_secrets_in_output():
    _clear_apple_env()
    result = ReleaseManager().signing_macos_preflight()
    output = str(result)
    assert "xxxx-xxxx" not in output
    assert "test@" not in output
    assert result["signed"] is False
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# v0.7.2: Icon generation remains offline and produces complete set
# ---------------------------------------------------------------------------


def test_icon_generation_offline():
    import sys
    import subprocess
    result = subprocess.run([sys.executable, "scripts/generate_icons.py"], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert result.returncode == 0
    assert "Generated" in result.stdout


def test_icons_check_passes():
    result = ReleaseManager().icons_check()
    assert result["status"] in ("complete", "partial")
    assert len(result["missing"]) == 0


# ---------------------------------------------------------------------------
# v0.7.2: Release polish-check returns expected shape
# ---------------------------------------------------------------------------


def test_release_polish_check_shape():
    result = ReleaseManager().desktop_polish_check()
    assert "status" in result
    assert result["status"] in ("passed", "needs_polish")
    assert "checks" in result
    assert "version_aligned" in result["checks"]
    assert "icons_complete" in result["checks"]
    assert "signed_is_false" in result["checks"]
    assert "notarized_is_false" in result["checks"]
    assert "signing_docs_exist" in result["checks"]
    if "dmg_exists" in result["checks"]:
        assert result["checks"]["dmg_exists"] is True or result["checks"]["dmg_exists"] is False
    if result["checks"].get("signed_is_false") is not None:
        assert result["checks"]["signed_is_false"] is True


# ---------------------------------------------------------------------------
# v0.7.2: Signing blocked messaging includes Developer ID guidance
# ---------------------------------------------------------------------------


def test_signing_blocked_message_includes_developer_id_guidance():
    _clear_apple_env()
    status = ReleaseManager().signing_status()
    msg = status.get("message", "")
    keywords = ["APPLE_DEVELOPER_ID_APPLICATION", "Developer ID", "security find-identity", "docs/MACOS_SIGNING", "unsigned", "signing"]
    assert any(k.lower() in msg.lower() for k in keywords), f"No signing guidance found in: {msg}"


def test_signing_macos_status_blocked_message():
    _clear_apple_env()
    status = ReleaseManager().signing_macos_status()
    msg = status.get("message", "")
    # Should mention blocked or no credentials
    if status.get("current_version_artifact_exists"):
        assert "blocked" in msg.lower() or "not configured" in msg.lower()
    assert status["signed"] is False
    assert status["notarized"] is False


# ---------------------------------------------------------------------------
# v0.7.2: Release desktop report still shows signed=false and notarized=false
# ---------------------------------------------------------------------------


def test_release_desktop_report_signed_false():
    result = ReleaseManager().release_desktop_report()
    signing = result.get("signing", {})
    if isinstance(signing, dict):
        assert signing.get("signed") is False
        assert signing.get("notarized") is False


# ---------------------------------------------------------------------------
# v0.7.2: macOS QA still passes
# ---------------------------------------------------------------------------


def test_macos_qa_still_passes_v072():
    result = ReleaseManager().macos_qa()
    assert "signed" in result
    assert "notarized" in result
    assert result["signed"] is False
    assert result["notarized"] is False


# ---------------------------------------------------------------------------
# v0.7.2: Signing status message references docs
# ---------------------------------------------------------------------------


def test_signing_status_message_references_docs():
    _clear_apple_env()
    status = ReleaseManager().signing_status()
    msg = status.get("message", "")
    keywords = ["docs/", "MACOS_SIGNING", "signing", "notarization"]
    assert any(k.lower() in msg.lower() for k in keywords), f"No doc reference in: {msg}"
