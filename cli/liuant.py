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
    "release": ["liuant release manifest", "liuant release checksum", "liuant release artifacts", "liuant release unsigned-artifacts", "liuant release unsigned-build-check", "liuant release verify-artifacts", "liuant release desktop-report", "liuant release build-report", "liuant release macos-qa", "liuant release polish-check", "liuant release candidate-check"],
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
        return {"commands": ["manifest", "checksum", "artifacts", "unsigned-artifacts", "verify-artifacts", "notes", "desktop-report", "build-report", "unsigned-build-check", "macos-qa", "polish-check", "candidate-check"]}
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
            return runner.run(agent_slug, prompt, options.get("ai") == "true", options.get("provider"), options.get("model"), options.get("rag") == "true", options.get("workspace"), options.get("rag_query"), parse_int(options.get("rag_limit"), 0) or None)
        if command == "runs":
            return runner.list_runs()
        if command == "export" and rest:
            return {"output_path": export_agent_run_markdown(rest[0])}
        return {"commands": ["list", "show <slug>", "create <name>", "update <slug> <instructions>", "disable <slug>", "enable <slug>", "run <agent_slug> <prompt>", "runs", "export <run_id>"]}
    if args.area == "models":
        manager = ModelManager()
        if command == "list":
            return manager.list()
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
        return {"commands": ["list", "setup", "test", "status", "set-default <provider>", "set-fallback <provider> <model>"]}
    if args.area == "providers":
        hub = ModelHub()
        if command == "categories":
            return hub.list_categories()
        if command == "list":
            _, options = parse_cli_options(rest)
            return hub.list_providers(options.get("category"))
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
        return {"commands": ["categories", "list --category <category>", "status", "show <provider>", "test <provider>", "enable <provider>", "disable <provider>", "set-default <category> <provider>", "set-model <category> <model>", "set-fallback <category> <provider>"]}
    if args.area == "text":
        hub = ModelHub()
        if command == "providers":
            return hub.list_providers("text")
        if command == "test" and rest:
            return hub.test_provider(rest[0])
        if command == "generate":
            prompt, options = parse_cli_options(rest)
            return hub.generate_text(
                prompt=prompt,
                system_prompt=options.get("system_prompt"),
                provider_name=options.get("provider"),
                model=options.get("model"),
                temperature=float(options.get("temperature", "0.7")),
                max_tokens=parse_int(options.get("max_tokens"), 0) or None,
            )
        return {"commands": ["providers", "test <provider_name>", "generate <prompt> --provider <provider> --model <model>"]}
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
        manager = SkillManager()
        if command == "available":
            return manager.available_skills()
        if command == "list":
            return manager.list()
        if command == "install" and rest:
            return manager.install(rest[0])
        if command == "enable" and rest:
            return manager.set_enabled(rest[0], True)
        if command == "disable" and rest:
            return manager.set_enabled(rest[0], False)
        if command == "uninstall" and rest:
            return manager.uninstall(rest[0])
        return {"commands": ["available", "list", "install <skill_name>", "enable <skill_name>", "disable <skill_name>", "uninstall <skill_name>"]}
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
