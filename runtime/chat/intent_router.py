from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runtime.config import SettingsManager, SkillManager
from runtime.connectors.manager import ConnectorManager
from runtime.memory import MemoryManager
from runtime.knowledge import KnowledgeBase
from runtime.providers import ModelHub
from runtime.automation import AutomationManager
from runtime.agents import AgentProfileManager
from runtime.security import SecretManager
from runtime.release import ReleaseManager

INTENT_PATTERNS: dict[str, list[str]] = {
    "provider_setup": [
        r"(set|use|configure|add|enable|switch|change)\s+.*(model|provider|llm|ai|api\s*key)",
        r"(kimi|openai|openrouter|ollama|anthropic|groq|claude|gemini|deepseek|mistral|replicate)",
        r"default\s+(model|provider)",
        r"api\s*key\s+for",
        r"connect\s+(provider|model)",
        r"show\s+(providers|models)",
        r"list\s+(providers|models)",
    ],
    "connector_setup": [
        r"connect\s+(gmail|telegram|linkedin|x|twitter|whatsapp|slack|discord)",
        r"(gmail|telegram|linkedin|x|twitter)\s+(setup|configure|oauth|connect)",
        r"add\s+(gmail|telegram|linkedin|x|twitter)\s+(connector|account|integration)",
    ],
    "agent_create": [
        r"create\s+(a|an|the)?\s*(new)?\s*(agent|assistant|bot|helper)",
        r"(make|build|create)\s+(a|an)?\s*(marketing|sales|support|front.?desk|coding|content|writing|research|data|social|email|telegram|customer).*(agent|assistant|bot)",
        r"new\s+agent\s+(called|named|for)",
    ],
    "agent_update": [
        r"(update|edit|change|modify|disable|enable|deactivate)\s+(agent|assistant|bot)\s",
        r"(update|edit|change)\s+.*(instructions|system.?prompt|tools|provider|model)",
    ],
    "automation_create": [
        r"every\s+(day|morning|evening|night|monday|tuesday|wednesday|thursday|friday|saturday|sunday|hour|minute|week|month)",
        r"daily\s+(at|at\s+\d)",
        r"(create|set|schedule|make)\s+(a|an)?\s*(automation|schedule|recurring|routine|task)",
        r"(automatically|auto)\s+(do|run|create|send|check|summarize|draft)",
        r"at\s+\d{1,2}(:\d{2})?\s*(am|pm)?",
    ],
    "skill_install": [
        r"(install|add|enable|activate)\s+(skill|plugin|extension|capability)",
        r"show\s+(skills|available\s+skills|capabilities)",
        r"available\s+(skills|plugins|extensions)",
        r"install\s+.*(video|image|content|campaign|marketing|social|email|telegram|coding|debug)",
    ],
    "memory_add": [
        r"remember\s+(that|this|my|the|our)",
        r"save\s+(this|that|my)\s+(in\s+)?(memory|notes|context)",
        r"store\s+(this\s+)?(information|detail|fact|note|preference)",
    ],
    "knowledge_search": [
        r"(search|find|look\s+up|query)\s+(my\s+)?(knowledge|notes|docs|database|kb)",
        r"(what|who|when|where|why|how)\s+(is|are|was|were|does|do|did|can|could|would|should)",
        r"index\s+(this|a|the)\s+(file|document|note|page)",
    ],
    "system_status": [
        r"(show|check|what'?s?|status|health)\s+(system|status|health|dashboard|overview)",
        r"what\s+can\s+you\s+do",
        r"help|commands|intents",
        r"(how|what)\s+(is|are)\s+(my|the)\s+(current|active|configured)",
    ],
    "approval_action": [
        r"(approve|confirm|accept|yes|go\s+ahead)\s+(draft|action|approval|pending)",
        r"(reject|deny|cancel|no|decline)\s+(draft|action|approval|pending)",
        r"show\s+(pending|approvals|drafts)",
        r"(pending|review)\s+(approvals|drafts|actions)",
    ],
    "release_status": [
        r"(release|build|package|dmg|artifact|signing|notarize|version)",
        r"(macos|windows|linux)\s+(build|package|installer)",
        r"app\s+version",
    ],
}

