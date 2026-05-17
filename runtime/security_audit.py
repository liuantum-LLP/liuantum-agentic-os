from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.config import ExportTracker, utc_now
from runtime.db import insert_record, list_records
from runtime.storage import ROOT, WORKSPACE


SECRET_PATTERNS = [
    re.compile(r"(?<![A-Za-z])sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"r8_[A-Za-z0-9_\-]{8,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ya29\.[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}"),
]


class SecretAudit:
    def run(self) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        findings.extend(self._scan_action_logs())
        findings.extend(self._scan_exports())
        findings.extend(self._check_docs())
        status = "passed" if not any(row["severity"] in {"high", "critical"} for row in findings) else "failed"
        return {"status": status, "finding_count": len(findings), "findings": findings, "created_at": utc_now()}

    def _scan_action_logs(self) -> list[dict[str, Any]]:
        findings = []
        for row in list_records("action_logs"):
            text = json.dumps(row, sort_keys=True)
            if self._has_raw_secret(text):
                findings.append(
                    {
                        "id": str(uuid4()),
                        "severity": "critical",
                        "area": "action_logs",
                        "record_id": row.get("id"),
                        "message": "Action log appears to contain a raw secret or token.",
                        "suggested_fix": "Remove the log row or replace the secret with a masked fingerprint.",
                    }
                )
        return findings

    def _scan_exports(self) -> list[dict[str, Any]]:
        findings = []
        for row in ExportTracker().list():
            path = Path(row.get("file_path", ""))
            try:
                resolved = path.resolve()
                resolved.relative_to(ROOT.resolve())
            except Exception:
                findings.append(
                    {
                        "id": str(uuid4()),
                        "severity": "high",
                        "area": "exports",
                        "record_id": row.get("id"),
                        "message": "Export path is outside the Liuant workspace tree.",
                        "suggested_fix": "Regenerate the export under workspace/outputs.",
                    }
                )
                continue
            if path.name in {".env", ".env.local"} or "token" in path.name.lower() or "key" in path.name.lower():
                findings.append(
                    {
                        "id": str(uuid4()),
                        "severity": "high",
                        "area": "exports",
                        "record_id": row.get("id"),
                        "message": "Export path looks like a secret-bearing file.",
                        "suggested_fix": "Do not export environment or token files.",
                    }
                )
            if path.exists() and path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")[:200_000]
                except Exception:
                    text = ""
                if self._has_raw_secret(text):
                    findings.append(
                        {
                            "id": str(uuid4()),
                            "severity": "critical",
                            "area": "exports",
                            "record_id": row.get("id"),
                            "message": "Export content appears to contain a raw secret.",
                            "suggested_fix": "Delete the export and regenerate with secret redaction.",
                        }
                    )
        return findings

    def _check_docs(self) -> list[dict[str, Any]]:
        security_doc = ROOT / "docs" / "SECURITY.md"
        if not security_doc.exists() or "Production requires OS keychain or encrypted secret storage" not in security_doc.read_text(encoding="utf-8", errors="ignore"):
            return [
                {
                    "id": str(uuid4()),
                    "severity": "medium",
                    "area": "docs",
                    "message": "Local token storage production warning is missing.",
                    "suggested_fix": "Document the local MVP token storage limitation.",
                }
            ]
        return []

    def _has_raw_secret(self, text: str) -> bool:
        normalized = text or ""
        if "****" in normalized and not any(pattern.search(normalized.replace("****", "")) for pattern in SECRET_PATTERNS):
            return False
        return any(pattern.search(normalized) for pattern in SECRET_PATTERNS)


def audit_secrets() -> dict[str, Any]:
    return SecretAudit().run()


def store_audit_result(result: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": str(uuid4()),
        "category": "security",
        "target": "secret_audit",
        "status": result["status"],
        "configured": True,
        "reachable": True,
        "authenticated": True,
        "capability_verified": result["status"] == "passed",
        "error_redacted": "" if result["status"] == "passed" else f"{result['finding_count']} findings",
        "setup_instructions_json": [],
        "metadata_json": {"finding_count": result["finding_count"], "findings": result["findings"]},
        "created_at": utc_now(),
    }
    return insert_record("verification_results", row)
