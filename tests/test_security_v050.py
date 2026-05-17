from datetime import datetime, timedelta, timezone
import json

from runtime.action_log import log_external_action
from runtime.api.app import auth_status, secrets_list, secrets_migrate
from runtime.backup import BackupManager
from runtime.config import SettingsManager, utc_now
from runtime.connectors.email.oauth_store import OAuthTokenStore
from runtime.db import get_record, insert_record
from runtime.security import AuthManager, SecretManager
from runtime.security.auth import public_api_path
from runtime.security.secret_store import EnvSecretStore, LocalEncryptedSecretStore, mask_secret
from runtime.security_audit import audit_secrets


def test_secret_store_masks_secrets():
    assert mask_secret("short") == "****"
    assert mask_secret("secret-value-1234") == "****1234"


def test_env_secret_store_is_read_only(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value-123456")
    store = EnvSecretStore()

    result = store.set_secret("OPENAI_API_KEY", "new-value")

    assert result["status"] == "read_only"
    assert store.get_secret("OPENAI_API_KEY") == "sk-test-value-123456"


def test_local_encrypted_store_round_trip(tmp_path):
    store = LocalEncryptedSecretStore(tmp_path / "secrets.enc.json")

    saved = store.set_secret("gmail:refresh", "refresh-token-raw", {"provider": "gmail"})
    value = store.get_secret("gmail:refresh")
    deleted = store.delete_secret("gmail:refresh")

    assert saved["secret_masked"].endswith("-raw")
    assert value == "refresh-token-raw"
    assert "refresh-token-raw" not in (tmp_path / "secrets.enc.json").read_text(encoding="utf-8")
    assert deleted["status"] == "deleted"


def test_oauth_token_save_stores_secret_refs_not_raw_tokens():
    OAuthTokenStore().save("gmail", "gmail", {"access_token": "access-token-raw", "refresh_token": "refresh-token-raw"})
    row = get_record("oauth_tokens", "gmail")

    assert row["access_token_secret_ref"] == "oauth:gmail:access_token"
    assert row["refresh_token_secret_ref"] == "oauth:gmail:refresh_token"
    assert row["access_token_local"] == ""
    assert OAuthTokenStore().get("gmail")["access_token_local"] == "access-token-raw"


def test_secret_migration_replaces_raw_token_fields():
    insert_record("oauth_tokens", {"id": "legacy", "provider": "legacy", "access_token_local": "legacy-access-raw", "refresh_token_local": "legacy-refresh-raw", "status": "authorized", "created_at": utc_now(), "updated_at": utc_now()})

    result = SecretManager().migrate()
    row = get_record("oauth_tokens", "legacy")

    assert result["migrated_count"] == 2
    assert row["access_token_local"] == ""
    assert row["access_token_secret_ref"] == "oauth:legacy:access_token"
    assert OAuthTokenStore().get("legacy")["refresh_token_local"] == "legacy-refresh-raw"


def test_api_secret_responses_do_not_include_raw_migrated_secrets():
    OAuthTokenStore().save("gmail", "gmail", {"access_token": "api-access-raw", "refresh_token": "api-refresh-raw"})

    serialized = json.dumps({"secrets": secrets_list(), "migrate": secrets_migrate()})

    assert "api-access-raw" not in serialized
    assert "api-refresh-raw" not in serialized


def test_auth_token_generated_and_hash_stored():
    result = AuthManager().token()
    setting = SettingsManager().get("local_api_token_hash")

    assert result["token"].startswith("liuant_")
    assert setting["value"]
    assert result["token"] not in setting["value"]


def test_protected_endpoint_policy_rejects_missing_token():
    assert public_api_path("/api/auth/status") is True
    assert public_api_path("/api/secrets/status") is False
    assert AuthManager().authorize(None, None) is False


def test_protected_endpoint_policy_accepts_valid_token():
    token = AuthManager().token()["token"]

    assert AuthManager().authorize(f"Bearer {token}", None) is True


def test_invalid_token_rejected():
    AuthManager().token()

    assert AuthManager().authorize("Bearer wrong-token", None) is False


def test_session_login_creates_session():
    manager = AuthManager()
    token = manager.token()["token"]

    result = manager.login(token, "pytest")

    assert result["authenticated"] is True
    assert manager.validate_session(result["session_token"]) is True


def test_session_expiry_rejects_request():
    token = "expired-session"
    insert_record("sessions", {"id": "expired", "session_token_hash": __import__("hashlib").sha256(token.encode()).hexdigest(), "created_at": utc_now(), "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), "last_seen_at": utc_now(), "user_agent_hash": "", "status": "active", "updated_at": utc_now()})

    assert AuthManager().validate_session(token) is False
    assert get_record("sessions", "expired")["status"] == "expired"


def test_token_rotation_invalidates_old_token():
    manager = AuthManager()
    old = manager.token()["token"]
    manager.rotate_token()

    assert manager.validate_token(old) is False


def test_backup_excludes_encrypted_secret_store_by_default():
    SecretManager().set_secret("demo", "secret-token-raw")
    backup = BackupManager().create()

    assert backup["status"] == "created"
    assert "encrypted secret store" in backup["excluded"]
    assert "secret-token-raw" not in __import__("pathlib").Path(backup["snapshot_path"]).read_text(encoding="utf-8")


def test_backup_include_encrypted_secrets_requires_confirm():
    blocked = BackupManager().create(include_encrypted_secrets=True, confirm=False)
    allowed = BackupManager().create(include_encrypted_secrets=True, confirm=True)

    assert blocked["status"] == "blocked"
    assert allowed["include_encrypted_secrets"] is True


def test_secret_audit_passes_after_migration():
    OAuthTokenStore().save("gmail", "gmail", {"access_token": "not-logged-access-token", "refresh_token": "not-logged-refresh-token"})
    SecretManager().migrate()
    log_external_action("test", "ok", {"token": "****1234"})

    result = audit_secrets()

    assert result["status"] == "passed"


def test_auth_status_api_shape():
    result = auth_status()

    assert "local_auth_enabled" in result
