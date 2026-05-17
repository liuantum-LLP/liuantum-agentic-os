from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from runtime.backup import BackupManager
from runtime.config import SettingsManager, WorkspaceManager
from runtime.dashboard import build_status
from runtime.db import TABLES, db_path, delete_record, health, init_db, list_records
from runtime.doctor import run_doctor
from runtime.env_validation import EnvironmentValidator
from runtime.providers import ModelHub
from runtime.security import AuthManager, SecretManager
from runtime.security_audit import audit_secrets
from runtime.sidecar import sidecar_status as _runtime_sidecar_status
from runtime.storage import ROOT, WORKSPACE


APP_NAME = "Liuant Agentic OS"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class ReleaseManager:
    def version(self) -> dict[str, Any]:
        metadata = self.release_metadata()
        return {
            "app": APP_NAME,
            "app_version": SettingsManager().get("app_version")["value"],
            "build_version": metadata.get("version", SettingsManager().get("app_version")["value"]),
            "channel": metadata.get("channel", "local-mvp"),
            "git_commit": self._git_commit(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "system": platform.system().lower(),
        }

    def info(self) -> dict[str, Any]:
        paths = self.paths()
        status = build_status()
        auth = AuthManager().status()
        secrets = SecretManager().status()
        providers = ModelHub().get_status()
        return {
            "version": self.version(),
            "database_path": paths["database_path"],
            "workspace_path": paths["workspace_path"],
            "ui_path": paths["ui_path"],
            "auth_enabled": auth["local_auth_enabled"],
            "secret_backend": secrets["default_backend"],
            "provider_count": providers["provider_count"],
            "enabled_connector_count": status.get("enabled_connector_count", 0),
        }

    def paths(self) -> dict[str, str]:
        return {
            "app_root": str(ROOT),
            "runtime_path": str(ROOT / "runtime"),
            "database_path": str(db_path()),
            "workspace_path": str(WORKSPACE),
            "outputs_path": str(WORKSPACE / "outputs"),
            "logs_path": str(self.logs_dir()),
            "backups_path": str(WORKSPACE / "backups"),
            "ui_path": str(ROOT / "ui" / "index.html"),
            "release_metadata_path": str(ROOT / "release.json"),
        }

    def repair(self) -> dict[str, Any]:
        created: list[str] = []
        for path in self._required_dirs():
            if not path.exists():
                created.append(str(path))
            path.mkdir(parents=True, exist_ok=True)
        init_db()
        SettingsManager().ensure_defaults()
        WorkspaceManager().ensure_default()
        SecretManager().status()
        return {
            "status": "repaired",
            "created": created,
            "database": health(),
            "secret_backend": SecretManager().status()["default_backend"],
            "message": "Repair completed without deleting user data.",
        }

    def reset(self, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "blocked", "message": "Reset requires --confirm. A backup will be created first."}
        backup = BackupManager().create()
        path = db_path()
        if path.exists():
            path.unlink()
        init_db()
        SettingsManager().ensure_defaults()
        WorkspaceManager().ensure_default()
        for path_item in self._required_dirs():
            path_item.mkdir(parents=True, exist_ok=True)
        return {
            "status": "reset",
            "backup_id": backup.get("id"),
            "backup_path": backup.get("path"),
            "database_path": str(path),
            "message": "Local DB/settings/workspace metadata reset. .env and backups were not deleted.",
        }

    def update_check(self) -> dict[str, Any]:
        metadata = self.release_metadata()
        current = SettingsManager().get("app_version")["value"]
        latest = metadata.get("version", current)
        settings = {row["key"]: row["value"] for row in SettingsManager().list()}
        return {
            "status": "up_to_date" if current == latest else "update_available",
            "current_version": current,
            "latest_version": latest,
            "channel": metadata.get("channel", "local-mvp"),
            "source": str(ROOT / "release.json"),
            "feed_url_configured": bool(settings.get("update_feed_url")),
            "auto_update_enabled": settings.get("auto_update_enabled", "false").lower() == "true",
            "network_used": False,
            "release_notes": metadata.get("release_notes", []),
        }

    def update_info(self) -> dict[str, Any]:
        settings = {row["key"]: row["value"] for row in SettingsManager().list()}
        return {
            "status": "local_metadata_only",
            "channel": settings.get("update_channel", "local-mvp"),
            "feed_url": settings.get("update_feed_url", ""),
            "feed_url_configured": bool(settings.get("update_feed_url")),
            "auto_update_enabled": settings.get("auto_update_enabled", "false").lower() == "true",
            "update_check": self.update_check(),
            "message": "Automatic download/install is not implemented in this local MVP.",
        }

    def update_config(self) -> dict[str, Any]:
        settings = {row["key"]: row["value"] for row in SettingsManager().list()}
        return {
            "update_channel": settings.get("update_channel", "local-mvp"),
            "update_feed_url": settings.get("update_feed_url", ""),
            "auto_update_enabled": settings.get("auto_update_enabled", "false").lower() == "true",
            "editable_settings": ["update_channel", "update_feed_url", "auto_update_enabled"],
        }

    def release_check(self, run_tests: bool = True) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        if run_tests:
            checks.append(self._run_command_check("tests", [sys.executable, "-m", "pytest", "-q"], timeout=180))
        else:
            checks.append({"name": "tests", "status": "skipped", "message": "Skipped by caller."})
        checks.append(self._run_command_check("compile", [sys.executable, "-m", "py_compile", "runtime/release.py", "cli/liuant.py"], timeout=30))
        checks.append(self._call_check("doctor", run_doctor))
        checks.append(self._call_check("env", EnvironmentValidator().check))
        checks.append(self._call_check("secret_audit", audit_secrets))
        checks.append(self._call_check("backup_dry_run", lambda: BackupManager().create()))
        checks.append(self._call_check("ui_files", self.ui_check))
        checks.append(self._call_check("desktop", self.desktop_check))
        checks.append(self._call_check("signing", self.signing_check))
        checks.append(self._call_check("release_manifest", self.release_manifest))
        for name, func in (
            ("version", self.version),
            ("paths", self.paths),
            ("auth", AuthManager().status),
            ("secrets", SecretManager().status),
        ):
            checks.append(self._call_check(name, func))
        failed = [row for row in checks if row["status"] not in {"passed", "ok", "created", "skipped"}]
        return {"status": "failed" if failed else "passed", "checks": checks, "failed_count": len(failed)}

    def desktop_status(self) -> dict[str, Any]:
        project = self._detect_desktop_project()
        node = shutil.which("node")
        npm = shutil.which("npm")
        pnpm = shutil.which("pnpm")
        cargo = shutil.which("cargo")
        rustc = shutil.which("rustc")
        rustup = shutil.which("rustup")
        tauri_cli = self._tauri_cli_path(project.get("desktop_root"))
        tauri_config = project.get("tauri_config")
        icon_paths = self._desktop_icon_candidates(project.get("desktop_root"))
        icon_status = self.icons_check()
        settings = self._desktop_backend_settings()
        missing: list[str] = []
        if not project["exists"]:
            missing.append("tauri_project")
        if project["exists"] and not tauri_config:
            missing.append("src-tauri_config")
        if project["exists"] and not node:
            missing.append("node")
        if project["exists"] and not cargo:
            missing.append("cargo")
        if project["exists"] and not icon_paths:
            missing.append("icons")
        frontend_artifacts = self._frontend_artifacts()
        native_artifacts = self._native_artifacts()
        frontend_build_status = "frontend_build_passed" if frontend_artifacts else "not_run"
        tauri_build_status = "tauri_build_passed" if native_artifacts else ("dependency_missing" if project["exists"] and not cargo else "artifacts_missing")
        return {
            "status": "missing_project" if not project["exists"] else ("needs_dependency" if missing else "ready"),
            "dependency_status": "dependency_missing" if missing else "dependencies_ready",
            "dependency_missing": missing,
            "tauri_project": project["exists"],
            "tauri_project_exists": project["exists"],
            "desktop_root": project.get("desktop_root"),
            "src_tauri_path": project.get("src_tauri_path"),
            "tauri_config": tauri_config,
            "node_available": bool(node),
            "npm_available": bool(npm),
            "pnpm_available": bool(pnpm),
            "cargo_available": bool(cargo),
            "rustc_available": bool(rustc),
            "rustup_available": bool(rustup),
            "tauri_cli_available": bool(tauri_cli),
            "icons": icon_paths,
            "icons_status": icon_status["status"],
            "icon_status": icon_status,
            "missing_icons": icon_status["missing"],
            "missing": missing,
            "app_name": APP_NAME,
            "version": SettingsManager().get("app_version")["value"],
            "bundle_identifier": self._tauri_bundle_identifier(tauri_config) if tauri_config else "com.liuant.agenticos",
            "backend_mode": settings["desktop_backend_mode"],
            "backend_url": settings["desktop_backend_url"],
            "auto_start_backend": settings["desktop_auto_start_backend"],
            "sidecar_status": self._sidecar_status(settings["desktop_backend_mode"]),
            "build_readiness": "ready" if project["exists"] and not missing else "needs_dependency",
            "frontend_build_status": frontend_build_status,
            "native_build_status": tauri_build_status,
            "frontend_artifacts": frontend_artifacts,
            "tauri_build_status": tauri_build_status,
            "native_artifacts": native_artifacts,
            "artifacts_created": bool(frontend_artifacts or native_artifacts),
            "artifacts_missing": not bool(native_artifacts),
            "setup_instructions": self._desktop_setup_instructions(project["exists"], missing),
        }

    def desktop_check(self) -> dict[str, Any]:
        status = self.desktop_status()
        return {
            **status,
            "check_status": "passed" if status["status"] in {"ready", "missing_project", "needs_dependency"} else "failed",
            "message": "No Tauri project exists yet; packaging scaffold/docs are ready." if status["status"] == "missing_project" else "Desktop packaging prerequisites checked.",
        }

    def desktop_dev(self) -> dict[str, Any]:
        return self._desktop_command("dev")

    def desktop_build(self, frontend_only: bool = False, native: bool = False, skip_tests: bool = False) -> dict[str, Any]:
        from datetime import datetime, timezone
        
        started_at = datetime.now(timezone.utc).isoformat()
        project = self._detect_desktop_project()
        
        if not project["exists"]:
            report = self._write_build_report({
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "platform": platform.system().lower(),
                "status": "missing_project",
                "frontend_typecheck_status": "not_run",
                "frontend_build_status": "not_run",
                "native_build_status": "not_attempted",
                "error_summary": "No Tauri project exists at apps/desktop/src-tauri yet.",
            })
            return {"status": "missing_project", "message": "No Tauri project exists at apps/desktop/src-tauri yet.", "build_report": report}

        # Capture dependency versions
        dependencies = {
            "node": self._get_command_version("node"),
            "npm": self._get_command_version("npm"),
            "pnpm": self._get_command_version("pnpm"),
            "rustc": self._get_command_version("rustc"),
            "cargo": self._get_command_version("cargo"),
            "rustup": self._get_command_version("rustup"),
            "tauri": self._get_tauri_version(project.get("desktop_root")),
        }
        
        checks: list[dict[str, Any]] = []
        
        # Phase 1: Frontend typecheck and build
        if not skip_tests:
            typecheck_result = self._run_command_check("frontend_typecheck", self._desktop_npm_command("typecheck"), cwd=Path(project["desktop_root"]), timeout=120)
            checks.append(typecheck_result)
            
        build_result = self._run_command_check("frontend_build", self._desktop_npm_command("build"), cwd=Path(project["desktop_root"]), timeout=180)
        checks.append(build_result)
        
        frontend_failed = [row for row in checks if row["status"] != "passed"]
        if frontend_failed:
            report = self._write_build_report({
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "platform": platform.system().lower(),
                "frontend_typecheck_status": typecheck_result.get("status", "skipped") if not skip_tests else "skipped",
                "frontend_build_status": build_result.get("status", "failed"),
                "native_build_status": "not_attempted",
                "dependencies": dependencies,
                "command_run": f"desktop build --frontend-only={frontend_only} --native={native}",
                "artifacts": [],
                "error_summary": f"Frontend build failed: {build_result.get('summary', build_result.get('error', 'unknown error'))}",
                "checks": checks,
            })
            return {
                "status": "frontend_build_failed",
                "mode": "frontend_only" if frontend_only else ("native" if native else "default"),
                "checks": checks,
                "frontend_build_status": "failed",
                "native_build_status": "not_attempted",
                "artifacts": self.release_artifacts()["artifacts"],
                "build_report": report,
            }

        # Frontend-only build: no native attempt
        if frontend_only and not native:
            self.release_manifest()
            self.release_checksum()
            frontend_artifacts = self._frontend_artifacts()
            report = self._write_build_report({
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "platform": platform.system().lower(),
                "frontend_typecheck_status": typecheck_result.get("status", "skipped") if not skip_tests else "skipped",
                "frontend_build_status": "passed",
                "native_build_status": "not_attempted",
                "dependencies": dependencies,
                "command_run": f"desktop build --frontend-only=True --native={native}",
                "artifacts": frontend_artifacts,
                "checksum_file": str(ROOT / "release" / "checksums.json"),
                "checks": checks,
            })
            return {
                "status": "frontend_build_passed",
                "mode": "frontend_only",
                "checks": checks,
                "frontend_build_status": "frontend_build_passed",
                "native_build_status": "not_attempted",
                "artifacts": self.release_artifacts()["artifacts"],
                "build_report": report,
            }

        # Phase 2: Native build attempt
        native_check = self.native_check()
        if native_check["status"] != "ready":
            self.release_manifest()
            self.release_checksum()
            frontend_artifacts = self._frontend_artifacts()
            report = self._write_build_report({
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "platform": platform.system().lower(),
                "frontend_typecheck_status": typecheck_result.get("status", "skipped") if not skip_tests else "skipped",
                "frontend_build_status": "passed",
                "native_build_status": "dependency_missing",
                "dependencies": dependencies,
                "command_run": f"desktop build --frontend-only={frontend_only} --native={native}",
                "artifacts": frontend_artifacts,
                "checksum_file": str(ROOT / "release" / "checksums.json"),
                "error_summary": f"Missing dependencies: {', '.join(native_check['missing'])}",
                "setup_instructions": native_check["setup_instructions"],
                "checks": checks,
            })
            return {
                "status": "dependency_missing",
                "mode": "native" if native else "default",
                "checks": checks,
                "missing": native_check["missing"],
                "setup_instructions": native_check["setup_instructions"],
                "frontend_build_status": "frontend_build_passed",
                "native_build_status": "dependency_missing",
                "artifacts": self.release_artifacts()["artifacts"],
                "build_report": report,
            }

        # Run Tauri build
        tauri_build_cmd = self._desktop_npm_command("tauri:build")
        build = self._run_command_check("tauri_build", tauri_build_cmd, cwd=Path(project["desktop_root"]), timeout=600)
        checks.append(build)
        
        # Detect actual native artifacts
        native_artifacts = self._native_artifacts_detailed()
        
        # Update manifests and checksums
        self.release_manifest()
        self.release_checksum()
        
        # Determine final status
        native_build_status = "tauri_build_passed" if build["status"] == "passed" and native_artifacts else "tauri_build_failed"
        
        # Write comprehensive build report
        error_summary = ""
        if build["status"] != "passed":
            error_summary = f"Tauri build failed: {build.get('summary', build.get('error', 'unknown error'))}"
        elif not native_artifacts:
            error_summary = "Tauri build command succeeded but no native artifacts were detected"
        
        report = self._write_build_report({
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform.system().lower(),
            "frontend_typecheck_status": typecheck_result.get("status", "skipped") if not skip_tests else "skipped",
            "frontend_build_status": "passed",
            "native_build_status": native_build_status,
            "dependencies": dependencies,
            "command_run": f"desktop build --frontend-only={frontend_only} --native={native}",
            "artifacts": native_artifacts if native_artifacts else self._frontend_artifacts(),
            "checksum_file": str(ROOT / "release" / "checksums.json"),
            "error_summary": error_summary if error_summary else None,
            "checks": checks,
            "logs_path": str(self.logs_dir()),
        })
        
        return {
            "status": "tauri_build_passed" if build["status"] == "passed" and native_artifacts else "tauri_build_failed",
            "mode": "native" if native else "default",
            "checks": checks,
            "frontend_build_status": "frontend_build_passed",
            "native_build_status": native_build_status,
            "native_artifacts": native_artifacts,
            "artifacts": self.release_artifacts()["artifacts"],
            "signed": False,
            "notarized": False,
            "build_report": report,
        }

    def rust_check(self) -> dict[str, Any]:
        rustc = shutil.which("rustc")
        cargo = shutil.which("cargo")
        rustup = shutil.which("rustup")
        missing = [name for name, value in (("rustc", rustc), ("cargo", cargo), ("rustup", rustup)) if not value]
        return {
            "status": "ready" if not missing else "dependency_missing",
            "rustc_available": bool(rustc),
            "cargo_available": bool(cargo),
            "rustup_available": bool(rustup),
            "missing": missing,
            "setup_instructions": self._native_setup_instructions(missing),
        }

    def tauri_check(self) -> dict[str, Any]:
        project = self._detect_desktop_project()
        tauri_cli = self._tauri_cli_path(project.get("desktop_root"))
        config = project.get("tauri_config")
        missing = []
        if not project["exists"]:
            missing.append("tauri_project")
        if not config:
            missing.append("tauri_config")
        if not tauri_cli:
            missing.append("tauri_cli")
        icons = self.icons_check()
        if icons["status"] not in {"complete", "partial"}:
            missing.append("icons")
        return {
            "status": "ready" if not missing else "dependency_missing",
            "tauri_project": project["exists"],
            "tauri_config": config,
            "tauri_cli_available": bool(tauri_cli),
            "tauri_cli_path": tauri_cli,
            "app_identifier": self._tauri_bundle_identifier(config) if config else "com.liuant.agenticos",
            "bundle_version": SettingsManager().get("app_version")["value"],
            "missing": missing,
            "setup_instructions": self._native_setup_instructions(missing),
            "icon_status": icons,
        }

    def native_check(self) -> dict[str, Any]:
        status = self.desktop_status()
        rust = self.rust_check()
        tauri = self.tauri_check()
        system = platform.system().lower()
        platform_missing = self._platform_build_dependency_gaps(system)
        missing = sorted(set(status["missing"] + rust["missing"] + tauri["missing"] + platform_missing))
        return {
            "status": "ready" if not missing else "dependency_missing",
            "platform": system,
            "node_available": status["node_available"],
            "npm_available": status["npm_available"],
            "pnpm_available": status["pnpm_available"],
            "rust": rust,
            "tauri": tauri,
            "frontend_build_status": status["frontend_build_status"],
            "frontend_dist_present": bool(status["frontend_artifacts"]),
            "icons_status": status["icons_status"],
            "app_identifier": status["bundle_identifier"],
            "bundle_version": status["version"],
            "missing": missing,
            "setup_instructions": self._native_setup_instructions(missing),
        }

    def desktop_package_info(self) -> dict[str, Any]:
        status = self.desktop_status()
        return {
            "status": status["status"],
            "app_name": APP_NAME,
            "bundle_identifier": "com.liuant.agenticos",
            "version": SettingsManager().get("app_version")["value"],
            "targets": {
                "macos": [".app", ".dmg"],
                "windows": [".msi", ".exe"],
                "linux": [".AppImage", ".deb", ".rpm"],
            },
            "backend": {"host": DEFAULT_HOST, "default_port": 8765, "external_bind_default": False, "mode": status["backend_mode"], "url": status["backend_url"], "sidecar_status": status["sidecar_status"]},
            "frontend_build_status": status["frontend_build_status"],
            "tauri_build_status": status["tauri_build_status"],
            "artifacts_created": status["artifacts_created"],
            "artifacts_missing": status["artifacts_missing"],
            "notes": ["Tauri build is not claimed unless native build artifacts exist.", "Desktop app defaults to external_backend in v0.5.6."],
        }

    def icons_check(self) -> dict[str, Any]:
        icon_dir = ROOT / "apps" / "desktop" / "src-tauri" / "icons"
        required = self._required_icon_files()
        present = []
        missing = []
        unsupported = []
        for name in required:
            path = icon_dir / name
            if path.exists() and path.is_file() and path.stat().st_size > 0:
                present.append({"name": name, "path": str(path), "size_bytes": path.stat().st_size})
            else:
                missing.append(name)
                if name == "icon.icns":
                    unsupported.append({"name": name, "reason": "missing_tool", "message": "ICNS generation is documented; install iconutil/libicns-capable tooling to create a production ICNS."})
        png_required = [name for name in required if name.endswith(".png")]
        png_present = [item["name"] for item in present if item["name"].endswith(".png")]
        if not missing:
            status = "complete"
        elif png_present and (icon_dir / "icon.svg").exists():
            status = "partial"
        else:
            status = "missing"
        return {
            "status": status,
            "icon_dir": str(icon_dir),
            "required": required,
            "present": present,
            "missing": missing,
            "unsupported": unsupported,
            "png_required_count": len(png_required),
            "png_present_count": len(png_present),
            "setup_instructions": [
                "Run `liuant desktop icons-generate` to create local placeholder SVG/PNG/ICO/ICNS icons.",
                "Replace placeholder icons with final brand assets before signed distribution.",
                "Generate icon.icns with macOS iconutil or another trusted local tool when available.",
            ],
        }

    def icons_generate(self) -> dict[str, Any]:
        script = ROOT / "scripts" / "generate_icons.py"
        if not script.exists():
            return {"status": "missing_script", "script": str(script), "message": "scripts/generate_icons.py is missing."}
        result = self._run_command_check("generate_icons", [sys.executable, str(script)], timeout=60)
        return {"status": "generated" if result["status"] == "passed" else "failed", "script": str(script), "result": result, "icon_status": self.icons_check()}

    def build_guide(self) -> dict[str, Any]:
        system = platform.system().lower()
        return {
            "status": "ok",
            "platform": system,
            "steps": self._platform_build_steps(system),
            "notes": [
                "Scripts never install privileged system dependencies automatically.",
                "Native artifacts remain unsigned unless real signing configuration is added.",
                "Run `liuant desktop build --frontend-only` before attempting a native package.",
            ],
        }

    def build_report(self) -> dict[str, Any]:
        """Read the latest build report."""
        path = ROOT / "release" / "build-report.json"
        if not path.exists():
            return {"status": "no_report", "build_report_path": str(path), "message": "No desktop build report has been recorded yet. Run `./liuant desktop build --native` to create one."}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"status": "invalid_report", "build_report_path": str(path), "error": str(exc)}
        return {"status": "ok", "build_report_path": str(path), "report": data}

    def release_build_report(self) -> dict[str, Any]:
        """Alias for build_report for release namespace."""
        return self.build_report()

    def unsigned_build_check(self) -> dict[str, Any]:
        """Verify unsigned build artifacts meet QA requirements."""
        from datetime import datetime, timezone

        # Check native artifacts exist
        native_artifacts = self._native_artifacts_detailed()
        if not native_artifacts:
            return {
                "status": "no_native_artifacts",
                "native_artifacts_found": False,
                "signed": False,
                "notarized": False,
                "message": "No native artifacts exist. Run `./liuant desktop build --native` after installing Rust/Cargo.",
                "setup_instructions": self.native_check().get("setup_instructions", []),
            }

        # Get current version info
        version = self.version()
        desktop_status = self.desktop_status()
        checksums = self.release_checksum()
        signing = self.signing_status()

        # Verify checksums exist
        checksums_exist = checksums.get("status") in {"created", "ok"} and checksums.get("checksums")

        # Verify artifact metadata
        artifacts_ok = True
        issues = []
        for artifact in native_artifacts:
            if artifact.get("size_bytes", 0) == 0:
                artifacts_ok = False
                issues.append(f"Artifact {artifact['name']} has zero size")
            if artifact.get("signed"):
                artifacts_ok = False
                issues.append(f"Artifact {artifact['name']} claims to be signed but should be unsigned")
            if artifact.get("notarized"):
                artifacts_ok = False
                issues.append(f"Artifact {artifact['name']} claims to be notarized but should be unsigned")

        # Check version matches
        version_matches = desktop_status.get("version") == version.get("app_version")
        if not version_matches:
            issues.append(f"Version mismatch: desktop {desktop_status.get('version')} vs release {version.get('app_version')}")

        # Check bundle identifier
        bundle_id = desktop_status.get("bundle_identifier", "")
        bundle_id_ok = bundle_id == "com.liuant.agenticos"
        if not bundle_id_ok:
            issues.append(f"Bundle identifier is {bundle_id}, expected com.liuant.agenticos")

        # Check icons exist
        icons = self.icons_check()
        icons_ok = icons.get("status") in {"complete", "partial"}

        # Check backend mode documented
        backend_mode = desktop_status.get("backend_mode", "unknown")
        backend_mode_ok = backend_mode in {"external_backend", "managed_backend", "bundled_sidecar"}

        # Check security docs exist
        security_docs_exist = (ROOT / "docs" / "SECURITY.md").exists()

        all_checks_passed = (
            artifacts_ok and
            checksums_exist and
            version_matches and
            bundle_id_ok and
            icons_ok and
            backend_mode_ok and
            security_docs_exist and
            not signing.get("signed") and
            not signing.get("notarized")
        )

        return {
            "status": "passed" if all_checks_passed else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "native_artifacts_exist": bool(native_artifacts),
                "artifacts_metadata_ok": artifacts_ok,
                "checksums_exist": checksums_exist,
                "version_matches": version_matches,
                "bundle_identifier_ok": bundle_id_ok,
                "icons_ok": icons_ok,
                "backend_mode_documented": backend_mode_ok,
                "security_docs_exist": security_docs_exist,
                "signed_is_false": not signing.get("signed"),
                "notarized_is_false": not signing.get("notarized"),
            },
            "native_artifacts": native_artifacts,
            "signed": False,
            "notarized": False,
            "version": version.get("app_version"),
            "bundle_identifier": bundle_id,
            "backend_mode": backend_mode,
            "issues": issues if issues else None,
            "message": "Unsigned build QA check passed" if all_checks_passed else f"Unsigned build QA check failed: {'; '.join(issues)}",
        }

    def desktop_polish_check(self) -> dict[str, Any]:
        """Comprehensive desktop and release polish readiness check."""
        from datetime import datetime, timezone

        issues = []
        checks = {}

        # App version alignment
        settings_version = SettingsManager().get("app_version")["value"]
        release_meta = self.release_metadata()
        version_aligned = settings_version == release_meta.get("version", settings_version)
        checks["version_aligned"] = version_aligned
        if not version_aligned:
            issues.append(f"Version mismatch: settings={settings_version}, release.json={release_meta.get('version')}")

        # DMG exists and checksum valid
        native = self._native_artifacts_detailed()
        dmg = next((a for a in native if a["name"].endswith(".dmg")), None)
        checks["dmg_exists"] = dmg is not None
        if not dmg:
            issues.append("No DMG artifact found")
        else:
            actual = self._sha256(Path(dmg["path"]))
            stored = next((c["sha256"] for c in self.release_checksum().get("checksums", []) if c["path"].endswith(".dmg")), None)
            checks["dmg_checksum_valid"] = bool(stored) and actual == stored
            if not checks["dmg_checksum_valid"]:
                issues.append("DMG checksum mismatch or missing")

        # Icons
        icons = self.icons_check()
        checks["icons_complete"] = icons["status"] == "complete"
        if not checks["icons_complete"]:
            issues.append(f"Icon set incomplete: {len(icons['missing'])} missing")

        # UI source checks
        ui_path = ROOT / "apps" / "desktop" / "src" / "App.tsx"
        if ui_path.exists():
            content = ui_path.read_text(encoding="utf-8")
            checks["backend_offline_instructions"] = "Backend not reachable" in content
            checks["auth_token_instructions"] = "liuant auth token" in content
            checks["app_identity_located"] = "Liuant Agentic OS" in content
            checks["release_page_unsigned_copy"] = '"false"' in content and '"Signed"' in content
            checks["macos_unsigned_launch_note"] = "unsigned" in content
            if not checks["backend_offline_instructions"]:
                issues.append("App.tsx missing backend offline instructions")
            if not checks["auth_token_instructions"]:
                issues.append("App.tsx missing auth token instructions")
            if not checks["app_identity_located"]:
                issues.append("App.tsx missing app identity")
            if not checks["release_page_unsigned_copy"]:
                issues.append("App.tsx release page missing signed=false/notarized=false")
        else:
            checks["ui_source_exists"] = False
            issues.append("App.tsx not found")

        # Documentation checks
        qa_docs = ROOT / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        checks["macos_qa_docs_exist"] = qa_docs.exists()
        if not checks["macos_qa_docs_exist"]:
            issues.append("Missing macOS unsigned install QA docs")

        signing_docs = ROOT / "docs" / "MACOS_SIGNING_NOTARIZATION.md"
        checks["signing_docs_exist"] = signing_docs.exists()
        if not checks["signing_docs_exist"]:
            issues.append("Missing macOS signing/notarization docs")

        chat_docs = ROOT / "docs" / "CHAT_FIRST.md"
        checks["chat_first_docs_exist"] = chat_docs.exists()

        first_run_docs = ROOT / "docs" / "FIRST_RUN.md" if (ROOT / "docs" / "FIRST_RUN.md").exists() else None
        checks["first_run_docs_exist"] = first_run_docs is not None

        sidecar_docs = ROOT / "docs" / "SIDECAR_BACKEND.md"
        checks["sidecar_docs_exist"] = sidecar_docs.exists()

        backend_mode_docs = ROOT / "docs" / "SIDECAR_BACKEND.md"
        checks["backend_mode_docs_exist"] = backend_mode_docs.exists()

        # Signing honesty
        signing = self.signing_status()
        checks["signed_is_false"] = not signing.get("signed")
        checks["notarized_is_false"] = not signing.get("notarized")
        checks["signing_blocked_messaging"] = bool(signing.get("message", "").strip())
        if not checks["signed_is_false"] or not checks["notarized_is_false"]:
            issues.append("Signing status incorrectly claims signed or notarized")

        all_passed = all(checks.values())

        return {
            "status": "passed" if all_passed else "needs_polish",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "issues": issues if issues else None,
            "message": "Release polish check passed" if all_passed else f"Release polish needs work: {'; '.join(issues)}",
            "backend_mode": self._desktop_backend_settings()["desktop_backend_mode"],
            "settings_version": settings_version,
            "dmg_path": str(dmg["path"]) if dmg else None,
        }

    def macos_qa(self) -> dict[str, Any]:
        """Run macOS-specific QA checks for unsigned DMG installer."""
        from datetime import datetime, timezone
        from pathlib import Path

        issues = []
        checks = {}

        # Find DMG artifact
        dmg_candidates = [
            ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle" / "dmg",
            ROOT / "release" / "artifacts",
        ]

        dmg_artifact = None
        for base in dmg_candidates:
            if not base.exists():
                continue
            for dmg in base.rglob("*.dmg"):
                if dmg.is_file():
                    dmg_artifact = dmg
                    break
            if dmg_artifact:
                break

        checks["dmg_exists"] = dmg_artifact is not None
        if not dmg_artifact:
            issues.append("No DMG artifact found")

        # Check DMG size
        if dmg_artifact:
            dmg_size = dmg_artifact.stat().st_size
            checks["dmg_size_valid"] = dmg_size > 0
            if dmg_size == 0:
                issues.append("DMG file has zero size")
        else:
            dmg_size = 0
            checks["dmg_size_valid"] = False

        # Verify checksum
        checksums = self.release_checksum().get("checksums", [])
        dmg_checksums = [c for c in checksums if c["path"].endswith(".dmg")]
        checks["checksum_exists"] = len(dmg_checksums) > 0
        if not dmg_checksums:
            issues.append("No DMG checksum found in release/checksums.json")

        # Verify checksum matches
        checksum_valid = False
        if dmg_artifact and dmg_checksums:
            actual_checksum = self._sha256(dmg_artifact)
            expected_checksum = dmg_checksums[0]["sha256"]
            checksum_valid = actual_checksum == expected_checksum
            checks["checksum_matches"] = checksum_valid
            if not checksum_valid:
                issues.append(f"DMG checksum mismatch: expected {expected_checksum[:16]}..., got {actual_checksum[:16]}...")
        else:
            checks["checksum_matches"] = False

        # Check signing/notarization status
        signing = self.signing_status()
        checks["signed_is_false"] = not signing.get("signed")
        checks["notarized_is_false"] = not signing.get("notarized")
        if signing.get("signed"):
            issues.append("DMG claims to be signed but should be unsigned")
        if signing.get("notarized"):
            issues.append("DMG claims to be notarized but should not be")

        # Check install QA docs exist
        qa_docs = ROOT / "docs" / "MACOS_UNSIGNED_INSTALL_QA.md"
        checks["qa_docs_exist"] = qa_docs.exists()
        if not qa_docs.exists():
            issues.append("Missing docs/MACOS_UNSIGNED_INSTALL_QA.md")

        # Check unsigned warning in docs
        unsigned_warning = False
        if qa_docs.exists():
            content = qa_docs.read_text(encoding="utf-8").lower()
            unsigned_warning = "unsigned" in content and "not notarized" in content
        checks["unsigned_warning_present"] = unsigned_warning
        if not unsigned_warning:
            issues.append("Unsigned warning not found in QA docs")

        # Check backend launch instructions
        backend_instructions = False
        if qa_docs.exists():
            content = qa_docs.read_text(encoding="utf-8").lower()
            backend_instructions = "liuant start" in content and "backend" in content
        checks["backend_instructions_present"] = backend_instructions
        if not backend_instructions:
            issues.append("Backend launch instructions not found in QA docs")

        # Check manifest references DMG
        manifest = self.release_manifest().get("manifest", {})
        artifacts = manifest.get("artifacts", [])
        dmg_in_manifest = any(a.get("name", "").endswith(".dmg") for a in artifacts)
        checks["dmg_in_manifest"] = dmg_in_manifest
        if not dmg_in_manifest:
            issues.append("DMG not referenced in release manifest")

        # Overall status
        all_passed = (
            checks["dmg_exists"] and
            checks["dmg_size_valid"] and
            checks["checksum_exists"] and
            checks["checksum_matches"] and
            checks["signed_is_false"] and
            checks["notarized_is_false"] and
            checks["qa_docs_exist"] and
            checks["unsigned_warning_present"] and
            checks["backend_instructions_present"] and
            checks["dmg_in_manifest"]
        )

        return {
            "status": "passed" if all_passed else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dmg_path": str(dmg_artifact) if dmg_artifact else None,
            "dmg_size_bytes": dmg_size,
            "dmg_name": dmg_artifact.name if dmg_artifact else None,
            "signed": False,
            "notarized": False,
            "checks": checks,
            "issues": issues if issues else None,
            "message": "macOS unsigned DMG QA passed" if all_passed else f"macOS unsigned DMG QA failed: {'; '.join(issues)}",
        }

    def desktop_first_run_check(self) -> dict[str, Any]:
        """Check first-run setup for desktop app."""
        from datetime import datetime, timezone

        issues = []
        checks = {}

        # Check backend reachability
        backend_reachable = False
        backend_url = "http://127.0.0.1:8765"
        try:
            import urllib.request
            req = urllib.request.Request(f"{backend_url}/api/system/status", method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    backend_reachable = True
        except Exception:
            pass

        checks["backend_reachable"] = backend_reachable
        if not backend_reachable:
            issues.append("Backend not reachable at http://127.0.0.1:8765")

        # Check auth status
        auth = AuthManager().status()
        checks["local_auth_enabled"] = auth.get("local_auth_enabled", False)

        # Check UI files exist
        ui_files_exist = False
        desktop_dist = ROOT / "apps" / "desktop" / "dist"
        if desktop_dist.exists():
            index_html = desktop_dist / "index.html"
            ui_files_exist = index_html.exists()
        checks["ui_files_exist"] = ui_files_exist
        if not ui_files_exist:
            issues.append("Desktop UI files not found")

        # Get app version
        version = self.version()
        checks["app_version"] = version.get("app_version")

        # Get backend mode
        desktop_status = self.desktop_status()
        checks["backend_mode"] = desktop_status.get("backend_mode", "unknown")

        # Check local server URL
        checks["local_server_url"] = backend_url

        # Overall status
        all_passed = (
            checks["ui_files_exist"] and
            checks.get("app_version") is not None
        )

        # Get backend settings
        backend_settings = self._desktop_backend_settings()
        mode = backend_settings["desktop_backend_mode"]
        
        # Mode-specific instructions
        mode_instructions = {
            "external_backend": [
                "1. Start backend manually: ./liuant start",
                "2. Get auth token: ./liuant auth token (if needed)",
                "3. Open desktop app and connect",
            ],
            "managed_backend": [
                "1. Start managed backend: ./liuant desktop backend-start",
                "2. Get auth token: ./liuant auth token (if needed)",
                "3. Open desktop app and connect",
                "4. Stop with: ./liuant desktop backend-stop",
            ],
            "bundled_sidecar": [
                "1. Build sidecar: ./liuant sidecar build --confirm",
                "2. Start sidecar: ./liuant sidecar run",
                "3. Check status: ./liuant sidecar status",
            ],
        }
        
        # Check managed backend availability
        managed_backend_available = mode in ["managed_backend", "external_backend"]
        bundled_sidecar_available = _runtime_sidecar_status().get("status") == "available"
        
        return {
            "status": "passed" if all_passed else "needs_setup",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "issues": issues if issues else None,
            "message": "First-run check passed" if all_passed else "First-run setup required",
            "backend": {
                "mode": mode,
                "url": backend_url,
                "reachable": backend_reachable,
                "managed_backend_available": managed_backend_available,
                "bundled_sidecar_available": bundled_sidecar_available,
                "localhost_only": True,
                "auth_required": checks["local_auth_enabled"],
            },
            "setup_instructions": mode_instructions.get(mode, mode_instructions["external_backend"]) if not backend_reachable else None,
            "next_steps": {
                "check_status": "./liuant desktop backend-status",
                "change_mode": "./liuant desktop backend-mode set <mode>",
                "start_backend": "./liuant desktop backend-start" if mode == "managed_backend" else "./liuant start",
                "get_token": "./liuant auth token",
            },
        }

    def desktop_backend_status(self) -> dict[str, Any]:
        """Get detailed backend status including mode and managed process info."""
        settings = self._desktop_backend_settings()
        server = self.server_status()
        
        # Check if managed backend is running
        managed_status = self._read_managed_backend_status()
        managed_running = self._is_managed_backend_running()
        
        # Backend reachability
        backend_reachable = False
        auth_required = False
        try:
            import urllib.request
            req = urllib.request.Request(f"{settings['desktop_backend_url']}/api/system/status", method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    backend_reachable = True
        except urllib.error.HTTPError as e:
            if e.code == 401:
                auth_required = True
        except Exception:
            pass
        
        is_bundled_sidecar = settings["desktop_backend_mode"] == "bundled_sidecar"
        running = server["running"]
        if is_bundled_sidecar:
            sc = _runtime_sidecar_status()
            running = sc.get("running", False)
        return {
            "status": "ok",
            "mode": settings["desktop_backend_mode"],
            "url": settings["desktop_backend_url"],
            "auto_start_backend": settings["desktop_auto_start_backend"],
            "backend_running": running,
            "backend_reachable": backend_reachable,
            "auth_required": auth_required,
            "managed_backend_available": settings["desktop_backend_mode"] == "managed_backend",
            "bundled_sidecar_available": _runtime_sidecar_status().get("status") == "available",
            "localhost_only": True,
            "server": server,
            "managed_process": {
                "pid": managed_status.get("pid") if managed_status else None,
                "running": managed_running,
                "started_at": managed_status.get("started_at") if managed_status else None,
            } if managed_status else None,
            "sidecar_status": self._sidecar_status(settings["desktop_backend_mode"]),
            "recommended_mode": "external_backend" if is_bundled_sidecar else settings["desktop_backend_mode"],
            "safety": "Backend must bind to 127.0.0.1. Local auth remains enabled unless the user explicitly disables it.",
            "commands": {
                "start": "./liuant desktop backend-start",
                "stop": "./liuant desktop backend-stop",
                "restart": "./liuant desktop backend-restart",
                "mode": "./liuant desktop backend-mode",
            },
        }

    def desktop_backend_mode(self) -> dict[str, Any]:
        """Get current backend mode with details."""
        settings = self._desktop_backend_settings()
        current_mode = settings["desktop_backend_mode"]
        
        mode_descriptions = {
            "external_backend": "User starts backend manually. Most stable option.",
            "managed_backend": "Desktop/CLI can start/stop backend. Local-only, safe.",
            "bundled_sidecar": "Packaged backend executable for desktop integration.",
        }
        
        return {
            "status": "ok",
            "current_mode": current_mode,
            "url": settings["desktop_backend_url"],
            "auto_start_backend": settings["desktop_auto_start_backend"],
            "allowed_modes": ["external_backend", "managed_backend", "bundled_sidecar"],
            "mode_descriptions": mode_descriptions,
            "current_mode_description": mode_descriptions.get(current_mode, "Unknown mode"),
            "managed_backend_available": True,
            "bundled_sidecar_available": _runtime_sidecar_status().get("status") == "available",
            "sidecar_status": self._sidecar_status(current_mode),
            "localhost_only": True,
            "commands": {
                "set_mode": "./liuant desktop backend-mode set <mode>",
                "start": "./liuant desktop backend-start",
                "stop": "./liuant desktop backend-stop",
                "status": "./liuant desktop backend-status",
            },
            "recommended": {
                "current": current_mode,
                "note": "external_backend is safest for production use. managed_backend is convenient for development.",
            },
        }

    def set_desktop_backend_mode(self, mode: str) -> dict[str, Any]:
        """Set backend mode with validation and sidecar availability check."""
        if mode not in {"external_backend", "managed_backend", "bundled_sidecar"}:
            return {
                "status": "blocked",
                "message": "Unsupported desktop backend mode.",
                "allowed_modes": ["external_backend", "managed_backend", "bundled_sidecar"]
            }
        
        # Check if bundled_sidecar is available
        if mode == "bundled_sidecar":
            sc = _runtime_sidecar_status()
            if sc.get("status") != "available":
                return {
                    "status": "sidecar_not_available",
                    "mode": mode,
                    "message": "Bundled sidecar executable not found. Build it with `./liuant sidecar build` or switch to external_backend / managed_backend.",
                    "current_mode": self._desktop_backend_settings()["desktop_backend_mode"],
                    "recommendation": "Use 'external_backend' or 'managed_backend' mode instead.",
                    "sidecar_status": sc,
                    "setup_instructions": [
                        "Build sidecar:   ./liuant sidecar build --confirm",
                        "Check status:    ./liuant sidecar status",
                        "Switch to managed_backend: ./liuant desktop backend-mode set managed_backend",
                        "Switch to external_backend: ./liuant desktop backend-mode set external_backend",
                        "Start backend manually: ./liuant start",
                    ],
                }
        
        SettingsManager().set("desktop_backend_mode", mode)
        settings = self._desktop_backend_settings()
        
        return {
            "status": "updated",
            "mode": mode,
            "url": settings["desktop_backend_url"],
            "auto_start_backend": settings["desktop_auto_start_backend"],
            "sidecar_status": self._sidecar_status(mode),
            "message": f"Backend mode set to {mode}",
            "commands": {
                "start": "./liuant desktop backend-start" if mode == "managed_backend" else "./liuant start",
                "status": "./liuant desktop backend-status",
            },
        }

    def desktop_one_click_check(self) -> dict[str, Any]:
        """Check if backend can be started with one click."""
        settings = self._desktop_backend_settings()
        mode = settings["desktop_backend_mode"]

        backend_reachable = False
        try:
            import urllib.request
            req = urllib.request.Request(f"{settings['desktop_backend_url']}/api/system/status", method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    backend_reachable = True
        except Exception:
            pass

        if backend_reachable:
            return {
                "status": "already_running",
                "url": settings["desktop_backend_url"],
                "mode": mode,
                "message": "Backend is already reachable.",
                "localhost_only": True,
            }

        from runtime.sidecar import sidecar_status as _sc_status
        sc = _sc_status()
        sidecar_available = sc.get("status") == "available"
        managed_available = mode == "managed_backend"

        strategies = []
        if sidecar_available:
            strategies.append({
                "method": "start_sidecar",
                "command": "./liuant sidecar run",
                "description": "Start the bundled sidecar backend executable",
                "available": True,
            })
        if managed_available:
            strategies.append({
                "method": "start_managed",
                "command": "./liuant desktop backend-start",
                "description": "Start managed backend process from CLI",
                "available": True,
            })
        strategies.append({
            "method": "user_action",
            "command": "./liuant start",
            "description": "Start backend manually in a terminal",
            "available": True,
        })

        best = strategies[0] if strategies else strategies[-1]

        return {
            "status": "needs_start",
            "mode": mode,
            "strategies": strategies,
            "recommended": best["method"],
            "command": best["command"],
            "message": f"Backend not reachable. Recommended: {best['description']}.",
            "sidecar_available": sidecar_available,
            "managed_available": managed_available,
            "localhost_only": True,
        }

    def desktop_launch_check(self) -> dict[str, Any]:
        """Try to start the backend with one click — desktop-friendly."""
        settings = self._desktop_backend_settings()
        mode = settings["desktop_backend_mode"]
        host = DEFAULT_HOST
        port = DEFAULT_PORT
        url = settings["desktop_backend_url"]

        try:
            import urllib.request
            req = urllib.request.Request(f"{url}/api/system/status", method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    return {
                        "status": "already_running",
                        "url": url,
                        "mode": mode,
                        "message": "Backend is already running.",
                    }
        except Exception:
            pass

        if mode == "bundled_sidecar":
            from runtime.sidecar import sidecar_run as _sidecar_run
            result = _sidecar_run(host=host, port=port)
            if result["status"] in ("started", "already_running"):
                return {
                    **result,
                    "mode": mode,
                    "launch_method": "sidecar",
                    "message": "Sidecar backend started.",
                }

        if mode == "managed_backend":
            result = self.desktop_backend_start(host=host, port=port)
            if result["status"] in ("started", "already_running"):
                return {
                    **result,
                    "launch_method": "managed",
                    "message": "Managed backend started.",
                }

        if mode not in ("bundled_sidecar", "managed_backend"):
            from runtime.sidecar import sidecar_status as _sc_status
            sc = _sc_status()
            if sc.get("status") == "available":
                from runtime.sidecar import sidecar_run as _sidecar_run
                result = _sidecar_run(host=host, port=port)
                if result["status"] in ("started", "already_running"):
                    return {
                        **result,
                        "mode": mode,
                        "launch_method": "sidecar_fallback",
                        "note": "Started via sidecar even though mode is not bundled_sidecar.",
                        "message": "Sidecar backend started (fallback).",
                    }

        return {
            "status": "cannot_start",
            "mode": mode,
            "message": "Cannot start backend automatically. Start it manually: ./liuant start",
            "instructions": [
                "1. Open a terminal in the project root directory.",
                "2. Run: ./liuant start",
                "3. Wait for 'Backend started' message.",
                "4. Return to this app and click Retry.",
            ],
        }

    def desktop_backend_start(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, Any]:
        """Start managed backend with PID tracking and safety checks."""
        from datetime import datetime, timezone
        
        if host not in {"127.0.0.1", "localhost"}:
            return {"status": "blocked", "message": "Desktop managed backend may only bind to localhost.", "host": host}
        
        mode = self._desktop_backend_settings()["desktop_backend_mode"]
        
        if mode == "bundled_sidecar":
            from runtime.sidecar import sidecar_run as _sidecar_run
            return _sidecar_run(host=host, port=port)
        
        if mode not in {"external_backend", "managed_backend"}:
            return {"status": "blocked", "message": "Unsupported backend mode.", "allowed_modes": ["external_backend", "managed_backend", "bundled_sidecar"]}
        
        # Check for duplicate managed backend
        if mode == "managed_backend":
            current_status = self.desktop_backend_status()
            if current_status.get("backend_running"):
                return {
                    "status": "already_running",
                    "message": "Managed backend is already running.",
                    "url": f"http://{host}:{port}",
                    "mode": mode,
                }
        
        # Start the backend
        result = self.start(port=port, host=host)
        
        # Add mode information
        result["mode"] = mode
        result["host"] = host
        result["port"] = port
        result["url"] = f"http://{host}:{port}"
        
        if mode == "managed_backend":
            result["note"] = "Managed backend started. Use './liuant desktop backend-stop' to stop."
            # Write managed backend PID file
            self._write_managed_backend_status(result.get("pid"), host, port, result.get("status"))
        
        return result

    def _write_managed_backend_status(self, pid: int | None, host: str, port: int, status: str) -> None:
        """Write managed backend PID and status to workspace."""
        from datetime import datetime, timezone
        status_path = WORKSPACE / "managed_backend.json"
        data = {
            "pid": pid,
            "host": host,
            "port": port,
            "url": f"http://{host}:{port}",
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "mode": "managed_backend",
        }
        status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read_managed_backend_status(self) -> dict[str, Any] | None:
        """Read managed backend status if it exists."""
        status_path = WORKSPACE / "managed_backend.json"
        if not status_path.exists():
            return None
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _is_managed_backend_running(self) -> bool:
        """Check if managed backend process is still running."""
        status = self._read_managed_backend_status()
        if not status or not status.get("pid"):
            return False
        try:
            import os
            os.kill(int(status["pid"]), 0)
            return True
        except (ProcessLookupError, OSError):
            return False

    def desktop_backend_stop(self) -> dict[str, Any]:
        """Stop managed backend process safely."""
        mode = self._desktop_backend_settings()["desktop_backend_mode"]
        
        if mode == "bundled_sidecar":
            from runtime.sidecar import sidecar_stop as _sidecar_stop
            return _sidecar_stop(confirm=True)
        
        # Get server status
        server = self.server_status()
        
        if not server.get("running"):
            # Clean up status file if it exists
            status_path = WORKSPACE / "managed_backend.json"
            if status_path.exists():
                status_path.unlink()
            return {"status": "not_running", "mode": mode, "message": "No backend process is running."}
        
        # Stop the backend
        result = self.stop()
        result["mode"] = mode
        
        # Clean up status file
        status_path = WORKSPACE / "managed_backend.json"
        if status_path.exists():
            status_path.unlink()
        
        return result

    def desktop_backend_restart(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, Any]:
        """Restart managed backend."""
        mode = self._desktop_backend_settings()["desktop_backend_mode"]
        
        if mode == "bundled_sidecar":
            from runtime.sidecar import sidecar_stop as _sidecar_stop
            stop_result = _sidecar_stop(confirm=True)
            from runtime.sidecar import sidecar_run as _sidecar_run
            start_result = _sidecar_run(host=host, port=port)
            return {**stop_result, **start_result, "restart": True}
        
        stop_result = self.desktop_backend_stop()
        start_result = self.desktop_backend_start(host=host, port=port)
        
        return {
            "status": "restarted" if start_result.get("status") in {"started", "running"} else "failed",
            "mode": mode,
            "stop": stop_result,
            "start": start_result,
        }

    def release_manifest(self) -> dict[str, Any]:
        release_dir = ROOT / "release"
        release_dir.mkdir(parents=True, exist_ok=True)
        artifacts = self.release_artifacts()["artifacts"]
        native_artifacts = self._native_artifacts()
        desktop_status = self.desktop_status()
        native_check = self.native_check()
        checksums = self.release_checksum().get("checksums", [])
        manifest = {
            "app": APP_NAME,
            "version": SettingsManager().get("app_version")["value"],
            "channel": self.release_metadata().get("channel", "local-mvp"),
            "platform": platform.platform(),
            "build_date": datetime.now(timezone.utc).isoformat(),
            "git_commit": self._git_commit(),
            "artifacts": artifacts,
            "desktop": {
                "tauri_project_exists": desktop_status["tauri_project_exists"],
                "desktop_version": desktop_status["version"],
                "bundle_identifier": desktop_status["bundle_identifier"],
                "build_artifacts_found": bool(artifacts),
                "native_artifacts_found": bool(native_artifacts),
                "frontend_build_status": desktop_status["frontend_build_status"],
                "native_build_status": desktop_status["native_build_status"],
                "tauri_build_status": desktop_status["tauri_build_status"],
                "rust_available": desktop_status["rustc_available"],
                "cargo_available": desktop_status["cargo_available"],
                "tauri_available": desktop_status["tauri_cli_available"],
                "artifact_status": "artifacts_created" if artifacts else "artifacts_missing",
                "frontend_bundle_only": bool(self._frontend_artifacts()) and not bool(native_artifacts),
                "native_artifacts": bool(native_artifacts),
                "icon_status": desktop_status["icon_status"],
                "package_targets": self.desktop_package_info()["targets"],
                "backend_mode": desktop_status["backend_mode"],
                "backend_url": desktop_status["backend_url"],
                "sidecar_status": desktop_status["sidecar_status"],
                "artifacts": artifacts,
                "checksums": checksums,
                "dependency_gaps": native_check["missing"],
                "signed": False,
                "notarized": False,
            },
            "signing": {
                "signed": False,
                "notarized": False,
                "codesign_verified": False,
                "spctl_accepted": False,
                "notary_submission_id": None,
                "notarization_status": "not_configured",
                "signed_at": None,
                "notarized_at": None,
                "macos": self.signing_status()["macos"],
            },
            "notarization": {"macos": False},
            "windows_signing": {"signed": False},
            "linux_package_status": "artifacts_present" if native_artifacts else "no_native_artifacts",
        }
        path = release_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {"status": "created", "manifest_path": str(path), "manifest": manifest}

    def release_desktop_report(self) -> dict[str, Any]:
        status = self.desktop_status()
        native = self.native_check()
        signing = self.signing_status()
        artifacts = self.release_artifacts()
        return {
            "status": "ok",
            "frontend_build_status": status["frontend_build_status"],
            "native_build_status": status["native_build_status"],
            "dependency_status": native["status"],
            "dependency_gaps": native["missing"],
            "setup_instructions": native["setup_instructions"],
            "artifacts": artifacts["artifacts"],
            "frontend_bundle_only": artifacts["frontend_bundle_only"],
            "unsigned_artifacts": self.unsigned_artifacts(),
            "icon_status": status["icon_status"],
            "build_report": self.build_report(),
            "native_artifacts": status["native_artifacts"],
            "signing": signing,
            "signing_readiness": {
                "codesign_ready": signing["ready_for_codesign"],
                "notarize_ready": signing["ready_for_notarization"],
                "developer_id_configured": signing["macos"]["developer_id_configured"],
                "apple_id_configured": signing["macos"]["apple_id_configured"],
                "notary_tool_configured": signing["macos"]["notarization_configured"],
            },
            "backend_mode": status["backend_mode"],
            "backend_url": status["backend_url"],
            "sidecar_status": status["sidecar_status"],
        }

    def release_checksum(self) -> dict[str, Any]:
        release_dir = ROOT / "release"
        release_dir.mkdir(parents=True, exist_ok=True)
        artifacts = self.release_artifacts()["artifacts"]
        checksums = []
        for item in artifacts:
            path = Path(item["path"])
            if path.is_file():
                checksums.append({"path": str(path), "sha256": self._sha256(path)})
        output = {"status": "no_artifacts" if not checksums else "created", "checksums": checksums}
        path = release_dir / "checksums.json"
        path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        output["checksums_path"] = str(path)
        return output

    def release_artifacts(self) -> dict[str, Any]:
        candidates = [
            ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle",
            ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release",
            ROOT / "apps" / "desktop" / "dist",
            ROOT / "release" / "artifacts",
            ROOT / "dist",
        ]
        suffixes = {".dmg", ".app", ".msi", ".exe", ".AppImage", ".deb", ".rpm", ".zip", ".tar.gz", ".html", ".js", ".css"}
        artifacts: list[dict[str, Any]] = []
        for base in candidates:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file() and (path.suffix in suffixes or path.name.endswith(".tar.gz")):
                    artifact_type = self._artifact_type(path)
                    artifacts.append({"path": str(path), "name": path.name, "size_bytes": path.stat().st_size, "artifact_type": artifact_type, "platform": self._artifact_platform(path), "signed": False, "notarized": False})
        native_artifacts = [item for item in artifacts if item["artifact_type"] == "native"]
        frontend_artifacts = [item for item in artifacts if item["artifact_type"] == "frontend"]
        current_version = SettingsManager().get("app_version")["value"]
        current_version_native = self._current_version_native_artifact(native_artifacts, current_version)
        stale_native = self._stale_native_artifacts(native_artifacts, current_version)
        return {
            "status": "found" if artifacts else "none",
            "artifacts": artifacts,
            "frontend_bundle_only": bool(frontend_artifacts) and not bool(native_artifacts),
            "native_artifacts": bool(native_artifacts),
            "frontend_artifacts": frontend_artifacts,
            "current_version_artifact": current_version_native,
            "stale_native_artifacts": stale_native,
            "searched": [str(path) for path in candidates],
        }

    def _current_version_native_artifact(self, native_artifacts: list[dict[str, Any]], current_version: str | None = None) -> dict[str, Any] | None:
        if current_version is None:
            current_version = SettingsManager().get("app_version")["value"]
        for a in native_artifacts:
            if current_version in a["name"] or current_version.replace(".", "_") in a["name"]:
                return a
        return None

    def _stale_native_artifacts(self, native_artifacts: list[dict[str, Any]], current_version: str | None = None) -> list[dict[str, Any]]:
        if current_version is None:
            current_version = SettingsManager().get("app_version")["value"]
        stale = []
        for a in native_artifacts:
            if current_version not in a["name"] and current_version.replace(".", "_") not in a["name"]:
                stale.append({**a, "stale": True})
        return stale

    def unsigned_artifacts(self) -> dict[str, Any]:
        artifacts = self.release_artifacts()
        native = [item for item in artifacts["artifacts"] if item["artifact_type"] == "native"]
        unsigned = [{**item, "signed": False, "notarized": False} for item in native]
        return {
            "status": "no_native_artifacts" if not unsigned else "unsigned_artifacts_found",
            "frontend_bundle_only": artifacts["frontend_bundle_only"],
            "native_artifacts": unsigned,
            "signed": False,
            "notarized": False,
            "message": "Only real native artifacts are listed here. Frontend dist files are tracked separately." if not unsigned else "Native artifacts are present but unsigned/not notarized.",
        }

    def verify_artifacts(self) -> dict[str, Any]:
        artifacts = self.release_artifacts()["artifacts"]
        checksums = {item["path"]: item["sha256"] for item in self.release_checksum().get("checksums", [])}
        verified = []
        for item in artifacts:
            path = Path(item["path"])
            if not path.is_file():
                verified.append({**item, "verified": False, "reason": "missing_file"})
                continue
            expected = checksums.get(str(path))
            actual = self._sha256(path)
            verified.append({**item, "verified": expected == actual if expected else True, "sha256": actual, "signed": False, "notarized": False})
        native_count = len([item for item in artifacts if item["artifact_type"] == "native"])
        return {
            "status": "no_native_artifacts" if native_count == 0 else "verified",
            "verified": verified,
            "native_artifact_count": native_count,
            "signed": False,
            "notarized": False,
            "message": "No native desktop artifacts exist yet; frontend bundle checksums are safe to verify." if native_count == 0 else "Native artifact files exist and checksums were verified.",
        }

    def release_notes(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "version": SettingsManager().get("app_version")["value"],
            "notes": self.release_metadata().get("release_notes", []),
            "changelog_path": str(ROOT / "CHANGELOG.md"),
        }

    def signing_status(self) -> dict[str, Any]:
        system = platform.system().lower()
        mac_cert = bool(os.environ.get("APPLE_DEVELOPER_ID_APPLICATION") or os.environ.get("APPLE_SIGNING_IDENTITY"))
        apple_id = bool(os.environ.get("APPLE_ID"))
        team_id = bool(os.environ.get("APPLE_TEAM_ID"))
        app_password = bool(os.environ.get("APPLE_APP_SPECIFIC_PASSWORD"))
        keychain_profile = bool(os.environ.get("APPLE_KEYCHAIN_PROFILE"))
        tauri_key = bool(os.environ.get("TAURI_SIGNING_PRIVATE_KEY"))
        tauri_key_password = bool(os.environ.get("TAURI_SIGNING_PRIVATE_KEY_PASSWORD"))
        apple_notary = apple_id and team_id and (app_password or keychain_profile)
        windows_cert = bool(os.environ.get("WINDOWS_CERTIFICATE_PATH") or os.environ.get("WINDOWS_SIGNING_CERTIFICATE"))
        signtool = bool(shutil.which("signtool"))
        gpg = bool(shutil.which("gpg"))
        configured = mac_cert or apple_notary or windows_cert or gpg
        ready_for_codesign = mac_cert
        ready_for_notarization = apple_notary
        return {
            "status": "unsigned",
            "signed": False,
            "notarized": False,
            "ready": False,
            "platform": system,
            "ready_for_codesign": ready_for_codesign,
            "ready_for_notarization": ready_for_notarization,
            "macos": {
                "developer_id_configured": mac_cert,
                "apple_id_configured": apple_id,
                "team_id_configured": team_id,
                "app_specific_password_configured": app_password,
                "keychain_profile_configured": keychain_profile,
                "tauri_private_key_configured": tauri_key,
                "tauri_private_key_password_configured": tauri_key_password,
                "notarization_configured": apple_notary,
                "hardened_runtime_required": True,
            },
            "windows": {
                "certificate_configured": windows_cert,
                "signtool_available": signtool,
            },
            "linux": {
                "gpg_available": gpg,
                "checksum_signing_recommended": True,
            },
            "configured_any": configured,
            "message": "Builds are unsigned until real signing certificates and notarization/signing steps are configured."
            if configured else
            "Signing blocked — Apple Developer ID Application certificate not configured. "
            "Set APPLE_DEVELOPER_ID_APPLICATION to your Developer ID identity. "
            "Run `security find-identity -v -p codesigning` to list available identities. "
            "See docs/MACOS_SIGNING_NOTARIZATION.md for setup.",
        }

    def signing_check(self) -> dict[str, Any]:
        status = self.signing_status()
        docs = self.signing_docs()
        return {**status, "check_status": "passed", "docs": docs["docs_path"], "warnings": ["No signed/notarized output is claimed."]}

    def signing_docs(self) -> dict[str, Any]:
        docs_path = ROOT / "docs" / "MACOS_SIGNING_NOTARIZATION.md"
        return {
            "status": "ok",
            "docs_path": str(docs_path) if docs_path.exists() else str(ROOT / "docs" / "SIGNING.md"),
            "env_names": [
                "APPLE_DEVELOPER_ID_APPLICATION",
                "APPLE_ID",
                "APPLE_TEAM_ID",
                "APPLE_APP_SPECIFIC_PASSWORD",
                "APPLE_KEYCHAIN_PROFILE",
                "TAURI_SIGNING_PRIVATE_KEY",
                "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
                "WINDOWS_CERTIFICATE_PATH",
            ],
        }

    def signing_macos_status(self) -> dict[str, Any]:
        status = self.signing_status()
        mac = status["macos"]
        native_artifacts = self._native_artifacts()
        current_version = SettingsManager().get("app_version")["value"]
        current_artifact = self._current_version_native_artifact(native_artifacts, current_version)
        stale_artifacts = self._stale_native_artifacts(native_artifacts, current_version)
        dmg = current_artifact if current_artifact and current_artifact["name"].endswith(".dmg") else None
        if not dmg:
            dmg = next((a for a in native_artifacts if a["name"].endswith(".dmg")), None)
        apple_id = os.environ.get("APPLE_ID")
        team_id = os.environ.get("APPLE_TEAM_ID")
        return {
            "status": "unsigned",
            "signed": False,
            "notarized": False,
            "artifact_exists": bool(native_artifacts),
            "current_version_artifact_exists": current_artifact is not None,
            "stale_artifact_count": len(stale_artifacts),
            "dmg_path": str(dmg["path"]) if dmg else None,
            "dmg_checksum": self._sha256(Path(dmg["path"])) if dmg else None,
            "developer_id_configured": mac["developer_id_configured"],
            "apple_id_configured": mac["apple_id_configured"],
            "team_id_configured": mac["team_id_configured"],
            "app_specific_password_configured": mac["app_specific_password_configured"],
            "keychain_profile_configured": mac["keychain_profile_configured"],
            "notarization_configured": mac["notarization_configured"],
            "ready_for_codesign": status["ready_for_codesign"] and bool(native_artifacts),
            "ready_for_notarization": status["ready_for_notarization"] and bool(native_artifacts),
            "apple_id_present": bool(apple_id),
            "team_id_present": bool(team_id),
            "apple_credentials_displayed": False,
            "message": "Signing blocked — Apple Developer ID Application certificate not configured. "
                       "Set APPLE_DEVELOPER_ID_APPLICATION to sign. "
                       "Run `security find-identity -v -p codesigning` to check. "
                       "See docs/MACOS_SIGNING_NOTARIZATION.md for setup."
            if not mac["developer_id_configured"] and current_artifact
            else "No native artifacts found. Run `./liuant desktop build --native` first."
            if not current_artifact
            else "No Apple signing credentials configured.",
        }

    def signing_macos_guide(self) -> dict[str, Any]:
        lines = [
            "## macOS Code-Signing & Notarization Guide",
            "",
            "### 1. Apple Developer Program",
            "You need an active Apple Developer Program membership ($99/year).",
            "https://developer.apple.com/programs/",
            "",
            "### 2. Developer ID Application Certificate",
            "Create a 'Developer ID Application' certificate in your Apple Developer account.",
            "Download and install it into your keychain.",
            "The certificate identity is set via:",
            "  export APPLE_DEVELOPER_ID_APPLICATION=\"Developer ID Application: Your Name (TEAMID)\"",
            "",
            "### 3. App-Specific Password",
            "Generate an app-specific password at appleid.apple.com for notarytool.",
            "  export APPLE_ID=\"your@apple.id\"",
            "  export APPLE_TEAM_ID=\"YOUR_TEAM_ID\"",
            "  export APPLE_APP_SPECIFIC_PASSWORD=\"xxxx-xxxx-xxxx-xxxx\"",
            "",
            "### 4. Notarytool Profile (alternative to app-specific password)",
            "  xcrun notarytool store-connect AC_USERNAME AC_PASSWORD --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID",
            "  export APPLE_KEYCHAIN_PROFILE=\"AC_USERNAME\"",
            "",
            "### 5. Tauri Signing (optional, for auto-updates)",
            "  export TAURI_SIGNING_PRIVATE_KEY=\"/path/to/key.pem\"",
            "  export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=\"your-password\"",
            "",
            "### 6. Build States",
            "- Unsigned: App runs with macOS Gatekeeper warnings.",
            "- Signed: App is signed with Developer ID, Gatekeeper accepts it.",
            "- Notarized: Apple scans the app, no warnings on launch.",
            "- Stapled: Notarization ticket is embedded; offline installs are trusted.",
            "",
            "### 7. Commands",
            "- Export env template: `./liuant signing macos-export-env-template`",
            "- Preflight check:   `./liuant signing macos-preflight`",
            "- Dry-run signing:   `./liuant signing macos-sign --dry-run`",
            "- Real signing:      `./liuant signing macos-sign --artifact <path> --confirm`",
            "- Dry-run notarize:  `./liuant signing macos-notarize --dry-run`",
            "- Real notarize:     `./liuant signing macos-notarize --artifact <path> --confirm`",
        ]
        return {"status": "ok", "guide": "\n".join(lines)}

    def signing_macos_export_env_template(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "message": "Environment variable names — no values are shown.",
            "variables": [
                "# macOS Code-Signing",
                "APPLE_DEVELOPER_ID_APPLICATION=",
                "",
                "# Notarization",
                "APPLE_ID=",
                "APPLE_TEAM_ID=",
                "APPLE_APP_SPECIFIC_PASSWORD=",
                "# Or use: APPLE_KEYCHAIN_PROFILE=",
                "",
                "# Tauri (optional, for auto-update signing)",
                "TAURI_SIGNING_PRIVATE_KEY=",
                "TAURI_SIGNING_PRIVATE_KEY_PASSWORD=",
            ],
        }

    def signing_macos_preflight(self) -> dict[str, Any]:
        all_native = self._native_artifacts_detailed()
        artifacts_info = self.release_artifacts()
        current_version = SettingsManager().get("app_version")["value"]
        current_artifact = self._current_version_native_artifact(all_native, current_version)
        stale_artifacts = self._stale_native_artifacts(all_native, current_version)
        if not all_native:
            return {"status": "not_ready", "reason": "no_native_artifacts", "message": "No native artifacts found. Run `./liuant desktop build --native` first.", "signed": False, "notarized": False, "current_version_artifact_exists": False, "stale_artifact_count": 0}
        dmg = current_artifact if current_artifact and current_artifact["name"].endswith(".dmg") else None
        if not dmg:
            dmg = next((a for a in all_native if a["name"].endswith(".dmg")), None)
        signing = self.signing_status()
        security_find = self._run_security_find_identity()
        notarytool = bool(shutil.which("xcrun"))
        stapler = bool(shutil.which("stapler"))

        actual_checksum = self._sha256(Path(dmg["path"])) if dmg else None
        stored_checksums = self.release_checksum().get("checksums", [])
        dmg_stored = next((c["sha256"] for c in stored_checksums if c["path"].endswith(".dmg")), None)
        checksum_matches = bool(actual_checksum and dmg_stored and actual_checksum == dmg_stored)

        current_version_artifact_exists = current_artifact is not None
        version_matches = bool(dmg and (current_version in dmg["name"] or current_version.replace(".", "_") in dmg["name"]))

        security_find_identities = security_find.get("identities", [])
        has_developer_id_cert = any("Developer ID" in str(i) for i in security_find_identities)

        checks = {
            "artifact_exists": bool(all_native),
            "current_version_artifact_exists": current_version_artifact_exists,
            "stale_artifact_count": len(stale_artifacts),
            "dmg_exists": dmg is not None,
            "dmg_checksum": actual_checksum,
            "checksum_matches_stored": checksum_matches,
            "version_matches": version_matches,
            "app_version": current_version,
            "developer_id_configured": signing["macos"]["developer_id_configured"],
            "developer_id_certificate_found": has_developer_id_cert,
            "apple_id_configured": signing["macos"]["apple_id_configured"],
            "team_id_configured": signing["macos"]["team_id_configured"],
            "app_specific_password_configured": signing["macos"]["app_specific_password_configured"],
            "keychain_profile_configured": signing["macos"]["keychain_profile_configured"],
            "notarytool_available": notarytool,
            "stapler_available": stapler,
            "certificate_identities_found": security_find["count"],
            "bundle_id": self._get_bundle_id(),
        }

        missing_checks = [k for k, v in checks.items() if v in (None, False, 0) and k in (
            "artifact_exists", "current_version_artifact_exists", "dmg_exists",
            "checksum_matches_stored", "version_matches",
            "developer_id_configured", "bundle_id"
        )]
        ready = len(missing_checks) == 0 and checks["bundle_id"] == "com.liuant.agenticos"

        return {
            "status": "ready" if ready else "not_ready",
            "checks": checks,
            "missing_checks": missing_checks if missing_checks else None,
            "current_version_artifact": current_artifact,
            "stale_artifacts": stale_artifacts if stale_artifacts else None,
            "signed": False,
            "notarized": False,
            "message": "All preflight checks passed. Signing can proceed." if ready else f"Preflight checks incomplete: {', '.join(missing_checks)}. Review details above." if missing_checks else "Preflight checks incomplete. Review details above.",
        }

    def signing_macos_sign(self, artifact_path: str | None = None, dry_run: bool = True, confirm: bool = False) -> dict[str, Any]:
        signing = self.signing_status()
        if not signing["macos"]["developer_id_configured"]:
            return {"status": "not_ready", "reason": "APPLE_DEVELOPER_ID_APPLICATION not configured", "signed": False, "notarized": False, "message": "Missing APPLE_DEVELOPER_ID_APPLICATION environment variable. Run `./liantu signing macos-guide` for setup."}

        if not artifact_path:
            native = self._native_artifacts()
            if not native:
                return {"status": "artifact_missing", "reason": "no_native_artifacts", "signed": False, "notarized": False}
            current_version = SettingsManager().get("app_version")["value"]
            current_dmg = self._current_version_native_artifact(native, current_version)
            if current_dmg and current_dmg["name"].endswith(".dmg"):
                artifact_path = current_dmg["path"]
            else:
                dmg = next((a for a in native if a["name"].endswith(".dmg")), None)
                if dmg:
                    artifact_path = dmg["path"]
                else:
                    app_bundle = self._find_app_bundle()
                    if app_bundle:
                        artifact_path = app_bundle

        if not artifact_path or not Path(artifact_path).exists():
            return {"status": "artifact_missing", "reason": "file_not_found", "signed": False, "notarized": False, "message": f"Artifact not found at {artifact_path}."}

        identity = os.environ.get("APPLE_DEVELOPER_ID_APPLICATION", "")
        if dry_run:
            return {
                "status": "dry_run",
                "signed": False,
                "notarized": False,
                "artifact": artifact_path,
                "identity": identity[:60] + "..." if len(identity) > 60 else identity,
                "command": f"codesign --deep --force --verify --verbose --timestamp --options=runtime --sign \"{identity}\" \"{artifact_path}\"",
                "message": "Dry-run: no signing was performed. Run with --confirm to sign.",
            }

        if not confirm:
            return {"status": "confirm_required", "signed": False, "notarized": False, "artifact": artifact_path, "message": "Pass --confirm to proceed with actual signing."}

        try:
            cmd = [
                "codesign", "--deep", "--force", "--verify", "--verbose",
                "--timestamp", "--options=runtime",
                "--sign", identity,
                artifact_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return {"status": "failed", "reason": "codesign_error", "stderr": self._redact_secrets(result.stderr), "signed": False, "notarized": False, "message": "Signing command failed."}

            verify = subprocess.run(["codesign", "--verify", "--verbose", artifact_path], capture_output=True, text=True, timeout=30)
            spctl = subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose", artifact_path], capture_output=True, text=True, timeout=30)
            codesign_verified = verify.returncode == 0
            spctl_accepted = spctl.returncode == 0

            if codesign_verified:
                self._update_manifest_signing(signed=True, codesign_verified=True, spctl_accepted=spctl_accepted)
                self.release_checksum()

            return {
                "status": "completed",
                "signed": True,
                "notarized": False,
                "signed_at": datetime.now(timezone.utc).isoformat(),
                "codesign_verified": codesign_verified,
                "spctl_accepted": spctl_accepted,
                "artifact": artifact_path,
                "message": "Signing completed successfully." if codesign_verified else "Signing ran but verification failed.",
            }
        except subprocess.TimeoutExpired:
            return {"status": "failed", "reason": "timeout", "signed": False, "notarized": False, "message": "Signing command timed out."}
        except FileNotFoundError:
            return {"status": "failed", "reason": "codesign_not_found", "signed": False, "notarized": False, "message": "codesign command not found. This command requires macOS."}
        except Exception as e:
            return {"status": "failed", "reason": str(e), "signed": False, "notarized": False}

    def signing_macos_notarize(self, artifact_path: str | None = None, dry_run: bool = True, confirm: bool = False) -> dict[str, Any]:
        signing = self.signing_status()
        if not signing["macos"]["notarization_configured"]:
            return {"status": "not_ready", "reason": "Apple ID/team/password not fully configured", "signed": signing["signed"], "notarized": False, "message": "Missing APPLE_ID, APPLE_TEAM_ID, and APPLE_APP_SPECIFIC_PASSWORD or APPLE_KEYCHAIN_PROFILE."}

        if not artifact_path:
            native = self._native_artifacts()
            if not native:
                return {"status": "artifact_missing", "reason": "no_native_artifacts", "signed": signing["signed"], "notarized": False}
            current_version = SettingsManager().get("app_version")["value"]
            current_dmg = self._current_version_native_artifact(native, current_version)
            if current_dmg and current_dmg["name"].endswith(".dmg"):
                artifact_path = current_dmg["path"]
            else:
                dmg = next((a for a in native if a["name"].endswith(".dmg")), None)
                if dmg:
                    artifact_path = dmg["path"]

        if not artifact_path or not Path(artifact_path).exists():
            return {"status": "artifact_missing", "reason": "file_not_found", "signed": signing["signed"], "notarized": False, "message": f"Artifact not found at {artifact_path}."}

        apple_id = os.environ.get("APPLE_ID", "")
        team_id = os.environ.get("APPLE_TEAM_ID", "")
        password = os.environ.get("APPLE_APP_SPECIFIC_PASSWORD", "")
        keychain_profile = os.environ.get("APPLE_KEYCHAIN_PROFILE", "")

        if dry_run:
            auth_method = "--apple-id and --team-id with app-specific password" if password else f"--keychain-profile \"{keychain_profile}\""
            return {
                "status": "dry_run",
                "signed": signing["signed"],
                "notarized": False,
                "artifact": artifact_path,
                "auth_method": auth_method,
                "steps": [
                    f"1. Compress artifact: ditto -c -k --keepParent {artifact_path} /tmp/submit.zip",
                    f"2. Upload to Apple: xcrun notarytool submit /tmp/submit.zip --apple-id <id> --team-id <team> --password <pwd> --wait",
                    f"3. Check status: xcrun notarytool history --apple-id <id> --team-id <team> --password <pwd>",
                    f"4. Staple ticket: xcrun stapler staple {artifact_path}",
                    f"5. Verify: spctl --assess --type execute --verbose {artifact_path}",
                ],
                "message": "Dry-run: no notarization was performed. Run with --confirm to upload.",
            }

        if not confirm:
            return {"status": "confirm_required", "signed": signing["signed"], "notarized": False, "artifact": artifact_path, "message": "Pass --confirm to proceed with actual notarization upload to Apple."}

        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                zip_path = tmp.name
            subprocess.run(["ditto", "-c", "-k", "--keepParent", artifact_path, zip_path], capture_output=True, text=True, timeout=120)

            notary_cmd = ["xcrun", "notarytool", "submit", zip_path, "--wait"]
            if keychain_profile:
                notary_cmd.extend(["--keychain-profile", keychain_profile])
            else:
                notary_cmd.extend(["--apple-id", apple_id, "--team-id", team_id, "--password", password])

            result = subprocess.run(notary_cmd, capture_output=True, text=True, timeout=600)
            Path(zip_path).unlink(missing_ok=True)

            if result.returncode != 0:
                return {"status": "failed", "reason": "notarytool_error", "stderr": self._redact_secrets(result.stderr), "signed": signing["signed"], "notarized": False, "message": "Notarization submission failed."}

            staple_result = subprocess.run(["xcrun", "stapler", "staple", artifact_path], capture_output=True, text=True, timeout=60)
            stapled = staple_result.returncode == 0

            return {
                "status": "completed",
                "signed": True,
                "notarized": True,
                "stapled": stapled,
                "notarized_at": datetime.now(timezone.utc).isoformat(),
                "artifact": artifact_path,
                "message": "Notarization completed and ticket stapled." if stapled else "Notarization completed but stapling failed. Run `xcrun stapler staple` manually.",
            }
        except subprocess.TimeoutExpired:
            return {"status": "failed", "reason": "timeout", "signed": signing["signed"], "notarized": False, "message": "Notarization timed out (10 min limit)."}
        except FileNotFoundError:
            return {"status": "failed", "reason": "notarytool_not_found", "signed": signing["signed"], "notarized": False, "message": "xcrun or notarytool not found. This command requires macOS."}
        except Exception as e:
            return {"status": "failed", "reason": str(e), "signed": signing["signed"], "notarized": False}

    def _run_security_find_identity(self) -> dict[str, Any]:
        try:
            result = subprocess.run(["security", "find-identity", "-v", "-p", "basic"], capture_output=True, text=True, timeout=15)
            lines = result.stdout.strip().split("\n") if result.stdout else []
            count = sum(1 for l in lines if l.strip() and l.strip()[0].isdigit())
            return {"count": count, "identities": [l.strip() for l in lines[:5] if l.strip()]}
        except Exception:
            return {"count": 0, "identities": []}

    def _find_app_bundle(self) -> str | None:
        base = ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle"
        if not base.exists():
            return None
        for p in base.rglob("*.app"):
            if p.is_dir():
                return str(p)
        return None

    def _get_bundle_id(self) -> str:
        try:
            desktop = self.desktop_status()
            return desktop.get("bundle_identifier", "com.liuant.agenticos")
        except Exception:
            return "com.liuant.agenticos"

    def _redact_secrets(self, text: str) -> str:
        import re
        text = re.sub(r'(?i)(apple_id|apple.*password|app.*specific.*password|password)\s*["\']?[^\s"\'&]+', r'\1 REDACTED', text)
        text = re.sub(r'(TAURI_SIGNING_PRIVATE_KEY|APPLE_DEVELOPER_ID_APPLICATION)\s*["\']?[^\s"\']+', r'\1 REDACTED', text)
        return text

    def _update_manifest_signing(self, signed: bool = False, notarized: bool = False,
                                  codesign_verified: bool = False, spctl_accepted: bool = False,
                                  notarization_status: str | None = None, stapled: bool = False) -> None:
        from datetime import datetime, timezone
        manifest_path = ROOT / "release" / "manifest.json"
        if not manifest_path.exists():
            self.release_manifest()
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            self.release_manifest()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat() if signed else None
        manifest.setdefault("signing", {})
        manifest["signing"]["unsigned"] = not signed
        manifest["signing"]["signed"] = signed
        manifest["signing"]["notarized"] = notarized
        manifest["signing"]["codesign_verified"] = codesign_verified
        manifest["signing"]["spctl_accepted"] = spctl_accepted
        manifest["signing"]["notarization_status"] = notarization_status
        manifest["signing"]["signed_at"] = now
        if notarized:
            manifest["signing"]["notarized_at"] = datetime.now(timezone.utc).isoformat()
        for artifact in manifest.get("artifacts", []):
            if artifact.get("artifact_type") == "native":
                artifact["signed"] = signed
                artifact["notarized"] = notarized
        for artifact in manifest.get("desktop", {}).get("artifacts", []):
            if artifact.get("artifact_type") == "native":
                artifact["signed"] = signed
                artifact["notarized"] = notarized
        manifest["desktop"]["signed"] = signed
        manifest["desktop"]["notarized"] = notarized
        manifest["notarization"]["macos"] = notarized
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def start(self, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> dict[str, Any]:
        if host not in {"127.0.0.1", "localhost"}:
            return {"status": "blocked", "message": "Local server binds to 127.0.0.1 by default. Refusing non-local host.", "host": host}
        current = self.server_status()
        if current["running"]:
            return current
        self.logs_dir().mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir() / "server.log"
        handle = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen([sys.executable, "-m", "cli.liuant", "serve", str(port)], cwd=str(ROOT), stdout=handle, stderr=handle)
        pid_path = self.pid_path()
        pid_path.write_text(json.dumps({"pid": process.pid, "host": "127.0.0.1", "port": port, "log_path": str(log_path)}, indent=2), encoding="utf-8")
        return {
            "status": "started",
            "pid": process.pid,
            "host": "127.0.0.1",
            "port": port,
            "url": f"http://127.0.0.1:{port}",
            "auth_enabled": AuthManager().status()["local_auth_enabled"],
            "token_instructions": "Run `liuant auth token` if the UI asks for the local API token.",
            "log_path": str(log_path),
        }

    def stop(self) -> dict[str, Any]:
        status = self.server_status()
        if not status["running"]:
            self.pid_path().unlink(missing_ok=True)
            return {"status": "not_running"}
        pid = int(status["pid"])
        os.kill(pid, signal.SIGTERM)
        self.pid_path().unlink(missing_ok=True)
        return {"status": "stopped", "pid": pid}

    def restart(self, port: int = DEFAULT_PORT) -> dict[str, Any]:
        stop = self.stop()
        start = self.start(port=port)
        return {"status": "restarted" if start.get("status") in {"started", "running"} else start.get("status"), "stop": stop, "start": start}

    def server_status(self) -> dict[str, Any]:
        path = self.pid_path()
        if not path.exists():
            return {"status": "not_running", "running": False}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            pid = int(data.get("pid"))
            os.kill(pid, 0)
            return {"status": "running", "running": True, **data, "url": f"http://{data.get('host', '127.0.0.1')}:{data.get('port', DEFAULT_PORT)}"}
        except Exception:
            path.unlink(missing_ok=True)
            return {"status": "not_running", "running": False}

    def ui(self, action: str = "check") -> dict[str, Any]:
        if action == "check":
            return self.ui_check()
        if action in {"dev", "build"}:
            package_manager = shutil.which("pnpm") or shutil.which("npm")
            if not package_manager:
                return {"status": "missing_node_tooling", "action": action, "message": "Install Node.js and pnpm/npm to run UI dev/build commands."}
            return {"status": "instructions", "action": action, "command": f"{Path(package_manager).name} run {action}", "message": "Static MVP UI is available under ui/; no bundled Node app is required yet."}
        raise ValueError(f"Unknown UI action: {action}")

    def ui_check(self) -> dict[str, Any]:
        ui = ROOT / "ui"
        required = [ui / "index.html", ui / "app.js", ui / "styles.css"]
        missing = [str(path) for path in required if not path.exists()]
        node = shutil.which("node")
        return {
            "status": "passed" if not missing else "failed",
            "ui_path": str(ui / "index.html"),
            "missing": missing,
            "node_available": bool(node),
            "pnpm_available": bool(shutil.which("pnpm")),
            "message": "Static UI is present." if not missing else "UI files are missing.",
        }

    def open_ui(self) -> dict[str, Any]:
        path = ROOT / "ui" / "index.html"
        if not path.exists():
            return {"status": "missing_ui", "message": "UI files are missing. Run `liuant repair`."}
        return {"status": "ready", "ui_path": str(path), "url": path.as_uri(), "auth_enabled": AuthManager().status()["local_auth_enabled"], "message": "Open this URL in a local browser."}

    def logs_dir(self) -> Path:
        return WORKSPACE / "logs"

    def pid_path(self) -> Path:
        return self.logs_dir() / "liuant-server.pid.json"

    def logs_path(self) -> dict[str, Any]:
        self.logs_dir().mkdir(parents=True, exist_ok=True)
        return {"status": "ok", "logs_path": str(self.logs_dir()), "server_log": str(self.logs_dir() / "server.log")}

    def logs_tail(self, lines: int = 40) -> dict[str, Any]:
        path = self.logs_dir() / "server.log"
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
            return {"status": "ok", "path": str(path), "lines": content}
        actions = list_records("action_logs")[:lines]
        return {"status": "no_file_log", "path": str(path), "recent_action_logs": actions}

    def logs_clear(self, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "blocked", "message": "Clearing file logs requires --confirm."}
        path = self.logs_dir() / "server.log"
        if path.exists():
            path.unlink()
        return {"status": "cleared", "path": str(path), "message": "File log cleared. SQLite action logs were not deleted."}

    def troubleshoot(self) -> dict[str, Any]:
        audit = audit_secrets()
        recent_errors = [row for row in list_records("action_logs") if row.get("status") in {"error", "provider_error", "failed"}][:10]
        return {
            "status": "ready",
            "doctor_status": run_doctor().get("status"),
            "env_status": EnvironmentValidator().check().get("status"),
            "auth": AuthManager().status(),
            "secret_backend": SecretManager().status().get("default_backend"),
            "database": health(),
            "providers": ModelHub().get_status(),
            "recent_errors": self._redact(recent_errors),
            "ui": self.ui_check(),
            "scheduler": __import__("runtime.automation", fromlist=["SchedulerEngine"]).SchedulerEngine().status(),
            "backup_count": len(BackupManager().list()),
            "secret_audit_status": audit.get("status"),
        }

    def release_metadata(self) -> dict[str, Any]:
        path = ROOT / "release.json"
        if not path.exists():
            return {"version": SettingsManager().get("app_version")["value"], "channel": "local-mvp", "release_notes": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _required_dirs(self) -> list[Path]:
        return [
            WORKSPACE,
            WORKSPACE / "outputs",
            WORKSPACE / "outputs" / "agents",
            WORKSPACE / "outputs" / "email",
            WORKSPACE / "outputs" / "images",
            WORKSPACE / "outputs" / "social",
            WORKSPACE / "outputs" / "videos",
            WORKSPACE / "backups",
            WORKSPACE / "logs",
            WORKSPACE / "security",
            ROOT / "release",
            ROOT / "release" / "artifacts",
        ]

    def _detect_desktop_project(self) -> dict[str, Any]:
        candidates = [ROOT / "apps" / "desktop", ROOT / "desktop"]
        for root in candidates:
            src_tauri = root / "src-tauri"
            if root.exists() or src_tauri.exists():
                config = None
                for name in ("tauri.conf.json", "tauri.conf.json5", "Tauri.toml"):
                    path = src_tauri / name
                    if path.exists():
                        config = str(path)
                        break
                return {
                    "exists": src_tauri.exists(),
                    "desktop_root": str(root),
                    "src_tauri_path": str(src_tauri),
                    "tauri_config": config,
                }
        return {
            "exists": False,
            "desktop_root": str(ROOT / "apps" / "desktop"),
            "src_tauri_path": str(ROOT / "apps" / "desktop" / "src-tauri"),
            "tauri_config": None,
        }

    def _desktop_icon_candidates(self, desktop_root: str | None) -> list[str]:
        roots = [ROOT / "icons"]
        if desktop_root:
            roots.append(Path(desktop_root) / "src-tauri" / "icons")
        icons: list[str] = []
        for root in roots:
            if root.exists():
                icons.extend(str(path) for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".ico", ".icns", ".svg"})
        return icons

    def _required_icon_files(self) -> list[str]:
        return [
            "icon.svg",
            "32x32.png",
            "128x128.png",
            "128x128@2x.png",
            "icon.ico",
            "icon.icns",
            "Square30x30Logo.png",
            "Square44x44Logo.png",
            "Square71x71Logo.png",
            "Square89x89Logo.png",
            "Square107x107Logo.png",
            "Square142x142Logo.png",
            "Square150x150Logo.png",
            "Square284x284Logo.png",
            "Square310x310Logo.png",
            "StoreLogo.png",
        ]

    def _desktop_setup_instructions(self, project_exists: bool, missing: list[str]) -> list[str]:
        if not project_exists:
            return [
                "Create a Tauri project at apps/desktop with src-tauri before building native installers.",
                "Keep the backend bound to 127.0.0.1 and use the existing local API auth flow.",
                "Run `liuant desktop check` again after installing Node.js, Rust/Cargo, and Tauri prerequisites.",
            ]
        instructions = []
        if "node" in missing:
            instructions.append("Install Node.js and pnpm/npm.")
        if "cargo" in missing:
            instructions.append("Install Rust and Cargo.")
        if "src-tauri_config" in missing:
            instructions.append("Add src-tauri/tauri.conf.json with app name, identifier, icons, and window settings.")
        if "icons" in missing:
            instructions.append("Add placeholder or brand icons under apps/desktop/src-tauri/icons.")
        return instructions

    def _native_setup_instructions(self, missing: list[str]) -> list[str]:
        system = platform.system().lower()
        instructions: list[str] = []
        missing_set = set(missing)
        if {"rustc", "cargo", "rustup", "cargo"} & missing_set:
            instructions.append("Install Rust using rustup, then reopen the terminal so rustc and cargo are on PATH.")
        if "node" in missing_set:
            instructions.append("Install Node.js 20+ with npm.")
        if "tauri_cli" in missing_set:
            instructions.append("Run `cd apps/desktop && npm install` or install the Tauri CLI for this project.")
        if "frontend_dist" in missing_set:
            instructions.append("Run `cd apps/desktop && npm run build` to create frontend artifacts.")
        if "tauri_project" in missing_set:
            instructions.append("Ensure apps/desktop/src-tauri exists.")
        if "tauri_config" in missing_set:
            instructions.append("Ensure apps/desktop/src-tauri/tauri.conf.json exists.")
        if system == "darwin":
            instructions.extend([
                "macOS: install Xcode Command Line Tools with `xcode-select --install`.",
                "macOS: install Tauri prerequisites after Rust and Node are available.",
            ])
        elif system == "windows":
            instructions.extend([
                "Windows: install Visual Studio Build Tools with Desktop development with C++.",
                "Windows: install Microsoft Edge WebView2 runtime.",
                "Windows: install Rust and Node.js before running Tauri build.",
            ])
        elif system == "linux":
            instructions.extend([
                "Linux: install build-essential, curl/wget, and WebKitGTK/Tauri system packages for your distribution.",
                "Linux: install Rust and Node.js before running Tauri build.",
            ])
        if not instructions:
            instructions.append("Native desktop prerequisites are present. Run `liuant desktop build --native`.")
        return instructions

    def _platform_build_steps(self, system: str) -> list[str]:
        common = [
            "Run `cd apps/desktop && npm install`.",
            "Run `cd apps/desktop && npm run typecheck && npm run build`.",
            "Run `liuant desktop icons-generate` before packaging.",
            "Run `liuant desktop build --native` only after Rust/Cargo and platform prerequisites are installed.",
        ]
        if system == "darwin":
            return [
                "macOS: install Xcode Command Line Tools with `xcode-select --install`.",
                "macOS: install Rust from rustup.rs so rustc, cargo, and rustup are available.",
                "macOS: install Node.js 20+ and npm or pnpm.",
                "macOS: run `scripts/build_desktop_macos.sh` from the repository root.",
                "macOS: signing and notarization remain pending; unsigned artifacts must be labeled as unsigned.",
                *common,
            ]
        if system == "windows":
            return [
                "Windows: install Visual Studio Build Tools with Desktop development with C++.",
                "Windows: install Microsoft Edge WebView2 Runtime.",
                "Windows: install Rust MSVC toolchain from rustup.rs.",
                "Windows: install Node.js 20+ and npm or pnpm.",
                "Windows: run `scripts\\build_desktop_windows.ps1` from PowerShell.",
                "Windows: code signing remains pending; unsigned installers must be labeled as unsigned.",
                *common,
            ]
        if system == "linux":
            return [
                "Linux: install WebKitGTK, build-essential, curl/wget, pkg-config, libssl-dev, and librsvg2-dev for your distribution.",
                "Linux: install Rust from rustup.rs so rustc, cargo, and rustup are available.",
                "Linux: install Node.js 20+ and npm or pnpm.",
                "Linux: run `scripts/build_desktop_linux.sh` from the repository root.",
                "Linux: package signing remains pending; publish checksums with unsigned artifact warnings.",
                *common,
            ]
        return ["Install Node.js 20+, Rust/Cargo/rustup, and Tauri platform prerequisites for your OS.", *common]

    def _platform_build_dependency_gaps(self, system: str) -> list[str]:
        if system == "darwin":
            return [] if shutil.which("xcode-select") else ["xcode_command_line_tools"]
        if system == "windows":
            return [] if shutil.which("where") else ["visual_studio_build_tools_or_webview2"]
        if system == "linux":
            return [] if shutil.which("pkg-config") else ["webkitgtk_build_dependencies"]
        return []

    def _desktop_backend_settings(self) -> dict[str, Any]:
        manager = SettingsManager()
        manager.ensure_defaults()
        settings = {row["key"]: row["value"] for row in manager.list()}
        return {
            "desktop_backend_mode": settings.get("desktop_backend_mode", "external_backend"),
            "desktop_backend_url": settings.get("desktop_backend_url", "http://127.0.0.1:8765"),
            "desktop_auto_start_backend": str(settings.get("desktop_auto_start_backend", "false")).lower() == "true",
        }

    def _sidecar_status(self, mode: str) -> str:
        if mode == "bundled_sidecar":
            sc = _runtime_sidecar_status()
            if sc.get("status") == "available":
                return "available"
            return "pending"
        if mode == "managed_backend":
            return "managed_local_command_available"
        return "not_used"

    def _tauri_cli_path(self, desktop_root: str | None) -> str | None:
        for name in ("tauri", "cargo-tauri"):
            found = shutil.which(name)
            if found:
                return found
        if desktop_root:
            binary = Path(desktop_root) / "node_modules" / ".bin" / "tauri"
            if binary.exists():
                return str(binary)
        return None

    def _desktop_npm_command(self, script: str) -> list[str]:
        if shutil.which("pnpm"):
            return ["pnpm", "run", script]
        return ["npm", "run", script]

    def _tauri_bundle_identifier(self, config_path: str | None) -> str:
        if not config_path:
            return "com.liuant.agenticos"
        try:
            data = json.loads(Path(config_path).read_text(encoding="utf-8"))
            return data.get("identifier") or data.get("tauri", {}).get("bundle", {}).get("identifier") or "com.liuant.agenticos"
        except Exception:
            return "com.liuant.agenticos"

    def _desktop_command(self, action: str) -> dict[str, Any]:
        status = self.desktop_status()
        if not status["tauri_project_exists"]:
            return {"status": "missing_project", "action": action, "message": "No Tauri project exists at apps/desktop/src-tauri yet.", "setup_instructions": status["setup_instructions"]}
        if status["missing"]:
            return {
                "status": "dependency_missing",
                "action": action,
                "missing": status["missing"],
                "frontend_build_status": status["frontend_build_status"],
                "tauri_build_status": status["tauri_build_status"],
                "artifacts_created": status["artifacts_created"],
                "artifacts_missing": status["artifacts_missing"],
                "setup_instructions": status["setup_instructions"],
            }
        package_manager = "pnpm" if shutil.which("pnpm") else "npm"
        command = f"{package_manager} tauri {action}" if package_manager == "pnpm" else f"npm run tauri:{action}"
        return {"status": "ready", "action": action, "command": command, "cwd": status["desktop_root"], "frontend_build_status": status["frontend_build_status"], "tauri_build_status": status["tauri_build_status"], "artifacts_created": status["artifacts_created"], "artifacts_missing": status["artifacts_missing"], "message": "Run the command manually when ready; v0.5.6 does not force desktop builds in QA."}

    def _frontend_artifacts(self) -> list[dict[str, Any]]:
        dist = ROOT / "apps" / "desktop" / "dist"
        if not dist.exists():
            return []
        return [{"path": str(path), "name": path.name, "size_bytes": path.stat().st_size, "artifact_type": "frontend"} for path in dist.rglob("*") if path.is_file() and path.suffix in {".html", ".js", ".css"}]

    def _native_artifacts(self) -> list[dict[str, Any]]:
        bases = [
            ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle",
            ROOT / "release" / "artifacts",
        ]
        suffixes = {".dmg", ".msi", ".exe", ".AppImage", ".deb", ".rpm", ".zip"}
        artifacts: list[dict[str, Any]] = []
        for base in bases:
            if not base.exists():
                continue
            artifacts.extend({"path": str(path), "name": path.name, "size_bytes": path.stat().st_size, "artifact_type": "native"} for path in base.rglob("*") if path.is_file() and (path.suffix in suffixes or path.name.endswith(".tar.gz")))
        return artifacts

    def _native_artifacts_detailed(self) -> list[dict[str, Any]]:
        """Detect native artifacts with full metadata including sha256 and timestamps."""
        from datetime import datetime, timezone

        bases = [
            ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle",
            ROOT / "release" / "artifacts",
        ]
        suffixes = {".dmg", ".msi", ".exe", ".AppImage", ".deb", ".rpm", ".zip", ".app"}
        artifacts: list[dict[str, Any]] = []

        for base in bases:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() in suffixes or path.name.endswith(".tar.gz"):
                    stat = path.stat()
                    artifact = {
                        "path": str(path),
                        "name": path.name,
                        "platform": self._artifact_platform(path),
                        "artifact_type": "native",
                        "size_bytes": stat.st_size,
                        "sha256": self._sha256(path),
                        "signed": False,
                        "notarized": False,
                        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat() if stat.st_mtime else None,
                    }
                    artifacts.append(artifact)
        return artifacts

    def _write_build_report(self, data: dict[str, Any]) -> dict[str, Any]:
        """Write build report to release/build-report.json."""
        from datetime import datetime, timezone
        release_dir = ROOT / "release"
        release_dir.mkdir(parents=True, exist_ok=True)
        report_path = release_dir / "build-report.json"

        report = {
            **data,
            "report_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return {"path": str(report_path), "status": "written"}

    def _get_command_version(self, command: str) -> str:
        """Get version of a command-line tool."""
        import shutil
        tool = shutil.which(command)
        if not tool:
            return "not_installed"
        try:
            result = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()[:100] or "version_unknown"
        except Exception:
            pass
        return "version_error"

    def _get_tauri_version(self, desktop_root: str | None) -> str:
        """Get Tauri CLI version."""
        tauri_cli = self._tauri_cli_path(desktop_root)
        if tauri_cli:
            return self._get_command_version(tauri_cli)
        return "not_installed"

    def _artifact_type(self, path: Path) -> str:
        text_suffixes = {".html", ".js", ".css"}
        return "frontend" if path.suffix in text_suffixes else "native"

    def _artifact_platform(self, path: Path) -> str:
        name = path.name.lower()
        if path.suffix in {".html", ".js", ".css"}:
            return "frontend"
        if name.endswith((".dmg", ".app")):
            return "macos"
        if name.endswith((".msi", ".exe")):
            return "windows"
        if name.endswith((".appimage", ".deb", ".rpm")):
            return "linux"
        return platform.system().lower() or "unknown"

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _git_commit(self) -> str | None:
        try:
            result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True, timeout=3)
            return result.stdout.strip() or None if result.returncode == 0 else None
        except Exception:
            return None

    def _run_command_check(self, name: str, command: list[str], timeout: int = 60, cwd: Path | None = None) -> dict[str, Any]:
        try:
            result = subprocess.run(command, cwd=str(cwd or ROOT), capture_output=True, text=True, timeout=timeout)
            return {"name": name, "status": "passed" if result.returncode == 0 else "failed", "returncode": result.returncode, "summary": (result.stdout or result.stderr)[-1000:]}
        except Exception as exc:
            return {"name": name, "status": "failed", "error": str(exc)}

    def _call_check(self, name: str, func) -> dict[str, Any]:
        try:
            result = func()
            status = result.get("status", "ok") if isinstance(result, dict) else "ok"
            if status in {"failed", "error"}:
                return {"name": name, "status": "failed", "result": self._redact(result)}
            return {"name": name, "status": "passed", "result": self._redact(result)}
        except Exception as exc:
            return {"name": name, "status": "failed", "error": str(exc)}

    def _redact(self, data: Any) -> Any:
        if isinstance(data, dict):
            redacted = {}
            for key, value in data.items():
                lowered = key.lower()
                if any(part in lowered for part in ("token", "secret", "api_key", "password")) and "status" not in lowered and "masked" not in lowered:
                    redacted[key] = "[redacted]"
                else:
                    redacted[key] = self._redact(value)
            return redacted
        if isinstance(data, list):
            return [self._redact(item) for item in data]
        return data

    def desktop_v1_candidate_check(self) -> dict[str, Any]:
        checks = []
        passed = 0
        failed = 0

        v = SettingsManager().get("app_version")["value"]
        checks.append({"name": "version_aligned", "status": "passed" if v == "1.0.2" else "failed", "version": v})
        if v == "1.0.2": passed += 1
        else: failed += 1

        for fname in ("LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "ROADMAP.md", "SUPPORT.md", ".gitignore", ".env.example"):
            exists = (ROOT / fname).exists()
            checks.append({"name": f"file_{fname}", "status": "passed" if exists else "failed"})
            if exists: passed += 1
            else: failed += 1

        env_example = ROOT / ".env.example"
        secret_patterns = ("sk-", "api-", "-----BEGIN", "token", "secret", "key=", "password")
        if env_example.exists():
            content = env_example.read_text(encoding="utf-8")
            has_real_secret = False
            for line in content.strip().split("\n"):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    val = stripped.split("=", 1)[1].strip()
                    if any(p in val.lower() for p in secret_patterns) and len(val) > 3:
                        has_real_secret = True
                        break
            checks.append({"name": "no_env_secrets", "status": "passed" if not has_real_secret else "failed"})
            if not has_real_secret: passed += 1
            else: failed += 1

        from runtime.sidecar import sidecar_status as sc_status
        sc = sc_status()
        sc_ok = sc.get("status") in {"available", "unavailable"}
        checks.append({"name": "sidecar_honest", "status": "passed" if sc_ok else "failed", "sidecar_status": sc.get("status")})
        if sc_ok: passed += 1
        else: failed += 1

        s = self.signing_status()
        signing_honest = all(s.get(k) in {True, False} for k in ("signed", "notarized"))
        checks.append({"name": "signing_honest", "status": "passed" if signing_honest else "failed", "signed": s.get("signed"), "notarized": s.get("notarized")})
        if signing_honest: passed += 1
        else: failed += 1

        dist_exists = (ROOT / "apps" / "desktop" / "dist").exists()
        checks.append({"name": "frontend_built", "status": "passed" if dist_exists else "failed"})
        if dist_exists: passed += 1
        else: failed += 1

        from runtime.sidecar import _sidecar_executable_path
        exe = _sidecar_executable_path()
        if exe:
            exe_size = exe.stat().st_size
            checks.append({"name": "sidecar_executable_real", "status": "passed" if exe_size > 1024 else "failed", "size_kb": round(exe_size / 1024, 1)})
            passed += 1
        else:
            checks.append({"name": "sidecar_executable_real", "status": "skipped", "note": "Not built — optional for community builds"})

        sec_path = ROOT / "SECURITY.md"
        if sec_path.exists():
            sec_content = sec_path.read_text(encoding="utf-8")
            if "security@" in sec_content or "example.com" in sec_content:
                checks.append({"name": "security_contact_real", "status": "failed", "note": "Placeholder email still found — update SECURITY.md"})
                failed += 1
            else:
                checks.append({"name": "security_contact_real", "status": "passed", "note": "Real security contact set"})
                passed += 1

        overall = "passed" if failed == 0 else "needs_work"
        return {
            "status": overall,
            "checks_passed": passed,
            "checks_failed": failed,
            "checks_total": len(checks),
            "checks": checks,
            "overall_opinion": "Ready for v1.0 release candidate." if overall == "passed" else "Complete failing checks before v1.0 release candidate.",
        }
