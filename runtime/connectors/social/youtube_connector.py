from .base_social import SocialCapabilities, SocialConnector


class YouTubeConnector(SocialConnector):
    platform = "youtube"
    display_name = "YouTube"
    oauth_docs_url = "https://developers.google.com/identity/protocols/oauth2"
    api_docs_url = "https://developers.google.com/youtube/v3"
    required_scopes = ("https://www.googleapis.com/auth/youtube.readonly",)
    optional_scopes = ("https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube")
    warnings = (
        "YouTube upload, delete, and community actions require explicit approval and elevated scopes.",
        "MVP drafts titles, descriptions, tags, community posts, and upload metadata.",
    )
    capabilities = SocialCapabilities(can_read_comments=True, can_publish_posts=True, can_upload_media=True)

