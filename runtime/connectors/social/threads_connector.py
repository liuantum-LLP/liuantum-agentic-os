from .base_social import SocialCapabilities, SocialConnector


class ThreadsConnector(SocialConnector):
    platform = "threads"
    display_name = "Threads"
    api_docs_url = "https://developers.facebook.com/docs/threads"
    warnings = (
        "Threads API support and permissions may change; this MVP provides setup metadata and draft workflows.",
        "Publishing requires official API support, eligible access, and approval.",
    )
    capabilities = SocialCapabilities()

