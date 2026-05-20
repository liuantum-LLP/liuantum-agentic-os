"""Skill workflow templates for Liuant Agentic OS v2.5.0.

Workflows combine multiple skills into practical, step-by-step pipelines.
Workflows do not run automatically after import. Execution requires user confirmation.

v2.5.0 additions: preview_workflow_run, workflow_permission_summary,
output chaining polish, audit logging, run history, dry-run improvements,
failure recovery, and rerun planning.
"""

from __future__ import annotations

import json
import re
import time
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.skills.executor import run_skill
from runtime.skills.manifest import KNOWN_PERMISSIONS, get_risk_level, is_critical_permission
from runtime.skills.registry import get_skill, list_installed_skills
from runtime.skills.workflow_audit import (
    record_workflow_run_start,
    record_workflow_run_complete,
    record_workflow_step,
    get_workflow_steps,
)
from runtime.storage import ROOT, WORKSPACE, read_json, write_json

SKILLS_DIR = WORKSPACE / "skills"
WORKFLOWS_DIR = SKILLS_DIR / "workflows"
WORKFLOW_REGISTRY_FILE = WORKFLOWS_DIR / "registry.json"
IMPORTED_WORKFLOWS_DIR = WORKFLOWS_DIR / "imported"

WORKFLOW_SCHEMA_VERSION = "1.0"
WORKFLOW_MANIFEST_NAME = "workflow.json"

WORKFLOW_SCHEMA = {
    "required": ["schema_version", "workflow_id", "name", "description", "pack_id", "version", "steps"],
    "fields": {
        "schema_version": str,
        "workflow_id": str,
        "name": str,
        "description": str,
        "pack_id": str,
        "version": str,
        "steps": list,
        "required_permissions": list,
        "approval_required": bool,
        "tags": list,
    },
}

STEP_SCHEMA = {
    "required": ["step_id", "skill_id", "command"],
    "fields": {
        "step_id": str,
        "skill_id": str,
        "command": str,
        "input_schema": dict,
        "input_from": dict,
        "output_key": str,
        "defaults": dict,
        "continue_on_error": bool,
    },
}


def _ensure_workflows_dir() -> None:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def _load_workflow_registry() -> dict[str, Any]:
    _ensure_workflows_dir()
    old_file = WORKFLOWS_DIR / "workflow_registry.json"
    if old_file.exists() and not WORKFLOW_REGISTRY_FILE.exists():
        try:
            shutil.copy2(old_file, WORKFLOW_REGISTRY_FILE)
        except Exception:
            pass
    if WORKFLOW_REGISTRY_FILE.exists():
        return read_json(WORKFLOW_REGISTRY_FILE, {"workflows": {}})
    return {"workflows": {}}


def _save_workflow_registry(registry: dict[str, Any]) -> None:
    _ensure_workflows_dir()
    write_json(WORKFLOW_REGISTRY_FILE, registry)


def _get_workflow_by_id(workflow_id: str) -> dict[str, Any] | None:
    """Get workflow data by ID from registry or examples."""
    registry = _load_workflow_registry()
    wf_info = registry.get("workflows", {}).get(workflow_id)
    if wf_info:
        return wf_info

    # Check imported workflows dir
    if IMPORTED_WORKFLOWS_DIR.exists():
        wf_dir = IMPORTED_WORKFLOWS_DIR / workflow_id
        if wf_dir.is_dir():
            wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
            if wf_file.exists():
                try:
                    wf = json.loads(wf_file.read_text(encoding="utf-8"))
                    if wf.get("workflow_id") == workflow_id:
                        return {**wf, "source": str(wf_file)}
                except Exception:
                    pass

    official_workflows_dir = ROOT / "examples" / "workflows"
    if official_workflows_dir.exists():
        for wf_dir in official_workflows_dir.iterdir():
            if wf_dir.is_dir():
                wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                if wf_file.exists():
                    try:
                        wf = json.loads(wf_file.read_text(encoding="utf-8"))
                        if wf.get("workflow_id") == workflow_id:
                            return {**wf, "source": str(wf_file)}
                    except Exception:
                        pass

    for pack_dir in (ROOT / "examples" / "skill-packs").iterdir():
        if pack_dir.is_dir():
            workflows_dir = pack_dir / "source" / "workflows"
            if workflows_dir.exists():
                for wf_dir in workflows_dir.iterdir():
                    if wf_dir.is_dir():
                        wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                        if wf_file.exists():
                            try:
                                wf = json.loads(wf_file.read_text(encoding="utf-8"))
                                if wf.get("workflow_id") == workflow_id:
                                    return {**wf, "source": str(wf_file)}
                            except Exception:
                                pass

    return None


