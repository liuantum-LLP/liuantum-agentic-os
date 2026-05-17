# Backups

v0.5.0 keeps backups secret-safe and adds explicit handling for the encrypted local secret store.

## CLI

```bash
./liuant backup create
./liuant backup create --include-encrypted-secrets true --confirm true
./liuant backup list
./liuant backup restore <backup_id> --confirm
```

Default backups are secret-safe:

- `.env` and `.env.local` are excluded.
- Raw provider keys are excluded.
- Raw OAuth and bot tokens are redacted in the sanitized snapshot.
- The encrypted local secret store is excluded by default.
- Backup metadata is stored in the `backups` table.

Including encrypted secrets requires explicit confirmation:

```bash
./liuant backup create --include-encrypted-secrets true --confirm true
```

This copies the encrypted local store, not raw secrets. Restore requires the same local key/passphrase.

Backups are saved under:

```text
workspace/backups/
```

## API

```text
POST /api/backup/create
GET  /api/backup/list
```

Restore remains intentionally manual in the MVP. Production backup/restore should use encrypted storage, tested restore drills, and access controls.

Release packaging backups continue to exclude `.env` and raw secrets. Desktop artifacts and release manifests can be regenerated and are not treated as secret storage.
