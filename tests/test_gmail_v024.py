import base64
import json

from runtime.action_log import list_external_actions
from runtime.approvals import ApprovalManager
from runtime.connectors.email.gmail_connector import GmailConnector, parse_message
import runtime.connectors.email.gmail_client as gmail_client
from runtime.connectors.email.draft_store import EmailDraftStore
from runtime.connectors.email.base_email import EmailDraft
from runtime.db import get_record, list_records
from runtime.api.app import gmail_status, gmail_oauth_start, email_search, email_recent, email_read, email_summarize, email_draft_reply
from runtime.providers import ModelHub


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def gmail_message(message_id: str = "msg-1", body: str = "Hello from Gmail", filename: str | None = None):
    parts = [{"mimeType": "text/plain", "body": {"data": encoded(body)}}]
    if filename:
        parts.append({"filename": filename, "mimeType": "application/pdf", "body": {"attachmentId": "att-1", "size": 1234}})
    return {
        "id": message_id,
        "threadId": "thread-1",
        "snippet": body[:80],
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "Sender <sender@example.com>"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": "Project update"},
                {"name": "Date", "value": "Sat, 16 May 2026 10:00:00 +0000"},
                {"name": "Message-ID", "value": "<original@example.com>"},
            ],
            "parts": parts,
        },
    }


