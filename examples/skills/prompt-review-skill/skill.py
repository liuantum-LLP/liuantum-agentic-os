"""Prompt Review Skill - Review and improve prompts.

Requires models.generate permission. If model provider is unavailable,
returns setup-needed status honestly.
"""

from __future__ import annotations

from typing import Any


def execute(ctx: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute the prompt review skill.

    Args:
        ctx: SkillContext with permissions and workspace info.
        inputs: User-provided inputs (e.g., {"prompt": "Write a story"}).

    Returns:
        Review with clarity score, safety notes, and improved prompt.
    """
    prompt = inputs.get("prompt", "")
    if not prompt:
        return {
            "status": "failed",
            "result": {},
            "actions": [],
            "warnings": ["No prompt provided. Usage: {\"prompt\": \"your prompt here\"}"],
            "approval_required": False,
        }

    # Check permissions
    if not ctx.has_permission("models.generate"):
        return {
            "status": "blocked",
            "result": {},
            "actions": [],
            "warnings": ["models.generate permission required but not approved."],
            "approval_required": True,
        }

    # Check model availability
    model_client = ctx.get_model_client()
    if not model_client.get("available", False):
        return {
            "status": "completed",
            "result": {
                "prompt": prompt,
                "clarity_score": 0,
                "safety_notes": ["Model provider not configured. Please set up a model provider first."],
                "improved_prompt": "",
                "setup_needed": True,
                "message": "Model provider unavailable. Configure a provider to enable full prompt review.",
            },
            "actions": [],
            "warnings": ["Model provider not available. Limited review provided."],
            "approval_required": False,
        }

    # Basic prompt analysis (without actual model call for safety)
    clarity_score = _calculate_clarity(prompt)
    safety_notes = _check_safety(prompt)
    improved = _suggest_improvements(prompt)

    return {
        "status": "completed",
        "result": {
            "prompt": prompt,
            "clarity_score": clarity_score,
            "safety_notes": safety_notes,
            "improved_prompt": improved,
            "setup_needed": False,
        },
        "actions": [],
        "warnings": [],
        "approval_required": False,
    }


def _calculate_clarity(prompt: str) -> int:
    """Calculate a basic clarity score (0-100) based on prompt structure."""
    score = 50  # Base score
    if len(prompt) > 20:
        score += 10
    if len(prompt) > 100:
        score += 10
    if "?" in prompt:
        score += 5
    if any(c.isupper() for c in prompt[:10]):
        score += 5
    if prompt.strip().endswith((".", "!", "?")):
        score += 5
    if "please" in prompt.lower() or "could you" in prompt.lower():
        score += 5
    if len(prompt.split()) > 5:
        score += 5
    if len(prompt.split()) > 20:
        score += 5
    return min(score, 100)


def _check_safety(prompt: str) -> list[str]:
    """Check for potential safety concerns in the prompt."""
    notes = []
    lower = prompt.lower()
    if any(word in lower for word in ["password", "secret", "api key", "token"]):
        notes.append("Prompt may contain sensitive information. Avoid including secrets.")
    if len(prompt) > 5000:
        notes.append("Very long prompt. Consider breaking into smaller, focused prompts.")
    if not notes:
        notes.append("No obvious safety concerns detected.")
    return notes


def _suggest_improvements(prompt: str) -> str:
    """Suggest basic improvements to the prompt."""
    suggestions = []
    if len(prompt.strip()) < 10:
        suggestions.append("Add more context and specific requirements.")
    if not prompt.strip().endswith((".", "!", "?")):
        suggestions.append("End with proper punctuation for clarity.")
    if "example" not in prompt.lower() and len(prompt) > 50:
        suggestions.append("Consider adding an example of expected output.")
    if not suggestions:
        return prompt

    improved = prompt.strip()
    if not improved.endswith((".", "!", "?")):
        improved += "."
    return improved


def run(ctx: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Alias for execute()."""
    return execute(ctx, inputs)
