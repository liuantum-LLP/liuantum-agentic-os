# Release

## Community Builds (Default)

Community builds are **unsigned** and **not notarized**. No Apple Developer credentials are required.

```bash
# Build
./liuant desktop build --native
# or via package script
./installer/package_macos.sh

# Verify
./liuant release unsigned-artifacts
./liuant release verify-artifacts
./liuant release polish-check

# Checksums
./liuant release checksum
```

On macOS, unsigned apps may require **right-click → Open** on first launch. This is expected.

## Maintainer Builds (Optional)

Maintainers can produce signed and notarized builds using the signing pipeline. See `docs/MACOS_SIGNING_NOTARIZATION.md`.

```bash
# Preflight
./liantu signing macos-status
./liuant signing macos-preflight

# Sign and notarize
./liuant signing macos-sign --confirm true
./liuant signing macos-notarize --confirm true

# Verify after signing
./liuant release verify-artifacts
```

## Release QA

```bash
./liantu release-check
./liantu desktop check
./liantu desktop native-check
./liantu release manifest
./liantu release checksum
```

## Release Polish-Check (v0.7.2)

```bash
./liuant release polish-check
```

Verifies:
- Version alignment across project files and Tauri config
- DMG exists and checksum matches stored value
- Icon set is complete (16 files)
- `signed=false` and `notarized=false` (honest signing status)
- Signing and QA documentation exists

## Manifest

`release/manifest.json` includes app name, version, channel, platform, build date, artifacts, and signing status.

```json
{
  "signing": {
    "unsigned": true,
    "signed": false,
    "notarized": false
  }
}
```

## Artifacts

```bash
./liuant release artifacts
```

Detects real files only. Native artifacts are produced by Tauri build under `apps/desktop/src-tauri/target/release/bundle`.

## Build Report

```bash
./liuant desktop build-report
```

Reads `release/build-report.json` if a build helper script has run.

## Artifact Checksums

```bash
./liuant release checksum
```

Generates SHA256 checksums for release artifacts. Use this to verify downloaded builds.

## Unsigned Build Verification

```bash
./liuant release unsigned-artifacts
./liuant release verify-artifacts
```

These commands keep `signed=false` and `notarized=false` until real signing/notarization is performed.

## Release Artifacts

Community releases include:
- Source tarball/zip
- Unsigned DMG (macOS)
- SHA256 checksums
- Release notes

## Reproducible Build Instructions

```bash
# Prerequisites: Python 3.11+, Node 20+, Rust/Cargo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cd apps/desktop
npm install
npm run typecheck
npm run build
./liuant desktop build --native
./liantu release checksum
./liantu release polish-check
```

The resulting DMG should match the published checksum for that release.
