# Verification Center

v0.5.0 keeps the live-safe verification workflows and adds local auth/secret status to the security posture.

## CLI

```bash
./liuant verify all
./liuant verify providers
./liuant verify text
./liuant verify image
./liuant verify video
./liuant verify gmail
./liuant verify telegram
./liuant verify social
./liuant verify storage
./liuant verify security
./liuant secrets status
./liuant auth status
```

Results include:

- configured
- reachable
- authenticated
- capability verified
- last verified time
- redacted error
- setup instructions

Results are stored in `verification_results`.

## Safe Defaults

Verification does not send emails, publish social posts, send Telegram replies, or upload videos.

Media generation checks do not create paid image/video generations by default. Use a live-generate flag only when you explicitly accept provider cost.

## Environment

```bash
./liuant env check
./liuant env template
./liuant env missing
```

The template and missing commands print variable names only, never values.

## API

```text
GET  /api/verify/status
POST /api/verify/all
POST /api/verify/providers
POST /api/verify/provider/{provider_name}
POST /api/verify/gmail
POST /api/verify/telegram
POST /api/verify/social
POST /api/verify/storage
POST /api/verify/security
```

## Current Limits

Verification is designed for local MVP readiness. Production monitoring, encrypted hosted secrets, multi-user auth, and deployment probes are still pending.

v0.5.6 includes desktop, signing, and release readiness checks through:

```bash
./liuant desktop check
./liuant signing check
./liuant release-check
```
