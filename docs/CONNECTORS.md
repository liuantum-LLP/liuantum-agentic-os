# Connector Architecture

Connectors use official APIs and OAuth wherever possible. The MVP does not scrape private pages, ask for raw passwords, or perform external mutations without approval.

## Lifecycle

```bash
./liuant connectors list
./liuant connectors create gmail
./liuant connectors create telegram
./liuant connectors test <connector_id>
./liuant connectors enable <connector_id>
./liuant connectors disable <connector_id>
./liuant connectors disconnect <connector_id>
```

Configured connector records are stored in SQLite in the `connectors` table.

## Social OAuth Connectors

v0.3.0 implements social OAuth setup and approval-gated publishing architecture for:

- LinkedIn
- X/Twitter

Config-ready placeholders remain for Meta/Facebook, Instagram, YouTube, Reddit, Threads, Pinterest, and TikTok.

CLI:

```bash
./liuant social connectors
./liuant social linkedin status
./liuant social linkedin setup
./liuant social linkedin oauth-url
./liuant social linkedin callback <code> --state <state>
./liuant social linkedin test
./liuant social linkedin disconnect

./liuant social x status
./liuant social x setup
./liuant social x oauth-url
./liuant social x callback <code> --state <state>
./liuant social x test
./liuant social x disconnect
```

Publishing is blocked unless all of these are true:

- The draft is approved.
- The exact approval record is approved.
- The connector is authorized and enabled.
- Manual publishing is enabled for that connector.
- The OAuth scopes include the required publish scope.
- Sensitive content has been explicitly confirmed.

No auto-publish endpoint exists.

Environment:

```text
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=http://localhost:8765/api/social/linkedin/oauth/callback

X_CLIENT_ID=
X_CLIENT_SECRET=
X_REDIRECT_URI=http://localhost:8765/api/social/x/oauth/callback
```

## Telegram Bot Connector

v0.2.5 implements a Telegram Bot API connector.

What works:

- Telegram connector setup from `TELEGRAM_BOT_TOKEN`.
- Bot token validation with Telegram `getMe`.
- Local webhook receivers:
  - `/api/telegram/webhook`
  - `/api/connectors/telegram/webhook`
- Incoming bot message storage in `telegram_messages`.
- Safe deterministic agent routing to `front-desk-management-agent` by default.
- Reply draft storage in `telegram_reply_drafts`.
- Approval records for `telegram_send_message`.
- Prompt-injection warnings and sensitive-content log redaction.
- Manual approved sending only when `telegram_manual_send_enabled=true`.

What remains disabled by default:

- Auto-reply.
- Broadcast/spam workflows.
- Shell/tool execution from Telegram.
- Reading a user's Telegram account DMs.
- Social publishing and Gmail sending.

CLI:

```bash
./liuant telegram status
./liuant telegram setup
./liuant telegram test
./liuant telegram enable
./liuant telegram disable
./liuant telegram messages
./liuant telegram drafts
./liuant telegram approve <draft_id>
./liuant telegram send-approved <draft_id>
```

Optional webhook secret:

```bash
export TELEGRAM_WEBHOOK_SECRET="your-secret"
```

When configured, requests must include `X-Telegram-Bot-Api-Secret-Token`.

## Notes

- X API access and pricing vary by plan.
- LinkedIn organization APIs and analytics may require review and approved access.
- Instagram/Facebook workflows use Meta Graph API and may require business or creator accounts.
- YouTube upload/delete/community actions require elevated scopes and explicit approval.
- WhatsApp requires WhatsApp Business Cloud API and approved templates where applicable.
- IMAP/SMTP should prefer OAuth or app-password style mechanisms where supported.
