import json
import subprocess
import sys

from runtime.action_log import list_external_actions
from runtime.approvals import ApprovalManager
from runtime.connectors.email.oauth_store import OAuthTokenStore
from runtime.connectors.social import social_api
from runtime.connectors.social.linkedin_connector import LinkedInConnector
from runtime.connectors.social.x_connector import XConnector
from runtime.db import get_record, update_record
from runtime.workflows import SocialContentWorkflow


def test_linkedin_status_missing_config(monkeypatch):
    monkeypatch.delenv("LINKEDIN_CLIENT_ID", raising=False)
    monkeypatch.delenv("LINKEDIN_CLIENT_SECRET", raising=False)

    status = LinkedInConnector().get_status()

    assert status["status"] == "missing_client_config"


def test_x_status_missing_config(monkeypatch):
    monkeypatch.delenv("X_CLIENT_ID", raising=False)
    monkeypatch.delenv("X_CLIENT_SECRET", raising=False)

    status = XConnector().get_status()

    assert status["status"] == "missing_client_config"


def test_oauth_url_does_not_expose_client_secret(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "linkedin-client")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "linkedin-secret-value")

    result = LinkedInConnector().start_oauth()

    assert result["status"] == "oauth_url_ready"
    assert "linkedin-secret-value" not in result["authorization_url"]


def test_oauth_callback_stores_masked_token_metadata(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "linkedin-client")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "linkedin-secret-value")
    connector = LinkedInConnector()
    start = connector.start_oauth()

    monkeypatch.setattr(social_api, "exchange_code", lambda *_args, **_kwargs: {"access_token": "access-token-1234", "refresh_token": "refresh-token-5678", "scope": "openid profile w_member_social", "token_type": "Bearer", "expires_in": 3600})
    monkeypatch.setattr(social_api, "get_json", lambda *_args, **_kwargs: {"id": "person-1", "name": "Liuant Admin"})

    result = connector.handle_callback("code-1", start["state"])
    serialized = json.dumps(result)
    token = OAuthTokenStore().sanitized("linkedin")

    assert result["status"] == "authorized"
    assert token["token_metadata_json"]["access_token_masked"].endswith("1234")
    assert "access-token-1234" not in serialized
    assert "refresh-token-5678" not in serialized
    assert "linkedin-secret-value" not in serialized


def test_action_logs_do_not_expose_social_tokens(monkeypatch):
    monkeypatch.setenv("X_CLIENT_ID", "x-client")
    monkeypatch.setenv("X_CLIENT_SECRET", "x-secret-value")
    connector = XConnector()
    start = connector.start_oauth()
    monkeypatch.setattr(social_api, "exchange_code", lambda *_args, **_kwargs: {"access_token": "x-access-token-1234", "refresh_token": "x-refresh-token-5678", "scope": "tweet.read users.read tweet.write", "token_type": "Bearer"})
    monkeypatch.setattr(social_api, "get_json", lambda *_args, **_kwargs: {"data": {"id": "x-1", "username": "liuant"}})

    connector.handle_callback("code", start["state"])
    serialized = json.dumps(list_external_actions())

    assert "x-access-token-1234" not in serialized
    assert "x-refresh-token-5678" not in serialized


def test_linkedin_test_mocked_success(monkeypatch):
    connector = LinkedInConnector()
    connector.setup()
    OAuthTokenStore().save("linkedin", "linkedin", {"access_token": "token"}, account_email="Liuant", scopes=["openid", "profile", "w_member_social"])
    monkeypatch.setattr(social_api, "get_json", lambda *_args, **_kwargs: {"id": "person-1", "name": "Liuant Admin"})

    result = connector.test_connection()

    assert result["success"] is True
    assert result["status"] == "authorized"


def test_x_test_mocked_success(monkeypatch):
    connector = XConnector()
    connector.setup()
    OAuthTokenStore().save("x", "x", {"access_token": "token"}, account_email="@liuant", scopes=["tweet.read", "users.read", "tweet.write"])
    monkeypatch.setattr(social_api, "get_json", lambda *_args, **_kwargs: {"data": {"id": "x-1", "username": "liuant"}})

    result = connector.test_connection()

    assert result["success"] is True


