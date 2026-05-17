from .facebook_connector import FacebookConnector
from .instagram_connector import InstagramConnector
from .linkedin_connector import LinkedInConnector
from .pinterest_connector import PinterestConnector
from .reddit_connector import RedditConnector
from .threads_connector import ThreadsConnector
from .tiktok_connector import TikTokConnector
from .whatsapp_connector import WhatsAppConnector
from .x_connector import XConnector
from .youtube_connector import YouTubeConnector

SOCIAL_CONNECTORS = {
    cls.platform: cls
    for cls in (
        XConnector,
        LinkedInConnector,
        InstagramConnector,
        FacebookConnector,
        YouTubeConnector,
        ThreadsConnector,
        RedditConnector,
        PinterestConnector,
        TikTokConnector,
        WhatsAppConnector,
    )
}


def list_social_connectors() -> list[dict]:
    return [connector().describe() for connector in SOCIAL_CONNECTORS.values()]


def get_social_connector(platform: str):
    try:
        return SOCIAL_CONNECTORS[platform]()
    except KeyError as exc:
        raise ValueError(f"Unknown social connector: {platform}") from exc
