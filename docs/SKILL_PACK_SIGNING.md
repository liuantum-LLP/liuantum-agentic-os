# Skill Pack Signing

Skill packs can be cryptographically signed using local maintainer keys. This provides authenticity and integrity verification without requiring an online trust server.

## Signing Algorithm

Liuant supports two signing algorithms:

1. **Ed25519** (preferred) — Uses the `cryptography` package for proper Ed25519 signatures. Provides strong cryptographic guarantees.
2. **HMAC-SHA256** (fallback) — Used when `cryptography` is not installed. Provides local-only integrity checking but cannot be verified without the private key.

## Key Management

### Generate a Key

```bash
./liuant skills pack keys generate --name local-maintainer
```

Returns a key ID and public key. The private key is stored locally in `workspace/skills/packs/keys/`.

### List Keys

```bash
./liuant skills pack keys list
```

### Trust a Key

```bash
./liuant skills pack keys trust <key_id> --confirm true
```

Trusted keys show packs as "verified" when their signature validates.

### Untrust a Key

```bash
./liuant skills pack keys untrust <key_id> --confirm true
```

## Signing a Pack

```bash
./liuant skills pack sign ./pack-source --key <key_id>
```

Creates `SIGNATURE.json` in the pack source directory containing:
- Algorithm used
- Signature value
- Signed timestamp
- Key ID
- Signer name
- Hashes of signed files

## Verifying a Pack

```bash
./liuant skills pack verify ./pack.liuantskillpack
```

Returns the trust state:
- `unsigned` — No signature found
- `signed_untrusted` — Signed but key not trusted locally
- `signed_trusted` — Signed and key is trusted locally
- `signature_invalid` — Signature verification failed

## Trust States

| State | Meaning |
|-------|---------|
| `unsigned` | Pack has no SIGNATURE.json |
| `signed_untrusted` | Pack is signed but the signing key is not in your trusted keys |
| `signed_trusted` | Pack is signed and the signing key is trusted locally |
| `signature_invalid` | Signature exists but verification failed (tampering detected) |
| `checksum_failed` | Pack checksums don't match (file corruption) |

## Security Notes

- Private keys are stored in `workspace/skills/packs/keys/keys.json`
- Private keys are **never** printed or exposed in API responses
- Unsigned packs are allowed but show a warning
- Signed but untrusted packs show a warning
- Invalid signatures block install by default
- Trust is local-only — there is no official trust server
- `.gitignore` should exclude the keys directory

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills/keys` | List all keys |
| POST | `/api/skills/keys/generate` | Generate a new key |
| POST | `/api/skills/keys/{key_id}/trust` | Trust a key |
| POST | `/api/skills/keys/{key_id}/untrust` | Untrust a key |
| POST | `/api/skills/packs/verify` | Verify pack signature |
| POST | `/api/skills/packs/trust-status` | Get pack trust state |
| POST | `/api/skills/packs/sign` | Sign a pack |
