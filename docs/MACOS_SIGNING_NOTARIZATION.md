# macOS Code-Signing & Notarization

> **Maintainer workflow — not required for community builds.**

Community builds of Liuant Agentic OS are **unsigned**. You can build, run, and develop the desktop app without any Apple Developer credentials. On macOS, unsigned apps may require right-click → Open on first launch.

This guide is for **project maintainers** who want to produce signed and notarized DMG releases for official distribution.

---

## Prerequisites

1. **Apple Developer Program membership** ($99/year) — only needed for signing, not for development.
2. **Developer ID Application certificate** (not Development or Distribution).
3. **App-Specific Password** for notarization.

## Environment Variables

| Variable | For | Description |
|---|---|---|
| `APPLE_DEVELOPER_ID_APPLICATION` | Signing | Full subject name of your Developer ID cert |
| `APPLE_ID` | Notarization | Apple ID email |
| `APPLE_TEAM_ID` | Notarization | Apple Team ID |
| `APPLE_APP_SPECIFIC_PASSWORD` | Notarization | App-specific password |
| `TAURI_SIGNING_PRIVATE_KEY` | Tauri updater | Optional — DMG-only distribution does not need this |

## Signing Workflow (Maintainers Only)

```bash
# Check readiness
./liuant signing macos-status

# Preflight
./liuant signing macos-preflight

# Sign (dry-run first)
./liuant signing macos-sign --dry-run
./liuant signing macos-sign --confirm true

# Notarize (dry-run first)
./liuant signing macos-notarize --dry-run
./liuant signing macos-notarize --confirm true
```

**After signing**, the release manifest (`release/manifest.json`) is updated with signing metadata and checksums are regenerated.

## Build States

| State | signed | notarized | Usable |
|---|---|---|---|
| **Unsigned** (default) | `false` | `false` | Local development, may need right-click Open |
| **Signed** | `true` | `false` | Fewer Gatekeeper warnings |
| **Notarized** | `true` | `true` | No Gatekeeper warnings |

## Safety

- Secrets are never printed in output.
- `signed=true` and `notarized=true` are never claimed unless verification succeeds.
- `--confirm true` is required for real operations.
- Unsigned build commands continue to return `signed: false, notarized: false`.

## Community Builds vs Maintainer Builds

| Aspect | Community Build | Maintainer Build |
|---|---|---|
| Signing | Unsigned | Optional, signed if credentials configured |
| Notarization | None | Optional, after signing |
| Apple Developer ID | Not required | Required for signing |
| macOS Gatekeeper | Right-click Open needed | No warning if notarized |
| Required for development | No | No |
