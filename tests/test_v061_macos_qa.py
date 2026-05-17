"""Tests for v0.6.1: macOS unsigned install QA and first-run checks.

Tests:
1. macos-qa detects DMG artifact metadata
2. macos-qa verifies checksum
3. macos-qa confirms unsigned/not notarized
4. first-run-check reports backend offline honestly
5. docs include unsigned launch instructions
6. desktop UI includes backend offline instructions
7. existing tests still pass
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.release import ReleaseManager


class TestV061MacOSQa:
    """Test suite for v0.6.1 macOS unsigned install QA."""

    def test_macos_qa_detects_dmg_artifact_metadata(self):
        """Test that macos-qa detects DMG artifact metadata."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        # Should detect DMG or report failure honestly
        assert "status" in result
        assert "dmg_path" in result or result["status"] == "failed"
        assert "checks" in result
        assert "dmg_exists" in result["checks"]

    def test_macos_qa_verifies_checksum(self):
        """Test that macos-qa verifies DMG checksum."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "checks" in result
        if result["checks"]["dmg_exists"]:
            # If DMG exists, verify checksum check was performed
            assert "checksum_matches" in result["checks"]
            assert "checksum_exists" in result["checks"]

    def test_macos_qa_confirms_unsigned_not_notarized(self):
        """Test that macos-qa confirms signed=false and notarized=false."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "checks" in result
        assert "signed_is_false" in result["checks"]
        assert "notarized_is_false" in result["checks"]
        assert result["checks"]["signed_is_false"] is True
        assert result["checks"]["notarized_is_false"] is True
        assert result.get("signed") is False
        assert result.get("notarized") is False

    def test_macos_qa_checks_qa_docs_exist(self):
        """Test that macos-qa checks for MACOS_UNSIGNED_INSTALL_QA.md."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "checks" in result
        assert "qa_docs_exist" in result["checks"]
        assert result["checks"]["qa_docs_exist"] is True

    def test_macos_qa_checks_unsigned_warning_present(self):
        """Test that macos-qa checks for unsigned warning in docs."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "checks" in result
        assert "unsigned_warning_present" in result["checks"]
        assert result["checks"]["unsigned_warning_present"] is True

    def test_macos_qa_checks_backend_instructions_present(self):
        """Test that macos-qa checks for backend launch instructions."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "checks" in result
        assert "backend_instructions_present" in result["checks"]
        assert result["checks"]["backend_instructions_present"] is True

    def test_macos_qa_checks_dmg_in_manifest(self):
        """Test that macos-qa checks DMG is referenced in manifest."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "checks" in result
        assert "dmg_in_manifest" in result["checks"]

    def test_macos_qa_returns_timestamp(self):
        """Test that macos-qa returns timestamp."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO format

    def test_macos_qa_returns_message(self):
        """Test that macos-qa returns message."""
        rm = ReleaseManager()
        result = rm.macos_qa()

        assert "message" in result
        assert len(result["message"]) > 0


class TestV061FirstRunCheck:
    """Test suite for v0.6.1 desktop first-run check."""

    def test_first_run_check_reports_backend_offline_honestly(self):
        """Test that first-run-check reports backend offline honestly."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "status" in result
        assert "checks" in result
        assert "backend_reachable" in result["checks"]
        # Should report truthfully, not fake online status
        assert isinstance(result["checks"]["backend_reachable"], bool)

    def test_first_run_check_returns_ui_files_status(self):
        """Test that first-run-check returns UI files status."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "checks" in result
        assert "ui_files_exist" in result["checks"]
        assert isinstance(result["checks"]["ui_files_exist"], bool)

    def test_first_run_check_returns_app_version(self):
        """Test that first-run-check returns app version."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "checks" in result
        assert "app_version" in result["checks"]
        assert result["checks"]["app_version"] is not None

    def test_first_run_check_returns_backend_mode(self):
        """Test that first-run-check returns backend mode."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "checks" in result
        assert "backend_mode" in result["checks"]
        assert result["checks"]["backend_mode"] in ["external_backend", "managed_backend", "bundled_sidecar"]

    def test_first_run_check_returns_local_server_url(self):
        """Test that first-run-check returns local server URL."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "checks" in result
        assert "local_server_url" in result["checks"]
        assert result["checks"]["local_server_url"] == "http://127.0.0.1:8765"

    def test_first_run_check_returns_timestamp(self):
        """Test that first-run-check returns timestamp."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO format

    def test_first_run_check_returns_setup_instructions_when_needed(self):
        """Test that first-run-check returns setup instructions when backend not reachable."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        if result["status"] == "needs_setup":
            assert "setup_instructions" in result
            assert len(result["setup_instructions"]) > 0

    def test_first_run_check_returns_message(self):
        """Test that first-run-check returns message."""
        rm = ReleaseManager()
        result = rm.desktop_first_run_check()

        assert "message" in result
        assert len(result["message"]) > 0


class TestV061DocsExist:
    """Test that v0.6.1 documentation exists."""

    def test_macos_unsigned_install_qa_docs_exists(self):
        """Test that MACOS_UNSIGNED_INSTALL_QA.md exists."""
        docs_path = Path(__file__).parent.parent / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        assert docs_path.exists()

    def test_macos_unsigned_install_qa_contains_unsigned_warning(self):
        """Test that MACOS_UNSIGNED_INSTALL_QA.md contains unsigned warning."""
        docs_path = Path(__file__).parent.parent / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        content = docs_path.read_text(encoding="utf-8").lower()
        assert "unsigned" in content
        assert "not notarized" in content or "notarized" in content

    def test_macos_unsigned_install_qa_contains_backend_instructions(self):
        """Test that MACOS_UNSIGNED_INSTALL_QA.md contains backend instructions."""
        docs_path = Path(__file__).parent.parent / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        content = docs_path.read_text(encoding="utf-8").lower()
        assert "liuant start" in content
        assert "backend" in content

    def test_macos_unsigned_install_qa_contains_sha256(self):
        """Test that MACOS_UNSIGNED_INSTALL_QA.md contains SHA256 verification."""
        docs_path = Path(__file__).parent.parent / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        content = docs_path.read_text(encoding="utf-8").lower()
        assert "sha256" in content

    def test_macos_unsigned_install_qa_contains_install_steps(self):
        """Test that MACOS_UNSIGNED_INSTALL_QA.md contains install steps."""
        docs_path = Path(__file__).parent.parent / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        content = docs_path.read_text(encoding="utf-8").lower()
        assert "drag" in content and "applications" in content
        assert "right-click" in content or "open" in content

    def test_macos_unsigned_install_qa_contains_troubleshooting(self):
        """Test that MACOS_UNSIGNED_INSTALL_QA.md contains troubleshooting."""
        docs_path = Path(__file__).parent.parent / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        content = docs_path.read_text(encoding="utf-8").lower()
        assert "troubleshooting" in content


class TestV061CommandsExist:
    """Test that v0.6.1 CLI commands exist."""

    def test_release_macos_qa_command_exists(self):
        """Test that release macos-qa command exists."""
        rm = ReleaseManager()
        assert hasattr(rm, "macos_qa")

    def test_desktop_first_run_check_command_exists(self):
        """Test that desktop first-run-check command exists."""
        rm = ReleaseManager()
        assert hasattr(rm, "desktop_first_run_check")
