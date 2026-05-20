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
    "skill_pack_list": [
        r"list\s+(skill\s*packs|installed\s*packs|imported\s*packs)",
        r"show\s+(skill\s*packs|my\s*packs|installed\s*packs)",
        r"what\s+(skill\s*packs|packs)\s+(do\s+i\s*have|are\s*installed)",
    ],
    "skill_pack_inspect": [
        r"inspect\s+(skill\s*pack|pack)\s",
        r"show\s+details\s+(for|about)\s+(skill\s*pack|pack)\s",
        r"what'?s?\s+(in|inside)\s+(the\s*)?(skill\s*pack|pack)\s",
    ],
    "skill_pack_validate": [
        r"validate\s+(skill\s*pack|pack)\s",
        r"check\s+(skill\s*pack|pack)\s+(validity|integrity|checksums)",
        r"verify\s+(skill\s*pack|pack)\s",
    ],
    "skill_pack_import": [
        r"import\s+(skill\s*pack|pack)\s",
        r"load\s+(skill\s*pack|pack)\s",
        r"bring\s+in\s+(skill\s*pack|pack)\s",
    ],
    "skill_pack_install": [
        r"install\s+(skill\s*pack|pack)\s",
        r"set\s+up\s+(skill\s*pack|pack)\s",
        r"add\s+(skill\s*pack|pack)\s",
    ],
    "skill_pack_remove": [
        r"remove\s+(skill\s*pack|pack)\s",
        r"delete\s+(skill\s*pack|pack)\s",
        r"uninstall\s+(skill\s*pack|pack)\s",
    ],
    "skill_catalog_search": [
        r"search\s+(catalog|skill\s*catalog)\s",
        r"find\s+(skills?|packs?)\s+(in\s+)?(catalog|library)",
        r"browse\s+(catalog|skill\s*catalog|available\s*packs)",
    ],
    "skill_catalog_install": [
        r"install\s+.*\s+from\s+(catalog|library)",
        r"get\s+.*\s+from\s+(catalog|skill\s*catalog)",
        r"catalog\s+install\s",
    ],
    "skill_pack_upgrade": [
        r"upgrade\s+(skill\s*pack|pack)\s",
        r"update\s+(skill\s*pack|pack)\s",
        r"show\s+upgrade\s+(plan|for)\s",
    ],
    "skill_pack_diff": [
        r"(diff|compare)\s+(skill\s*pack|pack)s?\s",
        r"compare\s+old\s+and\s+new\s",
        r"show\s+diff\s+(for|between)\s",
    ],
    "skill_pack_dependencies": [
        r"(check|show|list)\s+(dependencies|deps)\s+(for|of)\s",
        r"what\s+does\s+.*\s+depend\s+on",
        r"dependency\s+(check|plan|list)\s",
    ],
    "skill_pack_verify_signature": [
        r"verify\s+(signature|signing)\s+(for|of)\s",
        r"check\s+(signature|signing)\s+(for|of)\s",
        r"is\s+(this|the)\s+pack\s+(signed|verified)",
    ],
    "skill_pack_sign": [
        r"sign\s+(skill\s*pack|pack)\s",
        r"create\s+signature\s+(for|of)\s",
        r"sign\s+this\s+pack",
    ],
    "skill_pack_trust_status": [
        r"(is|check)\s+(this|the)\s+pack\s+(trusted|trust)",
        r"trust\s+status\s+(for|of)\s",
        r"who\s+(signed|created)\s+this\s+pack",
    ],
    "skill_pack_encode": [
        r"encode\s+(pack|skill\s*pack)\s+(as\s+)?base64",
        r"export\s+.*\s+as\s+base64",
        r"convert\s+pack\s+to\s+base64",
    ],
    "skill_pack_decode": [
        r"decode\s+base64\s+(pack|skill\s*pack)",
        r"import\s+from\s+base64",
        r"decode\s+this\s+pack",
    ],
    "skill_pack_analytics": [
        r"(show|get)\s+(pack|skill\s*pack)\s+analytics",
        r"pack\s+usage\s+(stats|statistics|analytics)",
        r"how\s+many\s+times\s+.*\s+(pack|installed|imported)",
    ],
    "workflow_list": [
        r"list\s+(workflows|workflow\s*templates)",
        r"show\s+(workflows|available\s+workflows)",
        r"what\s+workflows\s+(are\s+available|do\s+i\s+have)",
    ],
    "workflow_validate": [
        r"validate\s+workflow\b",
        r"check\s+workflow\s+(validity|syntax)",
        r"verify\s+workflow\b",
    ],
    "workflow_run": [
        r"run\s+workflow\b",
        r"execute\s+workflow\b",
        r"start\s+workflow\b",
    ],
    "workflow_preview": [
        r"preview\s+.*workflow",
        r"preview\s+(the\s+)?workflow",
        r"what\s+will\s+.*workflow\s+do",
        r"show\s+workflow\s+preview",
    ],
    "workflow_permissions": [
        r"what\s+permissions\s+.*workflow\s+need",
        r"what\s+permissions\s+(does|do)\s+(this|the)\s+workflow\s+need",
        r"workflow\s+permissions",
        r"check\s+workflow\s+permissions",
    ],
    "workflow_audit": [
        r"show\s+workflow\s+audit",
        r"workflow\s+audit",
        r"workflow\s+audit\s+(log|logs|history)",
        r"show\s+workflow\s+runs?",
        r"workflow\s+run\s+history",
        r"why\s+did\s+(the\s+)?workflow\s+fail",
    ],
    "workflow_dry_run": [
        r"dry\s*run\s+.*workflow",
        r"dry\s*run\s+(the\s+)?workflow",
        r"simulate\s+workflow\b",
        r"test\s+workflow\s+without\s+running",
    ],
    "workflow_rerun_plan": [
        r"rerun\s+(plan|from)\s+(failed\s+)?step",
        r"show\s+rerun\s+plan",
        r"how\s+to\s+rerun\s+workflow",
    ],
    "compatibility_check": [
        r"(check|show)\s+compatibility\s+(for|of)\s",
        r"is\s+(this|the)\s+pack\s+compatible",
        r"compatibility\s+(check|matrix|report)",
    ],
    "pack_lint": [
        r"lint\s+(pack|skill\s*pack)\s",
        r"check\s+(pack|skill\s*pack)\s+quality",
        r"pack\s+(score|grade|lint)",
    ],
    "changelog_generate": [
        r"generate\s+changelog\s",
        r"create\s+changelog\s",
        r"show\s+changes\s+between\s",
    ],
    "url_import": [
        r"import\s+(pack|skill\s*pack)\s+from\s+url",
        r"download\s+pack\s+from\s+https",
        r"fetch\s+pack\s+from\s+link",
    ],
    "recommendations": [
        r"(recommend|suggest)\s+(packs?|skills?|workflows?)",
        r"what\s+(packs?|skills?)\s+should\s+i\s+(install|get|try)",
        r"find\s+similar\s+(packs?|skills?)",
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
    "voice_status": [
        r"(show|check|get|what'?s?)\s+.*(voice|wake|speech|tts|stt|listening|mic)\s+(status|state|health)",
        r"voice\s+status",
    ],
    "voice_settings": [
        r"show\s+.*(voice|wake|speech|tts|stt|listening|mic)\s+(settings|config)",
        r"voice\s+settings",
    ],
    "voice_enable": [
        r"(enable|activate|turn\s+on)\s+(voice|wake|speech|listening|mic)",
    ],
    "voice_disable": [
        r"(disable|deactivate|turn\s+off)\s+(voice|wake|speech|listening|mic)",
    ],
    "voice_set_name": [
        r"(change|set|update|modify)\s+.*(assistant\s+name|voice\s+name|wake\s+name|name\s+to|name\s+set)",
    ],
    "voice_test_wake": [
        r"test\s+(wake|phrase|word|trigger)\s+",
    ],
    "voice_say": [
        r"(say|speak|read|talk|say\s+aloud|speak\s+aloud)\s+",
    ],
    "browser_open_url": [
        r"(open|go\s+to|visit)\s+(https?://)?(www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(/.*)?",
        r"(open|go\s+to|visit)\s+(the\s+)?(website|url|webpage|page|site)",
    ],
    "browser_search": [
        r"search\s+(the\s+)?web\s+(for)?",
        r"google\s+(for)?",
        r"find\s+online\s+(for)?",
    ],
    "browser_read_page": [
        r"(read|fetch|get|scrape)\s+(this\s+)?(web)?page",
        r"(read|fetch|get|scrape)\s+(this\s+)?(web)?site",
    ],
    "browser_summarize_page": [
        r"summarize\s+(this\s+)?(web)?page",
        r"summarize\s+(this\s+)?(web)?site",
    ],
    "browser_screenshot": [
        r"(take|get|capture)\s+(a\s+)?(screenshot|snapshot)",
    ],
    "browser_click": [
        r"click\s+(the\s+)?(button|link|element)",
    ],
    "browser_fill_form": [
        r"(fill|submit)\s+(the\s+)?form",
        r"type\s+(into|in)\s+(the\s+)?(box|input|field)",
    ],
    "desktop_open_app": [
        r"(open|launch)\s+(the\s+)?(app|application|program)\s+(called|named)?",
        r"(open|launch)\s+(vs\s*code|chrome|safari|firefox|terminal|finder|pycharm|cursor)",
    ],
    "desktop_open_file": [
        r"open\s+(the\s+)?file",
        r"open\s+(the\s+)?document",
    ],
    "desktop_open_folder": [
        r"open\s+(the\s+)?(folder|directory)",
    ],
}