INTENT_DESCRIPTIONS: dict[str, str] = {
    "provider_setup": "Configure AI models and providers (API keys, default models, fallback providers)",
    "connector_setup": "Connect external services (Gmail, Telegram, LinkedIn, X/Twitter)",
    "agent_create": "Create new AI agents for specific roles (marketing, support, coding, etc.)",
    "agent_update": "Update existing agent settings (instructions, tools, provider)",
    "automation_create": "Create recurring automated tasks (daily summaries, weekly reports, etc.)",
    "skill_install": "Install or enable skills and capabilities",
    "memory_add": "Save information to memory for future context",
    "knowledge_search": "Search knowledge base or index new documents",
    "system_status": "Show system health, providers, connectors, and configuration",
    "approval_action": "Review, approve, or reject pending actions and drafts",
    "release_status": "Check desktop app release, build, and signing status",
    "unknown": "I'm not sure what you want to do. Try asking about providers, agents, automations, or connectors.",
}

REQUIRED_FIELDS: dict[str, list[dict[str, str]]] = {
    "provider_setup": [
        {"field": "provider", "question": "Which provider do you want to configure?", "options": ["openai", "openrouter", "ollama", "kimi", "anthropic", "groq", "replicate"]},
        {"field": "api_key", "question": "Paste your API key. It will be stored securely and never shown again.", "secret": True},
        {"field": "default_model", "question": "What default model should this provider use?", "optional": True},
    ],
    "connector_setup": [
        {"field": "connector", "question": "Which connector do you want to connect?", "options": ["gmail", "telegram", "linkedin", "x"]},
        {"field": "credentials", "question": "Provide the required credentials. For OAuth connectors, I'll guide you through the browser flow.", "secret": True},
    ],
    "agent_create": [
        {"field": "name", "question": "What should the agent be called?"},
        {"field": "role", "question": "What role will this agent perform?"},
        {"field": "instructions", "question": "What instructions should the agent follow?", "optional": True},
    ],
    "automation_create": [
        {"field": "name", "question": "What should this automation be called?"},
        {"field": "schedule", "question": "How often should it run? (e.g., daily at 9am, every Monday)"},
        {"field": "task", "question": "What should the automation do?"},
    ],
}


def route_chat_message(message: str, user_context: dict[str, Any] | None = None) -> dict[str, Any]:
    message_lower = message.lower().strip()
    intent, confidence = _detect_intent(message_lower)
    handler = _INTENT_HANDLERS.get(intent)
    if handler:
        return handler(message, user_context or {})
    return _unknown_response()


def _detect_intent(message: str) -> tuple[str, float]:
    best_intent = "unknown"
    best_confidence = 0.0
    for intent, patterns in INTENT_PATTERNS.items():
        matches = sum(1 for p in patterns if re.search(p, message))
        if matches > 0:
            confidence = min(0.95, 0.4 + matches * 0.15)
            if confidence > best_confidence:
                best_confidence = confidence
                best_intent = intent
    return best_intent, best_confidence


def _provider_setup_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    providers = ModelHub().get_status()
    configured = [p["id"] for p in providers.get("providers", []) if p.get("status") in ("configured", "reachable")]
    available_providers = [p["id"] for p in providers.get("providers", [])]
    return {
        "intent": "provider_setup",
        "confidence": 0.85,
        "status": "preview",
        "message": _format_provider_status(providers, configured, available_providers),
        "data": {
            "configured_providers": configured,
            "available_providers": available_providers,
            "default_provider": providers.get("default_provider"),
        },
        "required_fields": [],
        "preview": {"type": "provider_list", "providers": configured, "available": available_providers},
        "actions": ["show_providers"],
        "next_questions": [
            "To configure a provider, tell me which one (e.g., 'set openai as default')",
            "To add an API key: 'add API key for openai'",
        ],
    }


