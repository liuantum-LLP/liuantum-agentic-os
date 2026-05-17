from .base_social import SocialCapabilities, SocialConnector


class WhatsAppConnector(SocialConnector):
    platform = "whatsapp"
    display_name = "WhatsApp Business"
    oauth_docs_url = "https://developers.facebook.com/docs/whatsapp/embedded-signup"
    api_docs_url = "https://developers.facebook.com/docs/whatsapp/cloud-api"
    required_scopes = ("whatsapp_business_management", "whatsapp_business_messaging")
    optional_scopes = ()
    warnings = (
        "Use WhatsApp Business Cloud API and approved message templates where required.",
        "Do not scrape WhatsApp or ask users for raw passwords.",
        "MVP creates message drafts only and requires approval before sending.",
    )
    capabilities = SocialCapabilities(
        can_read_posts=False,
        can_read_comments=False,
        can_read_messages=True,
        can_publish_posts=True,
        can_upload_media=True,
        can_fetch_analytics=False,
        requires_business_account=True,
    )

