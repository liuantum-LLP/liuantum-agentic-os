# Secrets

v0.5.0 adds local secret storage for Liuant Agentic OS.

## Backends

- `env`: read-only fallback from environment, `.env`, and `.env.local`.
- `local_encrypted`: MVP encrypted local file under `workspace/security/secrets.enc.json`.
- `keyring`: OS keychain if the optional Python `keyring` package is available.

Default priority:

1. keyring if available
2. local encrypted store
3. env fallback

## CLI

```bash
./liuant secrets status
./liuant secrets migrate
./liuant secrets list
./liuant secrets delete <name>
./liuant secrets rotate <name> <new_value>
```

## Migration

`./liuant secrets migrate` moves legacy local token fields into the active secret backend and leaves secret references such as:

```text
oauth:gmail:refresh_token
telegram:telegram_bot:bot_token
```

Public CLI/API/UI responses show only metadata:

- `secret_status`
- `secret_backend`
- `secret_masked`
- fingerprint

They do not return raw secret values.

## Limitations

The local encrypted store is for local MVP development. Production deployments should use OS keychain, HSM-backed, or managed encrypted secret storage with access controls and audit logging.

Release manifests, checksums, signing status, and update metadata contain only configuration status and artifact paths. They must not contain raw API keys, OAuth tokens, or local API tokens.