def _format_provider_status(providers: dict[str, Any], configured: list[str], available: list[str]) -> str:
    lines = ["## Provider Status\n"]
    lines.append(f"**Default provider:** {providers.get('default_provider', 'none')}\n")
    if configured:
        lines.append(f"**Configured:** {', '.join(configured)}\n")
    else:
        lines.append("**No providers configured yet.**\n")
    lines.append(f"\n**Available providers:** {', '.join(available)}\n")
    lines.append("\nSay 'set <provider> as default' or 'add API key for <provider>' to configure one.")
    return "".join(lines)


def _connector_setup_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    manager = ConnectorManager()
    connectors = manager.list()
    connected = [c["provider"] for c in connectors if c.get("status") in ("connected", "configured")]
    available = ["gmail", "telegram", "linkedin", "x"]
    detected = _extract_connector(message)
    return {
        "intent": "connector_setup",
        "confidence": 0.85,
        "status": "preview",
        "message": _format_connector_status(connected, available, detected),
        "data": {"connected": connected, "available": available, "detected": detected},
        "required_fields": _connector_fields(detected),
        "preview": {"type": "connector_list", "connected": connected},
        "actions": ["show_connectors"],
        "next_questions": _connector_next_questions(detected, connected),
    }


def _format_connector_status(connected: list[str], available: list[str], detected: str | None) -> str:
    lines = ["## Connector Status\n"]
    if connected:
        lines.append(f"**Connected:** {', '.join(connected)}\n")
    else:
        lines.append("**No connectors configured yet.**\n")
    lines.append(f"\n**Available:** {', '.join(available)}\n")
    if detected:
        if detected in connected:
            lines.append(f"\n{detected.title()} is already connected.\n")
        else:
            lines.append(f"\nTo connect {detected.title()}, I'll need some credentials.\n")
    else:
        lines.append("\nSay 'connect Gmail' or 'connect Telegram' to get started.")
    return "".join(lines)


def _extract_connector(message: str) -> str | None:
    for name in ["gmail", "telegram", "linkedin", "x", "twitter"]:
        if name in message:
            return "x" if name == "twitter" else name
    return None


def _connector_fields(detected: str | None) -> list[dict[str, str]]:
    if not detected:
        return []
    if detected == "gmail":
        return [
            {"field": "google_client_id", "question": "Paste your Google Client ID. It will be stored securely.", "secret": True},
            {"field": "google_client_secret", "question": "Paste your Google Client Secret. It will be stored securely.", "secret": True},
        ]
    if detected == "telegram":
        return [
            {"field": "bot_token", "question": "Paste your Telegram Bot Token from BotFather. It will be stored securely.", "secret": True},
        ]
    if detected in ("linkedin", "x"):
        return [
            {"field": "client_id", "question": f"Paste your {detected.title()} Client ID.", "secret": True},
            {"field": "client_secret", "question": f"Paste your {detected.title()} Client Secret.", "secret": True},
        ]
    return []


def _connector_next_questions(detected: str | None, connected: list[str]) -> list[str]:
    if detected and detected not in connected:
        return [f"Provide the required credentials for {detected.title()}"]
    if not connected:
        return ["Connect Gmail", "Connect Telegram", "Connect LinkedIn"]
    return []


def _agent_create_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    profiles = AgentProfileManager()
    existing = profiles.list()
    existing_names = [a.get("name", a.get("slug", "")) for a in existing]
    detected_role = _extract_agent_role(message)
    return {
        "intent": "agent_create",
        "confidence": 0.85,
        "status": "needs_input",
        "message": _format_agent_create_message(detected_role, existing_names),
        "data": {"existing_agents": existing_names, "detected_role": detected_role},
        "required_fields": REQUIRED_FIELDS["agent_create"],
        "preview": {"type": "agent_create", "role": detected_role},
        "actions": [],
        "next_questions": ["What should I call the agent?", f"What instructions should the {detected_role or 'new'} agent follow?"],
    }


def _extract_agent_role(message: str) -> str | None:
    roles = ["marketing", "sales", "support", "front desk", "coding", "content", "writing", "research", "data", "social", "email", "telegram", "customer"]
    for role in roles:
        if role in message:
            return role
    return None


