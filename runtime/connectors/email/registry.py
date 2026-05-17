from .gmail_connector import GmailConnector
from .imap_smtp_connector import ImapSmtpConnector
from .outlook_connector import OutlookConnector

EMAIL_CONNECTORS = {
    cls.provider: cls
    for cls in (
        GmailConnector,
        OutlookConnector,
        ImapSmtpConnector,
    )
}


def list_email_connectors() -> list[dict]:
    return [connector().describe() for connector in EMAIL_CONNECTORS.values()]


def get_email_connector(provider: str):
    try:
        return EMAIL_CONNECTORS[provider]()
    except KeyError as exc:
        raise ValueError(f"Unknown email connector: {provider}") from exc
