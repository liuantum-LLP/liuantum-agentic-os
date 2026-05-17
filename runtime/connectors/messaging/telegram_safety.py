from __future__ import annotations

import re
from typing import Any


SENSITIVE_PATTERNS = (
    "password",
    "otp",
    "api key",
    "token",
    "credit card",
    "aadhaar",
    "pan",
    "bank account",
    "secret",
    "confidential",
)

PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "reveal system prompt",
    "run shell command",
    "delete files",
    "send email",
    "publish post",
    "share api key",
)


def inspect_message(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    sensitive = [pattern for pattern in SENSITIVE_PATTERNS if pattern in lower]
    injection = [pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in lower]
    risk_level = "high" if injection else "medium" if sensitive else "low"
    return {
        "risk_level": risk_level,
        "sensitive": bool(sensitive),
        "sensitive_matches": sensitive,
        "prompt_injection": bool(injection),
        "prompt_injection_matches": injection,
        "warning": _warning(sensitive, injection),
    }


def safe_preview(text: str, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    return value if len(value) <= limit else value[: limit - 1] + "..."


def redacted_text(text: str, safety: dict[str, Any]) -> str:
    if safety.get("sensitive"):
        return "[sensitive telegram message redacted]"
    return text or ""


def safe_error(exc: Exception | str) -> str:
    message = str(exc)
    return re.sub(r"\d{6,}:[A-Za-z0-9_-]{20,}", "****redacted-token", message)


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    return f"****{value[-4:]}" if len(value) > 4 else "****"


def _warning(sensitive: list[str], injection: list[str]) -> str | None:
    warnings: list[str] = []
    if sensitive:
        warnings.append("Sensitive content detected; logs are redacted and approval is required.")
    if injection:
        warnings.append("Prompt injection pattern detected; unsafe instructions were ignored.")
    return " ".join(warnings) or None