INTENT_DESCRIPTIONS: dict[str, str] = {
    "provider_setup": "Configure AI models and providers (API keys, default models, fallback providers)",
    "connector_setup": "Connect external services (Gmail, Telegram, LinkedIn, X/Twitter)",
    "agent_create": "Create new AI agents for specific roles (marketing, support, coding, etc.)",
    "agent_update": "Update existing agent settings (instructions, tools, provider)",
    "automation_create": "Create recurring automated tasks (daily summaries, weekly reports, etc.)",
    "skill_install": "Install or enable skills and capabilities",
    "workflow_list": "List available workflow templates",
    "workflow_validate": "Validate a workflow definition",
    "workflow_run": "Run a workflow (requires confirmation)",
    "workflow_preview": "Preview a workflow run without executing skills",
    "workflow_permissions": "Check what permissions a workflow needs",
    "workflow_audit": "Show workflow run history and audit logs",
    "workflow_dry_run": "Dry run a workflow to test without executing",
    "workflow_rerun_plan": "Show rerun plan from a failed workflow step",
    "compatibility_check": "Check pack compatibility with installed packs",
    "pack_lint": "Lint and score a skill pack",
    "changelog_generate": "Generate changelog between pack versions",
    "url_import": "Import a pack from a secure HTTPS URL",
    "recommendations": "Get local pack/skill recommendations",
    "memory_add": "Save information to memory for future context",
    "knowledge_search": "Search knowledge base or index new documents",
    "system_status": "Show system health, providers, connectors, and configuration",
    "approval_action": "Review, approve, or reject pending actions and drafts",
    "release_status": "Check desktop app release, build, and signing status",
    "voice_status": "Check the current voice assistant and wake phrase listening status",
    "voice_settings": "Show voice assistant settings configuration",
    "voice_enable": "Enable the voice assistant and speech features",
    "voice_disable": "Disable the voice assistant and speech features",
    "voice_set_name": "Change the assistant wake name",
    "voice_test_wake": "Test wake phrase detection against a sample transcript",
    "voice_say": "Speak a text string aloud using the TTS engine",
    "browser_open_url": "Open a specific URL in the browser",
    "browser_search": "Search the web for a query",
    "browser_read_page": "Read the text content of a webpage",
    "browser_summarize_page": "Summarize a webpage",
    "browser_screenshot": "Take a screenshot of a webpage",
    "browser_click": "Click an element on a webpage",
    "browser_fill_form": "Fill out a form on a webpage",
    "desktop_open_app": "Open a desktop application",
    "desktop_open_file": "Open a file using the desktop OS",
    "desktop_open_folder": "Open a folder using the desktop OS",
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
    "voice_enable": [
        {"field": "confirm", "question": "Type 'yes' to confirm enabling voice features:", "options": ["yes", "no"]}
    ],
    "voice_set_name": [
        {"field": "name", "question": "What is the new assistant name?"}
    ],
    "voice_test_wake": [
        {"field": "transcript", "question": "What is the transcript to test?"}
    ],
    "voice_say": [
        {"field": "text", "question": "What text should I say?"}
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


def _skill_pack_list_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import list_imported_packs
    packs = list_imported_packs()
    if not packs:
        return {
            "intent": "skill_pack_list",
            "confidence": 0.85,
            "status": "preview",
            "message": "## Skill Packs\n\nNo skill packs imported yet. Import a pack with `liuant skills pack import <path>` or browse the catalog.",
            "data": {"packs": []},
            "preview": {"type": "pack_list", "count": 0},
            "actions": [],
            "next_questions": ["Show skill catalog", "How do I import a skill pack?"],
        }
    lines = ["## Imported Skill Packs\n"]
    for p in packs:
        lines.append(f"- **{p['name']}** v{p['version']} ({p['skill_count']} skills) [{p['validation_status']}]\n")
    return {
        "intent": "skill_pack_list",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": {"packs": packs},
        "preview": {"type": "pack_list", "count": len(packs)},
        "actions": [],
        "next_questions": [f"Inspect {p['pack_id']}" for p in packs[:3]],
    }


def _skill_pack_inspect_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id = _extract_pack_identifier(message)
    if pack_id:
        from runtime.skills import pack_status
        status = pack_status(pack_id)
        if status.get("status") == "not_found":
            return {
                "intent": "skill_pack_inspect",
                "confidence": 0.7,
                "status": "needs_input",
                "message": f"Pack '{pack_id}' not found. Try importing it first.",
                "data": {},
                "preview": {"type": "pack_inspect", "pack_id": pack_id},
                "actions": [],
                "next_questions": [f"Import {pack_id}"],
            }
        skills = status.get("skills", [])
        lines = [f"## Pack: {status.get('name', pack_id)} v{status.get('version', '')}\n\n"]
        lines.append(f"**Skills:** {len(skills)}\n")
        for s in skills:
            lines.append(f"- {s.get('id', 'unknown')}\n")
        return {
            "intent": "skill_pack_inspect",
            "confidence": 0.85,
            "status": "preview",
            "message": "".join(lines),
            "data": status,
            "preview": {"type": "pack_inspect", "pack_id": pack_id},
            "actions": [],
            "next_questions": [f"Install {pack_id}", f"Validate {pack_id}"],
        }
    return {
        "intent": "skill_pack_inspect",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Which skill pack would you like to inspect? Provide the pack ID or path.",
        "data": {},
        "preview": {"type": "pack_inspect"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_validate_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_path = _extract_pack_path(message)
    if pack_path:
        from runtime.skills import validate_pack
        result = validate_pack(pack_path)
        status_emoji = {"passed": "✅", "warning": "⚠️", "failed": "❌"}.get(result.get("status", ""), "?")
        lines = [f"## Pack Validation {status_emoji}\n\n"]
        lines.append(f"**Pack:** {result.get('pack_id', 'unknown')} v{result.get('version', '')}\n")
        lines.append(f"**Status:** {result.get('status', '')}\n")
        if result.get("errors"):
            lines.append("\n**Errors:**\n")
            for e in result["errors"]:
                lines.append(f"- {e}\n")
        if result.get("warnings"):
            lines.append("\n**Warnings:**\n")
            for w in result["warnings"]:
                lines.append(f"- {w}\n")
        risk = result.get("risk_summary", {})
        lines.append(f"\n**Risk:** Low={risk.get('low', 0)}, Medium={risk.get('medium', 0)}, High={risk.get('high', 0)}, Critical={risk.get('critical', 0)}\n")
        return {
            "intent": "skill_pack_validate",
            "confidence": 0.85,
            "status": "preview",
            "message": "".join(lines),
            "data": result,
            "preview": {"type": "pack_validate", "status": result.get("status", "")},
            "actions": [],
            "next_questions": [f"Import {result.get('pack_id', '')}"] if result.get("status") == "passed" else [],
        }
    return {
        "intent": "skill_pack_validate",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Provide the path to the skill pack you want to validate.",
        "data": {},
        "preview": {"type": "pack_validate"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_import_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_path = _extract_pack_path(message)
    if pack_path:
        from pathlib import Path
        from runtime.skills import import_pack
        p = Path(pack_path)
        if not p.exists() and not p.is_absolute():
            from runtime.storage import ROOT
            p = ROOT / pack_path
        if not p.exists():
            return {
                "intent": "skill_pack_import",
                "confidence": 0.7,
                "status": "needs_confirmation",
                "message": f"Pack file not found at '{pack_path}'. Please provide a valid path.",
                "data": {},
                "preview": {"type": "pack_import", "path": pack_path},
                "actions": [],
                "next_questions": [],
            }
        return {
            "intent": "skill_pack_import",
            "confidence": 0.85,
            "status": "needs_confirmation",
            "message": f"Import skill pack from `{pack_path}`? This will extract skills to the imported packs directory. Skills will be disabled by default.",
            "data": {"path": str(p)},
            "preview": {"type": "pack_import", "path": str(p)},
            "actions": ["confirm_import"],
            "next_questions": [f"Confirm import {pack_path}"],
        }
    return {
        "intent": "skill_pack_import",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Provide the path to the skill pack you want to import.",
        "data": {},
        "preview": {"type": "pack_import"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_install_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id_or_path = _extract_pack_identifier(message)
    if pack_id_or_path:
        from pathlib import Path
        from runtime.storage import ROOT
        p = Path(pack_id_or_path)
        pack_path = None
        if p.exists():
            pack_path = str(p)
        else:
            from runtime.skills import search_catalog
            results = search_catalog(pack_id_or_path)
            if results:
                pack_path = str(ROOT / results[0].get("path", ""))
        if pack_path:
            return {
                "intent": "skill_pack_install",
                "confidence": 0.85,
                "status": "needs_confirmation",
                "message": f"Install skill pack from `{pack_path}`? Skills will be imported and installed, but disabled by default. Review permissions before enabling.",
                "data": {"path": pack_path},
                "preview": {"type": "pack_install", "path": pack_path},
                "actions": ["confirm_install"],
                "next_questions": [f"Confirm install {pack_id_or_path}"],
            }
    return {
        "intent": "skill_pack_install",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Which skill pack would you like to install? Provide a pack ID or file path.",
        "data": {},
        "preview": {"type": "pack_install"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_remove_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id = _extract_pack_identifier(message)
    if pack_id:
        return {
            "intent": "skill_pack_remove",
            "confidence": 0.85,
            "status": "needs_confirmation",
            "message": f"Remove skill pack '{pack_id}'? This removes the imported pack metadata but does NOT uninstall skills that were already installed.",
            "data": {"pack_id": pack_id},
            "preview": {"type": "pack_remove", "pack_id": pack_id},
            "actions": ["confirm_remove"],
            "next_questions": [f"Confirm remove {pack_id}"],
        }
    return {
        "intent": "skill_pack_remove",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Which skill pack would you like to remove?",
        "data": {},
        "preview": {"type": "pack_remove"},
        "actions": [],
        "next_questions": [],
    }


def _skill_catalog_search_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    query = _extract_search_query(message)
    if query:
        from runtime.skills import search_catalog
        results = search_catalog(query)
        if results:
            lines = ["## Catalog Search Results\n"]
            for r in results:
                lines.append(f"- **{r['name']}** v{r['version']} ({len(r.get('skills', []))} skills)\n")
                lines.append(f"  {r.get('description', '')}\n")
            return {
                "intent": "skill_catalog_search",
                "confidence": 0.85,
                "status": "preview",
                "message": "".join(lines),
                "data": {"results": results},
                "preview": {"type": "catalog_search", "count": len(results)},
                "actions": [],
                "next_questions": [f"Install {r['pack_id']}" for r in results[:3]],
            }
        return {
            "intent": "skill_catalog_search",
            "confidence": 0.8,
            "status": "preview",
            "message": f"No catalog packs found matching '{query}'. Try refreshing the catalog.",
            "data": {"results": []},
            "preview": {"type": "catalog_search", "count": 0},
            "actions": [],
            "next_questions": ["Refresh catalog"],
        }
    return {
        "intent": "skill_catalog_search",
        "confidence": 0.7,
        "status": "preview",
        "message": "## Skill Catalog\n\nSearch the local skill pack catalog. What are you looking for?",
        "data": {},
        "preview": {"type": "catalog_search"},
        "actions": [],
        "next_questions": ["Search for analytics skills", "Search for hello skills"],
    }


def _skill_catalog_install_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id = _extract_pack_identifier(message)
    if pack_id:
        from runtime.skills import search_catalog
        results = search_catalog(pack_id)
        if results:
            return {
                "intent": "skill_catalog_install",
                "confidence": 0.85,
                "status": "needs_confirmation",
                "message": f"Install '{results[0]['name']}' from catalog? Skills will be disabled by default. Review permissions before enabling.",
                "data": {"pack_id": pack_id, "pack_info": results[0]},
                "preview": {"type": "catalog_install", "pack_id": pack_id},
                "actions": ["confirm_catalog_install"],
                "next_questions": [f"Confirm install {pack_id}"],
            }
        return {
            "intent": "skill_catalog_install",
            "confidence": 0.7,
            "status": "needs_input",
            "message": f"Pack '{pack_id}' not found in catalog. Try refreshing.",
            "data": {},
            "preview": {"type": "catalog_install", "pack_id": pack_id},
            "actions": [],
            "next_questions": ["Refresh catalog"],
        }
    return {
        "intent": "skill_catalog_install",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Which pack from the catalog would you like to install?",
        "data": {},
        "preview": {"type": "catalog_install"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_upgrade_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id = _extract_pack_identifier(message)
    if pack_id:
        return {
            "intent": "skill_pack_upgrade",
            "confidence": 0.85,
            "status": "needs_confirmation",
            "message": f"Upgrade pack '{pack_id}'? This will create a backup and replace the current version. Run upgrade-plan first to review changes.",
            "data": {"pack_id": pack_id},
            "preview": {"type": "pack_upgrade", "pack_id": pack_id},
            "actions": ["confirm_upgrade"],
            "next_questions": [f"Show upgrade plan for {pack_id}"],
        }
    return {
        "intent": "skill_pack_upgrade",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Which pack would you like to upgrade? Provide the pack ID or path to the new version.",
        "data": {},
        "preview": {"type": "pack_upgrade"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_diff_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": "skill_pack_diff",
        "confidence": 0.8,
        "status": "needs_input",
        "message": "To compare packs, provide paths to both the old and new pack files: `liuant skills pack diff <old> <new>`",
        "data": {},
        "preview": {"type": "pack_diff"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_dependencies_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id = _extract_pack_identifier(message)
    if pack_id:
        from pathlib import Path
        from runtime.storage import ROOT
        from runtime.skills import resolve_pack_dependencies
        p = Path(pack_id)
        pack_path = None
        if p.exists():
            pack_path = str(p)
        else:
            from runtime.skills import search_catalog
            results = search_catalog(pack_id)
            if results:
                pack_path = str(ROOT / results[0].get("path", ""))
        if pack_path:
            result = resolve_pack_dependencies(pack_path)
            missing = result.get("missing", [])
            if missing:
                return {
                    "intent": "skill_pack_dependencies",
                    "confidence": 0.85,
                    "status": "preview",
                    "message": f"Pack '{pack_id}' has missing dependencies: {', '.join(m['pack_id'] for m in missing)}",
                    "data": result,
                    "preview": {"type": "pack_dependencies", "missing": missing},
                    "actions": [],
                    "next_questions": [f"Install missing dependencies for {pack_id}"],
                }
            return {
                "intent": "skill_pack_dependencies",
                "confidence": 0.85,
                "status": "preview",
                "message": f"Pack '{pack_id}' has all dependencies satisfied.",
                "data": result,
                "preview": {"type": "pack_dependencies", "resolved": result.get("resolved", [])},
                "actions": [],
                "next_questions": [f"Install {pack_id}"],
            }
    return {
        "intent": "skill_pack_dependencies",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Which pack's dependencies should I check?",
        "data": {},
        "preview": {"type": "pack_dependencies"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_verify_signature_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_path = _extract_pack_path(message)
    if pack_path:
        from pathlib import Path
        from runtime.storage import ROOT
        from runtime.skills import verify_pack_signature
        p = Path(pack_path)
        if not p.exists() and not p.is_absolute():
            p = ROOT / pack_path
        if p.exists():
            result = verify_pack_signature(str(p))
            status_msg = {"signed_trusted": "Trusted signature", "signed_untrusted": "Signed but untrusted", "unsigned": "Unsigned", "signature_invalid": "Invalid signature"}.get(result.get("status", ""), "Unknown")
            return {
                "intent": "skill_pack_verify_signature",
                "confidence": 0.85,
                "status": "preview",
                "message": f"Pack signature: {status_msg}. Signer: {result.get('signer', 'N/A')}",
                "data": result,
                "preview": {"type": "pack_verify", "status": result.get("status", "")},
                "actions": [],
                "next_questions": [],
            }
    return {
        "intent": "skill_pack_verify_signature",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Provide the path to the pack you want to verify.",
        "data": {},
        "preview": {"type": "pack_verify"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_sign_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": "skill_pack_sign",
        "confidence": 0.7,
        "status": "needs_confirmation",
        "message": "To sign a pack, use: `liuant skills pack sign <source> --key <key_id>`. Generate a key first with `liuant skills pack keys generate`.",
        "data": {},
        "preview": {"type": "pack_sign"},
        "actions": [],
        "next_questions": ["Generate a signing key", "List my keys"],
    }


def _skill_pack_trust_status_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_path = _extract_pack_path(message)
    if pack_path:
        from pathlib import Path
        from runtime.storage import ROOT
        from runtime.skills import get_trust_state
        p = Path(pack_path)
        if not p.exists() and not p.is_absolute():
            p = ROOT / pack_path
        if p.exists():
            result = get_trust_state(str(p))
            return {
                "intent": "skill_pack_trust_status",
                "confidence": 0.85,
                "status": "preview",
                "message": f"Pack trust state: {result.get('trust_state', 'unknown')}. {'Trusted' if result.get('trusted') else 'Not trusted locally.'}",
                "data": result,
                "preview": {"type": "pack_trust", "state": result.get("trust_state", "")},
                "actions": [],
                "next_questions": [],
            }
    return {
        "intent": "skill_pack_trust_status",
        "confidence": 0.6,
        "status": "needs_input",
        "message": "Provide the path to the pack you want to check trust status for.",
        "data": {},
        "preview": {"type": "pack_trust"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_encode_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": "skill_pack_encode",
        "confidence": 0.7,
        "status": "needs_confirmation",
        "message": "To encode a pack as base64: `liuant skills pack encode <path> --output <file.txt>`. Warning: base64 is not encryption.",
        "data": {},
        "preview": {"type": "pack_encode"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_decode_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": "skill_pack_decode",
        "confidence": 0.7,
        "status": "needs_confirmation",
        "message": "To decode a base64 pack: `liuant skills pack decode <file.txt>`. The decoded pack will be validated before import.",
        "data": {},
        "preview": {"type": "pack_decode"},
        "actions": [],
        "next_questions": [],
    }


def _skill_pack_analytics_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_id = _extract_pack_identifier(message)
    from runtime.skills import get_pack_analytics
    result = get_pack_analytics(pack_id)
    summary = result.get("summary", {})
    lines = ["## Pack Analytics\n\n"]
    lines.append(f"**Total Events:** {summary.get('total_events', 0)}\n")
    lines.append(f"**Validation Failures:** {summary.get('validation_failures', 0)}\n")
    if summary.get("last_imported"):
        lines.append(f"**Last Imported:** {summary['last_imported']}\n")
    if summary.get("last_installed"):
        lines.append(f"**Last Installed:** {summary['last_installed']}\n")
    return {
        "intent": "skill_pack_analytics",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": result,
        "preview": {"type": "pack_analytics", "total_events": summary.get("total_events", 0)},
        "actions": [],
        "next_questions": [],
    }


def _workflow_list_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import list_workflows
    workflows = list_workflows()
    lines = ["## Available Workflows\n\n"]
    if workflows:
        for wf in workflows:
            lines.append(f"- **{wf.get('workflow_id', '')}**: {wf.get('name', '')} ({wf.get('steps', 0)} steps)\n")
    else:
        lines.append("No workflows found.\n")
    return {
        "intent": "workflow_list",
        "confidence": 0.9,
        "status": "preview",
        "message": "".join(lines),
        "data": {"workflows": workflows},
        "preview": {"type": "workflow_list", "count": len(workflows)},
        "actions": [],
        "next_questions": ["Validate a workflow", "Run a workflow"],
    }


def _workflow_validate_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    wf_path = _extract_pack_path(message)
    if not wf_path:
        return {
            "intent": "workflow_validate",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Please provide the path to the workflow.json file.",
            "data": {},
            "required_fields": [{"field": "path", "question": "What is the path to workflow.json?"}],
            "preview": {"type": "workflow_validate"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import validate_workflow
    result = validate_workflow(wf_path)
    return {
        "intent": "workflow_validate",
        "confidence": 0.85,
        "status": "preview",
        "message": f"Workflow validation: {result.get('status', 'unknown')}\n\nErrors: {result.get('errors', [])}\nWarnings: {result.get('warnings', [])}",
        "data": result,
        "preview": {"type": "workflow_validate", "status": result.get("status")},
        "actions": [],
        "next_questions": ["Run this workflow", "Inspect this workflow"],
    }


def _workflow_run_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    wf_match = re.search(r'(?:workflow\s+)?([a-z0-9][a-z0-9_-]*(?:-[a-z0-9]+)*)', message.lower())
    wf_id = wf_match.group(1) if wf_match else None
    if not wf_id:
        return {
            "intent": "workflow_run",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Which workflow should I run?",
            "data": {},
            "required_fields": [{"field": "workflow_id", "question": "What is the workflow ID?"}],
            "preview": {"type": "workflow_run"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import preview_workflow_run, run_workflow
    preview = preview_workflow_run(wf_id)
    if preview.get("status") == "blocked":
        return {
            "intent": "workflow_run",
            "confidence": 0.85,
            "status": "blocked",
            "message": f"Workflow '{wf_id}' cannot run: {'; '.join(preview.get('warnings', []))}",
            "data": preview,
            "preview": {"type": "workflow_run", "status": "blocked"},
            "actions": [],
            "next_questions": ["Preview this workflow", "Check permissions"],
        }
    return {
        "intent": "workflow_run",
        "confidence": 0.85,
        "status": "needs_confirmation",
        "message": f"Ready to run workflow '{wf_id}'. This will execute {len(preview.get('steps', []))} steps. Confirm to proceed.",
        "data": preview,
        "preview": {"type": "workflow_run", "status": "ready"},
        "actions": ["run_workflow"],
        "next_questions": ["Preview first", "Check permissions"],
    }


def _workflow_preview_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    wf_match = re.search(r'(?:workflow\s+)?([a-z0-9][a-z0-9_-]*(?:-[a-z0-9]+)*)', message.lower())
    wf_id = wf_match.group(1) if wf_match else None
    if not wf_id:
        return {
            "intent": "workflow_preview",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Which workflow should I preview?",
            "data": {},
            "required_fields": [{"field": "workflow_id", "question": "What is the workflow ID?"}],
            "preview": {"type": "workflow_preview"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import preview_workflow_run
    result = preview_workflow_run(wf_id)
    status = result.get("status", "unknown")
    steps = result.get("steps", [])
    lines = [f"## Workflow Preview: {result.get('name', wf_id)}\n\n"]
    lines.append(f"**Status:** {status}\n\n")
    for step in steps:
        icon = "✅" if step.get("status") == "ready" else "❌"
        lines.append(f"{icon} {step.get('step_id', '')}: {step.get('skill_id', '')}/{step.get('command', '')} — {step.get('status', '')}\n")
    if result.get("missing_skills"):
        lines.append(f"\n**Missing skills:** {result['missing_skills']}\n")
    if result.get("approval_required"):
        lines.append("\n⚠️ This workflow requires approval for external actions.\n")
    return {
        "intent": "workflow_preview",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": result,
        "preview": {"type": "workflow_preview", "status": status},
        "actions": ["run_workflow"] if status == "ready" else [],
        "next_questions": ["Run this workflow", "Check permissions"],
    }


def _workflow_permissions_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    wf_match = re.search(r'(?:workflow\s+)?([a-z0-9][a-z0-9_-]*(?:-[a-z0-9]+)*)', message.lower())
    wf_id = wf_match.group(1) if wf_match else None
    if not wf_id:
        return {
            "intent": "workflow_permissions",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Which workflow's permissions should I check?",
            "data": {},
            "required_fields": [{"field": "workflow_id", "question": "What is the workflow ID?"}],
            "preview": {"type": "workflow_permissions"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import workflow_permission_summary
    result = workflow_permission_summary(wf_id)
    lines = [f"## Workflow Permissions: {wf_id}\n\n"]
    for perm in result.get("permissions", []):
        icon = "✅" if perm.get("approved") else "⚠️"
        lines.append(f"{icon} {perm['permission']} ({perm['risk_level']}) — required by: {', '.join(perm['required_by'])}\n")
    if result.get("missing_approvals"):
        lines.append(f"\n**Missing approvals:** {len(result['missing_approvals'])}\n")
    lines.append(f"\n**Can run:** {'Yes' if result.get('can_run') else 'No'}\n")
    return {
        "intent": "workflow_permissions",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": result,
        "preview": {"type": "workflow_permissions", "can_run": result.get("can_run")},
        "actions": [],
        "next_questions": ["Preview this workflow", "Run this workflow"],
    }


def _workflow_audit_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    wf_match = re.search(r'(?:workflow\s+)?([a-z0-9][a-z0-9_-]*(?:-[a-z0-9]+)*)', message.lower())
    wf_id = wf_match.group(1) if wf_match else None
    from runtime.skills.workflow_audit import get_workflow_audit, get_latest_workflow_run
    if wf_id:
        latest = get_latest_workflow_run(wf_id)
        if latest:
            lines = [f"## Latest Run: {wf_id}\n\n"]
            lines.append(f"**Status:** {latest.get('status', '')}\n")
            lines.append(f"**Duration:** {latest.get('duration_ms', 0)}ms\n")
            lines.append(f"**Steps:** {latest.get('completed_steps', 0)}/{latest.get('step_count', 0)}\n")
            if latest.get("failed_step_id"):
                lines.append(f"**Failed Step:** {latest['failed_step_id']}\n")
                lines.append(f"\n**Recovery:** Check the failed step and rerun from there.\n")
            return {
                "intent": "workflow_audit",
                "confidence": 0.85,
                "status": "preview",
                "message": "".join(lines),
                "data": latest,
                "preview": {"type": "workflow_audit", "status": latest.get("status")},
                "actions": [],
                "next_questions": ["Show all runs", "Rerun from failed step"],
            }
        return {
            "intent": "workflow_audit",
            "confidence": 0.8,
            "status": "preview",
            "message": f"No runs found for workflow '{wf_id}'.",
            "data": {},
            "preview": {"type": "workflow_audit"},
            "actions": [],
            "next_questions": [],
        }
    runs = get_workflow_audit(limit=10)
    lines = ["## Workflow Run History\n\n"]
    if runs:
        for run in runs[:5]:
            lines.append(f"- {run.get('workflow_id', '')}: {run.get('status', '')} ({run.get('duration_ms', 0)}ms)\n")
    else:
        lines.append("No workflow runs recorded.\n")
    return {
        "intent": "workflow_audit",
        "confidence": 0.8,
        "status": "preview",
        "message": "".join(lines),
        "data": {"runs": runs},
        "preview": {"type": "workflow_audit", "count": len(runs)},
        "actions": [],
        "next_questions": ["Show latest run", "Show runs for a specific workflow"],
    }


def _workflow_dry_run_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    wf_match = re.search(r'(?:workflow\s+)?([a-z0-9][a-z0-9_-]*(?:-[a-z0-9]+)*)', message.lower())
    wf_id = wf_match.group(1) if wf_match else None
    if not wf_id:
        return {
            "intent": "workflow_dry_run",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Which workflow should I dry run?",
            "data": {},
            "required_fields": [{"field": "workflow_id", "question": "What is the workflow ID?"}],
            "preview": {"type": "workflow_dry_run"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import run_workflow
    result = run_workflow(workflow_id=wf_id, dry_run=True, user_confirmed=True)
    lines = [f"## Dry Run: {wf_id}\n\n"]
    lines.append(f"**Status:** {result.get('status', '')}\n\n")
    plan = result.get("execution_plan", [])
    for step in plan:
        lines.append(f"- {step.get('step_id', '')}: {step.get('skill_id', '')}/{step.get('command', '')}\n")
        if step.get("input_from"):
            for param, src in step["input_from"].items():
                lines.append(f"  - {param}: {src}\n")
    return {
        "intent": "workflow_dry_run",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": result,
        "preview": {"type": "workflow_dry_run", "status": result.get("status")},
        "actions": ["run_workflow"],
        "next_questions": ["Run this workflow", "Check permissions"],
    }


def _workflow_rerun_plan_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    run_match = re.search(r'(?:run[-\s]?)([a-f0-9-]+)', message.lower())
    run_id = run_match.group(1) if run_match else None
    step_match = re.search(r'(?:step[-\s]?)([a-z0-9_-]+)', message.lower())
    step_id = step_match.group(1) if step_match else None
    if not run_id or not step_id:
        return {
            "intent": "workflow_rerun_plan",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Please provide the run ID and step ID for the rerun plan.",
            "data": {},
            "required_fields": [
                {"field": "run_id", "question": "What is the run ID?"},
                {"field": "step_id", "question": "Which step should I rerun from?"},
            ],
            "preview": {"type": "workflow_rerun_plan"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import preview_rerun_from_step
    result = preview_rerun_from_step(run_id, step_id)
    lines = [f"## Rerun Plan: {run_id}\n\n"]
    lines.append(f"**Status:** {result.get('status', '')}\n")
    lines.append(f"**Rerun from:** {step_id}\n")
    lines.append(f"**Preceding steps completed:** {result.get('preceding_steps_completed', 0)}\n")
    lines.append(f"**Remaining steps:** {result.get('remaining_steps', 0)}\n")
    if result.get("warnings"):
        lines.append(f"\n**Warnings:** {'; '.join(result['warnings'])}\n")
    lines.append(f"\n**Can rerun:** {'Yes' if result.get('can_rerun') else 'No'}\n")
    return {
        "intent": "workflow_rerun_plan",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": result,
        "preview": {"type": "workflow_rerun_plan", "can_rerun": result.get("can_rerun")},
        "actions": [],
        "next_questions": [],
    }


def _compatibility_check_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_path = _extract_pack_path(message)
    pack_id = _extract_pack_identifier(message)
    if not pack_path and not pack_id:
        return {
            "intent": "compatibility_check",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Please provide a pack path or pack ID to check compatibility.",
            "data": {},
            "required_fields": [{"field": "pack", "question": "Which pack should I check?"}],
            "preview": {"type": "compatibility_check"},
            "actions": [],
            "next_questions": [],
        }
    from runtime.skills import check_compatibility
    result = check_compatibility(pack_path=pack_path, pack_id=pack_id)
    return {
        "intent": "compatibility_check",
        "confidence": 0.85,
        "status": "preview",
        "message": f"Compatibility: {result.get('status', 'unknown')}\n\nConflicts: {len(result.get('conflicts', []))}\nWarnings: {len(result.get('warnings', []))}",
        "data": result,
        "preview": {"type": "compatibility_check", "status": result.get("status")},
        "actions": [],
        "next_questions": ["Check all packs", "Save compatibility matrix"],
    }


def _pack_lint_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    pack_path = _extract_pack_path(message)
    if not pack_path:
        return {
            "intent": "pack_lint",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Please provide the pack path to lint.",
            "data": {},
            "required_fields": [{"field": "path", "question": "What is the pack path?"}],
            "preview": {"type": "pack_lint"},
            "actions": [],
            "next_questions": [],
        }
    strict = "strict" in message.lower()
    from runtime.skills import lint_pack
    result = lint_pack(pack_path, strict=strict)
    return {
        "intent": "pack_lint",
        "confidence": 0.85,
        "status": "preview",
        "message": f"Pack lint: Score {result.get('score', 0)}/100 (Grade {result.get('grade', 'F')})\n\nStatus: {result.get('status', 'unknown')}",
        "data": result,
        "preview": {"type": "pack_lint", "score": result.get("score"), "grade": result.get("grade")},
        "actions": [],
        "next_questions": ["Fix lint issues", "Generate changelog"],
    }


def _url_import_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    import re
    url_match = re.search(r'https?://[^\s"\']+', message)
    if not url_match:
        return {
            "intent": "url_import",
            "confidence": 0.7,
            "status": "needs_input",
            "message": "Please provide the HTTPS URL to the pack.",
            "data": {},
            "required_fields": [{"field": "url", "question": "What is the HTTPS URL?"}],
            "preview": {"type": "url_import"},
            "actions": [],
            "next_questions": [],
        }
    url = url_match.group(0)
    from runtime.skills import preview_url_import
    result = preview_url_import(url)
    return {
        "intent": "url_import",
        "confidence": 0.85,
        "status": "preview",
        "message": f"URL import preview: {result.get('status', 'unknown')}\n\nHost: {result.get('host', '')}\nFilename: {result.get('filename', '')}",
        "data": result,
        "preview": {"type": "url_import", "url": url},
        "actions": ["import_from_url"],
        "next_questions": ["Import this pack", "Clear staging"],
    }


def _recommendations_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from runtime.skills import get_recommendations
    result = get_recommendations(limit=5)
    lines = ["## Recommendations\n\n"]
    packs = result.get("packs", [])
    if packs:
        lines.append("### Suggested Packs\n\n")
        for p in packs[:3]:
            lines.append(f"- **{p.get('pack_id', '')}**: {p.get('name', '')} - {p.get('reason', '')}\n")
    return {
        "intent": "recommendations",
        "confidence": 0.85,
        "status": "preview",
        "message": "".join(lines),
        "data": result,
        "preview": {"type": "recommendations", "pack_count": len(packs)},
        "actions": [],
        "next_questions": ["Install a recommended pack", "Show workflow recommendations"],
    }


def _extract_memory_content(message: str) -> str | None:
    """Extract pack ID or path from message."""
    import re
    patterns = [
        r"(?:pack|skill\s*pack)\s+['\"]?([a-z0-9][a-z0-9_-]*)['\"]?",
        r"(?:install|import|inspect|validate|remove)\s+['\"]?([a-z0-9][a-z0-9_.\/-]*\.liuantskillpack)['\"]?",
        r"(?:install|import|inspect|validate|remove)\s+['\"]?([a-z0-9][a-z0-9_-]*)['\"]?",
    ]
    for pattern in patterns:
        m = re.search(pattern, message.lower())
        if m:
            return m.group(1)
    for word in message.split():
        if re.match(r"^[a-z0-9][a-z0-9_-]*$", word.lower()) and "pack" in word.lower():
            return word.lower()
    return None


def _extract_pack_path(message: str) -> str | None:
    """Extract a file path from message."""
    import re
    m = re.search(r"['\"]?([^\s]+\.(?:liuantskillpack|zip))['\"]?", message)
    if m:
        return m.group(1)
    m = re.search(r"['\"]?([^\s]+/[^/]+\.(?:liuantskillpack|zip))['\"]?", message)
    if m:
        return m.group(1)
    return None


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

def _voice_status_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from runtime.voice.settings import get_voice_settings
    settings = get_voice_settings()
    return {
        "intent": "voice_status",
        "confidence": 0.95,
        "status": "completed",
        "message": (
            f"### Voice Assistant Status\n\n"
            f"- **Voice Assistant**: {'Enabled' if settings.get('voice_enabled') else 'Disabled'}\n"
            f"- **Wake Listening**: {'Enabled' if settings.get('wake_listening_enabled') else 'Disabled'}\n"
            f"- **Assistant Name**: `{settings.get('assistant_name')}`\n"
            f"- **Wake Phrases**: {', '.join(settings.get('wake_phrases', []))}\n"
            f"- **STT Provider**: `{settings.get('stt_provider')}`\n"
            f"- **TTS Provider**: `{settings.get('tts_provider')}`\n"
            f"- **Voice Reply**: {'Enabled' if settings.get('voice_reply_enabled') else 'Disabled'}\n"
            f"- **Store Transcripts**: {'Enabled' if settings.get('store_transcripts') else 'Disabled'}"
        ),
        "data": settings,
        "actions": ["show voice settings", "disable voice assistant"] if settings.get("voice_enabled") else ["enable voice assistant"]
    }

def _voice_settings_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return _voice_status_handler(message, ctx)

def _voice_enable_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": "voice_enable",
        "confidence": 0.95,
        "status": "preview",
        "message": "Enabling the voice assistant allows local audio capturing. Do you confirm?",
        "required_fields": [{"field": "confirm", "question": "Type 'yes' to confirm enabling voice features:", "options": ["yes", "no"]}],
        "data": {}
    }

def _voice_disable_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from runtime.voice.settings import update_voice_setting
    update_voice_setting("voice_enabled", False)
    update_voice_setting("wake_listening_enabled", False)
    return {
        "intent": "voice_disable",
        "confidence": 0.95,
        "status": "completed",
        "message": "Voice assistant and wake listening have been successfully disabled.",
        "data": {"voice_enabled": False, "wake_listening_enabled": False}
    }

def _voice_set_name_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    match = re.search(r"name\s+(?:set|to)\s+([^\s]+)", message, re.IGNORECASE)
    detected_name = match.group(1) if match else None
    if not detected_name:
        return {
            "intent": "voice_set_name",
            "confidence": 0.95,
            "status": "preview",
            "message": "Please specify the new assistant name.",
            "required_fields": [{"field": "name", "question": "What is the new assistant name?"}],
            "data": {}
        }
    from runtime.voice.settings import update_voice_setting
    try:
        settings = update_voice_setting("assistant_name", detected_name)
        return {
            "intent": "voice_set_name",
            "confidence": 0.95,
            "status": "completed",
            "message": f"Assistant name successfully updated to **{detected_name}**.",
            "data": settings
        }
    except Exception as e:
        return {
            "intent": "voice_set_name",
            "confidence": 0.95,
            "status": "error",
            "message": f"Could not set name: {e}"
        }

def _voice_test_wake_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    match = re.search(r"phrase\s+(.+)", message, re.IGNORECASE)
    transcript = match.group(1) if match else ""
    if not transcript:
        match = re.search(r"test\s+wake\s+(.+)", message, re.IGNORECASE)
        transcript = match.group(1) if match else ""
    if not transcript:
        return {
            "intent": "voice_test_wake",
            "confidence": 0.95,
            "status": "preview",
            "message": "Please specify the transcript text to test wake word matching.",
            "required_fields": [{"field": "transcript", "question": "What is the transcript to test?"}],
            "data": {}
        }
    from runtime.voice.settings import get_voice_settings
    from runtime.voice.wake import detect_wake_phrase
    settings = get_voice_settings()
    res = detect_wake_phrase(transcript, settings.get("wake_phrases", []))
    msg = f"Wake matching result for transcript: '_{transcript}_'\n\n"
    if res["woke"]:
        msg += f"✅ **Matched!** Wake phrase: '_{res['matched_phrase']}_'. Trailing command: '_{res.get('command_text', '')}_'."
    else:
        msg += "❌ **No match.** Checked phrases: " + ", ".join(f"'{p}'" for p in settings.get("wake_phrases", []))
    return {
        "intent": "voice_test_wake",
        "confidence": 0.95,
        "status": "completed",
        "message": msg,
        "data": res
    }

def _voice_say_handler(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    match = re.search(r"(?:say|speak)(?:\s+aloud)?\s+(.+)", message, re.IGNORECASE)
    text = match.group(1) if match else ""
    if not text:
        return {
            "intent": "voice_say",
            "confidence": 0.95,
            "status": "preview",
            "message": "Please specify the text to speak.",
            "required_fields": [{"field": "text", "question": "What text should I say?"}],
            "data": {}
        }
    from runtime.voice.settings import get_voice_settings
    from runtime.voice.tts import get_tts_provider
    from runtime.voice.session import redact_secrets
    settings = get_voice_settings()
    if settings.get("redact_transcripts", True):
        text = redact_secrets(text)
    tts = get_tts_provider(settings.get("tts_provider", "mock"))
    tts_res = tts.speak(text)
    return {
        "intent": "voice_say",
        "confidence": 0.95,
        "status": "completed",
        "message": f"Spoken aloud: \"{text}\"",
        "data": tts_res
    }


_INTENT_HANDLERS = {
    "voice_status": _voice_status_handler,
    "voice_settings": _voice_settings_handler,
    "voice_enable": _voice_enable_handler,
    "voice_disable": _voice_disable_handler,
    "voice_set_name": _voice_set_name_handler,
    "voice_test_wake": _voice_test_wake_handler,
    "voice_say": _voice_say_handler,
    "provider_setup": _provider_setup_handler,
    "connector_setup": _connector_setup_handler,
    "agent_create": _agent_create_handler,
    "agent_update": _agent_update_handler,
    "automation_create": _automation_create_handler,
    "skill_install": _skill_install_handler,
    "skill_pack_list": _skill_pack_list_handler,
    "skill_pack_inspect": _skill_pack_inspect_handler,
    "skill_pack_validate": _skill_pack_validate_handler,
    "skill_pack_import": _skill_pack_import_handler,
    "skill_pack_install": _skill_pack_install_handler,
    "skill_pack_remove": _skill_pack_remove_handler,
    "skill_pack_upgrade": _skill_pack_upgrade_handler,
    "skill_pack_diff": _skill_pack_diff_handler,
    "skill_pack_dependencies": _skill_pack_dependencies_handler,
    "skill_pack_verify_signature": _skill_pack_verify_signature_handler,
    "skill_pack_sign": _skill_pack_sign_handler,
    "skill_pack_trust_status": _skill_pack_trust_status_handler,
    "skill_pack_encode": _skill_pack_encode_handler,
    "skill_pack_decode": _skill_pack_decode_handler,
    "skill_pack_analytics": _skill_pack_analytics_handler,
    "skill_catalog_search": _skill_catalog_search_handler,
    "skill_catalog_install": _skill_catalog_install_handler,
    "workflow_list": _workflow_list_handler,
    "workflow_validate": _workflow_validate_handler,
    "workflow_run": _workflow_run_handler,
    "workflow_preview": _workflow_preview_handler,
    "workflow_permissions": _workflow_permissions_handler,
    "workflow_audit": _workflow_audit_handler,
    "workflow_dry_run": _workflow_dry_run_handler,
    "workflow_rerun_plan": _workflow_rerun_plan_handler,
    "compatibility_check": _compatibility_check_handler,
    "pack_lint": _pack_lint_handler,
    "url_import": _url_import_handler,
    "recommendations": _recommendations_handler,
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

    if intent == "voice_enable" and action == "configure":
        confirm = data.get("confirm", "")
        if confirm.lower() in ("yes", "true", "1", "on"):
            from runtime.voice.settings import update_voice_setting
            update_voice_setting("voice_enabled", True)
            return {"status": "completed", "message": "Voice assistant features have been enabled successfully."}
        return {"status": "completed", "message": "Voice assistant enablement canceled."}

    if intent == "voice_set_name" and action == "configure":
        name = data.get("name", "")
        if name:
            from runtime.voice.settings import update_voice_setting
            try:
                update_voice_setting("assistant_name", name)
                return {"status": "completed", "message": f"Assistant name successfully updated to **{name}**."}
            except Exception as e:
                return {"status": "error", "message": f"Could not set name: {e}"}
        return {"status": "error", "message": "Assistant name is required."}

    if intent == "voice_test_wake" and action == "configure":
        transcript = data.get("transcript", "")
        if transcript:
            from runtime.voice.settings import get_voice_settings
            from runtime.voice.wake import detect_wake_phrase
            settings = get_voice_settings()
            res = detect_wake_phrase(transcript, settings.get("wake_phrases", []))
            msg = f"Wake matching result for transcript: '_{transcript}_'\n\n"
            if res["woke"]:
                msg += f"✅ **Matched!** Wake phrase: '_{res['matched_phrase']}_'. Trailing command: '_{res.get('command_text', '')}_'."
            else:
                msg += "❌ **No match.**"
            return {"status": "completed", "message": msg, "data": res}
        return {"status": "error", "message": "Transcript is required."}

    if intent == "voice_say" and action == "configure":
        text = data.get("text", "")
        if text:
            from runtime.voice.settings import get_voice_settings
            from runtime.voice.tts import get_tts_provider
            from runtime.voice.session import redact_secrets
            settings = get_voice_settings()
            if settings.get("redact_transcripts", True):
                text = redact_secrets(text)
            tts = get_tts_provider(settings.get("tts_provider", "mock"))
            tts_res = tts.speak(text)
            return {"status": "completed", "message": f"Spoken aloud: \"{text}\"", "data": tts_res}
        return {"status": "error", "message": "Text is required."}

    return {"status": "error", "message": f"Unknown action: {action} for intent: {intent}"}
