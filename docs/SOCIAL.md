# Liuant Social Connectors

v0.3.0 implements social OAuth setup and approval-gated publishing architecture for LinkedIn and X/Twitter.

## Status

Implemented:

- LinkedIn connector setup.
- X/Twitter connector setup.
- OAuth URL generation.
- OAuth callback token storage.
- Token masking in CLI/API/UI.
- Connector status and test actions.
- Draft approval checks.
- Manual publish toggle.
- Official API publish call path when credentials, scopes, and access are available.
- Provider/API failure handling without fake published status.

Config-ready placeholders:

- Meta/Facebook
- Instagram
- YouTube
- Reddit
- Threads
- Pinterest
- TikTok

## LinkedIn Setup

```bash
export LINKEDIN_CLIENT_ID="..."
export LINKEDIN_CLIENT_SECRET="..."
export LINKEDIN_REDIRECT_URI="http://localhost:8765/api/social/linkedin/oauth/callback"

./liuant social linkedin setup
./liuant social linkedin oauth-url
./liuant social linkedin callback <code> --state <state>
./liuant social linkedin test
```

LinkedIn posting requires official LinkedIn API access and approved scopes such as `w_member_social` or `w_organization_social`.

## X/Twitter Setup

```bash
export X_CLIENT_ID="..."
export X_CLIENT_SECRET="..."
export X_REDIRECT_URI="http://localhost:8765/api/social/x/oauth/callback"

./liuant social x setup
./liuant social x oauth-url
./liuant social x callback <code> --state <state>
./liuant social x test
./liuant verify social
```

X posting requires official API access, an eligible API tier, and `tweet.write`.

## Approval-Gated Publishing

```bash
./liuant social drafts
./liuant social approve <draft_id>
./liuant social connector-enable-publish linkedin
./liuant social publish-approved <draft_id> --connector linkedin
```

Publishing is blocked unless:

- The draft is approved.
- The exact approval record is approved.
- The connector is authorized and enabled.
- Manual publishing is enabled.
- The connector has a publish scope.
- Sensitive content has been explicitly confirmed.

There is no auto-publish endpoint.

## API

- `GET /api/social/connectors`
- `GET /api/social/connectors/{id}`
- `POST /api/social/connectors/{id}/enable-publish`
- `POST /api/social/connectors/{id}/disable-publish`
- `GET /api/social/linkedin/status`
- `POST /api/social/linkedin/setup`
- `POST /api/social/linkedin/oauth/start`
- `GET /api/social/linkedin/oauth/callback`
- `POST /api/social/linkedin/test`
- `POST /api/social/linkedin/disconnect`
- `GET /api/social/x/status`
- `POST /api/social/x/setup`
- `POST /api/social/x/oauth/start`
- `GET /api/social/x/oauth/callback`
- `POST /api/social/x/test`
- `POST /api/social/x/disconnect`
- `POST /api/social/drafts/{draft_id}/publish-approved`

## Safety

- No scraping.
- No passwords.
- No auto-publish.
- No bulk publishing above 5 drafts.
- All publish attempts are logged.
- Tokens are never returned raw.
- Local token storage is for MVP development only; production requires encrypted secret storage or OS keychain.
