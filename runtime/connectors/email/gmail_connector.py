from __future__ import annotations

import base64
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.approvals import ApprovalManager
from runtime.config import utc_now
from runtime.connectors.email import gmail_client
from runtime.connectors.email.base_email import EmailCapabilities, EmailConnector, EmailDraft
from runtime.connectors.email.draft_store import EmailDraftStore
from runtime.connectors.email.email_safety import detect_sensitive_content, safe_preview, strip_html
from runtime.connectors.email.oauth_store import OAuthTokenStore, mask_secret
from runtime.db import insert_record, list_records, update_record
from runtime.providers import ModelHub


SCOPES = ("https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose")
DEFAULT_REDIRECT_URI = "http://localhost:8765/api/email/gmail/oauth/callback"


class GmailConnector(EmailConnector):
    provider = "gmail"
    display_name = "Gmail / Google Workspace Gmail"
    oauth_docs_url = "https://developers.google.com/identity/protocols/oauth2"
    api_docs_url = "https://developers.google.com/gmail/api"
    required_scopes = SCOPES
    optional_scopes = ()
    warnings = (
        "Only Gmail read and compose scopes are requested.",
        "Sending is disabled in v0.2.6.",
        "Local token storage is for MVP development only.",
        "Production requires OS keychain or encrypted secret storage.",
    )
    capabilities = EmailCapabilities(can_send=False)

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.store = OAuthTokenStore()

    def get_status(self) -> dict[str, Any]:
        connector = self._connector()
        token = self.store.sanitized("gmail")
        configured = bool(_env("GOOGLE_CLIENT_ID") and _env("GOOGLE_CLIENT_SECRET"))
        if not configured:
            status = "missing_client_config"
        elif token and token.get("status") == "authorized":
            status = "authorized"
        elif connector:
            status = connector.get("status", "needs_oauth")
        else:
            status = "not_configured"
        return {
            "status": status,
            "configured": configured,
            "authorized": status == "authorized",
            "account_email": token.get("account_email") if token else None,
            "scopes": list(SCOPES),
            "token_expires_at": token.get("expires_at") if token else None,
            "token_metadata": token.get("token_metadata_json") if token else None,
            "connector_id": connector.get("id") if connector else None,
            "setup_instructions": self._setup_instructions(configured),
            "send_enabled": False,
        }

    def setup(self) -> dict[str, Any]:
        connector = self._connector()
        if not connector:
            connector = insert_record("connectors", {
                "id": "gmail",
                "channel": "email",
                "provider": "gmail",
                "name": "Gmail",
                "status": "needs_oauth",
                "config_json": {"redirect_uri": _redirect_uri()},
                "scopes_json": list(SCOPES),
                "assigned_agent_slug": "email-assistant-agent",
                "permission_mode": "safe",
                "last_tested_at": None,
                "enabled": False,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "connector_type": "email",
                "display_name": "Gmail",
                "scopes": list(SCOPES),
                "config": {"redirect_uri": _redirect_uri()},
            })
        status = "needs_oauth" if self.get_status()["configured"] else "missing_client_config"
        connector = update_record("connectors", connector["id"], {"status": status, "scopes_json": list(SCOPES), "scopes": list(SCOPES), "updated_at": utc_now()})
        return {"status": status, "connector": self._sanitize_connector(connector), "gmail": self.get_status()}

    def start_oauth(self) -> dict[str, Any]:
        setup = self.setup()
        if not self.get_status()["configured"]:
            return {"status": "missing_client_config", "authorization_url": None, "setup_instructions": self._setup_instructions(False)}
        state = str(uuid4())
        connector = self._connector()
        update_record("connectors", connector["id"], {"status": "oauth_url_ready", "config_json": {"oauth_state": state, "redirect_uri": _redirect_uri()}, "config": {"oauth_state": state, "redirect_uri": _redirect_uri()}, "updated_at": utc_now()})
        query = urllib.parse.urlencode(
            {
                "client_id": _env("GOOGLE_CLIENT_ID"),
                "redirect_uri": _redirect_uri(),
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
        log_external_action("oauth_started", "oauth_url_ready", {"provider": "gmail", "connector_id": connector["id"]})
        return {"status": "oauth_url_ready", "authorization_url": url, "state": state, "connector_id": connector["id"], "scopes": list(SCOPES)}

    def handle_callback(self, code: str, state: str | None = None) -> dict[str, Any]:
        connector = self._connector()
        if not connector:
            raise ValueError("Run Gmail setup before OAuth callback.")
        expected_state = (connector.get("config_json") or {}).get("oauth_state") or (connector.get("config") or {}).get("oauth_state")
        if expected_state and state and state != expected_state:
            return {"status": "error", "error": "OAuth state mismatch."}
        token_data = gmail_client.exchange_code(code, _env("GOOGLE_CLIENT_ID"), _env("GOOGLE_CLIENT_SECRET"), _redirect_uri())
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(token_data.get("expires_in", 3600)))).isoformat()
        profile = {}
        if token_data.get("access_token"):
            try:
                profile = gmail_client.get_json("https://gmail.googleapis.com/gmail/v1/users/me/profile", token_data["access_token"])
            except Exception:
                profile = {}
        row = self.store.save("gmail", connector["id"], token_data, account_email=profile.get("emailAddress"), scopes=list(SCOPES), expires_at=expires_at)
        update_record("connectors", connector["id"], {"status": "authorized", "enabled": True, "last_tested_at": utc_now(), "updated_at": utc_now()})
        log_external_action("oauth_connected", "authorized", {"provider": "gmail", "connector_id": connector["id"], "account_email": row.get("account_email")})
        return {"status": "authorized", "account_email": row.get("account_email"), "connector_id": connector["id"], "token": self.store.sanitized("gmail")}

    def disconnect(self) -> dict[str, Any]:
        connector = self._connector()
        self.store.disconnect("gmail")
        if connector:
            update_record("connectors", connector["id"], {"status": "disconnected", "enabled": False, "updated_at": utc_now()})
        log_external_action("oauth_disconnected", "disconnected", {"provider": "gmail", "connector_id": connector.get("id") if connector else None})
        return {"status": "disconnected", "provider": "gmail"}

    def test_connection(self) -> dict[str, Any]:
        token = self._raw_token()
        if not token:
            return {"status": "needs_oauth", "success": False, "message": "Connect Gmail first."}
        try:
            profile = gmail_client.get_json("https://gmail.googleapis.com/gmail/v1/users/me/profile", token)
            connector = self._connector()
            if connector:
                update_record("connectors", connector["id"], {"status": "authorized", "last_tested_at": utc_now(), "updated_at": utc_now()})
            return {"status": "authorized", "success": True, "account_email": profile.get("emailAddress"), "messages_total": profile.get("messagesTotal")}
        except Exception as exc:
            status = "token_expired" if "401" in str(exc) else "error"
            return {"status": status, "success": False, "error": _safe_error(exc)}

    def search_messages(self, query: str, max_results: int = 10) -> dict[str, Any]:
        token = self._raw_token()
        if not token:
            return {"status": "needs_oauth", "results": []}
        url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{urllib.parse.urlencode({'q': query, 'maxResults': max_results})}"
        data = gmail_client.get_json(url, token)
        results = [self._message_summary(item["id"]) for item in data.get("messages", [])[:max_results]]
        return {"status": "completed", "query": query, "results": results}

    def recent_messages(self, max_results: int = 10) -> dict[str, Any]:
        return self.search_messages("newer_than:7d", max_results=max_results)

    def read_message(self, message_id: str) -> dict[str, Any]:
        token = self._raw_token()
        if not token:
            return {"status": "needs_oauth", "message_id": message_id}
        raw = gmail_client.get_json(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=full", token)
        detail = parse_message(raw)
        detail["sensitive_warning"] = detect_sensitive_content(detail.get("plain_text_body", ""))
        return {"status": "completed", "message": detail}

    def summarize_message(self, message_id: str) -> dict[str, Any]:
        read = self.read_message(message_id)
        if read.get("status") != "completed":
            return {"status": read.get("status"), "summary": "", "fallback_used": True}
        message = read["message"]
        text = f"Subject: {message.get('subject')}\nFrom: {message.get('from')}\nBody:\n{message.get('plain_text_body', '')[:3000]}"
        ai = ModelHub().generate_text(text, system_prompt="Summarize this email safely in 4 bullets.", max_tokens=300, metadata={"feature": "gmail_summarize", "message_id": message_id})
        if ai["status"] == "completed":
            return {"status": "completed", "summary": ai["text"], "provider_used": ai["provider"], "model": ai["model"], "fallback_used": ai.get("fallback_used", False)}
        return {"status": "local_fallback", "summary": local_summary(message), "provider_used": "local", "model": None, "fallback_used": True, "provider_status": ai["status"]}

    def create_draft_reply(self, message_id: str, body: str | None = None, tone: str = "professional") -> dict[str, Any]:
        read = self.read_message(message_id)
        if read.get("status") != "completed":
            return {"status": read.get("status"), "message": "Connect Gmail and read the message before drafting."}
        msg = read["message"]
        to_addr = _extract_email(msg.get("from", ""))
        subject = msg.get("subject", "Draft reply")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        body = body or f"Hi,\n\nThank you for your email. I reviewed your message and will follow up with the next steps.\n\nBest,"
        sensitive = detect_sensitive_content(f"{msg.get('plain_text_body', '')}\n{body}")
        local = EmailDraft(
            to=[to_addr] if to_addr else [],
            subject=subject,
            body=body,
            in_reply_to=message_id,
            connector_id="gmail",
            status="draft_pending_approval",
        ).to_dict()
        local.update({
            "provider": "gmail",
            "gmail_message_id": message_id,
            "gmail_thread_id": msg.get("thread_id"),
            "body_preview": safe_preview(body),
            "sensitive_warning": sensitive,
        })
        saved = EmailDraftStore().create_from_dict(local)
        token = self._raw_token()
        if not token:
            return {"status": "needs_oauth", "local_draft_id": saved["id"], "send_enabled": False}
        try:
            raw = gmail_client.build_draft_raw(to_addr, subject, body, msg.get("message_id"), msg.get("references"))
            draft = gmail_client.post_json("https://gmail.googleapis.com/gmail/v1/users/me/drafts", {"message": {"raw": raw, "threadId": msg.get("thread_id")}}, token)
            saved = update_record("email_drafts", saved["id"], {"status": "gmail_draft_created", "gmail_draft_id": draft.get("id"), "updated_at": utc_now()})
            approval = ApprovalManager().create("email_send", {**saved, "body": safe_preview(body), "warning": sensitive.get("warning"), "send_enabled": False}, "gmail")
            log_external_action("gmail_draft_created", "gmail_draft_created", {"local_draft_id": saved["id"], "gmail_draft_id": draft.get("id"), "warning": sensitive.get("warning"), "body_preview": safe_preview(body)}, "gmail", approval["id"])
            return {"status": "gmail_draft_created", "gmail_draft_id": draft.get("id"), "local_draft_id": saved["id"], "approval_id": approval["id"], "send_enabled": False, "message": "Draft created in Gmail. Sending is disabled in this version."}
        except Exception as exc:
            log_external_action("gmail_draft_create_failed", "provider_error", {"local_draft_id": saved["id"], "error": _safe_error(exc)}, "gmail")
            return {"status": "provider_error", "local_draft_id": saved["id"], "send_enabled": False, "error": _safe_error(exc)}

    def search(self, query: str) -> dict[str, Any]:
        return self.search_messages(query)

    def summarize(self, query: str | None = None) -> dict[str, Any]:
        return self.recent_messages()

    def draft_reply(self, message_id: str, tone: str = "professional") -> EmailDraft:
        return EmailDraft(to=[], subject="Draft reply", body=f"Draft reply for Gmail message {message_id} in a {tone} tone. Review before sending.", in_reply_to=message_id, connector_id="gmail")

    def _message_summary(self, message_id: str) -> dict[str, Any]:
        read = self.read_message(message_id)
        if read.get("status") != "completed":
            return {"message_id": message_id, "status": read.get("status")}
        msg = read["message"]
        return {key: msg.get(key) for key in ("message_id", "thread_id", "from", "to", "subject", "snippet", "date", "labels", "attachments")}

    def _connector(self) -> dict[str, Any] | None:
        return next((row for row in list_records("connectors") if row.get("provider") == "gmail" and row.get("channel") == "email"), None)

    def _raw_token(self) -> str | None:
        row = self.store.get("gmail")
        if not row or row.get("status") != "authorized":
            return None
        return row.get("access_token_local")

    def _setup_instructions(self, configured: bool) -> list[str]:
        if configured:
            return ["Run `liuant email gmail oauth-url` and open the returned URL.", "Paste the callback code with `liuant email gmail callback <code> --state <state>`."]
        return ["Set GOOGLE_CLIENT_ID.", "Set GOOGLE_CLIENT_SECRET.", f"Set GOOGLE_REDIRECT_URI or use default {_redirect_uri()}.", "Never enter your Gmail password into Liuant."]

    def _sanitize_connector(self, connector: dict[str, Any]) -> dict[str, Any]:
        safe = dict(connector)
        for key in ("client_secret", "access_token", "refresh_token"):
            safe.pop(key, None)
        return safe


def parse_message(raw: dict[str, Any]) -> dict[str, Any]:
    payload = raw.get("payload") or {}
    headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
    plain, html, attachments = _walk_parts(payload)
    body = plain or strip_html(html)
    return {
        "message_id": raw.get("id"),
        "thread_id": raw.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": raw.get("snippet", ""),
        "labels": raw.get("labelIds", []),
        "headers": headers,
        "plain_text_body": body,
        "html_body": html,
        "attachments": attachments,
        "references": headers.get("references"),
    }


def _walk_parts(part: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    plain = ""
    html = ""
    attachments = []
    mime = part.get("mimeType", "")
    body = part.get("body") or {}
    data = body.get("data")
    filename = part.get("filename")
    if filename:
        attachments.append({"filename": filename, "mime_type": mime, "size": body.get("size"), "attachment_id": body.get("attachmentId"), "download_supported": False})
    if data and mime == "text/plain":
        plain += _decode_b64(data)
    if data and mime == "text/html":
        html += _decode_b64(data)
    for child in part.get("parts", []) or []:
        child_plain, child_html, child_attachments = _walk_parts(child)
        plain += child_plain
        html += child_html
        attachments.extend(child_attachments)
    return plain, html, attachments


def _decode_b64(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8")).decode("utf-8", errors="replace")


def local_summary(message: dict[str, Any]) -> str:
    body = (message.get("plain_text_body") or message.get("snippet") or "").strip()
    return f"From: {message.get('from', '-')}\nSubject: {message.get('subject', '-')}\nSummary: {body[:400] or 'No message body available.'}"


def _env(key: str) -> str:
    if key == "GOOGLE_REDIRECT_URI":
        return os.environ.get(key) or DEFAULT_REDIRECT_URI
    return os.environ.get(key, "")


def _redirect_uri() -> str:
    return _env("GOOGLE_REDIRECT_URI")


def _extract_email(value: str) -> str:
    if "<" in value and ">" in value:
        return value.split("<", 1)[1].split(">", 1)[0].strip()
    return value.strip()


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for key in ("GOOGLE_CLIENT_SECRET",):
        secret = os.environ.get(key)
        if secret:
            text = text.replace(secret, mask_secret(secret))
    return text[:500]
