from .base_social import SocialCapabilities, SocialConnector


class FacebookConnector(SocialConnector):
    platform = "facebook_page"
    display_name = "Facebook Page"
    oauth_docs_url = "https://developers.facebook.com/docs/facebook-login"
    api_docs_url = "https://developers.facebook.com/docs/graph-api"
    required_scopes = ("pages_read_engagement", "pages_show_list")
    optional_scopes = ("pages_manage_posts", "pages_read_user_content")
    warnings = (
        "Facebook Page workflows use Meta Graph API permissions and app review where required.",
        "MVP drafts page content and requires approval before publishing.",
    )
    capabilities = SocialCapabilities(requires_business_account=True)

