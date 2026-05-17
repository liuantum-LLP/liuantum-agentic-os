from .base_social import SocialCapabilities, SocialConnector


class InstagramConnector(SocialConnector):
    platform = "instagram"
    display_name = "Instagram"
    oauth_docs_url = "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login"
    api_docs_url = "https://developers.facebook.com/docs/instagram-platform"
    required_scopes = ("instagram_basic", "pages_show_list")
    optional_scopes = ("instagram_content_publish", "instagram_manage_comments", "instagram_manage_insights")
    warnings = (
        "Instagram publishing uses Meta Graph API and generally requires a business or creator account.",
        "MVP prepares captions, schedules draft content, and queues approval before any media workflow.",
    )
    capabilities = SocialCapabilities(requires_business_account=True)