def test_linkedin_publish_blocked_without_approval():
    draft = SocialContentWorkflow().create_draft("linkedin", "Approved later")

    result = LinkedInConnector().publish_approved_draft(draft["id"])

    assert result["status"] == "publish_blocked"
    assert result["published"] is False


def test_x_publish_blocked_without_manual_publish_enabled():
    draft = _approved_draft("x")
    _authorized_connector("x", manual=False, scopes=["tweet.read", "users.read", "tweet.write"])

    result = XConnector().publish_approved_draft(draft["id"])

    assert result["status"] == "manual_publish_disabled"


def test_publish_blocked_when_connector_disabled():
    draft = _approved_draft("linkedin")
    _authorized_connector("linkedin", enabled=False, manual=True, scopes=["openid", "profile", "w_member_social"])

    result = LinkedInConnector().publish_approved_draft(draft["id"])

    assert result["status"] == "publish_blocked"


def test_publish_blocked_when_scope_unavailable():
    draft = _approved_draft("x")
    _authorized_connector("x", manual=True, scopes=["tweet.read", "users.read"])

    result = XConnector().publish_approved_draft(draft["id"])

    assert result["status"] == "capability_unavailable"


def test_publish_approved_mocked_success_stores_external_post_id(monkeypatch):
    draft = _approved_draft("x")
    _authorized_connector("x", manual=True, scopes=["tweet.read", "users.read", "tweet.write"])
    monkeypatch.setattr(social_api, "post_json", lambda *_args, **_kwargs: {"data": {"id": "tweet-123"}})

    result = XConnector().publish_approved_draft(draft["id"])
    saved = get_record("social_drafts", draft["id"])

    assert result["status"] == "published"
    assert saved["external_post_id"] == "tweet-123"
    assert saved["publish_status"] == "published"


def test_provider_error_does_not_claim_published(monkeypatch):
    draft = _approved_draft("x")
    _authorized_connector("x", manual=True, scopes=["tweet.read", "users.read", "tweet.write"])

    def fail(*_args, **_kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(social_api, "post_json", fail)
    result = XConnector().publish_approved_draft(draft["id"])

    assert result["status"] == "provider_error"
    assert result["published"] is False


def test_sensitive_content_requires_confirmation():
    draft = _approved_draft("linkedin", "Confidential password and API key should not publish")
    _authorized_connector("linkedin", manual=True, scopes=["openid", "profile", "w_member_social"])

    result = LinkedInConnector().publish_approved_draft(draft["id"])

    assert result["status"] == "sensitive_confirmation_required"
    assert result["published"] is False


def test_bulk_publish_safety_limit():
    result = SocialContentWorkflow().publish_approved_bulk(["a", "b", "c", "d", "e", "f"], "x")

    assert result["status"] == "bulk_publish_blocked"


def test_social_drafts_preserve_draft_only_behavior():
    draft = SocialContentWorkflow().create_draft("linkedin", "Draft-only post")

    assert draft["status"] == "draft"
    assert draft["publish_status"] == "draft"


def test_cli_social_linkedin_status_works():
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "social", "linkedin", "status"], capture_output=True, text=True, check=True)

    assert "Liuant Social" in result.stdout
    assert "missing_client_config" in result.stdout


def _approved_draft(platform: str, text: str = "Approved post") -> dict:
    workflow = SocialContentWorkflow()
    draft = workflow.create_draft(platform, text)
    approval = ApprovalManager().create("social_publish", draft, platform)
    update_record("social_drafts", draft["id"], {"approval_id": approval["id"]})
    ApprovalManager().decide(approval["id"], "approved")
    return workflow.approve_draft(draft["id"])


def _authorized_connector(platform: str, enabled: bool = True, manual: bool = True, scopes: list[str] | None = None) -> dict:
    connector = LinkedInConnector() if platform == "linkedin" else XConnector()
    connector.setup()
    OAuthTokenStore().save(platform, platform, {"access_token": f"{platform}-token"}, account_email=platform, scopes=scopes or [])
    row = get_record("connectors", platform)
    config = {**(row.get("config_json") or {}), "manual_publish_enabled": manual, "account_name": platform}
    return update_record("connectors", platform, {"status": "authorized", "enabled": enabled, "config_json": config, "config": {"manual_publish_enabled": manual}, "scopes_json": scopes or [], "scopes": scopes or []})
