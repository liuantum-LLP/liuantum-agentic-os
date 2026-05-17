# Desktop Packaging

v1.0.0 stable release. Sidecar backend built and tested. Community DMG rebuilt. Community builds are unsigned by default. Signing and notarization are optional maintainer workflows.

## Commands

```bash
./liuant desktop status
./liuant desktop check
./liuant desktop native-check
./liuant desktop rust-check
./liuant desktop tauri-check
./liuant desktop icons-check
./liuant desktop icons-generate
./liuant desktop build-guide
./liuant desktop build-report
./liuant desktop dev
./liuant desktop build --frontend-only
./liuant desktop build --native
./liuant desktop backend-status
./liuant desktop backend-mode
./liuant desktop package-info

# v0.7.0 signing commands
./liuant signing macos-status
./liantu signing macos-guide
./liuant signing macos-export-env-template
./liuant signing macos-preflight
./liuant signing macos-sign --confirm true
./liuant signing macos-notarize --confirm true

# v0.9.0 sidecar commands
./liuant sidecar status
./liant sidecar build --confirm
./liant sidecar check
./liant sidecar run
./liant sidecar stop --confirm
```

If dependencies are missing, commands return `needs_dependency` with setup instructions. Missing Node, pnpm/npm, Rust, or Cargo does not crash the release checks.

Current verified state in this environment:

- npm is available.
- pnpm is not available.
- Rust/Cargo is available (rustc 1.95.0, cargo 1.95.0).
- `npm install` completed.
- `npm run typecheck` passed.
- `npm run build` passed and produced frontend artifacts under `apps/desktop/dist`.
- `npm run tauri:build` can produce native .dmg artifacts.
- No Apple signing credentials configured — signing tests pass via missing-env checks.
- Brand icon set regenerated (premium neural orbit mark) — all 16 icon files present.
- Release polish-check passes.

## Current Layout

```text
apps/desktop/
  package.json
  dist/
  src/
  src-tauri/
    tauri.conf.json
    icons/
```

Current app identity:

- Name: Liuant Agentic OS
- Bundle identifier: `com.liuant.agenticos`
- Backend host: `127.0.0.1`
- External bind default: disabled

## Package Scripts

```bash
installer/package_macos.sh
installer/package_linux.sh
installer/package_windows.ps1
```

The macOS script supports signing flags (v0.7.0):

```bash
# Default: unsigned build
./installer/package_macos.sh

# Dry-run signing
./installer/package_macos.sh --dry-run-signing

# Sign only
./installer/package_macos.sh --sign

# Sign and notarize
./installer/package_macos.sh --sign --notarize
```

The scripts run release checks, desktop checks, and only attempt a Tauri build when a real desktop project and required dependencies exist.

## Desktop Development

```bash
./liuant start 8765
cd apps/desktop
pnpm install
pnpm run typecheck
pnpm run build
pnpm tauri dev
```

If `pnpm` is unavailable, use:

```bash
cd apps/desktop
npm install
npm run typecheck
npm run build
npm run tauri:dev
```

Native Tauri dev/build also requires Rust and Cargo.

## Brand Icon Set

v0.7.2 replaces the placeholder icons with a premium neural orbit mark: luminous core with orbiting agent nodes, radial data rings, and connection arcs on a deep-space gradient background. The SVG includes CSS animation for node opacity pulsing. All 16 icon files are generated offline.

The Tauri icon directory contains the full brand set:

- `icon.svg` (2.6 KB)
- `32x32.png` through `Square310x310Logo.png` (13 PNGs)
- `icon.ico`
- `icon.icns`

Regenerate them offline at any time:

```bash
./liuant desktop icons-generate
```

Check status with:

```bash
./liuant desktop icons-check
```

## Release Polish-Check

v0.7.2 adds `./liuant release polish-check` (alias: `./liuant desktop polish-check`). It verifies:
- Version alignment across project files and Tauri config
- DMG exists and checksum matches the stored value
- Icon set is complete
- `signed=false` and `notarized=false` (honest signing status)
- Signing and QA documentation exists

The desktop app defaults to `external_backend` mode. `managed_backend` can start/stop the same localhost-only backend through Liuant CLI helpers. `bundled_sidecar` mode is config-ready — the sidecar must be built first with `./liuant sidecar build --confirm`.

```bash
./liuant desktop backend-mode
./liuant desktop backend-mode set managed_backend
./liuant desktop backend-start
./liuant desktop backend-stop
./liuant desktop backend-mode set external_backend
./liuant desktop backend-mode set bundled_sidecar
```

## Artifact Status

`./liuant release artifacts` detects real files only. After the frontend build, current artifacts are:

- `apps/desktop/dist/index.html`
- `apps/desktop/dist/assets/*.css`
- `apps/desktop/dist/assets/*.js`

These are frontend artifacts, not native installers. Native artifacts are only expected after a successful Tauri build under `apps/desktop/src-tauri/target/release/bundle`.

Unsigned artifact commands:

```bash
./liuant release unsigned-artifacts
./liuant release verify-artifacts
```

They keep `signed=false` and `notarized=false` until real signing/notarization is performed.

## Sidecar Backend

v0.9.0 introduces a config-ready sidecar backend. The sidecar is a standalone executable built from Python source using PyInstaller or Nuitka.

```bash
# Build the sidecar
./liantu sidecar build --confirm

# Check status
./liantu sidecar status
./liantu sidecar check

# Run it
./liantu sidecar run
./liantu sidecar stop --confirm
```

The sidecar binds only to 127.0.0.1 and preserves local API auth. Community builds remain unsigned.

## Signing (Optional, Maintainers Only)

Signing and notarization are **optional maintainer workflows**. Community builds are unsigned by default.

- See `docs/MACOS_SIGNING_NOTARIZATION.md` for the complete maintainer signing guide.
- See `docs/SIGNING.md` for a quick reference.
- Unsigned builds pass all release checks and are fully functional for development.
- Windows and Linux code signing are not planned.

```bash
# Community build (unsigned, default)
./liuant desktop build --native
./liuant release polish-check
./liantu release unsigned-artifacts
```
