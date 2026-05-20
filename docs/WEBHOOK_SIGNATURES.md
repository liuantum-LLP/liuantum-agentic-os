# Webhook Signatures

Liuant Agentic OS v1.8.0 supports HMAC-SHA256 signature verification for webhook alerts.

## Overview

When a webhook secret is configured, all webhook payloads are signed with HMAC-SHA256 and sent with verification headers. This allows receivers to verify that the payload originated from Liuant and has not been tampered with.

## Configuration

### Set Webhook Secret

```bash
./liuant usage webhook set-secret --secret <your-secret> --confirm true
```

The secret is stored securely and never logged or printed.

### Rotate Secret

```bash
./liuant usage webhook rotate-secret --confirm true
```

Generates a new random 64-character hex secret. Update your receiver verification after rotation.

### Signature Test

```bash
./liuant usage webhook signature-test
```

Verifies HMAC is enabled and signature headers are generated correctly.

## Signature Headers

All webhook POST requests include these headers:

| Header | Description |
|--------|-------------|
| `X-Liuant-Event` | Event type (e.g., `budget_warning`, `provider_degraded`) |
| `X-Liuant-Timestamp` | Unix timestamp when the signature was generated |
| `X-Liuant-Signature` | `sha256=<hex digest>` of HMAC-SHA256 signature |
| `User-Agent` | `Liuant-Agentic-OS/1.8.0` |

## Signature Algorithm

```
message = timestamp + "." + raw_json_body
signature = HMAC-SHA256(secret, message)
```

The signature is the hex digest of the HMAC-SHA256 hash of the message, where:
- `timestamp` is the Unix timestamp string
- `raw_json_body` is the exact JSON payload string sent in the POST body
- `secret` is the webhook secret configured in Liuant

## Receiver Verification Example (Python)

```python
import hmac
import hashlib

def verify_webhook(payload_bytes: bytes, signature: str, timestamp: str, secret: str) -> bool:
    message = f"{timestamp}.{payload_bytes.decode()}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## Security Rules

- The webhook secret is never printed, logged, or exposed in any output.
- Only the secret reference is stored, not the plain secret.
- HMAC is enabled by default when a secret exists.
- Signature verification is the responsibility of the webhook receiver.
- Liuant does not verify incoming signatures (outbound only).

## CLI Commands

| Command | Description |
|---------|-------------|
| `usage webhook set-secret --secret <value> --confirm true` | Set HMAC secret |
| `usage webhook rotate-secret --confirm true` | Rotate to new random secret |
| `usage webhook signature-test` | Test signature generation |
| `usage webhook send-test --event budget_warning` | Send test webhook with signature |
