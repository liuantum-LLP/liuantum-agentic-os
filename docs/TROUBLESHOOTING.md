# Troubleshooting

## Quick Snapshot

```bash
./liuant troubleshoot
```

This summarizes doctor, env, auth, secret backend, DB status, providers, recent errors, UI status, scheduler status, and backup count. Secrets are redacted.

## Logs

```bash
./liuant logs path
./liuant logs tail
./liuant logs clear --confirm true
```

Clearing logs removes the file log only. SQLite action logs are preserved.

## Desktop Packaging

```bash
./liuant desktop status
./liuant desktop check
./liuant desktop native-check
./liuant desktop rust-check
./liuant desktop tauri-check
./liuant desktop icons-check
./liuant desktop build-guide
```

If dependencies are missing, install Node.js and Rust/Cargo. The desktop app expects the backend at `http://127.0.0.1:8765`; start it with `./liuant start 8765`.

Frontend-only checks:

```bash
cd apps/desktop
npm install
npm run typecheck
npm run build
```

If `npm run tauri:build` reports missing `cargo`, install Rust/Cargo before retrying. Liuant does not claim native artifacts until that build actually succeeds.

Platform helper scripts:

```bash
scripts/build_desktop_macos.sh
scripts/build_desktop_linux.sh
scripts/build_desktop_windows.ps1
```

They print missing dependencies and write `release/build-report.json`. They do not request privileged installs.

## Backend Mode

```bash
./liuant desktop backend-status
./liuant desktop backend-mode
./liuant desktop backend-mode set external_backend
```

If managed backend mode is enabled, `./liuant desktop backend-start` still refuses non-localhost binding. Bundled sidecar mode works after `./liuant sidecar build --confirm`.

## Signing (Optional, Maintainers Only)

Signing is a **maintainer-only workflow**. Community builds are unsigned by default.

```bash
# Community build check
./liuant release unsigned-artifacts
./liant release verify-artifacts
./liant release polish-check

# Maintainer signing (requires Apple Developer credentials)
./liant signing macos-status
./liant signing macos-preflight
./liant signing macos-sign --dry-run
./liant signing macos-sign --confirm true
./liant signing macos-notarize --dry-run
./liant signing macos-notarize --confirm true
```

Unsigned is the expected default. The signing pipeline wraps Apple's `codesign`, `notarytool`, and `stapler` — errors are passed through with secrets redacted.

Common issues:

- **`security find-identity` returns no identities**: You need a valid Developer ID Application certificate.
- **`xcrun notarytool submit` fails**: Check Apple ID credentials.
- **`codesign --verify` fails**: Artifact may have been modified after signing.
- **`spctl --assess` rejects**: Certificate may be Development, not Developer ID.

See `docs/MACOS_SIGNING_NOTARIZATION.md` for the maintainer guide.

## Release polish-check

Run `./liuant release candidate-check` (15 checks) or `./liuant release polish-check` to verify version alignment, DMG, icons, signing honesty, and documentation coverage.
