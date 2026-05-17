from .base_social import SocialCapabilities, SocialConnector


class PinterestConnector(SocialConnector):
    platform = "pinterest"
    display_name = "Pinterest"
    api_docs_url = "https://developers.pinterest.com/docs/api/v5/"
    warnings = (
        "Pinterest publishing and analytics require official API access and approved scopes.",
        "MVP includes setup metadata, draft pins, and approval queue integration.",
    )
    capabilities = SocialCapabilities()