def authorize(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    connector = GmailConnector()
    start = connector.start_oauth()
    monkeypatch.setattr(gmail_client, "exchange_code", lambda *_args: {"access_token": "access-token-raw", "refresh_token": "refresh-token-raw", "expires_in": 3600, "token_type": "Bearer", "scope": " ".join(connector.required_scopes)})
    monkeypatch.setattr(gmail_client, "get_json", lambda *_args: {"emailAddress": "me@example.com", "messagesTotal": 10})
    callback = connector.handle_callback("code-123", start["state"])
    return connector, callback


def test_gmail_status_when_missing_config(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    status = GmailConnector().get_status()

    assert status["status"] == "missing_client_config"
    assert status["authorized"] is False


def test_gmail_setup_creates_connector_record(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    result = GmailConnector().setup()

    assert result["connector"]["provider"] == "gmail"
    assert result["status"] == "needs_oauth"


def test_oauth_url_generation_does_not_expose_client_secret(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret-raw")

    result = GmailConnector().start_oauth()
    serialized = json.dumps(result)

    assert result["status"] == "oauth_url_ready"
    assert "client-secret-raw" not in serialized
    assert "gmail.compose" in result["authorization_url"]


def test_oauth_callback_stores_token_metadata_safely(monkeypatch):
    connector, callback = authorize(monkeypatch)

    token = connector.store.sanitized("gmail")
    assert callback["status"] == "authorized"
    assert token["token_metadata_json"]["access_token_masked"].endswith("-raw")
    assert "access_token_local" not in token


def test_api_response_does_not_include_tokens(monkeypatch):
    authorize(monkeypatch)

    serialized = json.dumps(gmail_status())

    assert "access-token-raw" not in serialized
    assert "refresh-token-raw" not in serialized


def test_action_logs_do_not_include_tokens(monkeypatch):
    authorize(monkeypatch)

    logs = json.dumps(list_external_actions())

    assert "access-token-raw" not in logs
    assert "refresh-token-raw" not in logs


def test_gmail_test_connection_mocked_success(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(gmail_client, "get_json", lambda *_args: {"emailAddress": "me@example.com", "messagesTotal": 20})

    result = connector.test_connection()

    assert result["success"] is True
    assert result["account_email"] == "me@example.com"


def test_gmail_test_connection_token_expired(monkeypatch):
    connector, _ = authorize(monkeypatch)

    def expired(*_args):
        raise RuntimeError("401 expired")

    monkeypatch.setattr(gmail_client, "get_json", expired)
    result = connector.test_connection()

    assert result["status"] == "token_expired"


def test_gmail_search_mocked_response_returns_safe_summaries(monkeypatch):
    connector, _ = authorize(monkeypatch)

    def fake_get(url, _token):
        if "messages?" in url:
            return {"messages": [{"id": "msg-1"}]}
        return gmail_message()

    monkeypatch.setattr(gmail_client, "get_json", fake_get)
    result = connector.search_messages("newer_than:7d")

    assert result["status"] == "completed"
    assert result["results"][0]["subject"] == "Project update"


def test_gmail_recent_mocked_response_works(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(connector, "search_messages", lambda query, max_results=10: {"status": "completed", "query": query, "results": []})

    assert connector.recent_messages()["query"] == "newer_than:7d"


def test_gmail_read_mocked_response_returns_message_detail(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(gmail_client, "get_json", lambda *_args: gmail_message(body="Plain text body"))

    result = connector.read_message("msg-1")

    assert result["message"]["plain_text_body"] == "Plain text body"
    assert result["message"]["from"] == "Sender <sender@example.com>"


def test_gmail_read_does_not_log_full_body(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(gmail_client, "get_json", lambda *_args: gmail_message(body="Very private full email body"))
    connector.read_message("msg-1")

    assert "Very private full email body" not in json.dumps(list_external_actions())


def test_gmail_summarize_uses_local_fallback_when_no_provider(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(connector, "read_message", lambda _id: {"status": "completed", "message": parse_message(gmail_message(body="This is a long body"))})
    monkeypatch.setattr(ModelHub, "generate_text", lambda *_args, **_kwargs: {"status": "needs_provider_setup", "provider": "openai", "model": "x"})

    result = connector.summarize_message("msg-1")

    assert result["status"] == "local_fallback"
    assert result["fallback_used"] is True


def test_gmail_summarize_uses_mocked_model_hub(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(connector, "read_message", lambda _id: {"status": "completed", "message": parse_message(gmail_message(body="Summarize me"))})
    monkeypatch.setattr(ModelHub, "generate_text", lambda *_args, **_kwargs: {"status": "completed", "text": "AI summary", "provider": "openai", "model": "gpt-test", "fallback_used": False})

    result = connector.summarize_message("msg-1")

    assert result["summary"] == "AI summary"
    assert result["provider_used"] == "openai"


def test_gmail_draft_reply_mocked_success_creates_records(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(connector, "read_message", lambda _id: {"status": "completed", "message": parse_message(gmail_message(body="Please reply"))})
    monkeypatch.setattr(gmail_client, "post_json", lambda *_args: {"id": "gmail-draft-1"})

    result = connector.create_draft_reply("msg-1", "Thanks for the update.")

    assert result["status"] == "gmail_draft_created"
    assert get_record("email_drafts", result["local_draft_id"])["gmail_draft_id"] == "gmail-draft-1"
    assert get_record("approvals", result["approval_id"])["action_type"] == "email_send"
    assert any(log["action_type"] == "gmail_draft_created" for log in list_external_actions())


def test_gmail_draft_reply_provider_error_does_not_claim_created(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(connector, "read_message", lambda _id: {"status": "completed", "message": parse_message(gmail_message(body="Please reply"))})

    def fail(*_args):
        raise RuntimeError("gmail unavailable")

    monkeypatch.setattr(gmail_client, "post_json", fail)
    result = connector.create_draft_reply("msg-1", "Body")

    assert result["status"] == "provider_error"
    assert "gmail_draft_id" not in result


def test_send_approved_remains_no_send():
    draft = EmailDraftStore().create(EmailDraft(to=["a@example.com"], subject="Hello", body="Body", connector_id="gmail"))
    approved = EmailDraftStore().approve(draft["id"])

    result = EmailDraftStore().mark_send_ready(approved["id"], "approval-1")

    assert result["status"] == "send_ready_not_sent"


def test_sensitive_content_warning_works(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(connector, "read_message", lambda _id: {"status": "completed", "message": parse_message(gmail_message(body="My OTP is 123456"))})
    monkeypatch.setattr(gmail_client, "post_json", lambda *_args: {"id": "gmail-draft-2"})
    result = connector.create_draft_reply("msg-1", "Contains secret")

    draft = get_record("email_drafts", result["local_draft_id"])
    assert draft["sensitive_warning"]["sensitive"] is True


def test_attachment_metadata_returned_no_download(monkeypatch):
    connector, _ = authorize(monkeypatch)
    monkeypatch.setattr(gmail_client, "get_json", lambda *_args: gmail_message(filename="report.pdf"))

    result = connector.read_message("msg-1")

    assert result["message"]["attachments"][0]["filename"] == "report.pdf"
    assert result["message"]["attachments"][0]["download_supported"] is False


def test_email_api_routes_work_with_missing_oauth():
    assert email_search({"query": "newer_than:7d"})["status"] in {"needs_oauth", "completed"}
    assert email_recent({})["status"] in {"needs_oauth", "completed"}
    assert email_read({"message_id": "msg-1"})["status"] in {"needs_oauth", "completed"}
    assert email_summarize({"message_id": "msg-1"})["status"] in {"needs_oauth", "completed", "local_fallback"}
    assert email_draft_reply({"message_id": "msg-1", "body": "Body"})["status"] in {"needs_oauth", "gmail_draft_created", "provider_error"}
