from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from runtime.action_log import list_external_actions
from runtime.agents import AgentRunner, list_agents
from runtime.approvals import ApprovalManager
from runtime.automation import AutomationManager, SchedulerEngine
from runtime.backup import BackupManager
from runtime.connectors.email.draft_store import EmailDraftStore
from runtime.connectors.email.registry import get_email_connector
from runtime.connectors.manager import ConnectorManager
from runtime.connectors.messaging import TelegramConnector
from runtime.connectors.social.linkedin_connector import LinkedInConnector
from runtime.connectors.social.x_connector import XConnector
from runtime.config import ExportTracker, OnboardingManager, PermissionManager, SettingsManager, SkillManager, WorkspaceManager
from runtime.dashboard import build_dashboard, build_status
from runtime.doctor import run_doctor
from runtime.env_validation import EnvironmentValidator
from runtime.exports import (
    export_agent_run_markdown,
    export_campaign_markdown,
    export_content_calendar_csv,
    export_image_prompt_markdown,
    export_video_storyboard_markdown,
)
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.models import ModelManager
from runtime.knowledge import KnowledgeBase
from runtime.memory import MemoryManager
from runtime.providers import ModelHub
from runtime.release import ReleaseManager
from runtime.security_audit import audit_secrets
from runtime.security import AuthManager, SecretManager
from runtime.verification import VerificationCenter
from runtime.workflows import SocialContentWorkflow

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box

    console = Console()
    HAS_RICH = True
except ModuleNotFoundError:
    console = None
    HAS_RICH = False