def _format_agent_create_message(role: str | None, existing: list[str]) -> str:
    lines = ["## Create Agent\n"]
    if role:
        lines.append(f"I can create a **{role.title()} Agent** for you.\n")
    else:
        lines.append("I can create a custom agent for you.\n")
    if existing:
        lines.append(f"\n**Existing agents:** {', '.join(existing[:5])}\n")
    lines.append("\nTo get started, tell me the agent's name and what it should do.")
    return "".join(lines)


def _agent_update_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": "agent_update",
        "confidence": 0.7,
        "status": "needs_input",
        "message": "Which agent would you like to update, and what should I change?",
        "data": {},
        "required_fields": [{"field": "agent_name", "question": "Which agent do you want to update?"}],
        "preview": {"type": "agent_update"},
        "actions": [],
        "next_questions": ["Show me my agents first", "Update instructions for..."],
    }


def _automation_create_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    schedule = _extract_schedule(message)
    task = _extract_task(message)
    return {
        "intent": "automation_create",
        "confidence": 0.8,
        "status": "needs_input",
        "message": _format_automation_message(schedule, task),
        "data": {"detected_schedule": schedule, "detected_task": task},
        "required_fields": REQUIRED_FIELDS["automation_create"] if not (schedule and task) else [],
        "preview": {"type": "automation_create", "schedule": schedule, "task": task},
        "actions": [],
        "next_questions": ["What should I name this automation?", "Confirm and create this automation"],
    }


