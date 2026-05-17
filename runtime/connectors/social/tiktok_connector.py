from .base_social import SocialCapabilities, SocialConnector


class TikTokConnector(SocialConnector):
    platform = "tiktok"
    display_name = "TikTok"
    api_docs_url = "https://developers.tiktok.com/"
    warnings = (
        "TikTok API capabilities vary by product and approval status.",
        "MVP creates scripts, captions, upload metadata, and approval-gated draft workflows.",
    )
    capabilities = SocialCapabilities()

