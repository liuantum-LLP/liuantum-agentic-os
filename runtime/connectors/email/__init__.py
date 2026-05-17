"""Email connector package."""

from .base_email import EmailCapabilities, EmailConnector, EmailDraft
from .gmail_connector import GmailConnector
from .imap_smtp_connector import ImapSmtpConnector
from .outlook_connector import OutlookConnector

__all__ = [
    "EmailCapabilities",
    "EmailConnector",
    "EmailDraft",
    "GmailConnector",
    "OutlookConnector",
    "ImapSmtpConnector",
]

