# Telegram Connector

Version: v0.2.5

Liuant Agentic OS supports Telegram through the Telegram Bot API. It does not read a user's Telegram account messages and does not ask for a Telegram password.

## Status

Implemented:

- Bot connector setup.
- Bot token validation with `getMe`.
- Local webhook update processing.
- Incoming message records.
- Safe agent-routed reply drafts.
- Approval queue records.
- Prompt-injection warnings.
- Sensitive-content redaction in logs.
- Optional manually approved sending.

Disabled by default:

- Auto-replies.
- Broadcast automation.
- Shell/tool execution from Telegram.
- Gmail/social actions from Telegram messages.
- File deletion or workspace modifications from Telegram messages.

## Setup

1. Create a bot with BotFather.
2. Set environment variables:

```bash
export TELEGRAM_BOT_TOKEN="123456:bot_token"
export TELEGRAM_WEBHOOK_SECRET="optional-secret"
export TELEGRAM_WEBHOOK_BASE_URL="https://your-public-url"
```

3. Run:

```bash
./liuant telegram setup
./liuant telegram test
./liuant verify telegram
./liuant telegram status
```

## Webhook

Local endpoint:

```text
/api/telegram/webhook
```

Connector alias:

```text
/api/connectors/telegram/webhook
```

If `TELEGRAM_WEBHOOK_SECRET` is set, Telegram webhook requests must include:

```text
X-Telegram-Bot-Api-Secret-Token: your-secret
```

For local development you may need a tunnel so Telegram can reach your local server.

## Reply Flow

1. Telegram sends a bot update to Liuant.
2. Liuant stores the incoming message in `telegram_messages`.
3. Liuant routes the message to `front-desk-management-agent` by default.
4. Liuant creates a reply draft in `telegram_reply_drafts`.
5. Liuant creates an approval record with exact preview.
6. Nothing is sent automatically.

Review drafts:

```bash
./liuant telegram messages
./liuant telegram drafts
./liuant telegram approve <draft_id>
./liuant telegram reject <draft_id>
```

Manual sending requires:

- connector enabled,
- approval approved,
- `telegram_manual_send_enabled=true`.

```bash
./liuant settings set telegram_manual_send_enabled true
./liuant telegram send-approved <draft_id>
```

## Safety

- Incoming messages are untrusted.
- Shell commands and system instructions inside messages are ignored.
- Sensitive content is redacted from logs.
- Prompt injection is marked high risk.
- Approval remains required for reply sending.

## Roadmap

- v0.2.6 Background scheduler: implemented as safe local tick-based scheduler.
- v0.2.7 Embeddings/RAG: implemented as local-first memory and knowledge search.
- v0.3 Social OAuth and publishing after approval: LinkedIn/X architecture implemented.
- v0.4 Real video provider integrations.
