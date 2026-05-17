from __future__ import annotations

import re
from typing import Any


SENSITIVE_RE = re.compile(r"\b(password|otp|credit card|aadhaar|pan|bank account|api key|secret|confidential|token)\b", re.IGNORECASE)


def detect_sensitive_content(text: str | None) -> dict[str, Any]:
    text = text or ""
    matches = sorted({match.group(1).lower() for match in SENSITIVE_RE.finditer(text)})
    return {"sensitive": bool(matches), "matches": matches, "warning": "Sensitive content detected. Review carefully before creating or approving drafts." if matches else None}


def safe_preview(text: str | None, limit: int = 180) -> str:
    text = (text or "").replace("\n", " ").strip()
    if detect_sensitive_content(text)["sensitive"]:
        return "[sensitive redacted]"
    return text[:limit]


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    text = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