EXAMPLES = {
    "doctor": ["liuant doctor"],
    "version": ["liuant version"],
    "info": ["liuant info"],
    "paths": ["liuant paths"],
    "repair": ["liuant repair"],
    "reset": ["liuant reset --confirm true"],
    "update-check": ["liuant update-check"],
    "release-check": ["liuant release-check"],
    "desktop": ["liuant desktop status", "liuant desktop icons-check", "liuant desktop build-guide", "liuant desktop native-check", "liuant desktop build --frontend-only", "liuant desktop backend-status", "liuant desktop backend-mode", "liuant desktop first-run-check", "liuant desktop polish-check", "liuant desktop one-click-check", "liuant desktop launch-check"],
    "release": ["liuant release manifest", "liuant release checksum", "liuant release artifacts", "liuant release unsigned-artifacts", "liuant release unsigned-build-check", "liuant release verify-artifacts", "liuant release desktop-report", "liuant release build-report", "liuant release macos-qa", "liuant release polish-check", "liuant release candidate-check", "liuant release ecosystem-check", "liuant release public-release-check"],
    "signing": ["liuant signing status", "liuant signing check", "liuant signing docs", "liuant signing macos-status", "liuant signing macos-guide", "liuant signing macos-export-env-template", "liuant signing macos-preflight", "liuant signing macos-sign --dry-run", "liuant signing macos-notarize --dry-run"],
    "sidecar": ["liuant sidecar status", "liuant sidecar build --confirm", "liuant sidecar check", "liuant sidecar run", "liuant sidecar stop --confirm"],
    "update-info": ["liuant update-info"],
    "update-config": ["liuant update-config"],
    "start": ["liuant start", "liuant start 8001"],
    "stop": ["liuant stop"],
    "restart": ["liuant restart"],
    "ui": ["liuant ui check", "liuant ui dev", "liuant ui build"],
    "open": ["liuant open"],
    "troubleshoot": ["liuant troubleshoot"],
    "status": ["liuant status"],
    "dashboard": ["liuant dashboard"],
    "agents": ['liuant agents list', 'liuant agents run content-creator-agent "Create 5 LinkedIn posts for Liuant Agentic OS"'],
    "chat": ['liuant chat "What is Liuant?"', 'liuant chat --model-role coding "Fix this error"', 'liuant chat --discussion "Plan Liuant launch"'],
    "models": ["liuant models status", "liuant models test openai"],
    "providers": ["liuant providers categories", "liuant providers list --category image", "liuant providers set-default video hyperframes_skill"],
    "text": ['liuant text generate "Write a 5-line marketing caption for Liuant Agentic OS"', "liuant text providers", "liuant text test openai"],
    "connectors": ["liuant connectors list", "liuant connectors create gmail"],
    "telegram": ["liuant telegram status", "liuant telegram setup", "liuant telegram messages", "liuant telegram drafts"],
    "email": ["liuant email draft-reply sample-message-id", "liuant email drafts"],
    "social": ["liuant social campaign create", "liuant social export <campaign_id>", "liuant social calendar-export <campaign_id>"],
    "approvals": ["liuant approvals list", "liuant approvals approve <approval_id>", "liuant approvals reject <approval_id>"],
    "image": ['liuant image generate "AI-powered software company poster" --mode model_based', 'liuant image generate "launch poster" --mode hyperframes_skill --platform linkedin'],
    "video": ['liuant video storyboard "Liuant Agentic OS launch video" --mode hyperframes_skill', 'liuant video generate "launch promo" --mode model_based'],
    "automations": ['liuant automations create "Every Monday create content calendar"', "liuant automations run <id>"],
    "scheduler": ["liuant scheduler status", "liuant scheduler due", "liuant scheduler tick", "liuant scheduler runs"],
    "embedding": ["liuant embedding test local_hash_embedding"],
    "memory": ['liuant memory add "User prefers premium dark UI" --type user', 'liuant memory search "UI preference"', "liuant memory list"],
    "knowledge": ['liuant knowledge add-text "Liuant Agentic OS is local-first"', 'liuant knowledge search "What is Liuant?"', "liuant knowledge sources"],
    "verify": ["liuant verify all", "liuant verify providers", "liuant verify security"],
    "env": ["liuant env check", "liuant env template", "liuant env missing"],
    "security": ["liuant security audit-secrets"],
    "secrets": ["liuant secrets status", "liuant secrets migrate", "liuant secrets list"],
    "auth": ["liuant auth status", "liuant auth token", "liuant auth rotate-token"],
    "backup": ["liuant backup create", "liuant backup list"],
    "content": ['liuant content create "AI course admissions campaign"', "liuant content list"],
    "logs": ["liuant logs path", "liuant logs tail", "liuant logs clear --confirm true"],
    "serve": ["liuant serve", "liuant serve 8001"],
    "settings": ["liuant settings list", "liuant settings get permission_mode", "liuant settings set debug_mode true"],
    "permissions": ["liuant permissions status", "liuant permissions set developer", "liuant permissions rules"],
    "skills": ["liuant skills available", "liuant skills install content-planning", "liuant skills list"],
    "workspace": ["liuant workspace list", "liuant workspace create client-a", "liuant workspace set-default client-a"],
    "exports": ["liuant exports list", "liuant exports show <id>"],
    "onboarding": ["liuant onboarding status", "liuant onboarding complete-step welcome"],
    "voice": ["liuant voice status", "liuant voice settings", "liuant voice enable --confirm true", "liuant voice test-wake 'Hey Liuant, list workflows'", "liuant voice say 'Hello world'"],
    "browser": ["liuant browser status", "liuant browser enable --confirm true", "liuant browser disable"],
    "search": ["liuant search status", "liuant search providers"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liuant")
    sub = parser.add_subparsers(dest="area", required=True)
    for area in (
        "doctor",
        "version",
        "info",
        "paths",
        "repair",
        "reset",
        "update-check",
        "release-check",
        "desktop",
        "release",
        "signing",
        "sidecar",
        "update-info",
        "update-config",
        "start",
        "stop",
        "restart",
        "ui",
        "open",
        "troubleshoot",
        "status",
        "dashboard",
        "agents",
        "chat",
        "models",
        "providers",
        "text",
        "connectors",
        "telegram",
        "social",
        "email",
        "image",
        "video",
        "automations",
        "scheduler",
        "embedding",
        "memory",
        "knowledge",
        "verify",
        "env",
        "security",
        "secrets",
        "auth",
        "backup",
        "approvals",
        "content",
        "logs",
        "serve",
        "settings",
        "permissions",
        "skills",
        "workspace",
        "exports",
        "onboarding",
        "usage",
        "voice",
        "browser",
        "search",
    ):
        area_parser = sub.add_parser(area)
        area_parser.add_argument("command", nargs="?")
        area_parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main() -> None:
    try:
        args = build_parser().parse_args()
        data = dispatch(args)
        render(args.area, data)
    except Exception as exc:
        render_error(str(exc))
        sys.exit(1)


def dispatch(args: argparse.Namespace) -> Any:
    command = args.command or "list"
    rest = args.args

    if args.area == "doctor":
        return run_doctor()
    if args.area == "version":
        return ReleaseManager().version()
    if args.area == "info":
        return ReleaseManager().info()
    if args.area == "paths":
        return ReleaseManager().paths()
    if args.area == "repair":
        return ReleaseManager().repair()
    if args.area == "reset":
        _, options = parse_cli_options([command] + rest if command else rest)
        return ReleaseManager().reset(confirm=options.get("confirm", "false").lower() in {"1", "true", "yes", "on"})
    if args.area == "update-check":
        return ReleaseManager().update_check()
    if args.area == "release-check":
        _, options = parse_cli_options([command] + rest if command else rest)
        return ReleaseManager().release_check(run_tests=options.get("skip_tests", "false").lower() not in {"1", "true", "yes", "on"})
    if args.area == "desktop":
        release = ReleaseManager()
        if command == "status":
            return release.desktop_status()
        if command == "check":
            return release.desktop_check()
        if command == "native-check":
            return release.native_check()
        if command == "rust-check":
            return release.rust_check()
        if command == "tauri-check":
            return release.tauri_check()
        if command == "dev":
            return release.desktop_dev()
        if command == "build":
            _, options = parse_cli_options(rest)
            return release.desktop_build(frontend_only=options.get("frontend_only") == "true", native=options.get("native") == "true", skip_tests=options.get("skip_tests") == "true")
        if command == "icons-check":
            return release.icons_check()
        if command == "icons-generate":
            return release.icons_generate()
        if command == "build-guide":
            return release.build_guide()
        if command == "build-report":
            return release.build_report()
        if command == "backend-status":
            return release.desktop_backend_status()
        if command == "backend-mode":
            if rest and rest[0] == "set" and len(rest) >= 2:
                return release.set_desktop_backend_mode(rest[1])
            return release.desktop_backend_mode()
        if command == "backend-start":
            _, options = parse_cli_options(rest)
            return release.desktop_backend_start(host=options.get("host", "127.0.0.1"), port=parse_int(options.get("port"), 8765))
        if command == "backend-stop":
            return release.desktop_backend_stop()
        if command == "backend-restart":
            _, options = parse_cli_options(rest)
            return release.desktop_backend_restart(host=options.get("host", "127.0.0.1"), port=parse_int(options.get("port"), 8765))
        if command == "package-info":
            return release.desktop_package_info()
        if command == "first-run-check":
            return release.desktop_first_run_check()
        if command == "polish-check":
            return release.desktop_polish_check()
        if command == "one-click-check":
            return release.desktop_one_click_check()
        if command == "launch-check":
            return release.desktop_launch_check()
        if command == "safe-apps":
            from runtime.automation.desktop import DesktopAutomationManager
            return DesktopAutomationManager().list_safe_apps()
        if command == "open-app" and rest:
            from runtime.automation.desktop import DesktopAutomationManager
            _, options = parse_cli_options(rest[1:])
            confirm = options.get("confirm", "false").lower() in {"1", "true", "yes", "on"}
            return DesktopAutomationManager().open_app(rest[0], confirm=confirm)
        return {"commands": ["status", "check", "icons-check", "icons-generate", "native-check", "rust-check", "tauri-check", "build-guide", "build-report", "dev", "build", "backend-status", "backend-mode", "backend-start", "backend-stop", "backend-restart", "package-info", "first-run-check", "polish-check", "one-click-check", "launch-check"]}
    if args.area == "release":
        release = ReleaseManager()
        if command == "manifest":
            return release.release_manifest()
        if command == "checksum":
            return release.release_checksum()
        if command == "artifacts":
            return release.release_artifacts()
        if command == "unsigned-artifacts":
            return release.unsigned_artifacts()
        if command == "verify-artifacts":
            return release.verify_artifacts()
        if command == "notes":
            return release.release_notes()
        if command == "desktop-report":
            return release.release_desktop_report()
        if command == "build-report":
            return release.release_build_report()
        if command == "unsigned-build-check":
            return release.unsigned_build_check()
        if command == "macos-qa":
            return release.macos_qa()
        if command == "polish-check":
            return release.desktop_polish_check()
        if command == "candidate-check":
            return release.desktop_v1_candidate_check()
        if command == "ecosystem-check":
            return release.ecosystem_check()
        if command == "public-release-check":
            return release.public_release_check()
        return {"commands": ["manifest", "checksum", "artifacts", "unsigned-artifacts", "verify-artifacts", "notes", "desktop-report", "build-report", "unsigned-build-check", "macos-qa", "polish-check", "candidate-check", "ecosystem-check", "public-release-check"]}
    if args.area == "signing":
        release = ReleaseManager()
        if command == "status":
            return release.signing_status()
        if command == "check":
            return release.signing_check()
        if command == "docs":
            return release.signing_docs()
        if command == "macos-status":
            return release.signing_macos_status()
        if command == "macos-guide":
            return release.signing_macos_guide()
        if command == "macos-export-env-template":
            return release.signing_macos_export_env_template()
        if command == "macos-preflight":
            return release.signing_macos_preflight()
        if command == "macos-sign":
            dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
            confirm = "--confirm" in sys.argv
            idx = None
            for i, a in enumerate(sys.argv):
                if a == "--artifact" and i + 1 < len(sys.argv):
                    idx = i + 1
                    break
            artifact = sys.argv[idx] if idx else None
            return release.signing_macos_sign(artifact_path=artifact, dry_run=dry_run, confirm=confirm)
        if command == "macos-notarize":
            dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
            confirm = "--confirm" in sys.argv
            idx = None
            for i, a in enumerate(sys.argv):
                if a == "--artifact" and i + 1 < len(sys.argv):
                    idx = i + 1
                    break
            artifact = sys.argv[idx] if idx else None
            return release.signing_macos_notarize(artifact_path=artifact, dry_run=dry_run, confirm=confirm)
        return {"commands": ["status", "check", "docs", "macos-status", "macos-guide", "macos-export-env-template", "macos-preflight", "macos-sign", "macos-notarize"]}
    if args.area == "sidecar":
        from runtime.sidecar import sidecar_build, sidecar_check, sidecar_run, sidecar_status, sidecar_stop
        if command == "status":
            return sidecar_status()
        if command == "check":
            return sidecar_check()
        if command == "run":
            _, options = parse_cli_options(rest)
            return sidecar_run(host=options.get("host", "127.0.0.1"), port=parse_int(options.get("port"), 8765))
        if command == "stop":
            _, options = parse_cli_options(rest)
            return sidecar_stop(confirm=options.get("confirm") == "true")
        if command == "build":
            _, options = parse_cli_options(rest)
            return sidecar_build(confirm=options.get("confirm") == "true")
        return {"commands": ["status", "build", "check", "run", "stop"]}
    if args.area == "update-info":
        return ReleaseManager().update_info()
    if args.area == "update-config":
        return ReleaseManager().update_config()
    if args.area == "start":
        port = int(command) if command and command.isdigit() else 8765
        return ReleaseManager().start(port=port)
    if args.area == "stop":
        return ReleaseManager().stop()
    if args.area == "restart":
        port = int(command) if command and command.isdigit() else 8765
        return ReleaseManager().restart(port=port)
    if args.area == "ui":
        return ReleaseManager().ui(command or "check")
    if args.area == "open":
        return ReleaseManager().open_ui()
    if args.area == "troubleshoot":
        return ReleaseManager().troubleshoot()
    if args.area == "status":
        return build_status()
    if args.area == "dashboard":
        return build_dashboard()
    if args.area == "agents":
        runner = AgentRunner()
        from runtime.agents import AgentProfileManager

        profiles = AgentProfileManager()
        if command == "list":
            return list_agents()
        if command == "show" and rest:
            return profiles.show(rest[0])
        if command == "create":
            name = " ".join(rest) or "Custom Agent"
            return profiles.create({"name": name, "instructions": f"Custom agent for {name}"})
        if command == "update" and len(rest) >= 2:
            return profiles.update(rest[0], {"instructions": " ".join(rest[1:])})
        if command == "disable" and rest:
            return profiles.set_enabled(rest[0], False)
        if command == "enable" and rest:
            return profiles.set_enabled(rest[0], True)
        if command == "run" and len(rest) >= 2:
            agent_slug = rest[0]
            prompt, options = parse_cli_options(rest[1:])
            return runner.run(
                agent_slug,
                prompt,
                ai_enhancement=options.get("ai") == "true",
                provider_name=options.get("provider"),
                model=options.get("model"),
                rag_enabled=options.get("rag") == "true",
                workspace_name=options.get("workspace"),
                rag_query=options.get("rag_query"),
                rag_limit=parse_int(options.get("rag_limit"), 0) or None,
                model_role=options.get("model_role"),
                discussion_mode=options.get("discussion") == "true",
                discussion_roles=[r.strip() for r in options.get("roles", "").split(",")] if options.get("roles") else None,
                discussion_rounds=parse_int(options.get("rounds"), 2),
                stream=options.get("stream") == "true",
            )
        if command == "runs":
            return runner.list_runs()
        if command == "export" and rest:
            return {"output_path": export_agent_run_markdown(rest[0])}
        return {"commands": ["list", "show <slug>", "create <name>", "update <slug> <instructions>", "disable <slug>", "enable <slug>", "run <agent_slug> <prompt>", "run <agent_slug> <prompt> --model-role coding", "run <agent_slug> <prompt> --discussion", "run <agent_slug> <prompt> --stream", "runs", "export <run_id>"]}
    if args.area == "chat":
        from runtime.chat.intent_router import route_chat_message
        from runtime.model_router import route_task_to_role
        message, options = parse_cli_options([command] + rest if command else rest)
        if not message:
            return {"commands": ['chat "message"', 'chat --model-role coding "Fix this error"', 'chat --discussion "Plan Liuant launch"', 'chat --stream "Explain Liuant"', 'chat --discussion --stream "Plan launch"']}
        if options.get("discussion") == "true" and options.get("stream") == "true":
            from runtime.chat.discussion import stream_discussion
            roles_str = options.get("roles", "")
            roles = [r.strip() for r in roles_str.split(",")] if roles_str else None
            rounds = parse_int(options.get("rounds"), 2)
            final_role = options.get("final_role", "thinking")
            print("Discussion started...", flush=True)
            final_text = []
            warnings = []
            usage_info = {}
            for chunk in stream_discussion(user_message=message, roles=roles, rounds=rounds, final_role=final_role):
                if chunk["type"] == "discussion_start":
                    print(f"Roles: {', '.join(chunk['roles'])} | Rounds: {chunk['rounds']}", flush=True)
                elif chunk["type"] == "role_start":
                    print(f"\n--- {chunk['role'].title()} (round {chunk.get('round', 1)}) [{chunk['provider']}/{chunk['model']}] ---", flush=True)
                elif chunk["type"] == "role_token":
                    print(chunk["content"], end="", flush=True)
                elif chunk["type"] == "role_done":
                    print(f"\n[{chunk['status']}]", flush=True)
                    if chunk.get("fallback_used"):
                        warnings.append(f"Fallback used for {chunk['role']}")
                elif chunk["type"] == "role_error":
                    print(f"\nError: {chunk['content']}", flush=True)
                elif chunk["type"] == "role_skip":
                    print(f"[{chunk['role']} skipped: {chunk['reason']}]", flush=True)
                elif chunk["type"] == "final_start":
                    print(f"\n\n--- Final Answer ({chunk['role']}) ---", flush=True)
                elif chunk["type"] == "final_token":
                    final_text.append(chunk["content"])
                    print(chunk["content"], end="", flush=True)
                elif chunk["type"] == "usage_update":
                    usage_info = chunk
                elif chunk["type"] == "discussion_done":
                    warnings.extend(chunk.get("warnings", []))
            print("", flush=True)
            if usage_info:
                print(f"\n--- Usage: {usage_info.get('estimated_tokens', 0)} tokens, ~${usage_info.get('estimated_cost', 0):.6f} ({'estimated' if usage_info.get('estimated') else 'exact'}) ---", flush=True)
            if warnings:
                print(f"Warnings: {'; '.join(warnings)}", flush=True)
            return {"status": "completed", "text": "".join(final_text), "warnings": warnings, "usage": usage_info}
        if options.get("discussion") == "true":
            from runtime.chat.discussion import run_discussion
            roles_str = options.get("roles", "")
            roles = [r.strip() for r in roles_str.split(",")] if roles_str else None
            rounds = parse_int(options.get("rounds"), 2)
            return run_discussion(user_message=message, roles=roles, rounds=rounds)
        if options.get("stream") == "true":
            role = options.get("model_role", "default")
            if options.get("model_role"):
                from runtime.model_roles import ModelRoleManager
                from runtime.model_router import get_model_for_role
                rm = ModelRoleManager()
                model_cfg = get_model_for_role(role, rm)
                if not model_cfg["configured"]:
                    return {"status": "error", "message": f"Role '{role}' not configured."}
                provider_name = model_cfg["provider"]
                model = model_cfg["model"]
            else:
                provider_name = None
                model = None
            hub = ModelHub()
            full_text = []
            for chunk in hub.stream_text(prompt=message, provider_name=provider_name, model=model, role=role):
                if chunk["type"] == "token":
                    full_text.append(chunk["content"])
                    print(chunk["content"], end="", flush=True)
                elif chunk["type"] == "error":
                    print(f"\nError: {chunk['content']}", flush=True)
                elif chunk["type"] == "metadata":
                    pass
                elif chunk["type"] == "done":
                    break
            if full_text:
                print(f"\n\n---\nRole: {role} | Provider: {chunk.get('provider', '')} | Model: {chunk.get('model', '')}", flush=True)
            return {"status": "completed", "text": "".join(full_text), "role": role, "provider": chunk.get("provider", ""), "model": chunk.get("model", "")}
        if options.get("model_role"):
            from runtime.model_roles import ModelRoleManager
            from runtime.model_router import get_model_for_role
            role = options["model_role"]
            rm = ModelRoleManager()
            hub = ModelHub()
            model_cfg = get_model_for_role(role, rm)
            if not model_cfg["configured"]:
                return {"status": "error", "message": f"Role '{role}' not configured. Set it with: ./liuant models role-set {role} --provider <provider> --model <model>"}
            try:
                response = hub.generate_text(
                    prompt=message,
                    provider_name=model_cfg["provider"],
                    model=model_cfg["model"],
                )
                response["role_used"] = role
                response["provider"] = model_cfg["provider"]
                response["model"] = model_cfg["model"]
                return response
            except Exception as exc:
                return {"status": "error", "message": str(exc)[:200], "role": role, "provider": model_cfg["provider"]}
        return route_chat_message(message)
    if args.area == "models" and command == "roles":
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        return rm.get_all_roles()
    if args.area == "models" and command == "role-set" and len(rest) >= 1:
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        role = rest[0]
        _, options = parse_cli_options(rest[1:])
        provider = options.get("provider", "")
        model = options.get("model", "")
        if not provider or not model:
            return {"error": "Both --provider and --model are required.", "usage": "./liuant models role-set <role> --provider <provider> --model <model>"}
        return rm.set_role(role, provider, model)
    if args.area == "models" and command == "role-test" and rest:
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        return rm.test_role(rest[0])
    if args.area == "models" and command == "role-reset" and rest:
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        return rm.reset_role(rest[0])
    if args.area == "models" and command == "role-reset-all":
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        return rm.reset_all_roles()
    if args.area == "models" and command == "discussion-status":
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        return rm.get_discussion_settings()
    if args.area == "models" and command == "discussion-set" and len(rest) >= 2:
        from runtime.model_roles import ModelRoleManager
        rm = ModelRoleManager()
        return rm.set_discussion_setting(rest[0], rest[1])
    if args.area == "models":
        manager = ModelManager()
        if command == "list":
            return manager.list()
        if command == "providers":
            return manager.hub.list_providers("text")
        if command == "provider-status" and rest:
            prov = rest[0]
            row = manager.hub.get_provider(prov)
            status = manager.hub._derive_status(row)
            return {
                "provider": row["id"],
                "status": status,
                "message": manager.hub._status_message(row, status),
                "provider_config": manager.hub._sanitize(row),
            }
        if command == "provider-test" and rest:
            return manager.test(rest[0])
        if command == "setup":
            return manager.setup()
        if command == "test":
            return manager.test(rest[0] if rest else None)
        if command == "status":
            return manager.status()
        if command == "set-default" and rest:
            return manager.set_default(rest[0])
        if command == "set-fallback" and len(rest) >= 2:
            return manager.set_fallback(rest[0], rest[1])
        if command == "provider-health":
            from runtime.usage.provider_health import ProviderHealthTracker
            tracker = ProviderHealthTracker()
            if rest:
                return tracker.get_health(rest[0])
            return tracker.get_all_health()
        return {"commands": ["list", "providers", "provider-status <provider>", "provider-test <provider>", "setup", "test", "status", "set-default <provider>", "set-fallback <provider> <model>", "roles", "role-set <role> --provider <p> --model <m>", "role-test <role>", "role-reset <role>", "discussion-status", "discussion-set <key> <value>", "provider-health", "provider-health <provider>"]}
    if args.area == "providers":
        hub = ModelHub()
        if command == "categories":
            return hub.list_categories()
        if command == "list":
            _, options = parse_cli_options(rest)
            return hub.list_providers(options.get("category"))
        if command == "profiles":
            return hub.list_profiles()
        if command == "bedrock":
            sub_cmd = rest[0] if rest else "status"
            sub_rest = rest[1:]
            if sub_cmd == "status":
                from runtime.providers import bedrock
                from runtime.providers.registry import mask_secret
                masked_creds = {k: mask_secret(v) for k, v in bedrock.get_aws_credentials().items()}
                return {"provider": "amazon_bedrock", "status": bedrock.status(), "credentials": masked_creds}
            if sub_cmd == "setup-guide":
                return {
                    "provider": "amazon_bedrock",
                    "guide": [
                        "To set up Amazon Bedrock, configure the following AWS credentials in your environment, .env, or .env.local file:",
                        "  AWS_ACCESS_KEY_ID=your_access_key_id",
                        "  AWS_SECRET_ACCESS_KEY=your_secret_access_key",
                        "  AWS_SESSION_TOKEN=your_session_token (optional)",
                        "  AWS_DEFAULT_REGION=your_aws_region (defaults to us-east-1)",
                        "  AWS_PROFILE=your_aws_profile (optional)",
                        "Ensure your AWS credentials have permission to invoke Amazon Bedrock converse API and the specific models (e.g. us.amazon.nova-lite-v1:0)."
                    ]
                }
            if sub_cmd == "test":
                from runtime.providers import bedrock
                test_model = None
                if sub_rest and sub_rest[0] == "--model" and len(sub_rest) > 1:
                    test_model = sub_rest[1]
                elif len(sub_rest) > 0 and not sub_rest[0].startswith("-"):
                    test_model = sub_rest[0]
                return bedrock.test(model_id=test_model)
            if sub_cmd == "models":
                return {
                    "provider": "amazon_bedrock",
                    "models": ["us.amazon.nova-lite-v1:0", "us.amazon.nova-micro-v1:0", "us.amazon.nova-pro-v1:0"]
                }
            if sub_cmd == "regions":
                return {
                    "provider": "amazon_bedrock",
                    "regions": ["us-east-1", "us-west-2", "eu-central-1", "ap-northeast-1"]
                }
            return {"commands": ["status", "setup-guide", "test [--model MODEL_ID]", "models", "regions"]}
        if command == "openrouter":
            sub_cmd = rest[0] if rest else "status"
            if sub_cmd == "setup-guide":
                return {
                    "provider": "openrouter",
                    "guide": [
                        "To set up OpenRouter, configure the following API key in your environment, .env, or .env.local file:",
                        "  OPENROUTER_API_KEY=your_openrouter_api_key",
                        "You can configure default models using:",
                        "  ./liuant providers set-model text openai/gpt-4.1-mini"
                    ]
                }
            if sub_cmd == "status":
                row = hub.get_provider("openrouter")
                return {"provider": "openrouter", "status": row["status"]}
            return {"commands": ["status", "setup-guide"]}
        if command == "profile-status" and rest:
            prov = rest[0]
            row = hub.get_provider(prov)
            status = hub._derive_status(row)
            return {
                "profile": row["id"],
                "status": status,
                "message": hub._status_message(row, status),
                "provider_config": hub._sanitize(row),
            }
        if command == "profile-test" and rest:
            return hub.test_provider(rest[0])
        if command == "status":
            return hub.get_status()
        if command == "show" and rest:
            return hub.get_provider(rest[0])
        if command == "test" and rest:
            return hub.test_provider(rest[0])
        if command == "enable" and rest:
            return hub.enable_provider(rest[0])
        if command == "disable" and rest:
            return hub.disable_provider(rest[0])
        if command == "set-default" and len(rest) >= 2:
            return hub.set_default_provider(rest[0], rest[1])
        if command == "set-model" and len(rest) >= 2:
            return hub.set_default_model(rest[0], rest[1])
        if command == "set-fallback" and len(rest) >= 2:
            return hub.set_fallback_provider(rest[0], rest[1])
        return {"commands": ["categories", "list --category <category>", "status", "show <provider>", "test <provider>", "enable <provider>", "disable <provider>", "set-default <category> <provider>", "set-model <category> <model>", "set-fallback <category> <provider>", "bedrock <command>", "openrouter <command>", "profiles", "profile-status <profile>", "profile-test <profile>"]}
    if args.area == "text":
        hub = ModelHub()
        if command == "providers":
            return hub.list_providers("text")
        if command == "test" and rest:
            return hub.test_provider(rest[0])
        if command == "generate":
            prompt, options = parse_cli_options(rest)
            if options.get("stream") == "true":
                full_text = []
                role = options.get("role", "default")
                for chunk in hub.stream_text(
                    prompt=prompt,
                    system_prompt=options.get("system_prompt"),
                    provider_name=options.get("provider"),
                    model=options.get("model"),
                    role=role,
                ):
                    if chunk["type"] == "token":
                        full_text.append(chunk["content"])
                        print(chunk["content"], end="", flush=True)
                    elif chunk["type"] == "error":
                        print(f"\nError: {chunk['content']}", flush=True)
                    elif chunk["type"] == "done":
                        break
                if full_text:
                    print(f"\n\n---\nProvider: {chunk.get('provider', '')} | Model: {chunk.get('model', '')}", flush=True)
                return {"status": "completed", "text": "".join(full_text), "provider": chunk.get("provider", ""), "model": chunk.get("model", "")}
            return hub.generate_text(
                prompt=prompt,
                system_prompt=options.get("system_prompt"),
                provider_name=options.get("provider"),
                model=options.get("model"),
                temperature=float(options.get("temperature", "0.7")),
                max_tokens=parse_int(options.get("max_tokens"), 0) or None,
            )
        return {"commands": ["providers", "test <provider_name>", "generate <prompt> --provider <provider> --model <model>", "generate <prompt> --stream"]}
    if args.area == "embedding":
        hub = ModelHub()
        if command == "test":
            provider = rest[0] if rest else "local_hash_embedding"
            return hub.create_embedding("Liuant embedding test", provider_name=provider)
        if command == "create":
            text, options = parse_cli_options(rest)
            return hub.create_embedding(text, provider_name=options.get("provider"))
        return {"commands": ["test <provider>", "create <text> --provider <provider>"]}
    if args.area == "memory":
        manager = MemoryManager()
        if command == "add":
            text, options = parse_cli_options(rest)
            return manager.add(text, memory_type=options.get("type", "user"), agent_slug=options.get("agent"))
        if command == "search":
            query, options = parse_cli_options(rest)
            return manager.search(query, limit=parse_int(options.get("limit"), 5))
        if command == "list":
            return manager.list()
        if command == "delete" and rest:
            return manager.delete(rest[0])
        return {"commands": ["add <text> --type user|project|agent|task", "search <query>", "list", "delete <id>"]}
    if args.area == "knowledge":
        kb = KnowledgeBase()
        if command == "add-text":
            text, options = parse_cli_options(rest)
            return kb.add_text(text, title=options.get("title", "CLI Text"))
        if command == "index-file" and rest:
            return kb.index_file(rest[0])
        if command == "index-agent-run" and rest:
            return kb.index_agent_run(rest[0])
        if command == "search":
            query, options = parse_cli_options(rest)
            return kb.search(query, limit=parse_int(options.get("limit"), 5))
        if command == "sources":
            return kb.sources()
        if command == "delete-source" and rest:
            return kb.delete_source(rest[0])
        if command == "reindex" and rest:
            return kb.reindex_source(rest[0])
        return {"commands": ["add-text <text>", "index-file <path>", "index-agent-run <run_id>", "search <query>", "sources", "delete-source <id>", "reindex <id>"]}
    if args.area == "verify":
        verifier = VerificationCenter()
        _, options = parse_cli_options(rest)
        live_generate = options.get("live_generate", "false").lower() in {"1", "true", "yes", "on"}
        if command == "all":
            return verifier.verify_all(live_generate=live_generate)
        if command == "providers":
            return verifier.verify_providers(live_generate=live_generate)
        if command in {"text", "image", "video", "embedding", "speech_to_text", "text_to_speech"}:
            return verifier.verify_providers(category=command, live_generate=live_generate)
        if command == "gmail":
            return verifier.verify_gmail()
        if command == "telegram":
            return verifier.verify_telegram()
        if command == "social":
            return verifier.verify_social()
        if command == "storage":
            return verifier.verify_storage()
        if command in {"security", "secrets"}:
            return verifier.verify_security()
        if command == "provider" and rest:
            return verifier.verify_provider(rest[0], live_generate=live_generate)
        return verifier.status()
    if args.area == "env":
        validator = EnvironmentValidator()
        if command == "check":
            return validator.check()
        if command == "template":
            return validator.template()
        if command == "missing":
            return validator.missing()
        return {"commands": ["check", "template", "missing"]}
    if args.area == "security":
        if command == "audit-secrets":
            return audit_secrets()
        return {"commands": ["audit-secrets"]}
    if args.area == "secrets":
        manager = SecretManager()
        if command == "status":
            return manager.status()
        if command == "migrate":
            return manager.migrate()
        if command == "list":
            return manager.list_secrets()
        if command == "delete" and rest:
            return manager.delete_secret(rest[0])
        if command == "rotate" and len(rest) >= 2:
            return manager.rotate_secret(rest[0], " ".join(rest[1:]))
        return {"commands": ["status", "migrate", "list", "delete <name>", "rotate <name> <new_value>"]}
    if args.area == "auth":
        manager = AuthManager()
        if command == "status":
            return manager.status()
        if command == "enable":
            return manager.enable()
        if command == "disable":
            _, options = parse_cli_options(rest)
            return manager.disable(confirm=options.get("confirm", "false").lower() in {"1", "true", "yes", "on"})
        if command == "token":
            return manager.token()
        if command == "rotate-token":
            return manager.rotate_token()
        if command == "login":
            token = rest[0] if rest else manager.token()["token"]
            return manager.login(token, "liuant-cli")
        return {"commands": ["status", "enable", "disable --confirm true", "token", "rotate-token", "login [token]"]}
    if args.area == "backup":
        manager = BackupManager()
        if command == "create":
            _, options = parse_cli_options(rest)
            return manager.create(
                include_secrets=options.get("include_secrets", "false").lower() in {"1", "true", "yes", "on"},
                include_encrypted_secrets=options.get("include_encrypted_secrets", "false").lower() in {"1", "true", "yes", "on"},
                confirm=options.get("confirm", "false").lower() in {"1", "true", "yes", "on"},
            )
        if command == "list":
            return manager.list()
        if command == "restore" and rest:
            _, options = parse_cli_options(rest[1:])
            return manager.restore(rest[0], confirm=options.get("confirm", "false").lower() in {"1", "true", "yes", "on"})
        return {"commands": ["create", "list", "restore <backup_id> --confirm"]}
    if args.area == "connectors":
        manager = ConnectorManager()
        if command == "list":
            return {"available": manager.available(), "configured": manager.list()}
        if command == "show" and rest:
            return manager.show(rest[0])
        if command == "create":
            provider = rest[0] if rest else "gmail"
            connector_type = "email" if provider in {"gmail", "outlook", "imap_smtp"} else "social"
            connector_type = "telegram" if provider in {"telegram", "telegram_bot"} else connector_type
            connector_type = "webhook" if provider == "webhook" else connector_type
            return manager.create(connector_type=connector_type, provider=provider, display_name=provider)
        if command == "test" and rest:
            return manager.test(rest[0])
        if command == "enable" and rest:
            return manager.set_enabled(rest[0], True)
        if command == "disable" and rest:
            return manager.set_enabled(rest[0], False)
        if command == "disconnect" and rest:
            return manager.disconnect(rest[0])
        return {"commands": ["list", "create <provider>", "show <id>", "test <id>", "enable <id>", "disable <id>", "disconnect <id>"]}
    if args.area == "telegram":
        connector = TelegramConnector()
        if command == "status":
            return connector.get_status()
        if command == "setup":
            _, options = parse_cli_options(rest)
            token = options.get("bot_token") or options.get("token")
            return connector.setup(token, options.get("agent"), options.get("permission_mode", "safe"))
        if command == "test":
            return connector.test_connection()
        if command == "enable":
            return connector.enable()
        if command == "disable":
            return connector.disable()
        if command == "disconnect":
            return connector.disconnect()
        if command == "messages":
            return connector.list_messages()
        if command == "drafts":
            return connector.list_drafts()
        if command == "approve" and rest:
            return connector.approve_draft(rest[0])
        if command == "reject" and rest:
            return connector.reject_draft(rest[0])
        if command == "send-approved" and rest:
            return connector.send_approved(rest[0])
        return {"commands": ["status", "setup", "test", "enable", "disable", "disconnect", "messages", "drafts", "approve <draft_id>", "reject <draft_id>", "send-approved <draft_id>"]}
    if args.area == "social":
        workflow = SocialContentWorkflow()
        social_connectors = {"linkedin": LinkedInConnector(), "x": XConnector()}
        if command == "connectors":
            return [connector.get_status() for connector in social_connectors.values()]
        if command in social_connectors:
            connector = social_connectors[command]
            subcommand = rest[0] if rest else "status"
            subrest = rest[1:]
            if subcommand == "status":
                return connector.get_status()
            if subcommand == "setup":
                return connector.setup()
            if subcommand == "oauth-url":
                return connector.start_oauth()
            if subcommand == "callback" and subrest:
                _, options = parse_cli_options(subrest[1:])
                return connector.handle_callback(subrest[0], options.get("state"))
            if subcommand == "test":
                return connector.test_connection()
            if subcommand == "disconnect":
                return connector.disconnect()
            return {"commands": ["status", "setup", "oauth-url", "callback <code> --state <state>", "test", "disconnect"]}
        if command == "connector-enable-publish" and rest:
            return workflow.enable_connector_publish(rest[0])
        if command == "connector-disable-publish" and rest:
            return workflow.disable_connector_publish(rest[0])
        if command == "campaign" and rest[:1] == ["create"]:
            return workflow.create_campaign(
                campaign_name="CLI Campaign",
                platforms=["instagram", "linkedin", "x", "whatsapp"],
                project="Python course",
            )
        if command == "drafts":
            return workflow.list_drafts()
        if command == "approve" and rest:
            return workflow.approve_draft(rest[0])
        if command == "publish-approved" and rest:
            _, options = parse_cli_options(rest[1:])
            return workflow.publish_approved_draft(rest[0], options.get("connector"), options.get("confirm_sensitive", "false").lower() in {"true", "1", "yes"})
        if command == "publish" and rest:
            return workflow.publish_draft(rest[0])
        if command == "draft" and len(rest) >= 2:
            return workflow.create_draft(platform=rest[0], text=" ".join(rest[1:]))
        if command == "export" and rest:
            return {"output_path": export_campaign_markdown(rest[0])}
        if command == "calendar-export" and rest:
            return {"output_path": export_content_calendar_csv(rest[0])}
        return {"commands": ["connectors", "linkedin status|setup|oauth-url|callback|test|disconnect", "x status|setup|oauth-url|callback|test|disconnect", "campaign create", "draft <platform> <text>", "drafts", "approve <draft_id>", "publish-approved <draft_id> --connector <connector_id>", "connector-enable-publish <connector_id>", "connector-disable-publish <connector_id>", "export <campaign_id>", "calendar-export <campaign_id>"]}
    if args.area == "email":
        connector = get_email_connector("gmail")
        drafts = EmailDraftStore()
        if command == "gmail":
            sub = rest[0] if rest else "status"
            sub_rest = rest[1:]
            if sub == "status":
                return connector.get_status()
            if sub == "setup":
                return connector.setup()
            if sub == "oauth-url":
                return connector.start_oauth()
            if sub == "callback" and sub_rest:
                _, options = parse_cli_options(sub_rest[1:])
                return connector.handle_callback(sub_rest[0], options.get("state"))
            if sub == "disconnect":
                return connector.disconnect()
            if sub == "test":
                return connector.test_connection()
            return {"commands": ["gmail status", "gmail setup", "gmail oauth-url", "gmail callback <code> --state <state>", "gmail disconnect", "gmail test"]}
        if command == "setup":
            return connector.describe()
        if command == "recent":
            return connector.recent_messages()
        if command == "summarize":
            return connector.summarize_message(rest[0]) if rest else connector.summarize()
        if command == "search":
            return connector.search_messages(" ".join(rest))
        if command == "read" and rest:
            return connector.read_message(rest[0])
        if command == "draft-reply":
            message_id = rest[0] if rest else "latest"
            _, options = parse_cli_options(rest[1:])
            return connector.create_draft_reply(message_id, tone=options.get("tone", "professional")) if message_id != "latest" else drafts.create(connector.draft_reply(message_id))
        if command == "drafts":
            return drafts.list()
        if command == "approve" and rest:
            return drafts.approve(rest[0])
        if command == "send-approved" and rest:
            return drafts.mark_send_ready(rest[0], rest[1] if len(rest) > 1 else None)
        return {"commands": ["setup", "summarize", "search <query>", "draft-reply", "drafts", "approve <draft_id>", "send-approved <draft_id> <approval_id>"]}
    if args.area == "image":
        manager = ImageGenerationManager()
        if command == "providers":
            return manager.list_providers()
        if command == "generate":
            prompt, options = parse_cli_options(rest)
            return manager.generate(
                prompt=prompt,
                provider_name=options.get("provider", ""),
                size=options.get("size", "1024x1024"),
                style=options.get("style", "clean editorial"),
                generation_mode=options.get("mode", options.get("generation_mode", "model_based")),
                template_name=options.get("template"),
                platform=options.get("platform"),
                creative_type=options.get("creative_type"),
            )
        if command == "jobs":
            return manager.list_jobs()
        if command == "export" and rest:
            return {"output_path": export_image_prompt_markdown(rest[0])}
        return {"commands": ["providers", "generate <prompt>", "jobs", "export <job_id>"]}
    if args.area == "video":
        manager = VideoGenerationManager()
        if command == "providers":
            return manager.list_providers()
        if command == "storyboard":
            prompt, options = parse_cli_options(rest)
            return manager.storyboard(
                topic=prompt,
                duration_seconds=parse_int(options.get("duration"), 30),
                aspect_ratio=options.get("aspect_ratio", options.get("ratio", "9:16")),
                generation_mode=options.get("mode", options.get("generation_mode", "model_based")),
                template_name=options.get("template"),
                platform=options.get("platform"),
                scene_count=parse_int(options.get("scene_count"), 4),
            )
        if command in {"generate", "package"}:
            prompt, options = parse_cli_options(rest)
            return manager.generate(
                prompt=prompt,
                provider_name=options.get("provider", "openai_sora"),
                model=options.get("model"),
                duration_seconds=parse_int(options.get("duration"), 30),
                aspect_ratio=options.get("aspect_ratio", options.get("ratio", "9:16")),
                resolution=options.get("resolution", "1080p"),
                style=options.get("style", "modern social video"),
                generation_mode="hyperframes_skill" if command == "package" else options.get("mode", options.get("generation_mode", "model_based")),
                template_name=options.get("template"),
                platform=options.get("platform"),
                scene_count=parse_int(options.get("scene_count"), 4),
            )
        if command == "jobs":
            return manager.list_jobs()
        if command == "job" and rest:
            return manager.get_job(rest[0]) or {"status": "not_found", "job_id": rest[0]}
        if command == "poll" and rest:
            return manager.poll_job(rest[0])
        if command == "download" and rest:
            return manager.download_job(rest[0])
        if command == "cancel" and rest:
            return manager.cancel_job(rest[0])
        if command == "export" and rest:
            return manager.export_job(rest[0])
        return {"commands": ["providers", "storyboard <topic>", "generate <prompt>", "package <prompt>", "jobs", "job <job_id>", "poll <job_id>", "download <job_id>", "cancel <job_id>", "export <job_id>"]}
    if args.area == "automations":
        manager = AutomationManager()
        if command == "list":
            return manager.list()
        if command == "show" and rest:
            return manager.show(rest[0])
        if command == "create":
            return manager.create(
                {
                    "name": "CLI Automation",
                    "agent_slug": "automation-builder-agent",
                    "trigger_type": "manual",
                    "schedule_text": "manual",
                    "task_prompt": " ".join(rest) or "Draft a safe automation plan.",
                }
            )
        if command == "create-daily":
            name, options = parse_cli_options(rest)
            return manager.create_daily(
                name or "Daily Automation",
                options.get("time", "09:00"),
                options.get("agent", "personal-assistant-agent"),
                options.get("task", "Create my daily plan"),
                options.get("timezone", "Asia/Kolkata"),
            )
        if command == "create-weekly":
            name, options = parse_cli_options(rest)
            return manager.create_weekly(
                name or "Weekly Automation",
                options.get("day", "monday"),
                options.get("time", "10:00"),
                options.get("agent", "content-creator-agent"),
                options.get("task", "Create weekly content calendar"),
                options.get("timezone", "Asia/Kolkata"),
            )
        if command == "create-interval":
            name, options = parse_cli_options(rest)
            return manager.create_interval(
                name or "Interval Automation",
                parse_int(options.get("minutes"), 60),
                options.get("agent", "personal-assistant-agent"),
                options.get("task", "Create a safe local report"),
            )
        if command == "run" and rest:
            return manager.run(rest[0])
        if command == "schedule" and rest:
            row = manager.show(rest[0])
            return {"id": row["id"], "schedule": row.get("schedule"), "schedule_text": row.get("schedule_text"), "next_run_at": row.get("next_run_at")}
        if command == "history" and rest:
            return manager.history(rest[0])
        if command == "enable" and rest:
            return manager.set_enabled(rest[0], True)
        if command == "disable" and rest:
            return manager.set_enabled(rest[0], False)
        return {"commands": ["list", "show <id>", "create", "create-daily <name> --time 09:00 --agent <slug> --task <task>", "create-weekly <name> --day monday --time 10:00", "create-interval <name> --minutes 60", "run <id>", "schedule <id>", "history <id>", "enable <id>", "disable <id>"]}
    if args.area == "scheduler":
        scheduler = SchedulerEngine()
        if command == "status":
            return scheduler.status()
        if command == "due":
            return scheduler.list_due()
        if command in {"tick", "run-due"}:
            _, options = parse_cli_options(rest)
            if command == "run-due":
                return scheduler.run_due(limit=parse_int(options.get("limit"), 5))
            return scheduler.tick()
        if command == "runs":
            return scheduler.runs()
        if command == "run-show" and rest:
            return scheduler.run_show(rest[0])
        return {"commands": ["status", "due", "tick", "run-due", "runs", "run-show <run_id>"]}
    
    if args.area == "browser":
        from runtime.automation.browser import BrowserAutomationManager
        manager = BrowserAutomationManager()
        if command == "status":
            return manager.status()
        if command == "enable":
            _, options = parse_cli_options(rest)
            if options.get("confirm", "false").lower() in {"1", "true", "yes", "on"}:
                from runtime.automation.browser_settings import update_browser_settings
                update_browser_settings({"browser_automation_enabled": True})
                return {"status": "enabled"}
            return {"status": "blocked", "message": "Requires --confirm true"}
        if command == "disable":
            from runtime.automation.browser_settings import update_browser_settings
            update_browser_settings({"browser_automation_enabled": False})
            return {"status": "disabled"}
        return {"commands": ["status", "enable --confirm true", "disable"]}

    if args.area == "search":
        from runtime.automation.search import SearchManager
        manager = SearchManager()
        if command == "status":
            return manager.provider_status("configured")
        if command == "providers":
            return manager.PROVIDERS
        return {"commands": ["status", "providers"]}

    if args.area == "approvals":
        manager = ApprovalManager()
        if command == "list":
            return manager.list()
        if command == "approve" and rest:
            return manager.decide(rest[0], "approved")
        if command == "reject" and rest:
            return manager.decide(rest[0], "rejected")
        return {"commands": ["list", "approve <id>", "reject <id>"]}
    if args.area == "content":
        if command == "create":
            from runtime.content_creator import ContentCreator

            return ContentCreator().create_package(topic=" ".join(rest) or "AI course")
        if command == "list":
            from runtime.content_creator import ContentCreator

            return ContentCreator().list_packages()
        return {"commands": ["create <topic>", "list"]}
    if args.area == "logs":
        release = ReleaseManager()
        if command == "path":
            return release.logs_path()
        if command == "tail":
            _, options = parse_cli_options(rest)
            return release.logs_tail(lines=parse_int(options.get("lines"), 40))
        if command == "clear":
            _, options = parse_cli_options(rest)
            return release.logs_clear(confirm=options.get("confirm", "false").lower() in {"1", "true", "yes", "on"})
        if command == "list":
            return list_external_actions()
        if command == "show" and rest:
            from runtime.db import get_record

            return get_record("action_logs", rest[0]) or {}
        if command == "agent-runs":
            return AgentRunner().list_runs()
        return {"commands": ["list", "show <id>", "agent-runs"]}
    if args.area == "voice":
        from runtime.voice.settings import get_voice_settings, update_voice_setting
        from runtime.voice.wake import detect_wake_phrase
        from runtime.voice.tts import get_tts_provider
        from runtime.voice.session import VoiceSessionManager
        
        if command == "status":
            return VoiceSessionManager().get_status()
        if command == "settings":
            return get_voice_settings()
        if command == "enable":
            _, options = parse_cli_options(rest)
            if options.get("confirm", "false").lower() not in {"1", "true", "yes", "on"}:
                return {"status": "error", "message": "You must use --confirm true to enable the voice assistant."}
            return update_voice_setting("voice_enabled", True)
        if command == "disable":
            return update_voice_setting("voice_enabled", False)
        if command == "wake-enable":
            _, options = parse_cli_options(rest)
            if options.get("confirm", "false").lower() not in {"1", "true", "yes", "on"}:
                return {"status": "error", "message": "You must use --confirm true to enable wake listening."}
            return update_voice_setting("wake_listening_enabled", True)
        if command == "wake-disable":
            return update_voice_setting("wake_listening_enabled", False)
        if command == "set-name" or (command == "name" and rest and rest[0] == "set"):
            name = rest[1] if command == "name" else rest[0] if rest else None
            if not name:
                return {"status": "error", "message": "Please provide a name."}
            return update_voice_setting("assistant_name", name)
        if command == "test-wake":
            transcript = " ".join(rest)
            settings = get_voice_settings()
            return detect_wake_phrase(transcript, settings.get("wake_phrases", []))
        if command in ("speak", "say"):
            text = " ".join(rest)
            settings = get_voice_settings()
            tts = get_tts_provider(settings.get("tts_provider", "mock"))
            return tts.speak(text)
        if command in ("session", "simulate"):
            _, options = parse_cli_options([command] + rest)
            transcript = options.get("transcript") or " ".join(r for r in rest if not r.startswith("--"))
            if command == "session" and rest and rest[0] == "simulate":
                transcript = options.get("transcript") or " ".join(r for r in rest[1:] if not r.startswith("--"))
            return VoiceSessionManager().simulate_voice_command(transcript)
        
        return {"commands": ["status", "settings", "enable --confirm true", "disable", "wake-enable --confirm true", "wake-disable", "set-name <name>", "test-wake <transcript>", "speak <text>", "simulate <transcript>"]}
    if args.area == "settings":
        manager = SettingsManager()
        if command == "list":
            return manager.list()
        if command == "get" and rest:
            return manager.get(rest[0])
        if command == "set" and len(rest) >= 2:
            return manager.set(rest[0], " ".join(rest[1:]))
        return {"commands": ["list", "get <key>", "set <key> <value>"]}
    if args.area == "permissions":
        manager = PermissionManager()
        if command == "status":
            return manager.status()
        if command == "set" and rest:
            return manager.set(rest[0])
        if command == "rules":
            return manager.rules_status()
        return {"commands": ["status", "set safe|developer|full_automation", "rules"]}
    if args.area == "skills":
        from runtime.skills import (
            approve_skill_permissions,
            create_skill_from_template,
            disable_skill,
            discover_skills,
            enable_skill,
            get_audit_logs,
            get_latest_audit,
            get_skill,
            get_skill_templates,
            install_skill,
            list_installed_skills,
            run_skill,
            search_skills,
            skill_permissions,
            skill_status,
            uninstall_skill,
            upgrade_skill,
        )
        from runtime.skills.validator import validate_skill
        _, options = parse_cli_options([command] + rest if command else rest)
        if command == "list":
            return {"skills": list_installed_skills()}
        if command == "installed":
            return {"skills": list_installed_skills()}
        if command == "validate" and rest:
            return validate_skill(rest[0])
        if command == "install" and rest:
            return install_skill(rest[0], upgrade=options.get("upgrade") == "true")
        if command == "enable" and rest:
            return enable_skill(rest[0])
        if command == "disable" and rest:
            return disable_skill(rest[0])
        if command == "uninstall" and rest:
            return uninstall_skill(rest[0], confirm=options.get("confirm") == "true")
        if command == "status" and rest:
            return skill_status(rest[0])
        if command == "permissions" and rest:
            return skill_permissions(rest[0])
        if command == "approve-permissions" and rest:
            perms = options.get("permissions", "").split(",")
            return approve_skill_permissions(rest[0], perms, confirm=options.get("confirm") == "true")
        if command == "run" and rest:
            inputs = {}
            input_str = options.get("input", "")
            if input_str:
                import json as _json
                try:
                    inputs = _json.loads(input_str)
                except _json.JSONDecodeError:
                    return {"status": "error", "message": "Invalid JSON for --input"}
            dry_run = options.get("dry-run", "true").lower() == "true"
            timeout = int(options.get("timeout", "30"))
            return run_skill(rest[0], inputs, dry_run=dry_run, timeout=timeout)
        if command == "templates":
            return {"templates": get_skill_templates()}
        if command == "search":
            query = rest[0] if rest else ""
            return {"results": search_skills(query)}
        if command == "discover":
            path = rest[0] if rest else ""
            paths = [path] if path else None
            return {"discovered": discover_skills(paths)}
        if command == "create" and rest:
            new_id = rest[0]
            template = options.get("template", "")
            name = options.get("name", new_id.replace("-", " ").title())
            if not template:
                return {"status": "error", "message": "Provide --template <template_id>"}
            return create_skill_from_template(template, new_id, name)
        if command == "upgrade" and rest:
            return upgrade_skill(rest[0], confirm=options.get("confirm") == "true", force=options.get("force") == "true")
        if command == "audit":
            skill_id = rest[0] if rest else None
            latest = options.get("latest") == "true"
            if latest:
                return {"latest": get_latest_audit(skill_id)}
            return {"audit_logs": get_audit_logs(skill_id)}
        if command == "pack":
            from runtime.skills.packs import (
                check_missing_dependencies,
                decode_pack,
                dependency_install_plan,
                diff_packs,
                encode_pack,
                export_base64_pack,
                export_pack,
                export_pack_analytics,
                generate_key,
                get_pack_analytics,
                get_trust_state,
                import_base64_pack,
                import_pack,
                install_pack,
                inspect_pack,
                list_imported_packs,
                list_keys,
                preview_install,
                remove_pack,
                resolve_pack_dependencies,
                rollback_pack,
                sign_pack,
                trust_key,
                untrust_key,
                upgrade_pack,
                upgrade_plan,
                validate_pack,
                verify_pack_signature,
            )
            pack_cmd = rest[0] if rest else ""
            pack_rest = rest[1:]
            if pack_cmd == "validate" and pack_rest:
                return validate_pack(pack_rest[0])
            if pack_cmd == "inspect" and pack_rest:
                return inspect_pack(pack_rest[0])
            if pack_cmd == "export":
                skill_ids_str = options.get("skills", "")
                if not skill_ids_str:
                    return {"status": "error", "message": "Provide --skills id1,id2,..."}
                skill_ids = [s.strip() for s in skill_ids_str.split(",") if s.strip()]
                output = options.get("output", f"workspace/outputs/skill-packs/{options.get('pack-id', 'pack')}.liuantskillpack")
                pack_meta = {
                    "pack_id": options.get("pack-id", "unnamed-pack"),
                    "name": options.get("name", "Unnamed Pack"),
                    "version": options.get("version", "0.1.0"),
                    "description": options.get("description", ""),
                    "author": options.get("author", "Unknown"),
                    "license": options.get("license", "MIT"),
                    "tags": [t.strip() for t in options.get("tags", "").split(",") if t.strip()],
                }
                return export_pack(skill_ids, output, pack_meta)
            if pack_cmd == "import" and pack_rest:
                return import_pack(pack_rest[0])
            if pack_cmd == "install" and pack_rest:
                selected = options.get("skills", "")
                selected_skills = [s.strip() for s in selected.split(",") if s.strip()] if selected else None
                return install_pack(pack_rest[0], selected_skills)
            if pack_cmd == "list":
                return {"packs": list_imported_packs()}
            if pack_cmd == "remove" and pack_rest:
                return remove_pack(pack_rest[0], confirm=options.get("confirm") == "true")
            if pack_cmd == "dependencies" and pack_rest:
                return resolve_pack_dependencies(pack_rest[0])
            if pack_cmd == "install-plan" and pack_rest:
                return dependency_install_plan(pack_rest[0])
            if pack_cmd == "upgrade" and pack_rest:
                return upgrade_pack(pack_rest[0], confirm=options.get("confirm") == "true", force=options.get("force") == "true")
            if pack_cmd == "upgrade-plan" and pack_rest:
                return upgrade_plan(pack_rest[0])
            if pack_cmd == "rollback" and pack_rest:
                return rollback_pack(pack_rest[0], confirm=options.get("confirm") == "true")
            if pack_cmd == "diff" and len(pack_rest) >= 2:
                return diff_packs(pack_rest[0], pack_rest[1], include_files=options.get("include-files") == "true")
            if pack_cmd == "preview-install" and pack_rest:
                return preview_install(pack_rest[0])
            if pack_cmd == "verify" and pack_rest:
                return verify_pack_signature(pack_rest[0])
            if pack_cmd == "trust-status" and pack_rest:
                return get_trust_state(pack_rest[0])
            if pack_cmd == "sign" and pack_rest:
                key_id = options.get("key", "")
                if not key_id:
                    return {"status": "error", "message": "Provide --key <key_id>"}
                return sign_pack(pack_rest[0], key_id)
            if pack_cmd == "encode" and pack_rest:
                output = options.get("output", "")
                return encode_pack(pack_rest[0], output if output else None)
            if pack_cmd == "decode" and pack_rest:
                output = options.get("output", "")
                return decode_pack(pack_rest[0], output if output else None)
            if pack_cmd == "import-base64" and pack_rest:
                return import_base64_pack(pack_rest[0])
            if pack_cmd == "export-base64" and pack_rest:
                skill_ids_str = options.get("skills", "")
                if not skill_ids_str:
                    return {"status": "error", "message": "Provide --skills id1,id2,..."}
                skill_ids = [s.strip() for s in skill_ids_str.split(",") if s.strip()]
                output = options.get("output", f"workspace/outputs/skill-packs/{pack_rest[0]}.txt")
                pack_meta = {
                    "pack_id": pack_rest[0],
                    "name": pack_rest[0].replace("-", " ").title(),
                    "version": options.get("version", "0.1.0"),
                    "description": "",
                    "author": "Unknown",
                    "license": "MIT",
                    "tags": [],
                }
                return export_base64_pack(skill_ids, output, pack_meta)
            if pack_cmd == "analytics":
                pack_id = pack_rest[0] if pack_rest else None
                fmt = options.get("export", "")
                if fmt:
                    return {"content": export_pack_analytics(fmt)}
                return get_pack_analytics(pack_id)
            if pack_cmd == "keys":
                key_cmd = pack_rest[0] if pack_rest else ""
                key_rest = pack_rest[1:]
                if key_cmd == "generate":
                    name = options.get("name", "local-maintainer")
                    return generate_key(name)
                if key_cmd == "list":
                    return {"keys": list_keys()}
                if key_cmd == "trust" and key_rest:
                    return trust_key(key_rest[0], confirm=options.get("confirm") == "true")
                if key_cmd == "untrust" and key_rest:
                    return untrust_key(key_rest[0], confirm=options.get("confirm") == "true")
                return {"commands": ["generate --name <name>", "list", "trust <key_id> --confirm true", "untrust <key_id> --confirm true"]}
            return {"commands": ["validate <pack_path>", "inspect <pack_path>", "export --skills id1,id2 --pack-id <id> --name <name> --version <ver> --output <path>", "import <pack_path>", "install <pack_path> [--skills id1,id2]", "list", "remove <pack_id> --confirm true", "dependencies <pack_path>", "install-plan <pack_path>", "upgrade <pack_path> --confirm true [--force true]", "upgrade-plan <pack_path>", "rollback <pack_id> --confirm true", "diff <old> <new> [--include-files true]", "preview-install <pack_path>", "verify <pack_path>", "trust-status <pack_path>", "sign <source> --key <key_id>", "encode <pack_path> [--output <path>]", "decode <encoded_path> [--output <path>]", "import-base64 <encoded_path>", "export-base64 <pack_id> --skills id1,id2 [--output <path>]", "analytics [pack_id] [--export markdown|json|csv]", "keys <subcommand>"]}
        if command == "workflow":
            from runtime.skills.workflows import (
                discover_workflows,
                export_workflow_run,
                get_workflow_run,
                inspect_workflow,
                list_workflow_runs,
                list_workflows,
                preview_rerun_from_step,
                preview_workflow_run,
                register_workflow,
                run_workflow,
                validate_workflow,
                workflow_permission_summary,
            )
            from runtime.skills.workflow_audit import get_workflow_audit
            wf_cmd = rest[0] if rest else ""
            wf_rest = rest[1:]
            if wf_cmd == "list":
                return {"workflows": list_workflows()}
            if wf_cmd == "discover":
                paths_str = options.get("paths", "")
                paths = [p.strip() for p in paths_str.split(",") if p.strip()] if paths_str else None
                return discover_workflows(paths)
            if wf_cmd == "validate" and wf_rest:
                wf_path = wf_rest[0]
                wf_id = options.get("workflow-id")
                if wf_id:
                    return validate_workflow(workflow_id=wf_id)
                return validate_workflow(wf_path)
            if wf_cmd == "inspect" and wf_rest:
                wf_path = wf_rest[0]
                wf_id = options.get("workflow-id")
                if wf_id:
                    return inspect_workflow(workflow_id=wf_id)
                return inspect_workflow(wf_path)
            if wf_cmd == "preview" and wf_rest:
                wf_id = wf_rest[0]
                inputs_str = options.get("input", "{}")
                try:
                    inputs = json.loads(inputs_str)
                except json.JSONDecodeError:
                    inputs = {}
                return preview_workflow_run(wf_id, inputs=inputs)
            if wf_cmd == "permissions" and wf_rest:
                return workflow_permission_summary(wf_rest[0])
            if wf_cmd == "run" and wf_rest:
                wf_id = wf_rest[0]
                dry_run = options.get("dry-run", "false") == "true"
                confirmed = options.get("confirm", "false") == "true"
                inputs_str = options.get("input", "{}")
                try:
                    inputs = json.loads(inputs_str)
                except json.JSONDecodeError:
                    inputs = {}
                return run_workflow(workflow_id=wf_id, inputs=inputs, dry_run=dry_run, user_confirmed=confirmed or dry_run)
            if wf_cmd == "audit":
                wf_id = wf_rest[0] if wf_rest else None
                latest = options.get("latest", "false") == "true"
                if latest and wf_id:
                    from runtime.skills.workflow_audit import get_latest_workflow_run
                    return {"latest_run": get_latest_workflow_run(wf_id)}
                return {"runs": get_workflow_audit(workflow_id=wf_id, limit=20)}
            if wf_cmd == "runs" and wf_rest:
                return {"runs": list_workflow_runs(workflow_id=wf_rest[0], limit=20)}
            if wf_cmd == "runs":
                return {"runs": list_workflow_runs(limit=20)}
            if wf_cmd == "run-detail" and wf_rest:
                run_data = get_workflow_run(wf_rest[0])
                if not run_data:
                    return {"status": "error", "message": f"Run '{wf_rest[0]}' not found"}
                from runtime.skills.workflow_audit import get_workflow_steps
                steps = get_workflow_steps(wf_rest[0])
                return {"run": run_data, "steps": steps}
            if wf_cmd == "export-run" and wf_rest:
                fmt = options.get("format", "json")
                return {"content": export_workflow_run(wf_rest[0], format=fmt)}
            if wf_cmd == "rerun-plan" and wf_rest:
                run_id = wf_rest[0]
                from_step = options.get("from-step", "")
                if not from_step:
                    return {"status": "error", "message": "Provide --from-step <step_id>"}
                return preview_rerun_from_step(run_id, from_step)
            if wf_cmd == "discover":
                paths_str = options.get("paths", "")
                paths = [p.strip() for p in paths_str.split(",") if p.strip()] if paths_str else None
                return discover_workflows(paths)
            if wf_cmd == "register" and wf_rest:
                return register_workflow(wf_rest[0])
            return {"commands": ["list", "discover [--paths path1,path2]", "validate <workflow.json>", "validate --workflow-id <id>", "inspect <workflow.json>", "preview <workflow_id> [--input '{...}']", "permissions <workflow_id>", "run <workflow_id> [--dry-run true] [--confirm true] [--input '{...}']", "audit [workflow_id] [--latest]", "runs [workflow_id]", "run-detail <run_id>", "export-run <run_id> [--format json|markdown]", "rerun-plan <run_id> --from-step <step_id>", "register <workflow.json>"]}
        if command == "compatibility":
            from runtime.skills.compatibility import (
                check_all_installed_compatibility,
                check_compatibility,
                load_compatibility_matrix,
                save_compatibility_matrix,
            )
            compat_cmd = rest[0] if rest else ""
            compat_rest = rest[1:]
            if compat_cmd == "check" and compat_rest:
                return check_compatibility(pack_path=compat_rest[0])
            if compat_cmd == "check-pack" and compat_rest:
                return check_compatibility(pack_id=compat_rest[0])
            if compat_cmd == "check-all":
                return check_all_installed_compatibility()
            if compat_cmd == "save":
                return save_compatibility_matrix()
            if compat_cmd == "load":
                return load_compatibility_matrix()
            return {"commands": ["check <pack_path>", "check-pack <pack_id>", "check-all", "save", "load"]}
        if command == "lint":
            from runtime.skills.linter import apply_safe_lint_fixes, lint_pack
            lint_cmd = rest[0] if rest else ""
            lint_rest = rest[1:]
            if lint_cmd:
                strict = options.get("strict", "false") == "true"
                fix_suggestions = options.get("fix-suggestions", "false") == "true"
                apply_fixes = options.get("apply-safe-fixes", "false") == "true"
                confirm = options.get("confirm", "false") == "true"
                if apply_fixes:
                    return apply_safe_lint_fixes(lint_cmd, confirm=confirm)
                return lint_pack(lint_cmd, strict=strict, fix_suggestions=fix_suggestions)
            return {"commands": ["<pack_path> [--strict true] [--fix-suggestions] [--apply-safe-fixes --confirm true]"]}
        if command == "changelog":
            from runtime.skills.changelog import (
                generate_changelog,
                generate_changelog_from_registry,
                update_pack_changelog,
            )
            cl_cmd = rest[0] if rest else ""
            cl_rest = rest[1:]
            if cl_cmd == "generate" and len(cl_rest) >= 2:
                return generate_changelog(cl_rest[0], cl_rest[1])
            if cl_cmd == "from-registry" and cl_rest:
                return generate_changelog_from_registry(cl_rest[0])
            if cl_cmd == "update" and cl_rest:
                entries_str = options.get("entries", "[]")
                try:
                    entries = json.loads(entries_str)
                except json.JSONDecodeError:
                    entries = []
                return update_pack_changelog(cl_rest[0], entries)
            return {"commands": ["generate <old_pack> <new_pack>", "from-registry <pack_id>", "update <source_dir> --entries '[...]'"]}
        if command == "url-import":
            from runtime.skills.url_import import (
                clear_staging,
                import_staged,
                install_staged,
                list_staged_packs,
                preview_url_import,
            )
            url_cmd = rest[0] if rest else ""
            url_rest = rest[1:]
            if url_cmd == "preview" and url_rest:
                return preview_url_import(url_rest[0])
            if url_cmd == "import-staged" and url_rest:
                return import_staged(url_rest[0], confirm=options.get("confirm") == "true")
            if url_cmd == "install-staged" and url_rest:
                return install_staged(url_rest[0], confirm=options.get("confirm") == "true")
            if url_cmd == "import" and url_rest:
                install = options.get("install", "false") == "true"
                return preview_url_import(url_rest[0])
            if url_cmd == "list":
                return {"staged": list_staged_packs()}
            if url_cmd == "clear":
                return clear_staging()
            return {"commands": ["preview <https_url>", "import-staged <staged_id> --confirm true", "install-staged <staged_id> --confirm true", "list", "clear"]}
        if command == "recommend":
            from runtime.skills.recommender import (
                get_recommendations,
                recommend_by_category,
                recommend_low_risk_alternatives,
                recommend_packs,
                recommend_skills_for_workflow,
            )
            rec_cmd = rest[0] if rest else ""
            rec_rest = rest[1:]
            explain = options.get("explain", "false") == "true"
            if rec_cmd == "packs":
                limit = int(options.get("limit", "5"))
                return {"recommendations": recommend_packs(limit=limit, explain=explain)}
            if rec_cmd == "workflow" and rec_rest:
                return recommend_skills_for_workflow(rec_rest[0])
            if rec_cmd == "category" and rec_rest:
                limit = int(options.get("limit", "5"))
                return {"recommendations": recommend_by_category(rec_rest[0], limit=limit)}
            if rec_cmd == "alternatives" and rec_rest:
                return {"alternatives": recommend_low_risk_alternatives(rec_rest[0])}
            if rec_cmd == "all":
                query = rec_rest[0] if rec_rest else ""
                limit = int(options.get("limit", "5"))
                return get_recommendations(query=query, limit=limit, explain=explain)
            if rec_cmd and not rec_cmd.startswith("-"):
                limit = int(options.get("limit", "5"))
                for_workflow = options.get("for-workflow", "")
                return get_recommendations(query=rec_cmd, limit=limit, explain=explain, for_workflow=for_workflow)
            return {"commands": ["packs [--limit 5] [--explain]", "workflow <workflow_id>", "category <tag> [--limit 5]", "alternatives <pack_id>", "all [query] [--limit 5] [--explain]", "<query> [--explain] [--for-workflow <id>]"]}
        if command == "catalog":
            from runtime.skills.packs import (
                catalog_install,
                refresh_catalog,
                search_catalog,
            )
            catalog_cmd = rest[0] if rest else ""
            catalog_rest = rest[1:]
            if catalog_cmd == "refresh":
                return refresh_catalog()
            if catalog_cmd == "search" and catalog_rest:
                return {"results": search_catalog(catalog_rest[0])}
            if catalog_cmd == "install" and catalog_rest:
                return catalog_install(catalog_rest[0])
            if catalog_cmd == "inspect" and catalog_rest:
                results = search_catalog(catalog_rest[0])
                if results:
                    return results[0]
                return {"status": "error", "message": f"Pack '{catalog_rest[0]}' not found in catalog"}
            return refresh_catalog()
        return {"commands": ["list", "installed", "validate <path>", "install <path> [--upgrade true]", "enable <skill_id>", "disable <skill_id>", "uninstall <skill_id> --confirm true", "status <skill_id>", "permissions <skill_id>", "approve-permissions <skill_id> --permissions perm1,perm2 --confirm true", "run <skill_id> --input '{...}' [--timeout 30] [--dry-run true]", "templates", "search [query]", "discover [path]", "create <new_id> --template <template_id>", "upgrade <path> --confirm true", "audit [skill_id] [--latest]", "pack <subcommand>", "catalog <subcommand>"]}
    if args.area == "workspace":
        manager = WorkspaceManager()
        if command == "list":
            return manager.list()
        if command == "create" and rest:
            return manager.create(rest[0])
        if command == "set-default" and rest:
            return manager.set_default(rest[0])
        if command == "show" and rest:
            return manager.show(rest[0])
        return {"commands": ["list", "create <name>", "set-default <name>", "show <name>"]}
    if args.area == "exports":
        manager = ExportTracker()
        if command == "list":
            return manager.list()
        if command in {"show", "open"} and rest:
            return manager.show(rest[0])
        return {"commands": ["list", "show <id>", "open <id>"]}
    if args.area == "onboarding":
        manager = OnboardingManager()
        if command == "status":
            return manager.status()
        if command == "reset":
            return manager.reset()
        if command == "complete-step" and rest:
            return manager.complete_step(rest[0])
        return {"commands": ["status", "reset", "complete-step <step>"]}
    if args.area == "usage":
        from runtime.usage import UsageTracker
        tracker = UsageTracker()
        if command == "summary":
            _, options = parse_cli_options(rest)
            ws = options.get("workspace")
            return tracker.get_summary(workspace=ws)
        if command == "today":
            _, options = parse_cli_options(rest)
            ws = options.get("workspace")
            return tracker.get_today(workspace=ws)
        if command == "by-provider":
            _, options = parse_cli_options(rest)
            ws = options.get("workspace")
            return tracker.get_by_provider(workspace=ws)
        if command == "by-role":
            _, options = parse_cli_options(rest)
            ws = options.get("workspace")
            return tracker.get_by_role(workspace=ws)
        if command == "reset":
            _, options = parse_cli_options(rest)
            return tracker.reset() if options.get("confirm") == "true" else {"status": "error", "message": "Set --confirm true to reset."}
        if command == "budget":
            return tracker.get_budget()
        if command == "budget-set":
            _, options = parse_cli_options(rest)
            kwargs = {}
            for k in ("daily_estimated_cost_limit", "monthly_estimated_cost_limit", "per_provider_limit", "per_role_limit", "discussion_mode_cost_warning_threshold", "cloud_model_warning_enabled", "budget_blocking_enabled"):
                if k in options:
                    kwargs[k] = float(options[k]) if k != "cloud_model_warning_enabled" and k != "budget_blocking_enabled" else options[k].lower() == "true"
            return tracker.set_budget(**kwargs) if kwargs else {"status": "error", "message": "Provide --daily, --monthly, --per-provider, --per-role, --discussion-threshold, --cloud-warning, or --blocking."}
        if command == "budget-reset":
            return tracker.reset_budget()
        if command == "alerts":
            _, options = parse_cli_options(rest)
            if options.get("history") == "true":
                return {"alerts": tracker.get_alert_history(include_dismissed=False)}
            return tracker.check_budget_alerts()
        if command == "export":
            _, options = parse_cli_options(rest)
            fmt = options.get("format", "csv")
            ws = options.get("workspace")
            return tracker.export_usage(fmt=fmt, workspace=ws)
        if command == "anomalies":
            return tracker.detect_anomalies()
        if command == "trends":
            _, options = parse_cli_options(rest)
            days = int(options.get("days", 7))
            if options.get("monthly") == "true":
                return tracker.get_monthly_trends()
            return tracker.get_trends(days=days)
        if command == "webhook":
            _, options = parse_cli_options(rest)
            sub = options.get("subcommand", rest[0] if rest else "status")
            if sub == "status":
                return tracker.get_webhook_status()
            if sub == "set-url" and rest:
                url = rest[1] if len(rest) > 1 else ""
                return tracker.set_webhook_url(url, confirm=options.get("confirm") == "true")
            if sub == "test":
                return tracker.send_webhook_test(event_type=options.get("event", "budget_warning"))
            if sub == "enable":
                return tracker.enable_webhooks(confirm=options.get("confirm") == "true")
            if sub == "disable":
                return tracker.disable_webhooks()
            if sub == "send-test":
                from runtime.usage.webhooks import WebhookDelivery
                delivery = WebhookDelivery()
                return delivery.send_test(event_type=options.get("event", "budget_warning"))
            if sub == "delivery-history":
                from runtime.usage.webhooks import WebhookDelivery
                delivery = WebhookDelivery()
                limit = int(options.get("limit", 50))
                return {"deliveries": delivery.get_delivery_history(limit=limit)}
            if sub == "retry-failed":
                from runtime.usage.webhooks import WebhookDelivery
                delivery = WebhookDelivery()
                if options.get("confirm") != "true":
                    return {"status": "error", "message": "Retry requires --confirm true."}
                return delivery.retry_failed()
            if sub == "set-secret":
                if options.get("confirm") != "true":
                    return {"status": "error", "message": "Setting webhook secret requires --confirm true."}
                secret = options.get("secret", "")
                if not secret:
                    return {"status": "error", "message": "Provide --secret <value>."}
                tracker.settings.set("webhook_secret", secret)
                tracker.settings.set("webhook_hmac_enabled", "true")
                return {"status": "updated", "message": "Webhook HMAC secret set. Secret is stored securely and never logged."}
            if sub == "rotate-secret":
                if options.get("confirm") != "true":
                    return {"status": "error", "message": "Rotating webhook secret requires --confirm true."}
                import secrets
                new_secret = secrets.token_hex(32)
                tracker.settings.set("webhook_secret", new_secret)
                return {"status": "rotated", "message": "Webhook HMAC secret rotated. Update your receiver verification."}
            if sub == "signature-test":
                from runtime.usage.webhooks import WebhookDelivery
                delivery = WebhookDelivery()
                payload_json = '{"event_type":"test","workspace":"default","level":"info","message":"HMAC signature test","timestamp":"' + utc_now() + '","source":"liuant-agentic-os"}'
                headers = delivery._build_signature_headers(payload_json, "signature_test")
                has_signature = "X-Liuant-Signature" in headers
                has_timestamp = "X-Liuant-Timestamp" in headers
                return {"hmac_enabled": delivery._is_hmac_enabled(), "has_signature_header": has_signature, "has_timestamp_header": has_timestamp, "message": "HMAC signature test complete." if has_signature else "HMAC not enabled or secret not set."}
            return {"status": "error", "message": "Usage: webhook status|set-url <url> --confirm true|test|enable --confirm true|disable|send-test|delivery-history|retry-failed --confirm true|set-secret --confirm true|rotate-secret --confirm true|signature-test"}
        if command == "discussion-costs":
            _, options = parse_cli_options(rest)
            ws = options.get("workspace")
            disc_id = options.get("discussion-id")
            latest = options.get("latest") == "true"
            rounds = options.get("rounds") == "true"
            costs = tracker.get_discussion_costs_by_round(discussion_id=disc_id, workspace=ws, latest=latest, rounds=rounds)
            if latest and costs["discussions"]:
                return {"latest": costs["discussions"][0], "total_cost": costs["total_cost"]}
            return costs
        if command == "cleanup-scheduler":
            _, options = parse_cli_options(rest)
            sub = options.get("subcommand", rest[0] if rest else "status")
            if sub == "status":
                return tracker.get_cleanup_scheduler_status()
            if sub == "enable":
                return tracker.enable_cleanup_scheduler(confirm=options.get("confirm") == "true")
            if sub == "disable":
                return tracker.disable_cleanup_scheduler()
            if sub == "run-now":
                dry_run = options.get("dry-run") == "true"
                confirm = options.get("confirm") == "true"
                export_before = options.get("export-before", "true").lower() == "true"
                return tracker.run_cleanup_now(dry_run=dry_run, confirm=confirm, export_before=export_before)
            return {"status": "error", "message": "Usage: cleanup-scheduler status|enable --confirm true|disable|run-now [--dry-run] [--confirm true] [--export-before true]"}
        if command == "cleanup":
            _, options = parse_cli_options(rest)
            if options.get("dry-run") == "true" and options.get("show-export-plan") == "true":
                return tracker.cleanup_dry_run_with_export_plan()
            if options.get("dry-run") == "true" or not options.get("confirm"):
                return tracker.cleanup_dry_run()
            export_before = options.get("export-before-cleanup", "false").lower() == "true"
            if export_before:
                export_result = tracker.export_usage(fmt="json")
                if export_result.get("status") != "exported":
                    return {"status": "error", "message": "Export failed. Cleanup aborted."}
            return tracker.cleanup_confirm()
        return {"commands": ["summary [--workspace current|all|<name>]", "today [--workspace current]", "by-provider [--workspace current]", "by-role [--workspace current]", "reset --confirm true", "budget", "budget-set --daily 2.00 --monthly 30.00", "budget-reset", "alerts [--history]", "export --format csv|json|markdown [--workspace current]", "anomalies", "trends --days 7|30", "trends --monthly", "webhook status|set-url|test|enable|disable|send-test|delivery-history|retry-failed|set-secret|rotate-secret|signature-test", "discussion-costs [--latest] [--rounds] [--discussion-id <id>] [--workspace current]", "retention", "retention-set --days 90", "cleanup [--dry-run] [--confirm true] [--show-export-plan] [--export-before-cleanup]", "cleanup-scheduler status|enable|disable|run-now"]}
    if args.area == "serve":
        from runtime.api.simple_server import run_server

        port_value = args.command if args.command and args.command.isdigit() else (rest[0] if rest else "8000")
        port = int(port_value)
        run_server(port=port)
        return {"status": "stopped"}
    raise ValueError(f"Unknown area: {args.area}")


def render(area: str, data: Any) -> None:
    if HAS_RICH:
        render_rich(area, data)
    else:
        render_plain(area, data)
    print_examples(area)


def render_rich(area: str, data: Any) -> None:
    if area == "dashboard":
        table = Table(title="Liuant Dashboard", box=box.SIMPLE_HEAVY)
        table.add_column("Area")
        table.add_column("Count", justify="right")
        table.add_row("Agents", str(data["agents"]["count"]))
        table.add_row("Campaigns", str(data["campaigns"]["count"]))
        table.add_row("Pending Approvals", str(data["approvals"]["pending"]))
        table.add_row("Image Jobs", str(data["jobs"]["image"]["count"]))
        table.add_row("Video Jobs", str(data["jobs"]["video"]["count"]))
        table.add_row("Automations", str(data["automations"]["count"]))
        table.add_row("Configured Providers", str(data["providers"]["configured_count"]))
        console.print(table)
        return
    if area == "status":
        console.print(Panel(json.dumps(data, indent=2), title="Liuant Status", border_style="green"))
        return
    if isinstance(data, list):
        render_list_table(area, data)
        return
    if isinstance(data, dict) and {"id", "status"} & set(data.keys()):
        console.print(Panel(json.dumps(data, indent=2, sort_keys=True), title=f"{area.title()} OK", border_style="green"))
        return
    console.print(Panel(json.dumps(data, indent=2, sort_keys=True), title=area.title(), border_style="cyan"))


def render_list_table(area: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print(Panel("No records yet.", title=f"{area.title()} Empty", border_style="yellow"))
        return
    table = Table(title=area.title(), box=box.SIMPLE)
    keys = ["id", "name", "title", "skill_name", "slug", "provider", "platform", "status", "action_type", "campaign_name", "created_at"]
    visible = [key for key in keys if any(isinstance(row, dict) and key in row for row in rows)]
    for key in visible[:5]:
        table.add_column(key)
    for row in rows[:20]:
        table.add_row(*[short(str(row.get(key, ""))) for key in visible[:5]])
    console.print(table)


def render_plain(area: str, data: Any) -> None:
    print(f"\n== Liuant {area.title()} ==")
    if area == "dashboard" and isinstance(data, dict):
        for label, value in (
            ("Agents", data["agents"]["count"]),
            ("Campaigns", data["campaigns"]["count"]),
            ("Pending approvals", data["approvals"]["pending"]),
            ("Image jobs", data["jobs"]["image"]["count"]),
            ("Video jobs", data["jobs"]["video"]["count"]),
            ("Automations", data["automations"]["count"]),
            ("Configured providers", data["providers"]["configured_count"]),
        ):
            print(f"{label:22} {value}")
        return
    if isinstance(data, list):
        if not data:
            print("No records yet.")
            return
        for row in data[:20]:
            if isinstance(row, dict):
                print(" - " + " | ".join(f"{k}={short(str(row.get(k, '')))}" for k in ("id", "name", "title", "skill_name", "slug", "provider", "platform", "status", "action_type") if k in row))
            else:
                print(f" - {row}")
        return
    if isinstance(data, dict) and data.get("campaign_name"):
        print(f"Campaign:          {data.get('campaign_name')}")
        print(f"ID:                {data.get('id')}")
        print(f"Workspace:         {data.get('workspace_name')}")
        print(f"Platforms:         {', '.join(data.get('platforms_json', []))}")
        print(f"Content items:     {len(data.get('content_items_json', []))}")
        print("Saved to SQLite and workspace outputs.")
        return
    if isinstance(data, dict) and data.get("agent_slug") and data.get("result"):
        print(f"Agent:             {data.get('agent_slug')}")
        print(f"Run ID:            {data.get('id')}")
        print(f"Status:            {data.get('status')}")
        print(f"Draft count:       {data.get('result', {}).get('draft_count', '-')}")
        ai = data.get("result", {}).get("ai_enhancement")
        if ai:
            print(f"AI enhancement:    {ai.get('status')} via {ai.get('provider')} ({ai.get('model')})")
        print(f"Report:            {data.get('output_path', '-')}")
        return
    if isinstance(data, dict) and {"provider", "model", "fallback_used"} <= set(data.keys()):
        print(f"Provider:          {data.get('provider')}")
        print(f"Model:             {data.get('model') or '-'}")
        print(f"Status:            {data.get('status')}")
        print(f"Fallback used:     {data.get('fallback_used')}")
        if data.get("fallback_provider"):
            print(f"Fallback provider: {data.get('fallback_provider')}")
        if data.get("text"):
            print("\nGenerated text:")
            print(data.get("text"))
        if data.get("error"):
            print(f"Setup/Error:       {data.get('error')}")
        return
    if isinstance(data, dict) and data.get("provider") and data.get("prompt"):
        print(f"Job ID:            {data.get('id')}")
        print(f"Provider:          {data.get('provider')}")
        print(f"Status:            {data.get('status')}")
        print(f"Mode:              {data.get('generation_mode', '-')}")
        print(f"Render type:       {data.get('render_type', '-')}")
        print(f"Prompt:            {short(data.get('prompt', ''), 80)}")
        print(f"Output:            {data.get('output_path') or '-'}")
        print(f"Package:           {data.get('output_package_path') or '-'}")
        return
    if isinstance(data, dict) and data.get("action_type") and data.get("preview"):
        preview = data.get("preview", {})
        metadata = preview.get("metadata", {})
        print(f"Approval ID:       {data.get('id')}")
        print(f"Status:            {data.get('status')}")
        print(f"Action:            {data.get('action_type')}")
        print(f"Platform:          {data.get('connector_id')}")
        print(f"Campaign:          {metadata.get('campaign_name', '-')}")
        print(f"Agent:             {metadata.get('agent_slug', '-')}")
        print(f"Preview:           {short(preview.get('text') or preview.get('body') or '', 100)}")
        return
    print(json.dumps(data, indent=2, sort_keys=True))


def print_examples(area: str) -> None:
    examples = EXAMPLES.get(area)
    if not examples:
        return
    print("\nExamples:")
    for example in examples:
        print(f"  {example}")


def parse_cli_options(tokens: list[str]) -> tuple[str, dict[str, str]]:
    prompt_parts: list[str] = []
    options: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
                options[key] = tokens[index + 1]
                index += 2
            else:
                options[key] = "true"
                index += 1
        else:
            prompt_parts.append(token)
            index += 1
    return " ".join(prompt_parts), options


def parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def render_error(message: str) -> None:
    if HAS_RICH:
        console.print(Panel(message, title="Liuant Error", border_style="red"))
    else:
        print(f"Liuant error: {message}", file=sys.stderr)


def short(value: str, limit: int = 44) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "..."


if __name__ == "__main__":
    main()
