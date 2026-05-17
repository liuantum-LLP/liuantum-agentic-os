from .base_social import SocialCapabilities, SocialConnector


class RedditConnector(SocialConnector):
    platform = "reddit"
    display_name = "Reddit"
    oauth_docs_url = "https://github.com/reddit-archive/reddit/wiki/OAuth2"
    api_docs_url = "https://www.reddit.com/dev/api/"
    required_scopes = ("identity", "read")
    optional_scopes = ("submit", "history", "mysubreddits")
    warnings = (
        "Use Reddit API and subreddit rules. Do not automate spam or policy-violating behavior.",
        "MVP drafts posts/comments and requires approval before submission.",
    )
    capabilities = SocialCapabilities(can_upload_media=False)