def _extract_schedule(message: str) -> str | None:
    patterns = [
        (r"every\s+(morning|evening|night)", r"daily at \1"),
        (r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", r"weekly on \1"),
        (r"daily\s+at\s+(\d{1,2}(:\d{2})?\s*(am|pm)?)", r"daily at \1"),
        (r"every\s+(\d+)\s+(hour|minute|day|week|month)", r"every \1 \2"),
    ]
    for pattern, replacement in patterns:
        match = re.search(pattern, message)
        if match:
            return re.sub(pattern, replacement, message, count=1)
    return None


def _extract_task(message: str) -> str | None:
    action_patterns = [
        r"(summarize|create|draft|send|check|run|generate|review|analyze|report)\s+(.*)",
        r"(gmail|email|telegram|social|content|report|task|post)\s+(summar|draft|creat|check|run)",
    ]
    for pattern in action_patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(0)[:100]
    return None


def _format_automation_message(schedule: str | None, task: str | None) -> str:
    lines = ["## Create Automation\n"]
    if schedule:
        lines.append(f"**Schedule:** {schedule}\n")
    if task:
        lines.append(f"**Task:** {task}\n")
    if schedule and task:
        lines.append("\nI'll need a name and to confirm before creating.")
    else:
        lines.append("Tell me the schedule (e.g., 'every morning at 9am') and what to do.\n")
    lines.append("\n**Safety:** I'll never auto-send emails or publish social posts without your approval.")
    return "".join(lines)


def _skill_install_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    manager = SkillManager()
    available = manager.available_skills()
    installed = manager.list()
    installed_names = [s["skill_name"] for s in installed]
    lines = ["## Skills\n"]
    lines.append(f"\n**Installed:** {', '.join(installed_names) if installed_names else 'none'}\n")
    lines.append("\n**Available skills:**\n")
    for skill in available[:10]:
        status = "✅" if skill["skill_name"] in installed_names else "⬜"
        lines.append(f"- {status} **{skill['title']}**: {skill['description']}\n")
    if len(available) > 10:
        lines.append(f"\n... and {len(available) - 10} more\n")
    lines.append("\nSay 'install [skill name]' to add a skill.")
    return {
        "intent": "skill_install",
        "confidence": 0.8,
        "status": "preview",
        "message": "".join(lines),
        "data": {"installed": installed_names, "available_count": len(available)},
        "required_fields": [],
        "preview": {"type": "skill_list", "available": [s["skill_name"] for s in available[:10]]},
        "actions": ["show_skills"],
        "next_questions": [f"Install {s['skill_name']}" for s in available[:3] if s["skill_name"] not in installed_names],
    }


def _memory_add_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    content = _extract_memory_content(message)
    if content:
        manager = MemoryManager()
        result = manager.add(content, memory_type="user")
        return {
            "intent": "memory_add",
            "confidence": 0.9,
            "status": "completed",
            "message": f"Saved to memory: _{content}_\n\nI'll remember this for future context.",
            "data": {"content": content, "memory_id": result.get("id")},
            "required_fields": [],
            "preview": {"type": "memory_add", "content": content},
            "actions": ["memory_saved"],
            "next_questions": ["What else should I remember?", "Search my knowledge base"],
        }
    return {
        "intent": "memory_add",
        "confidence": 0.7,
        "status": "needs_input",
        "message": "What would you like me to remember?",
        "data": {},
        "required_fields": [{"field": "content", "question": "What should I remember?"}],
        "preview": {"type": "memory_add"},
        "actions": [],
        "next_questions": [],
    }


def _extract_memory_content(message: str) -> str | None:
    for prefix in ["remember that ", "remember this: ", "remember: ", "remember ", "save this: ", "store this: "]:
        if message.startswith(prefix):
            return message[len(prefix):].strip().capitalize()
    return None


def _knowledge_search_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    query = _extract_search_query(message)
    if query:
        kb = KnowledgeBase()
        search_result = kb.search(query, limit=5)
        results = search_result.get("results", [])
        lines = ["## Knowledge Search Results\n"]
        if results:
            for r in results:
                title = r.get("title", r.get("source", "untitled")) if isinstance(r, dict) else "result"
                snippet = str(r.get("content", "") if isinstance(r, dict) else r)[:120]
                lines.append(f"- **{title}**: {snippet}...\n")
        else:
            lines.append("No results found.\n")
            lines.append("\nTry indexing a file or adding text to the knowledge base.")
        return {
            "intent": "knowledge_search",
            "confidence": 0.85,
            "status": "completed" if results else "empty",
            "message": "".join(lines),
            "data": {"query": query, "results_count": len(results)},
            "required_fields": [],
            "preview": {"type": "knowledge_results", "query": query, "count": len(results)},
            "actions": [],
            "next_questions": ["Index a file", "Add text: Liuant Agentic OS is..."] if not results else [],
        }
    return {
        "intent": "knowledge_search",
        "confidence": 0.7,
        "status": "needs_input",
        "message": "What would you like to search for in your knowledge base?",
        "data": {},
        "required_fields": [{"field": "query", "question": "What are you looking for?"}],
        "preview": {"type": "knowledge_search"},
        "actions": [],
        "next_questions": [],
    }


def _extract_search_query(message: str) -> str | None:
    for prefix in ["search ", "find ", "look up ", "query "]:
        if message.startswith(prefix):
            return message[len(prefix):].strip()
    return None


def _system_status_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    release = ReleaseManager()
    version = release.version()
    dashboard = __import__("runtime.dashboard", fromlist=["build_status"]).build_status()
    providers = ModelHub().get_status()
    settings = {row["key"]: row["value"] for row in SettingsManager().list()}
    connector_manager = ConnectorManager()
    connectors = connector_manager.list()
    connected_connectors = [c["provider"] for c in connectors if c.get("status") in ("connected", "configured")]
    agent_profiles = AgentProfileManager().list()
    automation_manager = AutomationManager()
    automations = automation_manager.list()

    lines = ["## Liuant Agentic OS\n"]
    lines.append(f"**Version:** {version.get('app_version')}\n")
    lines.append(f"**Backend Mode:** {settings.get('desktop_backend_mode', 'external_backend')}\n")
    lines.append(f"**Default Provider:** {settings.get('default_provider', 'none')}\n")
    lines.append(f"**Default Model:** {settings.get('default_model', 'none')}\n")
    lines.append(f"**Local Auth:** {'enabled' if settings.get('local_auth_enabled') == 'true' else 'disabled'}\n")
    lines.append(f"\n**Providers:** {providers.get('configured_count', 0)} configured, {providers.get('provider_count', 0)} available\n")
    lines.append(f"**Connectors:** {', '.join(connected_connectors) if connected_connectors else 'none configured'}\n")
    lines.append(f"**Agents:** {len(agent_profiles)} configured\n")
    lines.append(f"**Automations:** {len(automations)}\n")
    lines.append(f"**Pending Approvals:** {dashboard.get('approvals', {}).get('pending', 0)}\n")
    lines.append(f"\n**Connectors available:** gmail, telegram, linkedin, x\n")
    lines.append("\nSay what you'd like to configure. I can help with providers, connectors, agents, automations, or skills.")

    return {
        "intent": "system_status",
        "confidence": 0.95,
        "status": "completed",
        "message": "".join(lines),
        "data": {
            "version": version.get("app_version"),
            "providers_configured": providers.get("configured_count", 0),
            "connectors_connected": connected_connectors,
            "agents_count": len(agent_profiles),
            "automations_count": len(automations),
            "pending_approvals": dashboard.get("approvals", {}).get("pending", 0),
        },
        "required_fields": [],
        "preview": {"type": "system_status", "version": version.get("app_version")},
        "actions": ["show_status"],
        "next_questions": [
            "Configure a provider",
            "Connect Gmail",
            "Create an agent",
            "Create an automation",
        ],
    }


def _approval_action_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from runtime.approvals import ApprovalManager
    manager = ApprovalManager()
    pending = manager.list()
    lines = ["## Pending Approvals\n"]
    if pending:
        for item in pending[:5]:
            lines.append(f"- **{item.get('action_type', 'Action')}** from {item.get('connector_id', 'unknown')}: {str(item.get('preview', {}))[:80]}...\n")
        lines.append("\nSay 'approve [id]' or 'reject [id]' to decide.")
    else:
        lines.append("No pending approvals. Everything is up to date.\n")
    return {
        "intent": "approval_action",
        "confidence": 0.8,
        "status": "preview",
        "message": "".join(lines),
        "data": {"pending_count": len(pending)},
        "required_fields": [],
        "preview": {"type": "approval_list", "pending": len(pending)},
        "actions": ["show_approvals"],
        "next_questions": ["Approve latest", "Reject latest"] if pending else [],
    }


def _release_status_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    release = ReleaseManager()
    version = release.version()
    signing = release.signing_status()
    report = release.release_desktop_report()
    lines = ["## Release Status\n"]
    lines.append(f"**Version:** {version.get('app_version')}\n")
    lines.append(f"**Channel:** {version.get('channel')}\n")
    lines.append(f"**Platform:** {version.get('platform')}\n")
    lines.append(f"**Signed:** {signing.get('signed')}\n")
    lines.append(f"**Notarized:** {signing.get('notarized')}\n")
    lines.append(f"**Frontend Build:** {report.get('frontend_build_status')}\n")
    lines.append(f"**Native Build:** {report.get('native_build_status')}\n")
    lines.append("\nRun `./liuant release macos-qa` for DMG verification or `./liuant signing status` for signing details.")
    return {
        "intent": "release_status",
        "confidence": 0.9,
        "status": "completed",
        "message": "".join(lines),
        "data": {"version": version.get("app_version"), "signed": signing.get("signed"), "notarized": signing.get("notarized")},
        "required_fields": [],
        "preview": {"type": "release_status", "version": version.get("app_version")},
        "actions": ["show_release"],
        "next_questions": [],
    }


def _unknown_response() -> dict[str, Any]:
    return {
        "intent": "unknown",
        "confidence": 0.0,
        "status": "needs_input",
        "message": "I'm not sure what you'd like to do. Here's what I can help with:\n\n"
        "- **Providers**: 'show providers', 'set openai as default'\n"
        "- **Connectors**: 'connect Gmail', 'connect Telegram'\n"
        "- **Agents**: 'create a marketing agent'\n"
        "- **Automations**: 'every morning summarize Gmail'\n"
        "- **Skills**: 'show available skills'\n"
        "- **Memory**: 'remember my company is Liuant'\n"
        "- **Knowledge**: 'search my knowledge base'\n"
        "- **Status**: 'show system status'",
        "data": {},
        "required_fields": [],
        "preview": {"type": "help"},
        "actions": [],
        "next_questions": [
            "Show system status",
            "Create a marketing agent",
            "Connect Gmail",
            "Every morning create a task list",
        ],
    }


_INTENT_HANDLERS = {
    "provider_setup": _provider_setup_handler,
    "connector_setup": _connector_setup_handler,
    "agent_create": _agent_create_handler,
    "agent_update": _agent_update_handler,
    "automation_create": _automation_create_handler,
    "skill_install": _skill_install_handler,
    "memory_add": _memory_add_handler,
    "knowledge_search": _knowledge_search_handler,
    "system_status": _system_status_handler,
    "approval_action": _approval_action_handler,
    "release_status": _release_status_handler,
}


def execute_intent_action(intent: str, action: str, data: dict[str, Any]) -> dict[str, Any]:
    if intent == "provider_setup" and action == "set_default":
        provider = data.get("provider")
        if provider:
            try:
                hub = ModelHub()
                provider_data = hub.set_default_provider("text", provider)
                return {"status": "completed", "message": f"Default text provider set to **{provider}**.", "data": provider_data}
            except Exception as e:
                return {"status": "error", "message": f"Could not set provider: {e}"}
        return {"status": "error", "message": "No provider specified."}

    if intent == "connector_setup" and action == "create_connector":
        connector = data.get("connector")
        if connector:
            try:
                cm = ConnectorManager()
                ct = "email" if connector in ("gmail",) else "messaging" if connector in ("telegram",) else "social"
                result = cm.create(connector_type=ct, provider=connector, display_name=connector)
                return {"status": "completed", "message": f"{connector.title()} connector created. Configure OAuth via Settings > Connectors.", "data": result}
            except Exception as e:
                return {"status": "error", "message": f"Could not create connector: {e}"}
        return {"status": "error", "message": "No connector specified."}

    if intent == "agent_create" and action == "create_agent":
        name = data.get("name", "")
        instructions = data.get("instructions", "")
        if name:
            try:
                apm = AgentProfileManager()
                result = apm.create({"name": name, "instructions": instructions or f"Custom agent for {name}", "slug": name.lower().replace(" ", "-")})
                return {"status": "completed", "message": f"Agent **{name}** created! You can find it in Settings > Agents.", "data": result}
            except Exception as e:
                return {"status": "error", "message": f"Could not create agent: {e}"}
        return {"status": "error", "message": "Agent name is required."}

    if intent == "automation_create" and action == "create_automation":
        name = data.get("name", "")
        schedule = data.get("schedule", "")
        task = data.get("task", "")
        if name and schedule:
            try:
                am = AutomationManager()
                schedule_map = {
                    "daily": {"trigger_type": "schedule", "schedule_text": f"0 9 * * *" if "morning" in schedule.lower() else "0 9 * * *"},
                }
                result = am.create({
                    "name": name,
                    "agent_slug": "personal-assistant-agent",
                    "trigger_type": "schedule",
                    "schedule_text": schedule,
                    "task_prompt": task or f"Run {name} automation",
                })
                return {"status": "completed", "message": f"Automation **{name}** created! Schedule: {schedule}. Review in Settings > Automations.", "data": result}
            except Exception as e:
                return {"status": "error", "message": f"Could not create automation: {e}"}
        return {"status": "error", "message": "Name and schedule are required."}

    if intent == "skill_install" and action == "install_skill":
        skill = data.get("skill", "")
        if skill:
            try:
                sm = SkillManager()
                result = sm.install(skill)
                return {"status": "completed", "message": f"Skill **{skill}** installed! Enable it in Settings > Skills.", "data": result}
            except Exception as e:
                return {"status": "error", "message": f"Could not install skill: {e}"}
        return {"status": "error", "message": "No skill specified."}

    if intent == "memory_add" and action == "save_memory":
        content = data.get("content", "")
        if content:
            try:
                mm = MemoryManager()
                result = mm.add(content, memory_type="user")
                return {"status": "completed", "message": f"Saved to memory: _{content}_", "data": result}
            except Exception as e:
                return {"status": "error", "message": f"Could not save: {e}"}
        return {"status": "error", "message": "No content to remember."}

    return {"status": "error", "message": f"Unknown action: {action} for intent: {intent}"}
