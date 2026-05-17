from .base_social import SocialCapabilities
from .social_oauth import OAuthSocialConnector


class XConnector(OAuthSocialConnector):
    platform = "x"
    display_name = "X.com / Twitter"
    client_id_env = "X_CLIENT_ID"
    client_secret_env = "X_CLIENT_SECRET"
    redirect_uri_env = "X_REDIRECT_URI"
    default_redirect_uri = "http://localhost:8765/api/social/x/oauth/callback"
    authorization_url = "https://twitter.com/i/oauth2/authorize"
    token_url = "https://api.twitter.com/2/oauth2/token"
    profile_url = "https://api.twitter.com/2/users/me"
    publish_url = "https://api.twitter.com/2/tweets"
    oauth_docs_url = "https://developer.x.com/en/docs/authentication/oauth-2-0"
    api_docs_url = "https://developer.x.com/en/docs/x-api"
    required_scopes = ("tweet.read", "users.read", "offline.access")
    publish_scopes = ("tweet.write",)
    optional_scopes = ("tweet.write", "like.read", "follows.read")
    api_access_note = "X posting requires official API access, an eligible plan, and tweet.write scope."
    warnings = (
        "Use official X API access only; do not scrape private pages.",
        "X API access and pricing vary by plan and may not be free.",
        "Search, mentions, analytics, and posting depend on approved scopes and plan limits.",
        "MVP creates drafts only; publishing requires explicit approval.",
    )
    capabilities = SocialCapabilities()

    def _external_id(self, data: dict) -> str:
        return str((data.get("data") or {}).get("id") or data.get("id") or "")

    def _external_url(self, external_id: str, data: dict) -> str:
        username = (((self._connector() or {}).get("config_json") or {}).get("account_name") or "").lstrip("@")
        return f"https://x.com/{username}/status/{external_id}" if username and external_id else ""
