from __future__ import annotations

import json
from types import SimpleNamespace

from cli.liuant import dispatch
from runtime.action_log import log_external_action
from runtime.backup import BackupManager
from runtime.connectors.email.oauth_store import OAuthTokenStore
from runtime.db import get_record, insert_record, list_records
from runtime.env_validation import EnvironmentValidator
from runtime.exports import export_image_prompt_markdown
from runtime.generation.image import ImageGenerationManager
from runtime.providers import ModelHub
from runtime.security_audit import audit_secrets
from runtime.verification import VerificationCenter


def test_verify_status_empty_state():
    status = VerificationCenter().status()

    assert status["status"] == "empty"
    assert status["count"] == 0


def test_provider_verification_missing_key():
    result = VerificationCenter().verify_provider("openai")

    assert result["category"] == "text"
    assert result["target"] == "openai"
    assert result["status"] in {"needs_provider_setup", "missing_key"}
    assert not result["capability_verified"]


def test_openai_text_verification_mocked_success(monkeypatch):
    def fake_generate_text(self, prompt, system_prompt=None, provider_name=None, model=None, temperature=0.7, max_tokens=None, workspace_name=None, metadata=None):
        return {"status": "completed", "provider": provider_name, "model": "gpt-test", "text": "hello", "error": None, "usage": {}, "fallback_used": False, "fallback_provider": None}

    monkeypatch.setattr(ModelHub, "generate_text", fake_generate_text)
    result = VerificationCenter().verify_provider("openai")

    assert result["status"] == "completed"
    assert result["capability_verified"]


def test_telegram_verification_mocked_getme(monkeypatch):
    from runtime.connectors.messaging.telegram_connector import TelegramConnector

    monkeypatch.setattr(TelegramConnector, "get_status", lambda self: {"status": "configured", "configured": True, "setup_instructions": []})
    monkeypatch.setattr(TelegramConnector, "test_connection", lambda self: {"status": "configured", "success": True, "bot_username": "liuant_bot"})

    result = VerificationCenter().verify_telegram()

    assert result["status"] == "configured"
    assert result["authenticated"]


def test_gmail_verification_mocked_profile(monkeypatch):
    connector = __import__("runtime.connectors.email.gmail_connector", fromlist=["GmailConnector"]).GmailConnector
    monkeypatch.setattr(connector, "get_status", lambda self: {"status": "authorized", "configured": True, "authorized": True, "setup_instructions": [], "account_email": "user@example.com"})
    monkeypatch.setattr(connector, "test_connection", lambda self: {"status": "authorized", "success": True, "account_email": "user@example.com"})

    result = VerificationCenter().verify_gmail()

    assert result["status"] == "authorized"
    assert result["capability_verified"]


def test_replicate_verification_missing_model(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_fakeverifier")
    hub = ModelHub()
    hub.ensure_defaults()

    result = VerificationCenter().verify_provider("replicate_video")

    assert result["status"] == "needs_model_setup"
    assert "REPLICATE_API_TOKEN" not in json.dumps(result)


def test_secret_audit_detects_raw_fake_token():
    log_external_action("test_secret", "failed", {"token": "sk-thisisrawandbad123456"})

    result = audit_secrets()

    assert result["status"] == "failed"
    assert any(finding["area"] == "action_logs" for finding in result["findings"])


def test_secret_audit_accepts_masked_values():
    log_external_action("test_secret_masked", "ok", {"token": "****1234"})

    result = audit_secrets()

    assert not any(finding.get("record_id") for finding in result["findings"] if finding["message"].startswith("Action log") and finding.get("record_id") == "test_secret_masked")


def test_env_missing_lists_names_only():
    result = EnvironmentValidator().missing()

    assert "variables" in result
    assert all("=" not in item for item in result["variables"])


def test_backup_create_excludes_env_and_raw_tokens(monkeypatch):
    OAuthTokenStore().save("gmail", "gmail", {"access_token": "ya29.rawtokenvalue", "refresh_token": "refresh-raw-token"})

    backup = BackupManager().create()
    snapshot = __import__("pathlib").Path(backup["snapshot_path"]).read_text(encoding="utf-8")

    assert backup["status"] == "created"
    assert ".env" in backup["excluded"]
    assert "ya29.rawtokenvalue" not in snapshot


def test_backup_metadata_created():
    backup = BackupManager().create()

    saved = get_record("backups", backup["id"])
    assert saved["id"] == backup["id"]


def test_verification_results_stored():
    result = VerificationCenter().verify_storage()

    rows = list_records("verification_results")
    assert any(row["id"] == result["id"] for row in rows)


def test_api_verify_status_works():
    api_app = __import__("runtime.api.app", fromlist=["verify_status"])

    status = api_app.verify_status()

    assert "status" in status


def test_cli_env_check_works():
    result = dispatch(SimpleNamespace(area="env", command="check", args=[]))

    assert result["status"] == "ok"


def test_env_file_export_attempt_is_audited():
    job = ImageGenerationManager().generate("audit image")
    path = export_image_prompt_markdown(job["id"])
    insert_record(
        "exported_files",
        {
            "id": "bad-env-export",
            "workspace_name": "default",
            "export_type": "env",
            "source_table": "settings",
            "source_id": "env",
            "file_path": ".env",
            "format": "text",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )

    result = audit_secrets()

    assert path
    assert any(finding["area"] == "exports" for finding in result["findings"])
