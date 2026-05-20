# Webhook Alerts (v1.9.0)

Liuant Agentic OS supports real HTTP webhook alert delivery with retry logic and HMAC signature verification for budget and provider health notifications.

## Overview

Webhook alerts are **disabled by default** and require explicit user confirmation to enable. When enabled, alerts are sent to a configured HTTPS URL with safe payloads that contain no secrets, prompts, or raw provider errors.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `webhook_alerts_enabled` | `false` | Enable/disable webhook delivery |
| `webhook_url` | `null` | HTTPS endpoint URL |
| `webhook_secret` | `null` | Optional HMAC secret (stored in SecretStore) |
| `webhook_test_mode` | `true` | Send test payloads only until approved |
| `webhook_requires_approval` | `true` | Production delivery requires explicit approval |
| `webhook_allowed_event_types` | `budget_warning,budget_exceeded,provider_degraded,provider_rate_limited,cost_anomaly` | Allowed event types |

## Webhook Payload

```json
{
  "event_type": "budget_warning",
  "workspace": "default",
  "level": "warning",
  "message": "Daily cost at 90% of limit ($1.80/$2.00)",
  "provider": "openrouter",
  "model": "deepseek/deepseek-reasoner",
  "estimated_cost": 1.80,
  "timestamp": "2026-05-18T10:00:00Z",
  "source": "liuant-agentic-os"
}
```

**Safety guarantees:**
- No prompts, API keys, tokens, or raw provider errors
- Messages truncated to 500 characters
- Provider names truncated to 50 characters
- Model names truncated to 100 characters
- All costs marked as estimated unless exact usage metadata exists

## CLI Usage

```bash
# Check webhook status
./liuant usage webhook status

# Set webhook URL (requires confirmation)
./liuant usage webhook set-url "https://example.com/webhook" --confirm true

# Send test payload
./liuant usage webhook test

# Enable webhooks (requires confirmation, starts in test mode)
./liuant usage webhook enable --confirm true

# Disable webhooks
./liuant usage webhook disable

# Send real test webhook with HTTP delivery
./liuant usage webhook send-test --event budget_warning

# View delivery history
./liuant usage webhook delivery-history

# Retry failed deliveries
./liuant usage webhook retry-failed --confirm true

# Set HMAC secret
./liuant usage webhook set-secret --secret <value> --confirm true

# Rotate HMAC secret
./liuant usage webhook rotate-secret --confirm true

# Test HMAC signature generation
./liuant usage webhook signature-test
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/usage/webhook/status` | GET | Get webhook configuration |
| `/api/usage/webhook/set-url` | POST | Set webhook URL (requires confirm=true) |
| `/api/usage/webhook/test` | POST | Send test payload |
| `/api/usage/webhook/enable` | POST | Enable webhooks (requires confirm=true) |
| `/api/usage/webhook/disable` | POST | Disable webhooks |
| `/api/usage/webhook/send-test` | POST | Send real test webhook with HTTP delivery |
| `/api/usage/webhook/delivery-history` | GET | Get recent delivery history |
| `/api/usage/webhook/retry-failed` | POST | Retry failed deliveries (requires confirm=true) |

## Delivery Log

Webhook deliveries are logged in the `webhook_deliveries` table with:
- `url_hash`: SHA-256 hash of the webhook URL (first 16 chars)
- `payload_hash`: SHA-256 hash of the JSON payload (first 16 chars)
- `status`: success, failed, skipped
- `status_code`: HTTP response code
- `retry_count`: Number of retries attempted
- `error_redacted`: Redacted error message (no secrets)
- `test_mode`: Whether this was a test delivery

Full URLs and payloads are **never** stored in the delivery log.

## Retry Logic

- Default max retries: 3
- Exponential backoff: 1s, 2s, 4s (capped at 60s)
- Retries on: timeout, 429 (rate limit), 5xx (server error)
- Does NOT retry: 4xx (except 429), connection refused

## Safety

- Webhooks are **disabled by default**
- URL must use **HTTPS**
- Enabling requires **explicit confirmation**
- Test mode is **enforced** until production approval
- Secrets stored in **SecretStore**, not plain config
- Payloads contain **no sensitive data**
- No auto-delivery of external actions
- HMAC secret never printed or logged
- Delivery log stores hashes only, not full URL/payload
- Errors are redacted before storage

## UI (v1.9.0)

The Usage & Costs settings page includes:

### Webhook Delivery History Table
- Shows: event type, workspace, status, status code, retry count, URL hash, payload hash, test mode, delivered at
- Buttons: Send Test Webhook, Retry Failed, Refresh
- Never displays full webhook URL or payload body
- Color-coded rows: green for success, red for failed

### HMAC Status Card
- Shows: HMAC enabled status, secret configured status, signature/timestamp header names
- Buttons: Signature Test, Rotate Secret
- Secret is never displayed
- Links to docs/WEBHOOK_SIGNATURES.md for receiver verification

## Local Test Server (v1.9.0)

Integration tests use a local mock HTTP server to test real webhook delivery:
- Receives POST requests and captures headers/body
- Configurable response codes (200, 429, 500, 400)
- Verifies HMAC signature generation
- Tests retry logic for 429/500, no retry for 400

### HTTP Localhost Exception
For testing purposes, `http://127.0.0.1` and `http://localhost` URLs are allowed when:
- Webhook test mode is enabled, OR
- `LIUANT_WEBHOOK_TEST_ALLOW_HTTP_LOCALHOST=true` environment variable is set

This exception is **never** available in production. Normal runtime requires HTTPS.