def _resolve_nested_value(data: dict[str, Any], key_path: str) -> Any:
    """Resolve a nested key path like 'csv_summary.summary_text' from a dict."""
    parts = key_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _resolve_step_inputs(
    step: dict[str, Any],
    context: dict[str, Any],
    user_inputs: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Resolve step inputs from input_from, defaults, and user inputs.

    Returns (resolved_inputs, errors).
    """
    resolved = {}
    errors = []
    input_from = step.get("input_from", {})
    defaults = step.get("defaults", {})

    for param_name, source in input_from.items():
        if source in context:
            resolved[param_name] = context[source]
        elif "." in source:
            nested = _resolve_nested_value(context, source)
            if nested is not None:
                resolved[param_name] = nested
            else:
                errors.append(f"Step '{step.get('step_id', '')}': output key '{source}' not found in context for parameter '{param_name}'")
        else:
            errors.append(f"Step '{step.get('step_id', '')}': output key '{source}' not found in context for parameter '{param_name}'")

    for param_name, default_value in defaults.items():
        if param_name not in resolved:
            resolved[param_name] = default_value

    for param_name in user_inputs:
        if param_name not in input_from:
            resolved[param_name] = user_inputs[param_name]

    return resolved, errors


def _get_skill_permissions(skill_id: str) -> list[str]:
    """Get permissions for an installed skill."""
    skill = get_skill(skill_id)
    if skill:
        skill_path = skill.get("path", "")
        if skill_path:
            skill_json_path = Path(skill_path) / "skill.json"
            if skill_json_path.exists():
                try:
                    sm = json.loads(skill_json_path.read_text(encoding="utf-8"))
                    return sm.get("permissions", [])
                except Exception:
                    pass
    return []


# ============================================================
# v2.4.0: Validate, Inspect, Run, List, Register
# ============================================================

def validate_workflow(workflow_path: str | Path) -> dict[str, Any]:
    """Validate a workflow.json file."""
    workflow_path = Path(workflow_path)
    if not workflow_path.exists():
        return {"status": "failed", "errors": [f"Workflow file not found: {workflow_path}"]}

    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "failed", "errors": [f"Invalid workflow.json: {exc}"]}

    errors = []
    warnings = []

    for field in WORKFLOW_SCHEMA["required"]:
        if field not in workflow:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"status": "failed", "errors": errors, "warnings": []}

    steps = workflow.get("steps", [])
    if not steps:
        errors.append("Workflow must have at least one step")

    step_ids = set()
    output_keys = set()
    for step in steps:
        for field in STEP_SCHEMA["required"]:
            if field not in step:
                errors.append(f"Step '{step.get('step_id', 'unknown')}' missing required field: {field}")

        sid = step.get("step_id", "")
        if sid in step_ids:
            errors.append(f"Duplicate step_id: {sid}")
        step_ids.add(sid)

        out_key = step.get("output_key", "")
        if out_key:
            if out_key in output_keys:
                warnings.append(f"Duplicate output_key: {out_key}")
            output_keys.add(out_key)

        input_from = step.get("input_from", {})
        for key, source in input_from.items():
            if source not in output_keys and "." not in source:
                warnings.append(f"Step '{sid}' references output_key '{source}' that is not produced by any previous step")

    required_perms = workflow.get("required_permissions", [])
    unknown_perms = [p for p in required_perms if p not in KNOWN_PERMISSIONS]
    if unknown_perms:
        warnings.append(f"Unknown permissions: {unknown_perms}")

    risk = get_risk_level(required_perms)

    installed = {s["id"]: s for s in list_installed_skills()}
    missing_skills = []
    for step in steps:
        sid = step.get("skill_id", "")
        if sid not in installed:
            missing_skills.append(sid)

    if missing_skills:
        warnings.append(f"Skills not installed: {missing_skills}")

    status = "passed" if not errors else "failed"
    if not errors and warnings:
        status = "warning"

    return {
        "status": status,
        "workflow_id": workflow.get("workflow_id", ""),
        "name": workflow.get("name", ""),
        "version": workflow.get("version", ""),
        "steps": len(steps),
        "errors": errors,
        "warnings": warnings,
        "risk_level": risk,
        "required_permissions": required_perms,
        "missing_skills": missing_skills,
    }


def inspect_workflow(workflow_path: str | Path | None = None, workflow_id: str | None = None) -> dict[str, Any]:
    """Inspect a workflow.json file or workflow by ID."""
    workflow = None
    if workflow_id:
        wf_data = _get_workflow_by_id(workflow_id)
        if not wf_data:
            return {"status": "error", "message": f"Workflow '{workflow_id}' not found"}
        workflow = wf_data
    elif workflow_path:
        p = Path(workflow_path)
        if not p.exists():
            wf_data = _get_workflow_by_id(str(workflow_path))
            if wf_data:
                workflow = wf_data
            else:
                return {"status": "error", "message": f"Workflow file or ID not found: {workflow_path}"}
        else:
            try:
                workflow = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return {"status": "error", "message": f"Invalid workflow.json: {exc}"}
    else:
        return {"status": "error", "message": "Provide workflow_path or workflow_id"}

    installed = {s["id"]: s for s in list_installed_skills()}
    steps_info = []
    for step in workflow.get("steps", []):
        sid = step.get("skill_id", "")
        skill_info = installed.get(sid, {})
        steps_info.append({
            "step_id": step.get("step_id", ""),
            "skill_id": sid,
            "command": step.get("command", ""),
            "installed": sid in installed,
            "enabled": skill_info.get("enabled", False),
            "input_from": step.get("input_from", {}),
            "output_key": step.get("output_key", ""),
            "defaults": step.get("defaults", {}),
        })

    return {
        "status": "ok",
        "workflow_id": workflow.get("workflow_id", ""),
        "name": workflow.get("name", ""),
        "description": workflow.get("description", ""),
        "pack_id": workflow.get("pack_id", ""),
        "version": workflow.get("version", ""),
        "steps": steps_info,
        "required_permissions": workflow.get("required_permissions", []),
        "approval_required": workflow.get("approval_required", False),
        "tags": workflow.get("tags", []),
        "source": workflow.get("source", ""),
    }


# ============================================================
# v2.5.0: Workflow Run Preview
# ============================================================

def preview_workflow_run(
    workflow_id: str,
    inputs: dict[str, Any] | None = None,
    workspace: str = "default",
) -> dict[str, Any]:
    """Preview a workflow run without executing any skills.

    Returns step-by-step readiness status, missing skills, permissions,
    and whether approval is required.
    """
    wf_data = _get_workflow_by_id(workflow_id)
    if not wf_data:
        return {"status": "blocked", "workflow_id": workflow_id, "message": f"Workflow '{workflow_id}' not found"}

    steps = wf_data.get("steps", [])
    installed = {s["id"]: s for s in list_installed_skills()}
    output_keys = set(inputs or {})

    step_previews = []
    missing_skills = []
    disabled_skills = []
    missing_permissions = []
    all_permissions = set()
    warnings = []
    external_actions_possible = False

    for step in steps:
        sid = step.get("skill_id", "")
        skill_info = installed.get(sid, {})
        skill_installed = sid in installed
        skill_enabled = skill_info.get("enabled", False)

        perms = _get_skill_permissions(sid)
        all_permissions.update(perms)

        input_from = step.get("input_from", {})
        input_source = "user_input"
        for param, src in input_from.items():
            if src in output_keys:
                input_source = "previous_step"
                break

        if not skill_installed:
            status = "missing_skill"
            if sid not in missing_skills:
                missing_skills.append(sid)
        elif not skill_enabled:
            status = "disabled_skill"
            if sid not in disabled_skills:
                disabled_skills.append(sid)
        else:
            status = "ready"

        step_preview = {
            "step_id": step.get("step_id", ""),
            "skill_id": sid,
            "command": step.get("command", ""),
            "enabled": skill_enabled,
            "installed": skill_installed,
            "permissions_required": perms,
            "permissions_approved": skill_info.get("approved_permissions", []),
            "status": status,
            "input_source": input_source,
            "output_key": step.get("output_key", ""),
        }
        step_previews.append(step_preview)

        if step.get("output_key"):
            output_keys.add(step.get("output_key", ""))

        if any(is_critical_permission(p) for p in perms):
            external_actions_possible = True

    for perm in all_permissions:
        if perm not in KNOWN_PERMISSIONS:
            missing_permissions.append(perm)

    approval_required = external_actions_possible or any(
        is_critical_permission(p) for p in all_permissions
    )

    blocked_reasons = []
    if missing_skills:
        blocked_reasons.append(f"Missing skills: {missing_skills}")
    if disabled_skills:
        blocked_reasons.append(f"Disabled skills: {disabled_skills}")

    if blocked_reasons:
        status = "blocked"
        warnings.extend(blocked_reasons)
    elif missing_permissions:
        status = "warning"
        warnings.append(f"Unknown permissions: {missing_permissions}")
    else:
        status = "ready"

    return {
        "status": status,
        "workflow_id": workflow_id,
        "name": wf_data.get("name", ""),
        "steps": step_previews,
        "missing_skills": missing_skills,
        "disabled_skills": disabled_skills,
        "missing_permissions": missing_permissions,
        "external_actions_possible": external_actions_possible,
        "approval_required": approval_required,
        "warnings": warnings,
    }


# ============================================================
# v2.5.0: Workflow Permission Summary
# ============================================================

def workflow_permission_summary(workflow_id: str) -> dict[str, Any]:
    """Collect permissions across all workflow steps."""
    wf_data = _get_workflow_by_id(workflow_id)
    if not wf_data:
        return {"status": "error", "workflow_id": workflow_id, "message": f"Workflow '{workflow_id}' not found"}

    steps = wf_data.get("steps", [])
    installed = {s["id"]: s for s in list_installed_skills()}
    permission_map: dict[str, dict[str, Any]] = {}

    for step in steps:
        sid = step.get("skill_id", "")
        perms = _get_skill_permissions(sid)
        for perm in perms:
            if perm not in permission_map:
                permission_map[perm] = {
                    "permission": perm,
                    "required_by": [],
                    "risk_level": get_risk_level([perm]),
                    "approved": False,
                }
            permission_map[perm]["required_by"].append(sid)

            if sid in installed:
                skill_info = installed[sid]
                approved = skill_info.get("approved_permissions", [])
                if perm in approved or skill_info.get("enabled", False):
                    permission_map[perm]["approved"] = True

    permissions = list(permission_map.values())
    critical = [p for p in permissions if is_critical_permission(p["permission"])]
    missing = [p for p in permissions if not p["approved"]]

    return {
        "workflow_id": workflow_id,
        "permissions": permissions,
        "critical_permissions": critical,
        "missing_approvals": missing,
        "can_run": len(missing) == 0,
    }


# ============================================================
# v2.5.0: Improved Workflow Run with Output Chaining & Audit
# ============================================================

def run_workflow(workflow_path: str | Path | None = None, workflow_id: str | None = None, inputs: dict[str, Any] | None = None, dry_run: bool = True, user_confirmed: bool = False, workspace: str = "default") -> dict[str, Any]:
    """Execute a workflow step by step with output chaining and audit logging.

    Args:
        workflow_path: Path to workflow.json (alternative to workflow_id).
        workflow_id: Workflow ID from registry (alternative to workflow_path).
        inputs: Initial inputs for the workflow.
        dry_run: If True, simulate without executing skills.
        user_confirmed: Whether user has confirmed execution.
        workspace: Workspace identifier for audit logs.

    Returns:
        Structured workflow execution result.
    """
    workflow = None

    if workflow_path:
        workflow_path = Path(workflow_path)
        if not workflow_path.exists():
            return {"status": "error", "message": f"Workflow file not found: {workflow_path}"}
        try:
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"status": "error", "message": f"Invalid workflow.json: {exc}"}
    elif workflow_id:
        wf_data = _get_workflow_by_id(workflow_id)
        if not wf_data:
            return {"status": "error", "message": f"Workflow '{workflow_id}' not found"}
        workflow = wf_data
    else:
        return {"status": "error", "message": "Provide workflow_path or workflow_id"}

    wf_id = workflow.get("workflow_id", workflow_id or "unknown")
    steps = workflow.get("steps", [])

    run_id = record_workflow_run_start(
        workflow_id=wf_id,
        workspace=workspace,
        dry_run=dry_run,
        user_confirmed=user_confirmed,
        step_count=len(steps),
    )

    if dry_run:
        step_plans = []
        output_keys = set(inputs or {})
        for step in steps:
            sid = step.get("skill_id", "")
            skill_info = get_skill(sid) or {}
            input_from = step.get("input_from", {})
            resolved_params = {}
            for param, src in input_from.items():
                if src in output_keys:
                    resolved_params[param] = f"<from:{src}>"
                elif "." in src:
                    resolved_params[param] = f"<nested:{src}>"
                else:
                    resolved_params[param] = f"<missing:{src}>"
            step_plans.append({
                "step_id": step.get("step_id", ""),
                "skill_id": sid,
                "command": step.get("command", ""),
                "input_from": resolved_params,
                "defaults": step.get("defaults", {}),
                "output_key": step.get("output_key", ""),
            })
            if step.get("output_key"):
                output_keys.add(step.get("output_key", ""))

        record_workflow_run_complete(run_id, "dry_run", completed_steps=0)
        return {
            "status": "dry_run",
            "run_id": run_id,
            "workflow_id": wf_id,
            "message": f"Workflow '{wf_id}' would execute {len(steps)} steps.",
            "execution_plan": step_plans,
            "steps": steps,
        }

    if not user_confirmed:
        record_workflow_run_complete(run_id, "blocked", error_redacted="User confirmation required")
        return {"status": "blocked", "message": "Workflow execution requires user confirmation. Set user_confirmed=True.", "run_id": run_id}

    installed = {s["id"]: s for s in list_installed_skills()}
    context = dict(inputs or {})
    step_results = []
    warnings = []
    external_actions_count = 0
    completed_steps = 0

    for step in steps:
        step_start = time.time()
        sid = step.get("skill_id", "")
        step_id = step.get("step_id", "")

        if sid not in installed:
            record_workflow_step(run_id, step_id, sid, step.get("command", ""), "failed", error_redacted=f"Skill '{sid}' not installed")
            record_workflow_run_complete(run_id, "failed", completed_steps=completed_steps, failed_step_id=step_id, error_redacted=f"Skill '{sid}' not installed", warnings_count=len(warnings), external_actions_count=external_actions_count)
            return {"status": "failed", "message": f"Skill '{sid}' not installed", "step": step_id, "run_id": run_id, "step_results": step_results}

        skill_info = installed[sid]
        if not skill_info.get("enabled", False):
            record_workflow_step(run_id, step_id, sid, step.get("command", ""), "failed", error_redacted=f"Skill '{sid}' is disabled")
            record_workflow_run_complete(run_id, "failed", completed_steps=completed_steps, failed_step_id=step_id, error_redacted=f"Skill '{sid}' is disabled", warnings_count=len(warnings), external_actions_count=external_actions_count)
            return {"status": "failed", "message": f"Skill '{sid}' is disabled. Enable it first.", "step": step_id, "run_id": run_id, "step_results": step_results}

        step_inputs, input_errors = _resolve_step_inputs(step, context, inputs or {})
        if input_errors:
            continue_on_error = step.get("continue_on_error", False)
            for err in input_errors:
                warnings.append(err)
            if not continue_on_error:
                record_workflow_step(run_id, step_id, sid, step.get("command", ""), "failed", error_redacted="; ".join(input_errors))
                record_workflow_run_complete(run_id, "failed", completed_steps=completed_steps, failed_step_id=step_id, error_redacted="; ".join(input_errors), warnings_count=len(warnings), external_actions_count=external_actions_count)
                return {"status": "failed", "message": f"Input resolution failed for step '{step_id}'", "errors": input_errors, "run_id": run_id, "step_results": step_results}

        result = run_skill(sid, step_inputs, dry_run=False)
        step_duration = int((time.time() - step_start) * 1000)
        step_results.append({"step_id": step_id, "skill_id": sid, "result": result})

        if result.get("status") == "failed":
            record_workflow_step(run_id, step_id, sid, step.get("command", ""), "failed", duration_ms=step_duration, output_key=step.get("output_key", ""), error_redacted=result.get("message", "Unknown error"))
            record_workflow_run_complete(run_id, "failed", completed_steps=completed_steps, failed_step_id=step_id, error_redacted=result.get("message", "Unknown error"), warnings_count=len(warnings), external_actions_count=external_actions_count)
            recovery_suggestion = f"Check skill '{sid}' configuration and inputs. Rerun from step '{step_id}' after fixing the issue."
            return {"status": "failed", "message": f"Step '{step_id}' failed", "step": step_id, "run_id": run_id, "step_results": step_results, "recovery_suggestion": recovery_suggestion}

        if result.get("approval_required"):
            external_actions_count += 1
            record_workflow_step(run_id, step_id, sid, step.get("command", ""), "approval_required", duration_ms=step_duration, output_key=step.get("output_key", ""))
            record_workflow_run_complete(run_id, "approval_required", completed_steps=completed_steps, approval_required=True, warnings_count=len(warnings), external_actions_count=external_actions_count)
            return {"status": "approval_required", "message": f"Step '{step_id}' requires approval", "step_results": step_results, "run_id": run_id}

        out_key = step.get("output_key", "")
        if out_key:
            context[out_key] = result.get("result", {})

        record_workflow_step(run_id, step_id, sid, step.get("command", ""), "completed", duration_ms=step_duration, output_key=out_key, warnings_count=0)
        completed_steps += 1

    record_workflow_run_complete(run_id, "completed", completed_steps=completed_steps, warnings_count=len(warnings), external_actions_count=external_actions_count)
    return {
        "status": "completed",
        "workflow_id": wf_id,
        "run_id": run_id,
        "step_results": step_results,
        "context": {k: v for k, v in context.items() if k not in (inputs or {})},
        "warnings": warnings,
    }


# ============================================================
# v2.5.0: Workflow Run History
# ============================================================

def list_workflow_runs(workflow_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List workflow runs with summary data."""
    from runtime.skills.workflow_audit import list_workflow_runs as _list_runs
    return _list_runs(workflow_id=workflow_id, limit=limit)


def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    """Get a specific workflow run."""
    from runtime.skills.workflow_audit import get_workflow_run as _get_run
    return _get_run(run_id)


def export_workflow_run(run_id: str, format: str = "json") -> str:
    """Export a workflow run as JSON or markdown."""
    from runtime.skills.workflow_audit import export_workflow_run as _export
    return _export(run_id, format=format)


# ============================================================
# v2.5.0: Workflow Failure Recovery
# ============================================================

def preview_rerun_from_step(run_id: str, step_id: str) -> dict[str, Any]:
    """Preview a rerun from a specific failed step.

    Does not actually rerun — returns a safe preview of what would happen.
    """
    from runtime.skills.workflow_audit import get_workflow_run as _get_run
    run_data = _get_run(run_id)
    if not run_data:
        return {"status": "error", "message": f"Run '{run_id}' not found"}

    wf_id = run_data.get("workflow_id", "")
    wf_data = _get_workflow_by_id(wf_id)
    if not wf_data:
        return {"status": "error", "message": f"Workflow '{wf_id}' not found for rerun"}

    steps = wf_data.get("steps", [])
    target_step = None
    target_idx = None
    for i, step in enumerate(steps):
        if step.get("step_id") == step_id:
            target_step = step
            target_idx = i
            break

    if not target_step:
        return {"status": "error", "message": f"Step '{step_id}' not found in workflow '{wf_id}'"}

    preceding_steps = steps[:target_idx]
    can_rerun = True
    warnings = []

    sid = target_step.get("skill_id", "")
    installed = {s["id"]: s for s in list_installed_skills()}
    if sid not in installed:
        can_rerun = False
        warnings.append(f"Skill '{sid}' is still not installed")
    elif not installed[sid].get("enabled", False):
        can_rerun = False
        warnings.append(f"Skill '{sid}' is still disabled")

    return {
        "status": "ready" if can_rerun else "blocked",
        "run_id": run_id,
        "workflow_id": wf_id,
        "rerun_from_step": step_id,
        "preceding_steps_completed": len(preceding_steps),
        "remaining_steps": len(steps) - target_idx,
        "can_rerun": can_rerun,
        "warnings": warnings,
        "note": "This is a preview only. Actual rerun requires confirmation.",
    }


# ============================================================
# v2.4.0: List and Register
# ============================================================

def list_workflows() -> list[dict[str, Any]]:
    """List all discovered workflows from packs, examples, and imported folders."""
    workflows = []
    registry = _load_workflow_registry()

    for wf_id, wf_info in registry.get("workflows", {}).items():
        workflows.append({
            "workflow_id": wf_id,
            "name": wf_info.get("name", ""),
            "description": wf_info.get("description", ""),
            "pack_id": wf_info.get("pack_id", ""),
            "version": wf_info.get("version", ""),
            "steps": len(wf_info.get("steps", [])),
            "source": wf_info.get("source", ""),
        })

    # Read from imported workflows directory
    if IMPORTED_WORKFLOWS_DIR.exists():
        for wf_dir in IMPORTED_WORKFLOWS_DIR.iterdir():
            if wf_dir.is_dir():
                wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                if wf_file.exists():
                    try:
                        wf = json.loads(wf_file.read_text(encoding="utf-8"))
                        if wf.get("workflow_id") not in [w["workflow_id"] for w in workflows]:
                            workflows.append({
                                "workflow_id": wf.get("workflow_id", ""),
                                "name": wf.get("name", ""),
                                "description": wf.get("description", ""),
                                "pack_id": wf.get("pack_id", ""),
                                "version": wf.get("version", ""),
                                "steps": len(wf.get("steps", [])),
                                "source": str(wf_file),
                            })
                    except Exception:
                        pass

    for pack_dir in (ROOT / "examples" / "skill-packs").iterdir():
        if pack_dir.is_dir():
            workflows_dir = pack_dir / "source" / "workflows"
            if workflows_dir.exists():
                for wf_dir in workflows_dir.iterdir():
                    if wf_dir.is_dir():
                        wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                        if wf_file.exists():
                            try:
                                wf = json.loads(wf_file.read_text(encoding="utf-8"))
                                if wf.get("workflow_id") not in [w["workflow_id"] for w in workflows]:
                                    workflows.append({
                                        "workflow_id": wf.get("workflow_id", ""),
                                        "name": wf.get("name", ""),
                                        "description": wf.get("description", ""),
                                        "pack_id": wf.get("pack_id", ""),
                                        "version": wf.get("version", ""),
                                        "steps": len(wf.get("steps", [])),
                                        "source": str(wf_file),
                                    })
                            except Exception:
                                pass

    official_workflows_dir = ROOT / "examples" / "workflows"
    if official_workflows_dir.exists():
        for wf_dir in official_workflows_dir.iterdir():
            if wf_dir.is_dir():
                wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                if wf_file.exists():
                    try:
                        wf = json.loads(wf_file.read_text(encoding="utf-8"))
                        if wf.get("workflow_id") not in [w["workflow_id"] for w in workflows]:
                            workflows.append({
                                "workflow_id": wf.get("workflow_id", ""),
                                "name": wf.get("name", ""),
                                "description": wf.get("description", ""),
                                "pack_id": wf.get("pack_id", ""),
                                "version": wf.get("version", ""),
                                "steps": len(wf.get("steps", [])),
                                "source": str(wf_file),
                            })
                    except Exception:
                        pass

    return sorted(workflows, key=lambda x: x.get("workflow_id", ""))


def discover_workflows(paths: list[str] | None = None) -> dict[str, Any]:
    """Discover workflows from specified paths or default locations."""
    discovered = []
    paths_to_check = paths or [
        str(ROOT / "examples" / "skill-packs"),
        str(ROOT / "examples" / "workflows"),
        str(IMPORTED_WORKFLOWS_DIR),
    ]

    for path_str in paths_to_check:
        path = Path(path_str)
        if not path.exists():
            continue

        if path.name in ("workflows", "imported"):
            for wf_dir in path.iterdir():
                if not wf_dir.is_dir():
                    continue

                wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                if not wf_file.exists():
                    continue

                try:
                    wf = json.loads(wf_file.read_text(encoding="utf-8"))
                    validation = validate_workflow(wf_file)
                    discovered.append({
                        "workflow_id": wf.get("workflow_id", ""),
                        "name": wf.get("name", ""),
                        "description": wf.get("description", ""),
                        "pack_id": wf.get("pack_id", ""),
                        "version": wf.get("version", ""),
                        "path": str(wf_file),
                        "validation": validation,
                    })
                except Exception:
                    continue
        else:
            for pack_dir in path.iterdir():
                if not pack_dir.is_dir():
                    continue

                workflows_dir = pack_dir / "source" / "workflows"
                if not workflows_dir.exists():
                    workflows_dir = pack_dir

                for wf_dir in workflows_dir.iterdir():
                    if not wf_dir.is_dir():
                        continue

                    wf_file = wf_dir / WORKFLOW_MANIFEST_NAME
                    if not wf_file.exists():
                        continue

                    try:
                        wf = json.loads(wf_file.read_text(encoding="utf-8"))
                        validation = validate_workflow(wf_file)
                        discovered.append({
                            "workflow_id": wf.get("workflow_id", ""),
                            "name": wf.get("name", ""),
                            "description": wf.get("description", ""),
                            "pack_id": wf.get("pack_id", ""),
                            "version": wf.get("version", ""),
                            "path": str(wf_file),
                            "validation": validation,
                        })
                    except Exception:
                        continue

    return {"discovered": discovered, "count": len(discovered)}


def validate_workflow(workflow_path: str | Path | None = None, workflow_id: str | None = None) -> dict[str, Any]:
    """Validate a workflow.json file or workflow by ID."""
    if workflow_id:
        wf_data = _get_workflow_by_id(workflow_id)
        if not wf_data:
            return {"status": "failed", "errors": [f"Workflow '{workflow_id}' not found"], "warnings": []}
        workflow = wf_data
        workflow_path = wf_data.get("source", workflow_path)
    else:
        p = Path(workflow_path)
        if not p.exists():
            wf_data = _get_workflow_by_id(str(workflow_path))
            if wf_data:
                workflow = wf_data
                workflow_path = wf_data.get("source", workflow_path)
            else:
                return {"status": "failed", "errors": [f"Workflow file not found: {workflow_path}"]}
        else:
            try:
                workflow = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return {"status": "failed", "errors": [f"Invalid workflow.json: {exc}"]}

    errors = []
    warnings = []

    for field in WORKFLOW_SCHEMA["required"]:
        if field not in workflow:
            errors.append(f"Missing required field: {field}")

    if errors:
        return {"status": "failed", "errors": errors, "warnings": []}

    steps = workflow.get("steps", [])
    if not steps:
        errors.append("Workflow must have at least one step")

    step_ids = set()
    output_keys = set()
    for step in steps:
        for field in STEP_SCHEMA["required"]:
            if field not in step:
                errors.append(f"Step '{step.get('step_id', 'unknown')}' missing required field: {field}")

        sid = step.get("step_id", "")
        if sid in step_ids:
            errors.append(f"Duplicate step_id: {sid}")
        step_ids.add(sid)

        out_key = step.get("output_key", "")
        if out_key:
            if out_key in output_keys:
                warnings.append(f"Duplicate output_key: {out_key}")
            output_keys.add(out_key)

        input_from = step.get("input_from", {})
        for key, source in input_from.items():
            if source not in output_keys and "." not in source:
                warnings.append(f"Step '{sid}' references output_key '{source}' that is not produced by any previous step")

    required_perms = workflow.get("required_permissions", [])
    unknown_perms = [p for p in required_perms if p not in KNOWN_PERMISSIONS]
    if unknown_perms:
        warnings.append(f"Unknown permissions: {unknown_perms}")

    risk = get_risk_level(required_perms)

    installed = {s["id"]: s for s in list_installed_skills()}
    missing_skills = []
    for step in steps:
        sid = step.get("skill_id", "")
        if sid not in installed:
            missing_skills.append(sid)

    if missing_skills:
        warnings.append(f"Skills not installed: {missing_skills}")

    status = "passed" if not errors else "failed"
    if not errors and warnings:
        status = "warning"

    return {
        "status": status,
        "workflow_id": workflow.get("workflow_id", ""),
        "name": workflow.get("name", ""),
        "version": workflow.get("version", ""),
        "steps": len(steps),
        "errors": errors,
        "warnings": warnings,
        "risk_level": risk,
        "required_permissions": required_perms,
        "missing_skills": missing_skills,
    }


def register_workflow(workflow_path: str | Path) -> dict[str, Any]:
    """Register a workflow from a workflow.json file."""
    workflow_path = Path(workflow_path)
    if not workflow_path.exists():
        return {"status": "error", "message": f"Workflow file not found: {workflow_path}"}

    validation = validate_workflow(workflow_path)
    if validation["status"] == "failed":
        return {"status": "error", "message": "Workflow validation failed", "errors": validation["errors"]}

    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid workflow.json"}

    wf_id = workflow.get("workflow_id", "")
    registry = _load_workflow_registry()
    registry["workflows"][wf_id] = {
        "name": workflow.get("name", ""),
        "description": workflow.get("description", ""),
        "pack_id": workflow.get("pack_id", ""),
        "version": workflow.get("version", ""),
        "steps": workflow.get("steps", []),
        "required_permissions": workflow.get("required_permissions", []),
        "source": str(workflow_path),
    }
    _save_workflow_registry(registry)

    return {
        "status": "registered",
        "workflow_id": wf_id,
        "name": workflow.get("name", ""),
    }


def export_workflow(workflow_id: str, output_path: str | Path) -> dict[str, Any]:
    """Export a workflow as a .liuantworkflow ZIP package."""
    wf_data = _get_workflow_by_id(workflow_id)
    if not wf_data:
        return {"status": "error", "message": f"Workflow '{workflow_id}' not found"}

    import hashlib
    # Find the source directory of the workflow if possible
    wf_folder = None
    if "source" in wf_data:
        src_path = Path(wf_data["source"])
        if src_path.exists():
            wf_folder = src_path.parent

    files_to_write = {}
    if wf_folder and wf_folder.is_dir():
        for f in wf_folder.iterdir():
            if f.is_file() and f.name != "CHECKSUMS.json":
                try:
                    files_to_write[f.name] = f.read_bytes()
                except Exception:
                    pass

    # Ensure vital files exist
    if "workflow.json" not in files_to_write:
        clean_wf = {k: v for k, v in wf_data.items() if k != "source"}
        files_to_write["workflow.json"] = json.dumps(clean_wf, indent=2).encode("utf-8")

    if "README.md" not in files_to_write:
        files_to_write["README.md"] = f"# {wf_data.get('name', workflow_id)}\n\n{wf_data.get('description', '')}\n".encode("utf-8")

    if "sample_input.json" not in files_to_write:
        files_to_write["sample_input.json"] = b"{}\n"

    if "expected_output.json" not in files_to_write:
        files_to_write["expected_output.json"] = b"{}\n"

    # CHECKSUMS.json calculation (must exclude itself)
    checksums = {}
    for name, content in sorted(files_to_write.items()):
        h = hashlib.sha256()
        h.update(content)
        checksums[name] = h.hexdigest()

    files_to_write["CHECKSUMS.json"] = json.dumps(checksums, indent=2).encode("utf-8")

    # Write ZIP
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, content in sorted(files_to_write.items()):
                z.writestr(name, content)
    except Exception as e:
        return {"status": "error", "message": f"Failed to write export package: {e}"}

    return {
        "status": "exported",
        "workflow_id": workflow_id,
        "path": str(output_path),
    }


def validate_workflow_file(archive_path: str | Path) -> dict[str, Any]:
    """Validate a .liuantworkflow ZIP package."""
    archive_path = Path(archive_path)
    if not archive_path.exists():
        return {"status": "failed", "errors": [f"File not found: {archive_path}"], "warnings": []}

    if not zipfile.is_zipfile(archive_path):
        return {"status": "failed", "errors": ["Not a valid ZIP archive"], "warnings": []}

    errors = []
    warnings = []

    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            namelist = z.namelist()

            # Path traversal check
            from runtime.skills.packs import _check_path_traversal
            traversal_violations = _check_path_traversal(namelist)
            if traversal_violations:
                return {"status": "failed", "errors": traversal_violations, "warnings": []}

            # Check CHECKSUMS.json exists
            if "CHECKSUMS.json" not in namelist:
                return {"status": "failed", "errors": ["Missing CHECKSUMS.json in archive"], "warnings": []}

            try:
                checksums_data = json.loads(z.read("CHECKSUMS.json").decode("utf-8"))
            except Exception as e:
                return {"status": "failed", "errors": [f"Failed to parse CHECKSUMS.json: {e}"], "warnings": []}

            # Verify checksums for all files
            import hashlib
            files_in_zip = [name for name in namelist if name != "CHECKSUMS.json"]

            # Every file in zip must have a valid checksum
            for name in files_in_zip:
                if name not in checksums_data:
                    errors.append(f"File '{name}' in archive is not listed in CHECKSUMS.json")
                    continue
                content = z.read(name)
                h = hashlib.sha256()
                h.update(content)
                actual_sha = h.hexdigest()
                if actual_sha != checksums_data[name]:
                    errors.append(f"Checksum mismatch for file '{name}': expected {checksums_data[name]}, got {actual_sha}")

            # Every entry in CHECKSUMS.json must correspond to an actual file in the zip
            for name in checksums_data:
                if name not in namelist:
                    errors.append(f"File '{name}' listed in CHECKSUMS.json is missing from the archive")

            if errors:
                return {"status": "failed", "errors": errors, "warnings": []}

            # Scan for secrets in text files
            from runtime.skills.manifest import SECRET_PATTERNS
            text_extensions = {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".js", ".ts"}
            for name in files_in_zip:
                ext = Path(name).suffix.lower()
                if ext in text_extensions or ext == "":
                    try:
                        content_str = z.read(name).decode("utf-8", errors="ignore")
                        for pattern_str in SECRET_PATTERNS:
                            pattern = re.compile(pattern_str) if isinstance(pattern_str, str) else pattern_str
                            if pattern.search(content_str):
                                errors.append(f"Secret-like pattern detected in '{name}'")
                    except Exception:
                        pass

            if errors:
                return {"status": "failed", "errors": errors, "warnings": []}

            # Validate workflow.json itself
            if "workflow.json" not in namelist:
                return {"status": "failed", "errors": ["Missing workflow.json in archive"], "warnings": []}

            try:
                wf_json = json.loads(z.read("workflow.json").decode("utf-8"))
            except Exception as e:
                return {"status": "failed", "errors": [f"Failed to parse workflow.json: {e}"], "warnings": []}

            # Write workflow.json temporarily to run standard validate_workflow
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp.write(z.read("workflow.json"))
                tmp_path = Path(tmp.name)

            try:
                val_res = validate_workflow(tmp_path)
                if val_res["status"] == "failed":
                    errors.extend(val_res.get("errors", []))
                else:
                    warnings.extend(val_res.get("warnings", []))
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

    except Exception as e:
        return {"status": "failed", "errors": [f"Validation exception: {e}"], "warnings": []}

    status = "passed" if not errors else "failed"
    if not errors and warnings:
        status = "warning"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "workflow_id": wf_json.get("workflow_id", "") if "wf_json" in locals() else ""
    }


