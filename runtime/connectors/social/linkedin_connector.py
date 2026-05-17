from .base_social import SocialCapabilities
from .social_oauth import OAuthSocialConnector


class LinkedInConnector(OAuthSocialConnector):
    platform = "linkedin"
    display_name = "LinkedIn"
    client_id_env = "LINKEDIN_CLIENT_ID"
    client_secret_env = "LINKEDIN_CLIENT_SECRET"
    redirect_uri_env = "LINKEDIN_REDIRECT_URI"
    default_redirect_uri = "http://localhost:8765/api/social/linkedin/oauth/callback"
    authorization_url = "https://www.linkedin.com/oauth/v2/authorization"
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    profile_url = "https://api.linkedin.com/v2/userinfo"
    publish_url = "https://api.linkedin.com/v2/ugcPosts"
    oauth_docs_url = "https://learn.microsoft.com/linkedin/shared/authentication/authorization-code-flow"
    api_docs_url = "https://learn.microsoft.com/linkedin/"
    required_scopes = ("openid", "profile", "w_member_social")
    publish_scopes = ("w_member_social", "w_organization_social")
    optional_scopes = ("r_organization_social", "w_organization_social", "r_ads_reporting")
    api_access_note = "LinkedIn posting and organization analytics require official LinkedIn app access and approved scopes."
    warnings = (
        "Use LinkedIn official APIs only; scraping LinkedIn is not allowed.",
        "Organization posting and analytics require LinkedIn approval and eligible app access.",
        "MVP creates personal/page drafts only; publishing requires explicit approval.",
    )
    capabilities = SocialCapabilities()

    def _publish_payload(self, draft: dict) -> dict:
        account_id = ((self._connector() or {}).get("config_json") or {}).get("account_id") or "me"
        return {
            "author": f"urn:li:person:{account_id}" if not str(account_id).startswith("urn:") else account_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": draft.get("text", "")},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
