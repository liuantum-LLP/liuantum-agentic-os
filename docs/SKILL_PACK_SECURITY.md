# Skill Pack Security

Skill packs are local files that extend Liuant's capabilities. This document describes the security model for skill pack handling.

## Validation Checks

Every pack is validated before import/install:

1. **Archive integrity** — Must be a valid ZIP file
2. **Path safety** — No absolute paths or path traversal (`..`)
3. **Manifest schema** — Required fields, valid types, slug-safe pack_id
4. **Skill existence** — All listed skills must exist in the pack
5. **Skill validation** — Each skill passes the standard skill validator
6. **Secret scanning** — No secret-like values (API keys, tokens, passwords)
7. **Install scripts** — No `install.sh`, `setup.sh`, `post_install.sh`, etc.
8. **Checksum verification** — `CHECKSUMS.json` must match actual files
9. **Duplicate detection** — No duplicate skill IDs within a pack

## Risk Assessment

Each pack generates a risk summary based on its skills' permissions:

| Risk Level | Permissions |
|------------|-------------|
| Low | `workspace.read`, `workspace.write`, `filesystem.read`, `filesystem.write`, `usage.read` |
| Medium | `models.generate` |
| High | `tools.browser`, `tools.email_draft`, `tools.social_draft` |
| Critical | `secrets.read`, `tools.shell`, `network.http` |

## Import/Install Safety

- **Import** extracts to `workspace/skills/packs/imported/` — does NOT install or enable
- **Install** copies skills to `workspace/skills/installed/` — skills are **disabled by default**
- **No auto-execution** — Skills never run during import/install
- **No install scripts** — Pack installation does not execute any scripts
- **Permission gating** — Critical permissions require explicit approval before enable/run
- **Dry-run available** — Use `inspect` and `validate` before importing

## Secret Protection

- Pack export scans for secret-like patterns and refuses to export if found
- Pack validation fails if secret-like values are detected
- Patterns include: `api_key = ...`, `sk-...`, `Bearer ...`
- Scanned files: `.py`, `.json`, `.md`, `.txt`, `.yaml`, `.yml`, `.toml`, `.js`, `.ts`

## Process Isolation

Installed skills from packs run with the same process isolation as individual skills:

- Subprocess execution with cleaned environment
- No API keys or secrets passed to child processes
- Filesystem access restricted to skill and workspace directories
- Timeout enforcement (default 30s)
- Audit logging of all executions

## Best Practices

1. Always `validate` and `inspect` a pack before importing
2. Review skill permissions before enabling
3. Approve critical permissions explicitly
4. Keep packs from trusted sources
5. Verify checksums match after download
6. Remove packs you no longer need
