from .base_email import EmailCapabilities, EmailConnector


class ImapSmtpConnector(EmailConnector):
    provider = "imap_smtp"
    display_name = "Generic IMAP/SMTP"
    required_scopes = ()
    optional_scopes = ()
    warnings = (
        "Prefer OAuth-based providers when available.",
        "Do not ask users for raw account passwords; use app passwords or OAuth where supported.",
        "SMTP send is approval-gated and disabled by default.",
    )
    capabilities = EmailCapabilities(requires_oauth=False)

