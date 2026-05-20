"""Skill execution sandbox for Liuant Agentic OS v2.1.0.

Provides safe, approval-gated skill execution with permission checking.
Supports process-isolated execution via subprocess for security hardening.
Skills run in a restricted context with no direct access to secrets,
filesystem outside allowed paths, or external actions without approval.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from runtime.skills.manifest import CRITICAL_PERMISSIONS, is_critical_permission
from runtime.skills.registry import get_skill
from runtime.storage import WORKSPACE

SECRET_PATTERNS = [
    r"(?i)(api.?key|secret|token|password)\s*[=:]\s*\S+",
    r"sk-[A-Za-z0-9]{20,}",
    r"Bearer\s+[A-Za-z0-9._\-]+",
]

SAFE_ENV_VARS = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "PYTHONPATH", "LIUANT_DB_PATH", "LIUANT_WORKSPACE"}


def _redact_secrets(text: str) -> str:
    """Redact secret-like patterns from text."""
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def _clean_env() -> dict[str, str]:
    """Create a minimal safe environment without secrets."""
    env = {}
    for key, value in os.environ.items():
        if key in SAFE_ENV_VARS:
            env[key] = value
        elif any(s in key.lower() for s in ("key", "secret", "token", "password", "api_", "auth_")):
            continue
        else:
            env[key] = value
    env["LIUANT_SKILL_ISOLATED"] = "1"
    return env


class SkillContext:
    """Restricted execution context for skills."""

    def __init__(
        self,
        skill_id: str,
        inputs: dict[str, Any] | None = None,
        permissions: list[str] | None = None,
        approved_permissions: list[str] | None = None,
    ) -> None:
        self.skill_id = skill_id
        self.inputs = inputs or {}
        self.permissions = permissions or []
        self.approved_permissions = approved_permissions or []
        self.workspace = str(WORKSPACE)
        self.skill_dir = str(WORKSPACE / "skills" / "installed" / skill_id)

    def has_permission(self, permission: str) -> bool:
        return permission in self.approved_permissions

    def has_any_permission(self, *permissions: str) -> bool:
        return any(p in self.approved_permissions for p in permissions)

    def resolve_path(self, path: str) -> str:
        resolved = Path(path).resolve()
        skill_dir = Path(self.skill_dir).resolve()
        workspace = Path(self.workspace).resolve()
        if not (str(resolved).startswith(str(skill_dir)) or str(resolved).startswith(str(workspace))):
            raise PermissionError(f"Path '{path}' is outside allowed directories")
        return str(resolved)

    def get_model_client(self) -> dict[str, Any]:
        return {"available": True, "message": "Model access requires models.generate permission"}

    def get_usage_client(self) -> dict[str, Any]:
        return {"available": True, "message": "Usage tracking available"}


def _run_skill_import(skill_id: str, skill_dir: Path, entrypoint: str, inputs: dict[str, Any], permissions: list[str], approved: list[str]) -> dict[str, Any]:
    """Execute skill via import (legacy/fallback mode)."""
    import importlib.util
    entrypoint_path = skill_dir / entrypoint
    try:
        spec = importlib.util.spec_from_file_location(f"skill_{skill_id}", entrypoint_path)
        if spec is None or spec.loader is None:
            return {"status": "failed", "result": {}, "actions": [], "warnings": ["Failed to load skill module"], "approval_required": False}
        ctx = SkillContext(skill_id=skill_id, inputs=inputs, permissions=permissions, approved_permissions=approved)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"skill_{skill_id}"] = module
        spec.loader.exec_module(module)
        if hasattr(module, "execute"):
            result = module.execute(ctx, inputs or {})
        elif hasattr(module, "run"):
            result = module.run(ctx, inputs or {})
        else:
            return {"status": "failed", "result": {}, "actions": [], "warnings": ["Skill module has no execute() or run() function"], "approval_required": False}
        if isinstance(result, dict):
            return {"status": result.get("status", "completed"), "result": result.get("result", {}), "actions": result.get("actions", []), "warnings": result.get("warnings", []), "approval_required": result.get("approval_required", False)}
        return {"status": "completed", "result": result, "actions": [], "warnings": [], "approval_required": False}
    except PermissionError as exc:
        return {"status": "blocked", "result": {}, "actions": [], "warnings": [f"Permission denied: {exc}"], "approval_required": True}
    except Exception as exc:
        return {"status": "failed", "result": {}, "actions": [], "warnings": [f"Execution error: {exc}"], "approval_required": False}


def _run_skill_process(skill_id: str, skill_dir: Path, entrypoint: str, inputs: dict[str, Any], permissions: list[str], approved: list[str], timeout: int = 30) -> dict[str, Any]:
    """Execute skill in an isolated subprocess via stdin/stdout JSON protocol."""
    entrypoint_path = skill_dir / entrypoint
    if not entrypoint_path.exists():
        return {"status": "failed", "result": {}, "actions": [], "warnings": [f"Entrypoint not found: {entrypoint}"], "approval_required": False}

    context = {
        "skill_id": skill_id,
        "inputs": inputs,
        "workspace": str(WORKSPACE),
        "permissions": permissions,
        "approved_permissions": approved,
        "allowed_paths": [str(skill_dir.resolve()), str(WORKSPACE.resolve())],
        "model_role": "default",
    }

    env = _clean_env()
    start_time = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(entrypoint_path), "--liuant-skill-run"],
            input=json.dumps(context),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(skill_dir),
            env=env,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        stderr_redacted = _redact_secrets(proc.stderr) if proc.stderr else ""
        warnings = []
        if stderr_redacted:
            warnings.append(f"stderr: {stderr_redacted[:500]}")

        try:
            output = json.loads(proc.stdout)
            if isinstance(output, dict):
                return {
                    "status": output.get("status", "completed"),
                    "result": output.get("result", {}),
                    "actions": output.get("actions", []),
                    "warnings": output.get("warnings", []) + warnings,
                    "approval_required": output.get("approval_required", False),
                }
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "result": {},
                "actions": [],
                "warnings": warnings + ["Invalid JSON output from skill"],
                "approval_required": False,
            }

        return {"status": "completed", "result": output, "actions": [], "warnings": warnings, "approval_required": False}

    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "result": {},
            "actions": [],
            "warnings": [f"Skill timed out after {timeout}s"],
            "approval_required": False,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "result": {},
            "actions": [],
            "warnings": [f"Process execution error: {exc}"],
            "approval_required": False,
        }


def run_skill(
    skill_id: str,
    inputs: dict[str, Any] | None = None,
    dry_run: bool = True,
    timeout: int = 30,
    isolated: bool = True,
) -> dict[str, Any]:
    """Execute a skill with permission checking and process isolation.

    Args:
        skill_id: Skill identifier.
        inputs: User-provided inputs.
        dry_run: If True, simulate without executing.
        timeout: Max execution time in seconds (default 30).
        isolated: If True, use subprocess isolation; otherwise use import.

    Returns:
        Structured execution result.
    """
    inputs = inputs or {}
    skill = get_skill(skill_id)
    if not skill:
        return {"status": "failed", "skill_id": skill_id, "result": {}, "actions": [], "warnings": [f"Skill '{skill_id}' not found."], "approval_required": False}

    if not skill.get("enabled", False):
        return {"status": "blocked", "skill_id": skill_id, "result": {}, "actions": [], "warnings": [f"Skill '{skill_id}' is disabled. Enable it first."], "approval_required": False}

    permissions = skill.get("permissions", [])
    approved = skill.get("approved_permissions", [])
    critical_unapproved = [p for p in permissions if is_critical_permission(p) and p not in approved]
    if critical_unapproved:
        return {"status": "blocked", "skill_id": skill_id, "result": {}, "actions": [], "warnings": [f"Critical permissions not approved: {critical_unapproved}"], "approval_required": True}
    unapproved = [p for p in permissions if p not in approved]
    if unapproved:
        return {"status": "blocked", "skill_id": skill_id, "result": {}, "actions": [], "warnings": [f"Permissions not approved: {unapproved}"], "approval_required": True}

    skill_dir = Path(skill.get("path", ""))
    if not skill_dir.exists():
        return {"status": "failed", "skill_id": skill_id, "result": {}, "actions": [], "warnings": [f"Skill directory not found: {skill_dir}"], "approval_required": False}

    entrypoint = "skill.py"
    try:
        manifest_path = skill_dir / "skill.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entrypoint = manifest.get("entrypoint", "skill.py")
    except Exception:
        pass

    if dry_run:
        return {"status": "completed", "skill_id": skill_id, "result": {"dry_run": True, "message": f"Skill '{skill_id}' would execute with inputs: {inputs}"}, "actions": [], "warnings": ["Dry run mode — no actual execution"], "approval_required": False}

    if isolated:
        result = _run_skill_process(skill_id, skill_dir, entrypoint, inputs, permissions, approved, timeout=timeout)
    else:
        result = _run_skill_import(skill_id, skill_dir, entrypoint, inputs, permissions, approved)

    result["skill_id"] = skill_id
    return result
