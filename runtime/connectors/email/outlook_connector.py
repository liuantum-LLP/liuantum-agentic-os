from .base_email import EmailCapabilities, EmailConnector


class OutlookConnector(EmailConnector):
    provider = "outlook"
    display_name = "Outlook / Microsoft 365"
    oauth_docs_url = "https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow"
    api_docs_url = "https://learn.microsoft.com/graph/api/resources/mail-api-overview"
    required_scopes = ("Mail.Read", "Mail.ReadWrite")
    optional_scopes = ("Mail.Send",)
    warnings = (
        "Use Microsoft Graph with least-privilege delegated scopes.",
        "Sending is disabled unless explicit user approval is present.",
    )
    capabilities = EmailCapabilities()