def import_workflow(archive_path: str | Path, confirm: bool = False) -> dict[str, Any]:
    """Import a workflow from a .liuantworkflow ZIP package."""
    archive_path = Path(archive_path)
    val_res = validate_workflow_file(archive_path)
    if val_res["status"] == "failed":
        return {"status": "failed", "message": "Workflow package validation failed", "errors": val_res["errors"]}

    if not confirm:
        return {"status": "blocked", "message": "Import requires explicit confirmation. Please pass confirm=true."}

    workflow_id = val_res.get("workflow_id")
    if not workflow_id:
        return {"status": "error", "message": "Could not determine workflow ID from package."}

    imported_dir = IMPORTED_WORKFLOWS_DIR / workflow_id
    if imported_dir.exists():
        shutil.rmtree(imported_dir)
    imported_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(imported_dir)
    except Exception as e:
        return {"status": "error", "message": f"Failed to extract archive: {e}"}

    # Register workflow via standard register_workflow
    reg_res = register_workflow(imported_dir / "workflow.json")
    if reg_res["status"] == "error":
        return reg_res

    return {
        "status": "imported",
        "workflow_id": workflow_id,
        "message": "Workflow imported successfully. Workflows do not auto-run."
    }


def export_workflow_run_report(run_id: str, format: str = "json") -> dict[str, Any]:
    """Export a redacted workflow run report in JSON, Markdown, or HTML formats."""
    run_data = get_workflow_run(run_id)
    if not run_data:
        return {"status": "error", "message": f"Run '{run_id}' not found"}

    steps = get_workflow_steps(run_id)

    # Resolve required permissions and recovery suggestions
    wf_id = run_data.get("workflow_id", "")
    wf_meta = _get_workflow_by_id(wf_id) or {}
    perms_used = wf_meta.get("required_permissions", [])

    recovery_advice = ""
    if run_data.get("status") == "failed":
        failed_step = run_data.get("failed_step_id", "")
        failed_skill = ""
        for s in steps:
            if s.get("step_id") == failed_step:
                failed_skill = s.get("skill_id", "")
                break
        recovery_advice = f"Check skill '{failed_skill}' configuration and inputs. Rerun from step '{failed_step}' after fixing the issue."

    # Redaction helper
    from runtime.skills.workflow_audit import _redact_secrets

    def redact_all(text: str) -> str:
        if not text:
            return ""
        # Apply standard redact
        res = _redact_secrets(text)
        # Extra prompt/keys sanitization
        res = re.sub(r'(?i)(["\']?(?:api_key|client_secret|access_token|token|password|secret)["\']?\s*[:=]\s*)(["\'][^"\']+["\'])', r'\1"[REDACTED]"', res)
        return res

    def redact_val(val: Any) -> Any:
        if isinstance(val, str):
            return redact_all(val)
        if isinstance(val, (dict, list)):
            serialized = json.dumps(val)
            redacted_str = redact_all(serialized)
            try:
                return json.loads(redacted_str)
            except Exception:
                return redacted_str
        return val

    # Apply redactions to run_data and steps
    clean_run = {k: redact_val(v) for k, v in run_data.items()}
    clean_steps = []
    for step in steps:
        clean_step = {k: redact_val(v) for k, v in step.items()}
        clean_steps.append(clean_step)

    content = ""
    if format == "json":
        content = json.dumps({
            "run": clean_run,
            "steps": clean_steps,
            "permissions_used": perms_used,
            "recovery_advice": recovery_advice
        }, indent=2)
    elif format == "markdown":
        lines = [
            f"# Workflow Run Report: {clean_run.get('run_id')}",
            f"- **Workflow ID:** {clean_run.get('workflow_id')}",
            f"- **Status:** {clean_run.get('status')}",
            f"- **Started At:** {clean_run.get('started_at')}",
            f"- **Completed At:** {clean_run.get('completed_at')}",
            f"- **Duration:** {clean_run.get('duration_ms')} ms",
            f"- **Steps:** {clean_run.get('completed_steps')} / {clean_run.get('step_count')}",
            f"- **Permissions Used:** {', '.join(perms_used) if perms_used else 'None'}"
        ]
        if recovery_advice:
            lines.append(f"- **Recovery Advice:** {recovery_advice}")
        lines.append("\n## Executed Steps")
        for s in clean_steps:
            lines.append(f"### Step: {s.get('step_id')} ({s.get('status')})")
            lines.append(f"- **Skill:** {s.get('skill_id')}")
            lines.append(f"- **Command:** {s.get('command')}")
            lines.append(f"- **Duration:** {s.get('duration_ms')} ms")
            if s.get("error_redacted"):
                lines.append(f"- **Error:** {s.get('error_redacted')}")
        content = "\n".join(lines)
    elif format == "html":
        steps_html = ""
        for s in clean_steps:
            err_html = f"<p><strong>Error:</strong> {s.get('error_redacted')}</p>" if s.get('error_redacted') else ""
            steps_html += f"""
            <div class="step">
                <h3>Step: {s.get('step_id')} (<span class="status-{s.get('status')}">{s.get('status')}</span>)</h3>
                <p><strong>Skill:</strong> {s.get('skill_id')} | <strong>Command:</strong> {s.get('command')}</p>
                <p><strong>Duration:</strong> {s.get('duration_ms')} ms</p>
                {err_html}
            </div>
            """
        recovery_html = f"<div class='recovery'><h3>Recovery Advice</h3><p>{recovery_advice}</p></div>" if recovery_advice else ""
        content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Workflow Run Report: {clean_run.get('run_id')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1f2937; margin: 40px; background: #f9fafb; line-height: 1.5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #111827; }}
        .meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 30px; padding: 20px; background: #f3f4f6; border-radius: 8px; }}
        .step {{ border-left: 4px solid #3b82f6; padding-left: 16px; margin-bottom: 20px; }}
        .status-completed {{ color: #10b981; font-weight: bold; }}
        .status-failed {{ color: #ef4444; font-weight: bold; }}
        .recovery {{ background: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 8px; margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Workflow Run Report: {clean_run.get('run_id')}</h1>
        <div class="meta">
            <div>
                <p><strong>Workflow ID:</strong> {clean_run.get('workflow_id')}</p>
                <p><strong>Status:</strong> <span class="status-{clean_run.get('status')}">{clean_run.get('status')}</span></p>
                <p><strong>Duration:</strong> {clean_run.get('duration_ms')} ms</p>
            </div>
            <div>
                <p><strong>Started At:</strong> {clean_run.get('started_at')}</p>
                <p><strong>Completed At:</strong> {clean_run.get('completed_at')}</p>
                <p><strong>Permissions:</strong> {', '.join(perms_used) if perms_used else 'None'}</p>
            </div>
        </div>
        {recovery_html}
        <h2>Execution Timeline Steps</h2>
        {steps_html}
    </div>
</body>
</html>
"""
    return {
        "status": "ok",
        "format": format,
        "content": content
    }


def get_workflow_run_timeline(run_id: str) -> dict[str, Any]:
    """Get a structured, chronological timeline of run execution events."""
    run_data = get_workflow_run(run_id)
    if not run_data:
        return {"status": "error", "message": f"Run '{run_id}' not found"}

    steps = get_workflow_steps(run_id)
    events = []

    # Workflow started event
    events.append({
        "event": "workflow_started",
        "timestamp": run_data.get("started_at"),
        "message": f"Workflow '{run_data.get('workflow_id')}' execution started."
    })

    # Steps events
    for s in steps:
        step_id = s.get("step_id")
        status = s.get("status")
        recorded_at = s.get("recorded_at")
        events.append({
            "event": "step_started",
            "timestamp": recorded_at,  # sequence order
            "message": f"Step '{step_id}' utilizing skill '{s.get('skill_id')}' started."
        })
        if status in ("completed", "success"):
            events.append({
                "event": "step_completed",
                "timestamp": recorded_at,
                "message": f"Step '{step_id}' completed successfully in {s.get('duration_ms')} ms."
            })
        elif status == "failed":
            events.append({
                "event": "step_failed",
                "timestamp": recorded_at,
                "message": f"Step '{step_id}' failed: {s.get('error_redacted')}."
            })
        elif status == "approval_required":
            events.append({
                "event": "approval_required",
                "timestamp": recorded_at,
                "message": f"Step '{step_id}' requires external action approval."
            })

    # Workflow finished event
    if run_data.get("completed_at"):
        events.append({
            "event": "workflow_finished",
            "timestamp": run_data.get("completed_at"),
            "message": f"Workflow finished with status: {run_data.get('status')}."
        })

    return {
        "run_id": run_id,
        "workflow_id": run_data.get("workflow_id"),
        "status": run_data.get("status"),
        "timeline": sorted(events, key=lambda x: x.get("timestamp") or "")
    }
