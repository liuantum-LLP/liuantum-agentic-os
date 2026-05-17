from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from runtime.config import utc_now
from runtime.db import delete_record, get_record, insert_record, list_records
from runtime.storage import WORKSPACE, read_json, write_json


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) <= 8:
        return "****"
    return f"****{text[-4:]}"


def secret_fingerprint(value: str | None) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


class SecretStore(ABC):
    backend = "base"

    @abstractmethod
    def set_secret(self, name: str, value: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_secret(self, name: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def delete_secret(self, name: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_secrets(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def rotate_secret(self, name: str, new_value: str) -> dict[str, Any]:
        return self.set_secret(name, new_value, {"rotated_at": utc_now()})

    def mask_secret(self, value: str) -> str:
        return mask_secret(value)


class EnvSecretStore(SecretStore):
    backend = "env"

    def __init__(self) -> None:
        self.env = _load_env_files()

    def set_secret(self, name: str, value: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"status": "read_only", "backend": self.backend, "name": name, "message": "Environment secret store is read-only."}

    def get_secret(self, name: str) -> str | None:
        return os.environ.get(name) or self.env.get(name)

    def delete_secret(self, name: str) -> dict[str, Any]:
        return {"status": "read_only", "backend": self.backend, "name": name, "message": "Environment secret store is read-only."}

    def list_secrets(self) -> list[dict[str, Any]]:
        names = sorted(set(os.environ) | set(self.env))
        return [{"name": name, "backend": self.backend, "secret_status": "available", "secret_masked": mask_secret(self.get_secret(name))} for name in names if _looks_secret_name(name)]


class LocalEncryptedSecretStore(SecretStore):
    backend = "local_encrypted"

    def __init__(self, path: Path | None = None) -> None:
        path_value = os.environ.get("LIUANT_SECRET_STORE_PATH")
        self.path = path or (Path(path_value) if path_value else WORKSPACE / "security" / "secrets.enc.json")
        self.key_path = Path(os.environ.get("LIUANT_LOCAL_SECRET_KEY_PATH", str(WORKSPACE / "security" / "local-secret.key")))

    def set_secret(self, name: str, value: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        store = self._read_store()
        encrypted = self._encrypt(value)
        existing = store.get(name, {})
        row = {
            "name": name,
            "backend": self.backend,
            "ciphertext": encrypted["ciphertext"],
            "nonce": encrypted["nonce"],
            "hmac": encrypted["hmac"],
            "metadata": metadata or existing.get("metadata", {}),
            "secret_masked": mask_secret(value),
            "fingerprint": secret_fingerprint(value),
            "created_at": existing.get("created_at") or utc_now(),
            "updated_at": utc_now(),
        }
        store[name] = row
        self._write_store(store)
        self._record_metadata(name, row)
        return self._public(row)

    def get_secret(self, name: str) -> str | None:
        row = self._read_store().get(name)
        if not row:
            return None
        try:
            return self._decrypt(row)
        except Exception:
            return None

    def delete_secret(self, name: str) -> dict[str, Any]:
        store = self._read_store()
        existed = name in store
        store.pop(name, None)
        self._write_store(store)
        delete_record("secret_records", name)
        return {"status": "deleted" if existed else "not_found", "name": name, "backend": self.backend}

    def list_secrets(self) -> list[dict[str, Any]]:
        store = self._read_store()
        for name, row in store.items():
            self._record_metadata(name, row)
        return [self._public(row) for row in store.values()]

    def _read_store(self) -> dict[str, Any]:
        return read_json(self.path, {})

    def _write_store(self, data: dict[str, Any]) -> None:
        write_json(self.path, data)

    def _record_metadata(self, name: str, row: dict[str, Any]) -> None:
        insert_record(
            "secret_records",
            {
                "id": name,
                "name": name,
                "backend": self.backend,
                "secret_status": "stored",
                "secret_masked": row.get("secret_masked", ""),
                "fingerprint": row.get("fingerprint", ""),
                "metadata": row.get("metadata", {}),
                "created_at": row.get("created_at") or utc_now(),
                "updated_at": row.get("updated_at") or utc_now(),
            },
        )

    def _public(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": row.get("name"),
            "backend": self.backend,
            "secret_status": "stored",
            "secret_masked": row.get("secret_masked", ""),
            "fingerprint": row.get("fingerprint", ""),
            "metadata": row.get("metadata", {}),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _key(self) -> bytes:
        passphrase = os.environ.get("LIUANT_SECRET_PASSPHRASE")
        if not passphrase:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.key_path.exists():
                self.key_path.write_text(base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"), encoding="utf-8")
                try:
                    self.key_path.chmod(0o600)
                except OSError:
                    pass
            passphrase = self.key_path.read_text(encoding="utf-8").strip()
        return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), b"liuant-local-secret-store-v1", 120_000, dklen=32)

    def _encrypt(self, value: str) -> dict[str, str]:
        nonce = os.urandom(16)
        key = self._key()
        payload = value.encode("utf-8")
        stream = _keystream(key, nonce, len(payload))
        cipher = bytes(a ^ b for a, b in zip(payload, stream))
        tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        return {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(cipher).decode("ascii"),
            "hmac": base64.b64encode(tag).decode("ascii"),
        }

    def _decrypt(self, row: dict[str, Any]) -> str:
        key = self._key()
        nonce = base64.b64decode(row["nonce"])
        cipher = base64.b64decode(row["ciphertext"])
        expected = base64.b64decode(row["hmac"])
        actual = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, actual):
            raise ValueError("Secret store integrity check failed.")
        stream = _keystream(key, nonce, len(cipher))
        return bytes(a ^ b for a, b in zip(cipher, stream)).decode("utf-8")


class KeyringSecretStore(SecretStore):
    backend = "keyring"

    def __init__(self) -> None:
        try:
            import keyring  # type: ignore
        except Exception:
            keyring = None
        self.keyring = keyring
        self.service = "liuant-agentic-os"

    def available(self) -> bool:
        return self.keyring is not None

    def set_secret(self, name: str, value: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.available():
            return {"status": "not_available", "backend": self.backend, "name": name}
        self.keyring.set_password(self.service, name, value)
        row = {"id": name, "name": name, "backend": self.backend, "secret_status": "stored", "secret_masked": mask_secret(value), "fingerprint": secret_fingerprint(value), "metadata": metadata or {}, "created_at": utc_now(), "updated_at": utc_now()}
        insert_record("secret_records", row)
        return {k: v for k, v in row.items() if k != "id"}

    def get_secret(self, name: str) -> str | None:
        if not self.available():
            return None
        return self.keyring.get_password(self.service, name)

    def delete_secret(self, name: str) -> dict[str, Any]:
        if not self.available():
            return {"status": "not_available", "backend": self.backend, "name": name}
        try:
            self.keyring.delete_password(self.service, name)
        except Exception:
            pass
        delete_record("secret_records", name)
        return {"status": "deleted", "backend": self.backend, "name": name}

    def list_secrets(self) -> list[dict[str, Any]]:
        return [row for row in list_records("secret_records") if row.get("backend") == self.backend]


class SecretManager:
    def __init__(self) -> None:
        keyring = KeyringSecretStore()
        self.write_store: SecretStore = keyring if keyring.available() else LocalEncryptedSecretStore()
        self.env_store = EnvSecretStore()

    @property
    def backend(self) -> str:
        return self.write_store.backend

    def set_secret(self, name: str, value: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.write_store.set_secret(name, value, metadata)

    def get_secret(self, name: str) -> str | None:
        value = self.write_store.get_secret(name)
        if value is not None:
            return value
        return self.env_store.get_secret(name)

    def delete_secret(self, name: str) -> dict[str, Any]:
        return self.write_store.delete_secret(name)

    def rotate_secret(self, name: str, new_value: str) -> dict[str, Any]:
        return self.write_store.rotate_secret(name, new_value)

    def list_secrets(self) -> list[dict[str, Any]]:
        rows = {row["name"]: row for row in list_records("secret_records")}
        for row in self.write_store.list_secrets():
            rows[row["name"]] = row
        return sorted(rows.values(), key=lambda row: row.get("name", ""))

    def status(self) -> dict[str, Any]:
        keyring = KeyringSecretStore()
        secrets = self.list_secrets()
        return {
            "status": "ready",
            "default_backend": self.backend,
            "keyring_available": keyring.available(),
            "local_encrypted_available": True,
            "env_fallback_available": True,
            "stored_secret_count": len(secrets),
            "unmigrated_secret_warnings": self.unmigrated_secret_warnings(),
            "limitations": ["Local encrypted storage is intended for local MVP development. Production should use OS keychain or managed encrypted secret storage."],
        }

    def migrate(self) -> dict[str, Any]:
        migrated: list[str] = []
        for row in list_records("oauth_tokens"):
            updates: dict[str, Any] = {}
            provider = row.get("provider") or row.get("id")
            if row.get("access_token_local"):
                name = f"oauth:{provider}:access_token"
                self.set_secret(name, row["access_token_local"], {"provider": provider, "kind": "access_token"})
                updates["access_token_secret_ref"] = name
                updates["access_token_local"] = ""
                migrated.append(name)
            if row.get("refresh_token_local"):
                name = f"oauth:{provider}:refresh_token"
                self.set_secret(name, row["refresh_token_local"], {"provider": provider, "kind": "refresh_token"})
                updates["refresh_token_secret_ref"] = name
                updates["refresh_token_local"] = ""
                migrated.append(name)
            if updates:
                from runtime.db import update_record

                updates["updated_at"] = utc_now()
                update_record("oauth_tokens", row["id"], updates)
        for row in list_records("connectors"):
            config = {**(row.get("config_json") or {})}
            token = config.get("bot_token_local")
            if token:
                name = f"telegram:{row.get('id')}:bot_token"
                self.set_secret(name, token, {"connector_id": row.get("id"), "provider": row.get("provider")})
                config["bot_token_secret_ref"] = name
                config.pop("bot_token_local", None)
                from runtime.db import update_record

                update_record("connectors", row["id"], {"config_json": config, "updated_at": utc_now()})
                migrated.append(name)
        return {"status": "completed", "migrated_count": len(migrated), "migrated": migrated, "backend": self.backend}

    def unmigrated_secret_warnings(self) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for row in list_records("oauth_tokens"):
            for key in ("access_token_local", "refresh_token_local"):
                if row.get(key):
                    warnings.append({"table": "oauth_tokens", "id": row.get("id"), "field": key})
        for row in list_records("connectors"):
            if (row.get("config_json") or {}).get("bot_token_local"):
                warnings.append({"table": "connectors", "id": row.get("id"), "field": "config_json.bot_token_local"})
        return warnings


def _keystream(key: bytes, nonce: bytes, size: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < size:
        chunks.append(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return b"".join(chunks)[:size]


def _load_env_files() -> dict[str, str]:
    data: dict[str, str] = {}
    root = Path(__file__).resolve().parents[2]
    for path in (root / ".env", root / ".env.local"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _looks_secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in ("token", "secret", "key", "password"))
