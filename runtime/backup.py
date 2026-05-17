from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.config import utc_now
from runtime.db import TABLES, insert_record, list_records
from runtime.storage import WORKSPACE


SECRET_KEYS = {"access_token_local", "refresh_token_local", "bot_token_local", "api_key", "client_secret", "client_secret_local"}


class BackupManager:
    def __init__(self) -> None:
        self.backup_dir = WORKSPACE / "backups"

    def create(self, include_secrets: bool = False, confirm: bool = False, include_encrypted_secrets: bool = False) -> dict[str, Any]:
        include_secrets = include_secrets or include_encrypted_secrets
        if include_secrets and not confirm:
            return {"status": "blocked", "message": "Secret-inclusive backups require explicit confirmation."}
        backup_id = str(uuid4())
        target = self.backup_dir / backup_id
        target.mkdir(parents=True, exist_ok=True)
        snapshot = {}
        for table in sorted(TABLES - {"backups"}):
            snapshot[table] = [row if include_secrets else self._sanitize(row) for row in list_records(table)]
        snapshot_path = target / "sqlite-sanitized-snapshot.json"
        snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
        if include_encrypted_secrets:
            secret_store = WORKSPACE / "security" / "secrets.enc.json"
            if secret_store.exists():
                (target / "secrets.enc.json").write_bytes(secret_store.read_bytes())
        metadata = {
            "id": backup_id,
            "status": "created",
            "path": str(target),
            "snapshot_path": str(snapshot_path),
            "include_secrets": bool(include_secrets),
            "include_encrypted_secrets": bool(include_encrypted_secrets),
            "excluded": [".env", ".env.local", "raw provider keys", "raw OAuth tokens", "encrypted secret store"] if not include_secrets else [".env", ".env.local", "raw provider keys", "raw OAuth tokens"],
            "created_at": utc_now(),
        }
        (target / "backup-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return insert_record("backups", metadata)

    def list(self) -> list[dict[str, Any]]:
        return list_records("backups")

    def restore(self, backup_id: str, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "blocked", "message": "Restore requires --confirm."}
        return {"status": "not_implemented", "backup_id": backup_id, "message": "Safe restore workflow is intentionally manual in this MVP."}

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            clean = {}
            for key, item in value.items():
                lowered = key.lower()
                if lowered in SECRET_KEYS or lowered.endswith("_token") or "secret" in lowered:
                    clean[key] = "[redacted]"
                else:
                    clean[key] = self._sanitize(item)
            return clean
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        return value
