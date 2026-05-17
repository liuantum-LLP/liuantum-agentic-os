# Local Authentication

v0.5.0 adds local API authentication and UI session protection.

## Settings

- `local_auth_enabled`: `true` by default
- `local_auth_mode`: `token`
- `local_api_token_hash`: stores only the token hash
- `session_timeout_minutes`: default `720`

## CLI

```bash
./liuant auth status
./liuant auth token
./liuant auth rotate-token
./liuant auth login <token>
./liuant auth disable --confirm true
```

`auth token` prints the local token with a warning. Do not paste it into websites, tickets, logs, or chat systems.

## API

```text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/status
POST /api/auth/rotate-token
```

Protected endpoints accept:

```http
Authorization: Bearer <local_api_token>
```

or a valid local session token.

## Protected Areas

Sensitive API paths are protected when local auth is enabled, including provider setup/generation, email, Telegram, social, scheduler, backups, secrets, knowledge indexing, approvals, and publish/send attempts.

Safe public endpoints are limited to:

- `/api/auth/status`
- `/api/auth/login`
- `/api/doctor`
- `/api/system/status`
- `/api/system/dashboard`

## Scope

This is single-user local authentication. It is not hosted multi-user auth, tenancy, role-based access control, or production identity management.

Release and desktop status endpoints follow the same local API protection model when auth is enabled. Health-style status can still be inspected from CLI without exposing the local API token.
