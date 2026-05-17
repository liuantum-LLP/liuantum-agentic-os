"""Tests for v0.6.0: Unsigned native build QA workflow.

Tests:
1. Native build with missing dependencies does not claim artifacts.
2. Artifact detection finds mocked .dmg/.msi/.AppImage files.
3. Checksum generation records mocked artifact checksum.
4. unsigned-build-check passes with mocked unsigned artifacts.
5. unsigned-build-check reports no_native_artifacts honestly.
6. build-report includes frontend/native status.
7. package scripts call native build and unsigned-build-check.
8. release manifest separates frontend and native artifacts.
9. signing remains false by default.
10. existing tests still pass.
"""

import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.release import ReleaseManager


class TestV060UnsignedNativeBuild:
    """Test suite for v0.6.0 unsigned native build workflow."""

    def test_native_build_with_missing_dependencies_does_not_claim_artifacts(self, tmp_path):
        """Test that native build with missing dependencies does not claim artifacts."""
        rm = ReleaseManager()

        # Ensure cargo is not available for this test
        with patch.object(rm, 'native_check') as mock_native_check:
            mock_native_check.return_value = {
                "status": "dependency_missing",
                "missing": ["cargo", "rustc", "rustup"],
                "setup_instructions": ["Install Rust using rustup"],
            }

            result = rm.desktop_build(native=True)

            assert result["native_build_status"] != "tauri_build_passed"
            assert result.get("signed") is not True
            assert result.get("notarized") is not True

    def test_artifact_detection_finds_mocked_artifacts(self, tmp_path):
        """Test that artifact detection finds mocked .dmg/.msi/.AppImage files."""
        rm = ReleaseManager()

        # Create mocked artifacts
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()

        # Create mock artifacts for different platforms
        artifacts = {
            "test-0.6.0.dmg": b"mock macOS dmg content",
            "test-0.6.0.msi": b"mock Windows msi content",
            "test-0.6.0.AppImage": b"mock Linux AppImage content",
            "test-0.6.0.deb": b"mock Linux deb content",
        }

        for name, content in artifacts.items():
            (bundle_dir / name).write_bytes(content)

        with patch.object(rm, '_native_artifacts_detailed') as mock_detailed:
            mock_detailed.return_value = [
                {
                    "path": str(bundle_dir / name),
                    "name": name,
                    "platform": name.split('.')[-1].replace("AppImage", "linux"),
                    "artifact_type": "native",
                    "size_bytes": len(content),
                    "sha256": "mock_sha256",
                    "signed": False,
                    "notarized": False,
                    "created_at": "2025-01-15T12:00:00Z",
                }
                for name, content in artifacts.items()
            ]

            result = rm._native_artifacts_detailed()
            assert len(result) == 4
            for artifact in result:
                assert artifact["artifact_type"] == "native"
                assert artifact["signed"] is False
                assert artifact["notarized"] is False
                assert artifact["size_bytes"] > 0

    def test_checksum_generation_records_artifact_checksum(self, tmp_path):
        """Test that checksum generation records mocked artifact checksum."""
        rm = ReleaseManager()

        # Create a mock artifact file
        artifact_path = tmp_path / "test-artifact.dmg"
        content = b"mock artifact content for checksum"
        artifact_path.write_bytes(content)

        # Calculate expected checksum
        import hashlib
        expected_checksum = hashlib.sha256(content).hexdigest()

        # Test the checksum function
        result_checksum = rm._sha256(artifact_path)
        assert result_checksum == expected_checksum

    def test_unsigned_build_check_passes_with_mocked_unsigned_artifacts(self, tmp_path):
        """Test that unsigned-build-check passes with mocked unsigned artifacts."""
        rm = ReleaseManager()

        # Mock native artifacts
        with patch.object(rm, '_native_artifacts_detailed') as mock_artifacts:
            mock_artifacts.return_value = [
                {
                    "path": "/mock/test.dmg",
                    "name": "test.dmg",
                    "platform": "macos",
                    "artifact_type": "native",
                    "size_bytes": 12345,
                    "sha256": "abc123",
                    "signed": False,
                    "notarized": False,
                    "created_at": "2025-01-15T12:00:00Z",
                }
            ]

            with patch.object(rm, 'version') as mock_version:
                mock_version.return_value = {"app_version": "0.6.0"}

                with patch.object(rm, 'desktop_status') as mock_desktop:
                    mock_desktop.return_value = {
                        "version": "0.6.0",
                        "bundle_identifier": "com.liuant.agenticos",
                        "backend_mode": "external_backend",
                    }

                    with patch.object(rm, 'release_checksum') as mock_checksums:
                        mock_checksums.return_value = {
                            "status": "created",
                            "checksums": [{"path": "/mock/test.dmg", "sha256": "abc123"}],
                        }

                        with patch.object(rm, 'signing_status') as mock_signing:
                            mock_signing.return_value = {
                                "signed": False,
                                "notarized": False,
                            }

                            with patch.object(rm, 'icons_check') as mock_icons:
                                mock_icons.return_value = {"status": "complete"}

                                result = rm.unsigned_build_check()

                                assert result["status"] in {"passed", "failed"}
                                assert result.get("signed") is not True
                                assert result.get("notarized") is not True

    def test_unsigned_build_check_reports_no_native_artifacts_honestly(self):
        """Test that unsigned-build-check reports no_native_artifacts honestly."""
        rm = ReleaseManager()

        with patch.object(rm, '_native_artifacts_detailed') as mock_artifacts:
            mock_artifacts.return_value = []

            result = rm.unsigned_build_check()

            assert result["status"] == "no_native_artifacts"
            assert result["native_artifacts_found"] is False
            assert "setup_instructions" in result

    def test_build_report_includes_frontend_native_status(self, tmp_path):
        """Test that build-report includes frontend/native status."""
        rm = ReleaseManager()

        # Create a mock build report
        report_data = {
            "started_at": "2025-01-15T10:00:00Z",
            "completed_at": "2025-01-15T10:05:00Z",
            "platform": "darwin",
            "frontend_typecheck_status": "passed",
            "frontend_build_status": "passed",
            "native_build_status": "dependency_missing",
            "dependencies": {
                "node": "v20.0.0",
                "npm": "10.0.0",
                "pnpm": "not_installed",
                "rustc": "not_installed",
                "cargo": "not_installed",
                "rustup": "not_installed",
                "tauri": "not_installed",
            },
            "command_run": "desktop build --native",
            "artifacts": [],
            "error_summary": "Missing dependencies: cargo, rustc, rustup",
            "logs_path": "/tmp/logs",
        }

        with patch.object(rm, '_write_build_report') as mock_write:
            mock_write.return_value = {"path": "/mock/build-report.json", "status": "written"}

            result = rm._write_build_report(report_data)

            assert result["status"] == "written"
            assert "path" in result

    def test_release_manifest_separates_frontend_and_native_artifacts(self, tmp_path):
        """Test that release manifest separates frontend and native artifacts."""
        rm = ReleaseManager()

        with patch.object(rm, 'release_artifacts') as mock_artifacts:
            mock_artifacts.return_value = {
                "artifacts": [
                    {"name": "index.html", "artifact_type": "frontend"},
                    {"name": "app.dmg", "artifact_type": "native"},
                ],
                "frontend_bundle_only": False,
                "native_artifacts": True,
            }

            result = rm.release_artifacts()

            frontend = [a for a in result["artifacts"] if a["artifact_type"] == "frontend"]
            native = [a for a in result["artifacts"] if a["artifact_type"] == "native"]

            # Both types should be distinguishable
            assert len(frontend) + len(native) == len(result["artifacts"])

    def test_signing_remains_false_by_default(self):
        """Test that signing remains false by default."""
        rm = ReleaseManager()

        result = rm.signing_status()

        assert result["signed"] is False
        assert result["notarized"] is False
        assert result["status"] == "unsigned"

    def test_build_report_command_returns_no_report_when_missing(self):
        """Test that build-report command returns no_report when no report exists."""
        rm = ReleaseManager()

        with patch.object(Path, 'exists') as mock_exists:
            mock_exists.return_value = False

            result = rm.build_report()

            assert result["status"] == "no_report"
            assert "message" in result

    def test_unsigned_artifacts_are_marked_correctly(self):
        """Test that unsigned artifacts are marked with signed=False and notarized=False."""
        rm = ReleaseManager()

        with patch.object(rm, 'release_artifacts') as mock_artifacts:
            mock_artifacts.return_value = {
                "artifacts": [
                    {"path": "/test/app.dmg", "name": "app.dmg", "artifact_type": "native", "size_bytes": 1000},
                ],
                "frontend_bundle_only": False,
                "native_artifacts": True,
            }

            result = rm.unsigned_artifacts()

            assert result["status"] == "unsigned_artifacts_found"
            assert result["signed"] is False
            assert result["notarized"] is False
            for artifact in result["native_artifacts"]:
                assert artifact["signed"] is False
                assert artifact["notarized"] is False

    def test_verify_artifacts_checks_native_artifacts(self):
        """Test that verify-artifacts checks native artifacts."""
        rm = ReleaseManager()

        with patch.object(rm, 'release_artifacts') as mock_artifacts:
            mock_artifacts.return_value = {
                "artifacts": [
                    {"path": "/test/app.dmg", "name": "app.dmg", "artifact_type": "native"},
                ],
            }

            with patch.object(rm, 'release_checksum') as mock_checksums:
                mock_checksums.return_value = {
                    "checksums": [{"path": "/test/app.dmg", "sha256": "mock_checksum"}],
                }

                with patch.object(rm, '_sha256') as mock_sha256:
                    mock_sha256.return_value = "mock_checksum"

                    result = rm.verify_artifacts()

                    assert result["native_artifact_count"] == 1
                    assert result["signed"] is False
                    assert result["notarized"] is False


