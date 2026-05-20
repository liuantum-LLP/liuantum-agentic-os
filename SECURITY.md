# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 3.1.x   | ✅ Active development |
| < 3.0   | ⚠️ Legacy          |

## Reporting a Vulnerability

**Do not file a public issue for security vulnerabilities.**

Report vulnerabilities privately to: `admin@liuantum.com`

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and work on a fix before public disclosure.

## Local Secret Storage

- API keys, OAuth tokens, and bot tokens are stored in the encrypted local SecretStore.
- CLI output and logs use `mask_secret()` to show only redacted values (e.g., `sk-a...1234`).
- `.env`, `.env.local`, and workspace files are excluded from backups and exports by default.
- Production deployments should use OS keychain or managed encrypted secret storage.

## Approval-Gated External Actions

- **Browser Automation:** Actions affecting browser state require explicit approval.
- **Desktop Automation:** Execution of local apps or scripts is gated by the Approval Queue.
- **Voice Automation:** Voice inputs are simulation-first by default; no always-listening without explicit enabling.
- Social publishing is disabled by default and requires explicit draft approval plus manual per-connector enablement.
- Email sending is not implemented.
- Telegram auto-reply is disabled by default; reply drafts require approval.
- Scheduled automations cannot send email, publish social posts, or auto-send Telegram messages.

## Responsible Disclosure

We request:
1. Report vulnerabilities privately — do not post them publicly.
2. Allow reasonable time for a fix before any disclosure.
3. Do not access, modify, or exfiltrate other users' data during testing.
4. Do not run automated scanners without prior coordination.
