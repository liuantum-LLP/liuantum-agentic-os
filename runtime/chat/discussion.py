"""Model-to-model discussion engine for Liuant Agentic OS v1.1.0.

Enables multiple model roles to collaborate on a single response.
Each role gives an independent answer, then reviews others, and a final
role synthesizes the best response.

Safety:
- Does not expose hidden chain-of-thought.
- Redacts secrets before model calls.
- Does not run tools/external actions during discussion.
- Text-only.
"""

from __future__ import annotations

import re
import json
from typing import Any
from uuid import uuid4

from runtime.model_roles import ModelRoleManager
from runtime.model_router import get_model_for_role, route_task_to_role
from runtime.providers import ModelHub

SENSITIVE_PATTERNS = re.compile(
    r"\b(password|otp|credit.?card|aadhaar|pan|secret|api.?key|token|bearer)\b",
    re.IGNORECASE,
)

CLOUD_PROVIDERS = {"openai", "openrouter", "anthropic", "gemini", "groq", "mistral", "together", "fireworks"}

ROLE_SELECTION_RULES: dict[str, list[str]] = {
    "coding": ["coding", "thinking"],
    "planning": ["planning", "thinking"],
    "thinking": ["thinking", "planning"],
    "default": ["default"],
}


def redact_secrets(text: str) -> str:
    """Redact potential secrets from text before sending to models."""
    if not SENSITIVE_PATTERNS.search(text):
        return text
    for pattern in [
        (r"(?i)(password|otp|secret|api.?key|token)\s*[=:]\s*\S+", r"\1=[REDACTED]"),
        (r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]"),
        (r"sk-[A-Za-z0-9_\-]+", "sk-[REDACTED]"),
    ]:
        text = re.sub(pattern[0], pattern[1], text)
    return text


def _is_cloud_provider(provider: str) -> bool:
    return provider.lower() in CLOUD_PROVIDERS


def _select_roles(task_role: str, requested_roles: list[str] | None = None) -> list[str]:
    """Select roles for discussion. Use requested if provided, else task-based."""
    if requested_roles and requested_roles != ["auto"]:
        return [r for r in requested_roles if r in ("thinking", "coding", "planning", "default", "fast")]
    return ROLE_SELECTION_RULES.get(task_role, ["default"])


def _generate_cost_note(roles: list[str], role_manager: ModelRoleManager) -> str:
    """Generate a cost warning if cloud models are used."""
    cloud_roles = []
    for role in roles:
        cfg = role_manager.get_role(role)
        if cfg["configured"] and _is_cloud_provider(cfg["provider"]):
            cloud_roles.append(role)
    if cloud_roles:
        return f"Discussion mode uses {len(roles)} model call(s) per round. Cloud roles: {', '.join(cloud_roles)}. Costs may apply."
    return "Discussion mode uses local models only. No cloud costs."


def run_discussion(
    user_message: str,
    roles: list[str] | None = None,
    rounds: int = 2,
    final_role: str = "thinking",
    context: dict[str, Any] | None = None,
    role_manager: ModelRoleManager | None = None,
    model_hub: ModelHub | None = None,
) -> dict[str, Any]:
    """Run a model-to-model discussion.

    Returns:
        dict with status, discussion_id, roles_used, rounds, transcript,
        final_answer, warnings, cost_note, fallback_used.
    """
    role_manager = role_manager or ModelRoleManager()
    model_hub = model_hub or ModelHub()

    discussion_settings = role_manager.get_discussion_settings()
    max_rounds = discussion_settings.get("discussion_mode_max_rounds", 4)
    rounds = min(rounds, max_rounds)

    safe_message = redact_secrets(user_message)
    task_role = route_task_to_role(user_message)
    selected_roles = _select_roles(task_role, roles)

    if not selected_roles:
        selected_roles = ["default"]

    discussion_id = str(uuid4())
    transcript: list[dict[str, Any]] = []
    warnings: list[str] = []
    fallback_used = False
    cost_note = _generate_cost_note(selected_roles, role_manager)

    previous_answers: dict[str, str] = {}

    for round_num in range(1, rounds + 1):
        for role in selected_roles:
            model_cfg = get_model_for_role(role, role_manager)
            if not model_cfg["configured"]:
                warnings.append(f"Role '{role}' not configured, skipping.")
                continue

            prompt = _build_role_prompt(
                role=role,
                user_message=safe_message,
                round_num=round_num,
                previous_answers=previous_answers,
                total_rounds=rounds,
            )

            try:
                response = model_hub.generate_text(
                    prompt=prompt,
                    system_prompt=_build_system_prompt(role, round_num),
                    provider_name=model_cfg["provider"],
                    model=model_cfg["model"],
                )

                if response.get("status") == "completed":
                    transcript.append({
                        "role": role,
                        "round": round_num,
                        "provider": model_cfg["provider"],
                        "model": model_cfg["model"],
                        "content": response.get("text", "")[:2000],
                        "status": "completed",
                    })
                    previous_answers[role] = response.get("text", "")
                else:
                    fallback_used = True
                    fallback_cfg = get_model_for_role("fallback", role_manager)
                    if fallback_cfg["configured"] and fallback_cfg["role"] != role:
                        fallback_response = model_hub.generate_text(
                            prompt=prompt,
                            system_prompt=_build_system_prompt(role, round_num),
                            provider_name=fallback_cfg["provider"],
                            model=fallback_cfg["model"],
                        )
                        if fallback_response.get("status") == "completed":
                            transcript.append({
                                "role": role,
                                "round": round_num,
                                "provider": fallback_cfg["provider"],
                                "model": fallback_cfg["model"],
                                "content": fallback_response.get("text", "")[:2000],
                                "status": "fallback",
                            })
                            previous_answers[role] = fallback_response.get("text", "")
                            warnings.append(f"Role '{role}' fell back to {fallback_cfg['provider']}.")
                        else:
                            transcript.append({
                                "role": role,
                                "round": round_num,
                                "provider": model_cfg["provider"],
                                "model": model_cfg["model"],
                                "content": "",
                                "status": f"failed: {response.get('status')}",
                            })
                    else:
                        transcript.append({
                            "role": role,
                            "round": round_num,
                            "provider": model_cfg["provider"],
                            "model": model_cfg["model"],
                            "content": "",
                            "status": f"failed: {response.get('status')}",
                        })
            except Exception as exc:
                fallback_used = True
                transcript.append({
                    "role": role,
                    "round": round_num,
                    "provider": model_cfg["provider"],
                    "model": model_cfg["model"],
                    "content": "",
                    "status": f"error: {str(exc)[:100]}",
                })
                warnings.append(f"Role '{role}' failed: {str(exc)[:100]}")

    final_answer = _synthesize_final_answer(
        final_role=final_role,
        user_message=user_message,
        previous_answers=previous_answers,
        role_manager=role_manager,
        model_hub=model_hub,
    )

    status = "completed"
    if fallback_used:
        status = "partial"
    if not any(t["status"] == "completed" for t in transcript):
        status = "fallback"

    return {
        "status": status,
        "discussion_id": discussion_id,
        "roles_used": selected_roles,
        "rounds": rounds,
        "transcript": transcript,
        "final_answer": final_answer,
        "warnings": warnings,
        "cost_note": cost_note,
        "fallback_used": fallback_used,
    }


