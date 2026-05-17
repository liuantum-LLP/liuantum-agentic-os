from __future__ import annotations

from typing import Any

SENSITIVE_TERMS = (
    "password",
    "otp",
    "bank details",
    "bank account",
    "api key",
    "token",
    "confidential",
    "aadhaar",
    "pan",
    "credit card",
)


def detect_sensitive_content(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    matches = [term for term in SENSITIVE_TERMS if term in lower]
    return {
        "sensitive": bool(matches),
        "matches": matches,
        "warning": "Sensitive content detected. Review carefully before publishing." if matches else None,
    }


def safe_preview(text: str, limit: int = 220) -> str:
    if detect_sensitive_content(text)["sensitive"]:
        return "[sensitive redacted]"
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "..."