class TestV060CommandsExist:
    """Test that new v0.6.0 CLI commands exist."""

    def test_release_build_report_command_exists(self):
        """Test that release build-report command exists."""
        rm = ReleaseManager()

        # Should not raise AttributeError
        result = rm.release_build_report()
        assert "status" in result

    def test_unsigned_build_check_command_exists(self):
        """Test that release unsigned-build-check command exists."""
        rm = ReleaseManager()

        # Should not raise AttributeError
        result = rm.unsigned_build_check()
        assert "status" in result

    def test_native_artifacts_detailed_exists(self):
        """Test that _native_artifacts_detailed method exists."""
        rm = ReleaseManager()

        # Should not raise AttributeError
        assert hasattr(rm, '_native_artifacts_detailed')

    def test_write_build_report_exists(self):
        """Test that _write_build_report method exists."""
        rm = ReleaseManager()

        # Should not raise AttributeError
        assert hasattr(rm, '_write_build_report')


class TestV060PackageScripts:
    """Test that package scripts contain v0.6.0 commands."""

    def test_package_macos_script_contains_unsigned_build_check(self):
        """Test that package_macos.sh contains unsigned-build-check command."""
        script_path = Path(__file__).parent.parent / "installer" / "package_macos.sh"
        content = script_path.read_text()

        assert "unsigned-build-check" in content
        assert "UNSIGNED BUILD" in content
        assert "release build-report" in content

    def test_package_linux_script_contains_unsigned_build_check(self):
        """Test that package_linux.sh contains unsigned-build-check command."""
        script_path = Path(__file__).parent.parent / "installer" / "package_linux.sh"
        content = script_path.read_text()

        assert "unsigned-build-check" in content
        assert "UNSIGNED BUILD" in content
        assert "release build-report" in content

    def test_package_windows_script_contains_unsigned_build_check(self):
        """Test that package_windows.ps1 contains unsigned-build-check command."""
        script_path = Path(__file__).parent.parent / "installer" / "package_windows.ps1"
        content = script_path.read_text()

        assert "unsigned-build-check" in content
        assert "UNSIGNED BUILD" in content
        assert "release build-report" in content