def _build_role_prompt(
    role: str,
    user_message: str,
    round_num: int,
    previous_answers: dict[str, str],
    total_rounds: int,
) -> str:
    """Build the prompt for a specific role in a discussion round."""
    if round_num == 1:
        return (
            f"You are acting in the '{role}' role. "
            f"Provide your best independent analysis of the following request:\n\n"
            f"User request: {user_message}\n\n"
            f"Focus on your role's expertise. Be concise and actionable."
        )
    else:
        other_answers = "\n\n".join(
            f"[{r}]: {a[:500]}" for r, a in previous_answers.items() if a
        )
        return (
            f"You are acting in the '{role}' role. This is round {round_num} of {total_rounds}. "
            f"Review the other roles' answers and improve your own:\n\n"
            f"User request: {user_message}\n\n"
            f"Other answers:\n{other_answers}\n\n"
            f"Provide your refined response. Address any gaps or errors you notice."
        )


def _build_system_prompt(role: str, round_num: int) -> str:
    """Build the system prompt for a role."""
    role_systems = {
        "thinking": "You are a deep reasoning expert. Analyze carefully and provide structured thinking.",
        "coding": "You are a coding expert. Provide precise, implementable solutions.",
        "planning": "You are a planning expert. Create actionable, structured plans.",
        "fast": "You are a quick-response model. Be brief and direct.",
        "default": "You are a helpful assistant. Provide clear, accurate responses.",
    }
    base = role_systems.get(role, role_systems["default"])
    if round_num > 1:
        base += " In this round, review and improve upon previous answers."
    return base


def _synthesize_final_answer(
    final_role: str,
    user_message: str,
    previous_answers: dict[str, str],
    role_manager: ModelRoleManager,
    model_hub: ModelHub,
) -> str:
    """Synthesize the final answer from all role contributions."""
    model_cfg = get_model_for_role(final_role, role_manager)
    if not model_cfg["configured"]:
        model_cfg = get_model_for_role("default", role_manager)

    if not model_cfg["configured"]:
        return "Discussion completed but no model is configured for the final synthesis. Please configure at least a default model in Settings."

    other_answers = "\n\n".join(
        f"[{r}]: {a[:800]}" for r, a in previous_answers.items() if a
    )

    prompt = (
        f"Synthesize the best response from these role contributions:\n\n"
        f"User request: {user_message}\n\n"
        f"Role contributions:\n{other_answers}\n\n"
        f"Provide a clear, comprehensive final answer that combines the best insights."
    )

    try:
        response = model_hub.generate_text(
            prompt=prompt,
            system_prompt="You are synthesizing the best response from multiple expert roles. Be clear, comprehensive, and actionable.",
            provider_name=model_cfg["provider"],
            model=model_cfg["model"],
        )
        if response.get("status") == "completed":
            return response.get("text", "")
    except Exception:
        pass

    if previous_answers:
        best = max(previous_answers.values(), key=len)
        return f"[Discussion synthesized locally]\n\n{best[:1000]}"

    return "Discussion completed but could not generate a final answer."
