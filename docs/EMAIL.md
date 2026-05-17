# Email And Gmail

Liuant Agentic OS v0.2.4 implements Gmail OAuth, read/search, summarization, and Gmail draft creation. It remains draft-only.

## Gmail Status

Implemented:

- Gmail OAuth setup.
- Gmail inbox search.
- Recent message listing.
- Selected message read.
- Message summarization with Model Hub and local fallback.
- Gmail draft creation through Gmail API.
- Local `email_drafts` row creation.
- Approval record creation for draft review.

Not implemented:

- Sending email.
- Reply-all automation.
- Attachment download.
- Auto-forwarding.
- Auto-delete.
- Auto-labeling.
- Gmail password collection.

## Setup

1. Create a Google Cloud project.
2. Enable the Gmail API.
3. Create an OAuth client.
4. Set environment variables:

```text
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8765/api/email/gmail/oauth/callback
```

The default redirect URI is:

```text
http://localhost:8765/api/email/gmail/oauth/callback
```

Run:

```bash
./liuant email gmail setup
./liuant email gmail oauth-url
./liuant email gmail status
```

After the browser OAuth flow returns a code:

```bash
./liuant email gmail callback <code> --state <state>
```

## Commands

```bash
./liuant email gmail status
./liuant email gmail setup
./liuant email gmail oauth-url
./liuant email gmail test
./liuant verify gmail
./liuant email gmail disconnect

./liuant email recent
./liuant email search "newer_than:7d"
./liuant email read <message_id>
./liuant email summarize <message_id>
./liuant email draft-reply <message_id> --tone professional
./liuant email drafts
```

## Draft-Only Behavior

When creating a Gmail reply draft, Liuant:

1. Reads the selected message.
2. Creates a local `email_drafts` record.
3. Creates a Gmail draft through the Gmail API.
4. Creates an approval record.
5. Logs the action with redacted metadata.
6. Returns `send_enabled: false`.

Liuant does not call Gmail send endpoints in v0.2.4.

## Token Storage Warning

Local token storage is for MVP development. Production requires OS keychain or encrypted secret storage.

CLI/API/UI responses show token status and masked token metadata only. Raw access and refresh tokens are never returned by Liuant APIs or logged to `action_logs`.

## Safety

- Gmail scopes are limited to `gmail.readonly` and `gmail.compose`.
- `gmail.send` scope is not requested.
- Sensitive content warnings are added for password, OTP, credit card, Aadhaar, PAN, bank account, API key, secret, confidential, and token patterns.
- Attachments are shown as metadata only and are not downloaded.
